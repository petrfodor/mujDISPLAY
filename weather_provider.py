# weather_provider.py
"""Počasí, jmeniny, email data."""

import time
import datetime  
import logging
import requests
import pythoncom
import win32com.client
import psutil
import os
import re
import i18n
import unicodedata
from app_state import AppState

logger = logging.getLogger(__name__)

class WeatherProvider:
    def __init__(self, state: AppState):
        self.state = state
        self.meteo_raw = None
        self.weather_texts = {
            "curr": i18n._("weather_loading"),
            "fore": i18n._("weather_loading"),
            "wind": i18n._("weather_loading"),
            "det": i18n._("weather_loading"),
            "emails": "",
            "event": "",
            "ip": ""
        }
        self.current_temp = 0
        self.unread_emails = 0
        self.name_day = i18n._("nameday_prefix", name="- - - ")
        self.last_name_day = 0
        self.last_used_lang = state.language.lower()  # Sleduje jazyk pro vynucení aktualizace

    def fetch_weather(self):
        logger.debug("Zahajuji aktualizaci počasí...")
        _, lat, lon, auto_geo = self.state.location
        
        if auto_geo:
            try:
                logger.debug("Zjišťuji polohu přes IP-API...")
                geo_resp = requests.get("http://ip-api.com/json/", timeout=5)
                geo_resp.raise_for_status()
                geo = geo_resp.json()
                if geo.get('status') == 'success':
                    logger.info(f"Poloha automaticky nastavena: {geo['city']}")
                    self.state.set_location(geo['city'], geo['lat'], geo['lon'])
                    lat, lon = geo['lat'], geo['lon']
            except Exception as e:
                logger.error(f"Selhalo zjištění polohy: {e}")

        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,wind_gusts_10m,uv_index&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=6"
            logger.debug(f"Volám Open-Meteo API: {url}")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Uložíme data do meteo_raw a pracujeme s nimi jako se slovníkem
            data = response.json()
            self.meteo_raw = data
            
            self.current_temp = int(data['current']['temperature_2m'])
            hum = data['current']['relative_humidity_2m']
            wind = int(data['current']['wind_speed_10m'])
            pressure = int(data['current']['surface_pressure'])
            uv = data['current']['uv_index']
            tmax = int(data['daily']['temperature_2m_max'][0])
            tmin = int(data['daily']['temperature_2m_min'][0])

            # ★★★ LOKALIZOVANÉ TEXTY ★★★
            self.weather_texts["curr"] = i18n._("weather_outside", temp=self.current_temp, hum=hum)
            self.weather_texts["fore"] = i18n._("weather_today", max=tmax, min=tmin)
            self.weather_texts["wind"] = i18n._("weather_wind", speed=wind)
            self.weather_texts["det"] = i18n._("weather_pressure_uv", pressure=pressure, uv=uv)
            
            logger.debug("Počasí úspěšně zpracováno a uloženo do textů.")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.warning(f"Počasí nedostupné (výpadek sítě): {e}")
        except Exception as e:
            logger.error(f"Neočekávaná chyba počasí: {e}")

    def map_weather_to_id(self, wmo_code):
        mapping = {0:7,1:8,2:9,3:10,45:11,48:11,51:12,53:12,55:12,61:12,63:12,65:12,71:13,73:13,75:13,80:14,81:14,82:14,95:14,96:14,99:14}
        return mapping.get(wmo_code, 10)

    def get_day_name(self, date_str, index):
        if index == 0:
            return i18n._("day_today")
        import datetime
        try:
            dt = datetime.datetime.strptime(date_str, '%Y-%m-%d')
            wd = dt.weekday()
            keys = ["day_short_mon", "day_short_tue", "day_short_wed",
                    "day_short_thu", "day_short_fri", "day_short_sat", "day_short_sun"]
            return i18n._(keys[wd])
        except:
            return "??"

    def update_email_and_ip(self):
        client = self.state._config.email_client
        if client == "Outlook":
            try:
                # Kontrola, zda Outlook běží
                outlook_running = any("outlook.exe" in p.name().lower() for p in psutil.process_iter(attrs=['name']))
                if outlook_running:
                    pythoncom.CoInitialize()
                    try:
                        outlook = win32com.client.GetActiveObject("Outlook.Application")
                    except:
                        outlook = win32com.client.Dispatch("Outlook.Application")
                    
                    ns = outlook.GetNamespace("MAPI")
                    
                    # 1. EMAILY (Inbox = 6)
                    inbox = ns.GetDefaultFolder(6)
                    self.unread_emails = inbox.UnReadItemCount
                    
                    # 2. KALENDÁŘ (Calendar = 9) - Filtrace dnešních akcí
                    ev_count = 0
                    ev_text = ""
                    try:
                        calendar = ns.GetDefaultFolder(9).Items
                        calendar.Sort("[Start]")
                        calendar.IncludeRecurrences = True
                        
                        now_dt = datetime.datetime.now()
                        f_start = now_dt.strftime('%m/%d/%Y %I:%M %p')
                        f_end = (now_dt.replace(hour=23, minute=59)).strftime('%m/%d/%Y %I:%M %p')
                        
                        # Dnešní události pro počítadlo
                        today_ev = calendar.Restrict(f"[Start] >= '{f_start}' AND [End] <= '{f_end}'")
                        ev_count = len(today_ev) if len(today_ev) < 100 else 0
                        
                        # První nadcházející událost pro textový řádek
                        upcoming = calendar.Restrict(f"[End] >= '{f_start}'")
                        for app in upcoming:
                            if not app.AllDayEvent:
                                ev_text = f"Plan: {app.Start.strftime('%H:%M')} - {unicodedata.normalize('NFD', app.Subject).encode('ascii', 'ignore').decode('ascii')}"
                                break
                    except Exception as e:
                        logger.debug(f"Outlook Calendar error: {e}")

                    # 3. ÚKOLY (Tasks = 13) - Pouze nedokončené
                    task_count = 0
                    try:
                        tasks = ns.GetDefaultFolder(13).Items.Restrict("[Status] <> 2")
                        task_count = len(tasks)
                    except:
                        pass
                    
                    # Sestavení finálních textů (ŽÁDNÉ OTAZNÍKY)
                    self.weather_texts["emails"] = f"E-mail: {self.unread_emails} | Akce: {ev_count} | Ukoly: {task_count}"
                    self.weather_texts["event"] = ev_text[:49]
                else:
                    self.weather_texts["emails"] = "Outlook zavren"
                    self.unread_emails = 0
                    self.weather_texts["event"] = ""
            except Exception as e:
                logger.debug(f"Outlook Critical Error: {e}")
                self.weather_texts["emails"] = "Outlook Offline"
                self.unread_emails = 0
        
        elif client == "Thunderbird":
            self.unread_emails = self._get_thunderbird_unread()
            is_run = any("thunderbird.exe" in p.name().lower() for p in psutil.process_iter())
            self.weather_texts["emails"] = f"Thunderbird ({'Aktivni' if is_run else 'Zavren'}): {self.unread_emails} mailů"
            self.weather_texts["event"] = ""
        else:
            self.weather_texts["emails"] = ""
            self.weather_texts["event"] = ""
            self.unread_emails = 0

        # --- Sekce IP a Síť (Ponechána beze změn) ---
        import socket, subprocess
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            output = subprocess.check_output("route print", shell=True).decode('cp852', errors='ignore')
            gw = "?.?.?.?"
            for line in output.split('\n'):
                if ' 0.0.0.0 ' in line:
                    parts = line.split()
                    if len(parts) >= 3: gw = parts[2]; break
            self.weather_texts["ip"] = f"IP: {ip}/24 | GW: {gw}"
        except:
            self.weather_texts["ip"] = "Offline"

    def _get_thunderbird_unread(self):
        total = 0
        base = os.path.join(os.environ['APPDATA'], 'Thunderbird', 'Profiles')
        if not os.path.exists(base): return 0
        try:
            for profile in os.listdir(base):
                path = os.path.join(base, profile)
                if os.path.isdir(path):
                    for root, dirs, files in os.walk(path):
                        for file in files:
                            if file.endswith('.msf'):
                                try:
                                    with open(os.path.join(root, file), 'rb') as f:
                                        content = f.read().decode('latin-1', errors='ignore')
                                        matches = re.findall(r'\^A2=([0-9a-fA-F]+)', content)
                                        if matches: total += int(matches[-1], 16)
                                except: continue
        except: pass
        return total

    def get_name_day(self):
        now = time.time()
        current_lang = self.state.language.lower()
        
        if (now - self.last_name_day > 3600 or 
            self.name_day.endswith("- - - ") or 
            current_lang != self.last_used_lang):
            
            try:
                name = None
                if current_lang == 'cz':
                    url = "https://svatkyapi.cz/api/day"
                    r = requests.get(url, timeout=5).json()
                    name = r.get('name')
                elif current_lang == 'sk':
                    url = "https://svatkyapi.cz/api/day?country=sk"
                    r = requests.get(url, timeout=5).json()
                    name = r.get('name')
                else:
                    lang_map = {'de': 'de', 'fr': 'fr', 'en': 'us'}
                    country_code = lang_map.get(current_lang, 'us')
                    url = "https://nameday.abalin.net/api/V2/today"
                    r = requests.get(url, timeout=5).json()
                    if r.get('success'):
                        name = r.get('data', {}).get(country_code)
                        if not name or name == "n/a":
                            name = r.get('data', {}).get('us', "---")

                if name:
                    if "," in name:
                        name = name.split(",")[0].strip()
                    name_clean = "".join(c for c in unicodedata.normalize('NFD', name)
                                         if unicodedata.category(c) != 'Mn')
                    
                    self.name_day = i18n._("nameday_prefix", name=name_clean)
                    self.last_name_day = now
                    self.last_used_lang = current_lang
                    logger.debug(f"Jmeniny aktualizovany pro jazyk {current_lang}: {name_clean}")
                
            except Exception as e:
                logger.error(f"Chyba pri nacitani jmenin: {e}")
                self.name_day = i18n._("nameday_prefix", name="- - - ")
                
        raw_name = self.name_day.split(": ")[-1] if ": " in self.name_day else "---"
        return i18n._("nameday_prefix", name=raw_name)

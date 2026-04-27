# weather_provider.py
"""Počasí, jmeniny, email data."""

import time
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
                geo = requests.get("http://ip-api.com/json/", timeout=5).json()
                if geo['status'] == 'success':
                    logger.info(f"Poloha automaticky nastavena: {geo['city']}")
                    self.state.set_location(geo['city'], geo['lat'], geo['lon'])
            except Exception as e:
                logger.error(f"Selhalo zjištění polohy: {e}")

        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,wind_gusts_10m,uv_index&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=6"
            logger.debug(f"Volám Open-Meteo API: {url}")
            r = requests.get(url, timeout=10).json()
            
            self.meteo_raw = r
            self.current_temp = int(r['current']['temperature_2m'])
            hum = r['current']['relative_humidity_2m']
            wind = int(r['current']['wind_speed_10m'])
            pressure = int(r['current']['surface_pressure'])
            uv = r['current']['uv_index']
            tmax = int(r['daily']['temperature_2m_max'][0])
            tmin = int(r['daily']['temperature_2m_min'][0])

            # ★★★ LOKALIZOVANÉ TEXTY ★★★
            self.weather_texts["curr"] = i18n._("weather_outside", temp=self.current_temp, hum=hum)
            self.weather_texts["fore"] = i18n._("weather_today", max=tmax, min=tmin)
            self.weather_texts["wind"] = i18n._("weather_wind", speed=wind)
            self.weather_texts["det"] = i18n._("weather_pressure_uv", pressure=pressure, uv=uv)
            
            logger.debug("Počasí úspěšně zpracováno a uloženo do textů.")
        except Exception as e:
            logger.exception(f"Kritická chyba při stahování počasí: {e}")

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
                pythoncom.CoInitialize()
                try:
                    outlook = win32com.client.GetActiveObject("Outlook.Application")
                except:
                    logger.debug("Outlook data error.")
                    outlook = win32com.client.Dispatch("Outlook.Application")
                ns = outlook.GetNamespace("MAPI")
                self.unread_emails = ns.GetDefaultFolder(6).UnReadItemCount
                self.weather_texts["emails"] = f"E-mail: {self.unread_emails} | Akce: ? | Ukoly: ?"
                self.weather_texts["event"] = ""
            except:
                self.weather_texts["emails"] = "Outlook Offline"
                self.unread_emails = 0
        elif client == "Thunderbird":
            self.unread_emails = self._get_thunderbird_unread()
            running = any("thunderbird.exe" in p.name().lower() for p in psutil.process_iter())
            self.weather_texts["emails"] = f"Thunderbird ({'Aktivni' if running else 'Zavren'}): {self.unread_emails} mailů"
        else:
            self.weather_texts["emails"] = ""
            self.unread_emails = 0

        import socket, subprocess
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            output = subprocess.check_output("route print", shell=True).decode('cp852')
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
        
        # AKTUALIZUJEME POKUD:
        # 1. Uplynula hodina
        # 2. Jméno je prázdné
        # 3. Změnil se jazyk aplikace (vynutí okamžitý dotaz v jiném jazyce)
        if (now - self.last_name_day > 3600 or 
            self.name_day.endswith("- - - ") or 
            current_lang != self.last_used_lang):
            
            try:
                name = None
                
                # 1. Specifické API pro CZ a SK
                if current_lang == 'cz':
                    url = "https://svatkyapi.cz/api/day"
                    r = requests.get(url, timeout=5).json()
                    name = r.get('name')
                elif current_lang == 'sk':
                    url = "https://svatkyapi.cz/api/day?country=sk"
                    r = requests.get(url, timeout=5).json()
                    name = r.get('name')
                
                # 2. Mezinárodní API abalin.net
                else:
                    lang_map = {'de': 'de', 'fr': 'fr', 'en': 'us'}
                    country_code = lang_map.get(current_lang, 'us')
                    url = "https://nameday.abalin.net/api/V2/today"
                    r = requests.get(url, timeout=5).json()
                    
                    if r.get('success'):
                        # Přístup k datům přes klíč 'data' dle vaší specifikace
                        name = r.get('data', {}).get(country_code)
                        if not name or name == "n/a":
                            name = r.get('data', {}).get('us', "---")

                if name:
                    if "," in name:
                        name = name.split(",")[0].strip()

                    # Odstranění diakritiky
                    name_clean = "".join(c for c in unicodedata.normalize('NFD', name)
                                         if unicodedata.category(c) != 'Mn')
                    
                    # Prefix se mění automaticky díky i18n._ při každém volání metody
                    self.name_day = i18n._("nameday_prefix", name=name_clean)
                    self.last_name_day = now
                    self.last_used_lang = current_lang
                    logger.debug(f"Jmeniny aktualizovany pro jazyk {current_lang}: {name_clean}")
                
            except Exception as e:
                logger.error(f"Chyba pri nacitani jmenin: {e}")
                self.name_day = i18n._("nameday_prefix", name="- - - ")
                
        # Vrátíme buď nově stažené jméno, nebo zaktualizujeme prefix pro stávající jméno v paměti
        # To zajistí, že i bez internetu se prefix (Svatek/Nameday) změní ihned
        raw_name = self.name_day.split(": ")[-1] if ": " in self.name_day else "---"
        return i18n._("nameday_prefix", name=raw_name)

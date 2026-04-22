"""
================================================================================
PROJEKT: mujDISPLAY Monitor
AUTOR:   Petr Fodor, Controlsystems.cz
VERZE:   v1.4 (2026-04-17)
================================================================================

CHANGELOG:
v1.6 (2026-04-22)
----------------
* PŘIDÁNO: Nový režim "Graf vytížení" (Stránka 5) pro sledování historie CPU/RAM.
* PŘIDÁNO: Dynamické řízení barev grafu (pco0/pco1) podle aktuálního vytížení.
* PŘIDÁNO: Automatické čištění grafu (cle) při přepnutí na stránku.
* ZMĚNA: Implementace časového zámku (Tick) pro plynulé vykreslování Waveformu.
* ZMĚNA: Pokud systém detekuje Play/Pause, mění se ikona v Media Control (p3.pic).
* OPRAVA: Ošetření inicializace proměnných grafu (eliminace pádů smyčky).
* OPRAVA: Synchronizace AppID na v1.5 pro stabilní ikonu v Taskbaru.

v1.5 (2026-04-21)
----------------
* OPRAVA:  Zobrazování ikon.
* ZMĚNA:  Pokud jde ze systému informace o tom zda se přehrává či je přehravání zastaveno, mění se ikona na Media Control.
* ZMĚNA: Velikost textu v media screen

v1.4 (2026-04-20)
----------------
* PŘIDÁNO: Nový režim "Media Control" (Stránka 4) pro ovládání hudby a videa (vč. YouTube).
* PŘIDÁNO: Obousměrná komunikace – tlačítka na displeji fyzicky ovládají média ve Windows.
* PŘIDÁNO: Detailní Media Info – zobrazení umělce, názvu skladby a času (odehraný/celkový).
* PŘIDÁNO: Progress Bar (j0) pro média s automatickým přepočtem na procenta.
* PŘIDÁNO: Podpora pro zobrazování aktuálního svátku (jmeniny) bez diakritiky (SvatkyAPI.cz).
* PŘIDÁNO: Možnost zapnout/vypnout zobrazení svátků v configu a Tray menu.
* PŘIDÁNO: Inteligentní Auto-Update HMI podle modelu panelu (TJC4832T135 / T1035).
* ZMĚNA:   Migrace na vzdálený server https://www.controlsystems.cz/downloads/mujdisplay/.
* OPRAVA:  Zabezpečení uvolňování sériového portu při stahování a flashování nového HMI.

v1.3 (2026-04-19)
----------------
* PŘIDÁNO: Inteligentní Auto-Update HMI (grafiky displeje) přímo ze serveru.
* PŘIDÁNO: Detekce HW modelu panelu (TJC4832T135 / TJC4832T035) pro stažení správného souboru.
* PŘIDÁNO: Fixní verifikace kompatibility přes konstantu COMPATIBLE_HMI_VERSION.
* PŘIDÁNO: Podpora pro dálkové zjišťování verze HMI v panelu (swver.val).
* ZMĚNA:   Kompletní migrace URL na https://www.controlsystems.cz/downloads/mujdisplay/.
* OPRAVA:  Zabezpečení nahrávacího procesu – automatický úklid (mazání) stažených .tft souborů.
* OPRAVA:  Synchronizace AppID na v1.3 pro korektní seskupování v hlavním panelu Windows.

v1.2 (2026-04-17)
----------------
* PŘIDÁNO: Automatické ukládání a načítání nastavení přes 'config.ini' (knihovna configparser).
* PŘIDÁNO: Systém automatických aktualizací (check_for_updates) s využitím batch helperu.

v1.1c (2026-04-16) 
----------------
* PŘIDÁNO: Dynamické škálování síťových grafů (Auto-scale) podle špičkového provozu.
* PŘIDÁNO: Možnost ručního zadání GPS souřadnic pro Meteo režim přímo z Tray menu.
* OPRAVA:  Ošetření kolizí na sériovém portu při přepínání mezi Monitorováním a Terminálem.

v1.1b (2026-04-13) 
-----
* PŘIDÁNO: Implementace Terminálu pro přímé posílání příkazů do Nextion displeje.
* PŘIDÁNO: Podpora pro nahrávání zkompilovaných .tft souborů (firmware) přímo z aplikace.
* ZMĚNA:   Optimalizace komunikačního bufferu pro CH340 a CP2102 převodníky.

v1.1a (2026-04-11) 
-----
* PŘIDÁNO: Integrace emailových klientů (Outlook a Thunderbird).
* PŘIDÁNO: Detekce uzamčení Windows (LogonUI) a automatické přepínání do nočního/meteo režimu.
* PŘIDÁNO: Tray ikona s dynamickým generováním menu podle dostupných COM portů.

v1.0 Initial (2026-04-09) 
--------------
* Základní monitorovací smyčka (CPU, RAM, Disk, Síť).
* Komunikace s Nextion přes standardní ASCII instrukce ukončené 0xFF 0xFF 0xFF.
* Základní Meteo data přes Open-Meteo API.

================================================================================
"""

import sys
import os
import serial
import serial.tools.list_ports
import psutil
import time
import datetime
import win32com.client
import pythoncom
import requests
import platform
import socket
import threading
import winreg
import subprocess
import tkinter as tk
import ctypes
import re
import logging
import configparser
from tkinter import simpledialog
from tkinter import filedialog
from tkinter import ttk
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
from plyer import notification
import pyautogui
from datetime import timezone
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager

# --- KONFIGURACE LOGOVÁNÍ ---
logger = logging.getLogger(__name__)
base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
log_path = os.path.join(base_path, "debug.log")
log_handler = logging.FileHandler(log_path, encoding='utf-8')
log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

# --- OPRAVA NÁZVU V NOTIFIKACÍCH (AppID) ---
myappid = 'mujDISPLAY.Monitor.1.6'
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except:
    pass

# --- KONFIGURACE A COPYRIGHT ---
CONFIG_FILE = os.path.join(base_path, "config.ini")
APP_NAME = "mujDISPLAY Monitor"
APP_VERSION = "v1.6"
COPYRIGHT = "©2026 Petr Fodor"
COMPATIBLE_HMI_VERSION = 1600 
CITY_LAT = 50.08
CITY_LON = 14.43
CITY_NAME = "Praha"

# Globální nastavení
SERIAL_PORT = 'Auto'
BAUD_RATE = 9600
UPLOAD_BAUD = 921600 
AUTO_BAUD = True
DISPLAY_MODE = "PC"
EMAIL_CLIENT = "Outlook"
LOCK_SHOW_METEO = True
LOCK_METEO_TIME = 120
LOOP_INTERVAL = 60
USE_SLEEP_CMD = False
AUTO_GEO = True
BRIGHTNESS = 100 
FORCE_OFF = False     
DEBUG_ENABLED = False  
AUTO_HMI_UPDATE = False
SHOW_NAMEDAY = True
running = True
last_menu_change = 0 
ser_lock = threading.Lock()


# Stavová data
current_out_temp = 0
weather_data = {"curr": "Nacitam...", "fore": "...", "wind": "...", "det": "..."}
cache = {}
ser = None
unread_emails_global = 0 
current_user = os.getlogin()
last_dn_str, last_up_str = "0B/s", "0B/s"
max_dn_recorded = 1024 * 1024 
max_up_recorded = 1024 * 1024
meteo_data_raw = None

# Barvy (RGB565)
GREEN, YELLOW, RED, BLUE, WHITE = 2016, 65504, 63488, 31, 65535

# --- POMOCNÉ FUNKCE ---
BASE_URL = "https://www.controlsystems.cz/downloads/mujdisplay/"
UPDATE_URL_VER = "https://controlsystems.cz/downloads/mujdisplay/version.txt"
UPDATE_URL_BIN = "https://controlsystems.cz/downloads/mujdisplay/mujDISPLAY_Monitor.exe"

import unicodedata

def remove_diacritics(text):
    """Odstraní českou diakritiku z textu."""
    return "".join(c for c in unicodedata.normalize('NFD', text)
                  if unicodedata.category(c) != 'Mn')
def media_updater_worker():
    """Běží v samostatném threadu a periodicky aktualizuje media info."""
    import asyncio
    
    async def update():
        while running:
            if DISPLAY_MODE == "Media" or (DISPLAY_MODE == "Loop" and target_page == 4):
                try:
                    info = await get_extended_media_info()
                    # Uložíme výsledek do atributu funkce, aby byl přístupný zvenčí
                    main_display_loop.shared_media_info = info
                except Exception as e:
                    pass
            time.sleep(1) # Stačí jednou za vteřinu

    # Spuštění smyčky v threadu
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(update())
    
async def get_extended_media_info():
    try:
        sessions = await MediaManager.request_async()
        current_session = sessions.get_current_session()
        
        if not current_session:
            return {"text": "Nic nehraje", "progress": 0, "time_str": "--:-- / --:--", "remaining": "--:--", "status_pic": 19}

        playback_info = current_session.get_playback_info()
        status_raw = playback_info.playback_status
        
        status_pic = 19
        if status_raw == 4: status_pic = 17
        elif status_raw == 5: status_pic = 18
        
        props = await current_session.try_get_media_properties_async()
        raw_title = f"{props.artist} - {props.title}"
        title = remove_diacritics(raw_title)[:49]
        
        timeline = current_session.get_timeline_properties()
        if not timeline or timeline.end_time.total_seconds() <= 0:
            return {"text": title, "progress": 0, "time_str": "00:00 / 00:00", "remaining": "00:00", "status_pic": status_pic}

        pos_raw = timeline.position.total_seconds()
        end = timeline.end_time.total_seconds()
        
        try:
            diff = (datetime.datetime.now(timezone.utc) - timeline.last_updated_time).total_seconds()
            # Přičítáme diff jen pokud stav je Playing (4)
            pos = pos_raw + diff if (pos_raw > 0 and status_raw == 4) else pos_raw
        except:
            pos = pos_raw

        if pos > end: pos = end
        rem = max(0, end - pos)
        progress = int((pos / end) * 100)
        
        def fmt_time(s):
            m, s = divmod(int(s), 60)
            return f"{m:02d}:{s:02d}"

        return {
            "text": title,
            "progress": progress,
            "time_str": f"{fmt_time(pos)} / {fmt_time(end)}",
            "remaining": f"-{fmt_time(rem)}",
            "status_pic": status_pic # <--- Opraveno
        }
    except Exception as e: 
        log_error(f"Media Info Error: {e}")
        return {"text": "Chyba Media API", "progress": 0, "time_str": "--:-- / --:--", "remaining": "--:--", "status_pic": 19}
    
def handle_media_click(event_data):
    """Zpracuje příchozí ID tlačítka z displeje a provede akci."""
    actions = {
        "play": "playpause",
        "stop": "stop",
        "prev": "prevtrack",
        "next": "nexttrack",
        "vup": "volumeup",
        "vdown": "volumedown"
    }
    if event_data in actions:
        pyautogui.press(actions[event_data])
        log_debug(f"Media Action: {actions[event_data]}")
def get_display_model():
    global ser
    if ser and ser.is_open:
        try:
            ser.reset_input_buffer()
            # Příkaz 'connect' vrací info o hardwaru
            send_cmd("connect")
            time.sleep(0.2)
            res = ser.read(ser.in_waiting)
            
            # Odpověď bývá v syrovém formátu odděleném čárkami
            # Příklad: comok 2,306-0,TJC4832T135_011,52,0,65535,0
            decoded = res.decode('ascii', errors='ignore')
            if "TJC" in decoded:
                parts = decoded.split(',')
                if len(parts) > 2:
                    model = parts[2]
                    log_info(f"Detekován model displeje: {model}")
                    return model
        except Exception as e:
            log_error(f"Nepodařilo se identifikovat model: {e}")
    return "Unknown"
    
def get_hmi_version_from_display():
    global ser
    if ser and ser.is_open:
        try:
            ser.reset_input_buffer()
            send_cmd("get swver.val")
            time.sleep(0.1)
            res = ser.read(ser.in_waiting)
            if len(res) >= 5 and res[0] == 0x71:
                return int.from_bytes(res[1:5], byteorder='little')
        except: pass
    return None    
    
def download_and_upload_hmi(url, model):
    global ser, DISPLAY_MODE
    
    # KROK A: Uvolnění portu (shodné se select_and_upload)
    log_info(f"Auto-Update HMI: Připravuji stažení {model}.tft")
    globals().update(DISPLAY_MODE="Uploading")
    
    if ser:
        try:
            ser.close()
        except: pass
    ser = None

    # KROK B: Stažení do dočasného souboru
    local_file = f"update_{model}.tft"
    try:
        send_pc_notification("Stahování", f"Stahuji grafiku pro {model}...")
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        
        with open(local_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        
        log_info(f"Soubor {local_file} stažen. Zahajuji nahrávání do panelu.")

        # KROK C: Nahrání pomocí tvé existující funkce upload_tft_file
        def run_update_process():
            try:
                # Použijeme tvou stávající funkci, která se postará o HW protokol
                upload_tft_file(local_file)
            finally:
                # Úklid po dokončení (i při chybě)
                if os.path.exists(local_file):
                    time.sleep(2) # Čas na uvolnění file handle
                    try: os.remove(local_file)
                    except: pass
                log_info("Auto-Update HMI dokončen.")

        threading.Thread(target=run_update_process, daemon=True).start()

    except Exception as e:
        log_error(f"Stažení HMI aktualizace selhalo: {e}")
        send_pc_notification("Chyba Update", "Nepodařilo se stáhnout soubor ze serveru.")
        globals().update(DISPLAY_MODE="PC") 
        
def check_hmi_update_flow():
    if not AUTO_HMI_UPDATE:
        return

    # 1. Zjistíme model z displeje (příkaz connect)
    model = get_display_model() 
    # 2. Zjistíme verzi z displeje (tvoje swver.val)
    current_display_ver = get_hmi_version_from_display()
    
    if model == "Unknown" or current_display_ver is None:
        log_debug("HMI Update: Displej neodpovídá nebo verze nebyla načtena.")
        return

    # 3. Porovnáme s fixní verzí v Pythonu
    if current_display_ver < COMPATIBLE_HMI_VERSION:
        log_info(f"HMI Update: Zjištěna starší verze ({current_display_ver} < {COMPATIBLE_HMI_VERSION})")
        
        root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
        ans = messagebox.askyesno("Aktualizace grafiky", 
            f"V připojeném panelu {model} je zastaralá grafika.\n"
            f"Chcete nyní ze serveru stáhnout a nainstalovat verzi {COMPATIBLE_HMI_VERSION}?")
        root.destroy()
        
        if ans:
            # Sestavíme URL přímo podle modelu a stáhneme .tft
            tft_url = f"{BASE_URL}{model}.tft"
            download_and_upload_hmi(tft_url, model)
        
def check_for_updates(manual=False):
    try:
        log_info("Kontrola aktualizací...")
        response = requests.get(UPDATE_URL_VER, timeout=5)
        latest_version = response.text.strip()

        if latest_version != APP_VERSION:
            if manual or True: # Zde můžeš přidat tkinter dotaz na uživatele
                root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
                ans = tk.messagebox.askyesno("Aktualizace", f"Je k dispozici nová verze {latest_version}.\nChcete ji nyní nainstalovat?")
                root.destroy()
                
                if ans:
                    perform_update()
        elif manual:
            send_pc_notification("Aktualizace", "Máte aktuální verzi.")
    except Exception as e:
        log_error(f"Chyba při kontrole aktualizací: {e}")

def perform_update():
    try:
        send_pc_notification("Aktualizace", "Stahuji novou verzi...")
        r = requests.get(UPDATE_URL_BIN, stream=True, timeout=15)
        new_file = "update_temp.exe" # nebo .py podle toho, co používáš
        
        with open(new_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        # Vytvoření dávkového souboru pro přepsání běžícího exe
        current_exe = sys.argv[0]
        batch_script = "update.bat"
        with open(batch_script, "w") as f:
            f.write(f"""
@echo off
timeout /t 2 /nobreak > nul
del "{current_exe}"
move "{new_file}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
            """)
        
        log_info("Aktualizace stažena, restartuji aplikaci...")
        subprocess.Popen([batch_script], shell=True)
        globals().update(running=False) # Ukončí hlavní smyčku
        os._exit(0) # Okamžitě ukončí proces
    except Exception as e:
        log_error(f"Selhání aktualizace: {e}")
        
def log_debug(msg):
    if DEBUG_ENABLED: logger.debug(msg)

def log_info(msg):
    if DEBUG_ENABLED: logger.info(msg)

def log_error(msg):
    if DEBUG_ENABLED: logger.error(msg)

def load_config():
    global SERIAL_PORT, BAUD_RATE, AUTO_BAUD, DISPLAY_MODE, EMAIL_CLIENT, \
           LOCK_SHOW_METEO, LOCK_METEO_TIME, LOOP_INTERVAL, USE_SLEEP_CMD, \
           AUTO_GEO, BRIGHTNESS, CITY_NAME, CITY_LAT, CITY_LON, DEBUG_ENABLED, \
           SHOW_NAMEDAY, AUTO_HMI_UPDATE
       

    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_FILE):
        # Pokud soubor neexistuje, vytvoříme ho s aktuálními (výchozími) hodnotami
        save_config()
        return

    try:
        config.read(CONFIG_FILE, encoding='utf-8')
        s = 'Settings'
        SERIAL_PORT = config.get(s, 'Port', fallback=SERIAL_PORT)
        BAUD_RATE = config.getint(s, 'BaudRate', fallback=BAUD_RATE)
        AUTO_BAUD = config.getboolean(s, 'AutoBaud', fallback=AUTO_BAUD)
        DISPLAY_MODE = config.get(s, 'DisplayMode', fallback=DISPLAY_MODE)
        EMAIL_CLIENT = config.get(s, 'EmailClient', fallback=EMAIL_CLIENT)
        LOCK_SHOW_METEO = config.getboolean(s, 'LockShowMeteo', fallback=LOCK_SHOW_METEO)
        LOCK_METEO_TIME = config.getint(s, 'LockMeteoTime', fallback=LOCK_METEO_TIME)
        LOOP_INTERVAL = config.getint(s, 'LoopInterval', fallback=LOOP_INTERVAL)
        USE_SLEEP_CMD = config.getboolean(s, 'UseSleepCmd', fallback=USE_SLEEP_CMD)
        AUTO_GEO = config.getboolean(s, 'AutoGeo', fallback=AUTO_GEO)
        BRIGHTNESS = config.getint(s, 'Brightness', fallback=BRIGHTNESS)
        DEBUG_ENABLED = config.getboolean(s, 'DebugEnabled', fallback=DEBUG_ENABLED)
        SHOW_NAMEDAY = config.getboolean(s, 'ShowNameday', fallback=SHOW_NAMEDAY )
        AUTO_HMI_UPDATE = config.getboolean(s, 'AutoHmiUpdate', fallback=AUTO_HMI_UPDATE)
        
        l = 'Location'
        CITY_NAME = config.get(l, 'CityName', fallback=CITY_NAME)
        CITY_LAT = config.getfloat(l, 'Lat', fallback=CITY_LAT)
        CITY_LON = config.getfloat(l, 'Lon', fallback=CITY_LON)
        
        log_info("Konfigurace načtena ze souboru.")
    except Exception as e:
        log_error(f"Chyba při načítání configu: {e}")

def save_config():
    config = configparser.ConfigParser()
    config['Settings'] = {
        'Port': str(SERIAL_PORT),
        'BaudRate': str(BAUD_RATE),
        'AutoBaud': str(AUTO_BAUD),
        'DisplayMode': str(DISPLAY_MODE),
        'EmailClient': str(EMAIL_CLIENT),
        'LockShowMeteo': str(LOCK_SHOW_METEO),
        'LockMeteoTime': str(LOCK_METEO_TIME),
        'LoopInterval': str(LOOP_INTERVAL),
        'UseSleepCmd': str(USE_SLEEP_CMD),
        'AutoGeo': str(AUTO_GEO),
        'Brightness': str(BRIGHTNESS),
        'DebugEnabled': str(DEBUG_ENABLED),
        'ShowNameday': str(SHOW_NAMEDAY)
    }
    config['Location'] = {
        'CityName': str(CITY_NAME),
        'Lat': str(CITY_LAT),
        'Lon': str(CITY_LON)
    }
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
        config.write(configfile)
    log_info("Konfigurace uložena.")
    
def format_speed(bytes_per_sec):
    for unit in ['B', 'KB', 'MB']:
        if bytes_per_sec < 1024: return f"{int(bytes_per_sec)}{unit}/s"
        bytes_per_sec /= 1024
    return f"{int(bytes_per_sec)}GB/s"

def get_color(val, low=50, high=80):
    if val < low: return GREEN
    if val < high: return YELLOW
    return RED

def send_pc_notification(title, message):
    try:
        notification.notify(title=title, message=message, app_name=APP_NAME, timeout=5)
        log_info(f"Notifikace: {title} - {message}")
    except: pass

def get_geo_location():
    global CITY_LAT, CITY_LON, CITY_NAME
    try:
        r = requests.get("http://ip-api.com/json/", timeout=5).json()
        if r['status'] == 'success':
            CITY_LAT, CITY_LON, CITY_NAME = r['lat'], r['lon'], r['city']
            return True
    except: pass
    return False
    
import unicodedata

def get_today_name_day():
    try:
        # Volání nového API
        r = requests.get("https://svatkyapi.cz/api/day", timeout=5).json()
        name = r['name']  # Získáme jméno z klíče "name"
        
        # Odstranění diakritiky (standardní Python cesta)
        import unicodedata
        name_clean = "".join(c for c in unicodedata.normalize('NFD', name)
                            if unicodedata.category(c) != 'Mn')
        
        return f"Dnes ma svatek: {name_clean}"
    except Exception as e:
        log_error(f"Chyba pri nacitani svatku: {e}")
        return "Dnes ma svatek: - - - "
        
        
def set_autostart(enabled=True):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_registry_name = "mujDISPLAY_Monitor"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enabled:
            exe_path = os.path.realpath(sys.argv[0])
            winreg.SetValueEx(key, app_registry_name, 0, winreg.REG_SZ, exe_path)
        else:
            try: winreg.DeleteValue(key, app_registry_name)
            except: pass
        winreg.CloseKey(key)
    except: pass

def is_autostart_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, "mujDISPLAY_Monitor")
        return True
    except: return False

def find_nextion_port():
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        if any(x in port.description for x in ["USB", "Serial", "CH340", "CP2102", "FTDI", "UART"]):
            return port.device
    return None

def map_weather_to_id(wmo_code):
    mapping = {0:7, 1:8, 2:9, 3:10, 45:11, 48:11, 51:12, 53:12, 55:12, 61:12, 63:12, 65:12, 71:13, 73:13, 75:13, 80:14, 81:14, 82:14, 95:14, 96:14, 99:14}
    return mapping.get(wmo_code, 10)

def get_cz_day_name(date_str, index):
    if index == 0: return "Dnes"
    days = ["Po", "Ut", "St", "Ct", "Pa", "So", "Ne"]
    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return days[date_obj.weekday()]
    except: return "??"

def get_network_info():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0); s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        output = subprocess.check_output("route print", shell=True).decode('cp852')
        gateway = "?.?.?.?"
        for line in output.split('\n'):
            if ' 0.0.0.0 ' in line:
                parts = line.split()
                if len(parts) >= 3: gateway = parts[2]; break
        return f"{ip}/24", gateway
    except: return "Offline", "?.?.?.?"

def get_disks_info():
    try:
        partitions = psutil.disk_partitions(); res = ""
        for p in partitions:
            if 'cdrom' in p.opts or p.fstype == '': continue
            usage = psutil.disk_usage(p.mountpoint)
            res += f"{p.device[0]}: {int(usage.free / (1024**3))}G "
        return res.strip()
    except: return "Disk Error"

def is_pc_locked():
    try:
        for p in psutil.process_iter(attrs=['name'], ad_value=None):
            if p.info['name'] == "LogonUI.exe": return True
    except: pass
    return False

def get_thunderbird_unread():
    total_unread = 0
    base_path = os.path.join(os.environ['APPDATA'], 'Thunderbird', 'Profiles')
    if not os.path.exists(base_path): return 0
    try:
        for profile in os.listdir(base_path):
            profile_path = os.path.join(base_path, profile)
            for root, dirs, files in os.walk(profile_path):
                for file in files:
                    if file.endswith('.msf'):
                        try:
                            with open(os.path.join(root, file), 'rb') as f:
                                content = f.read().decode('latin-1', errors='ignore')
                                matches = re.findall(r'\^A2=([0-9a-fA-F]+)', content)
                                if matches: total_unread += int(matches[-1], 16)
                        except: continue
        return total_unread
    except: return 0

def get_email_data():
    global unread_emails_global
    if EMAIL_CLIENT == "None": return "", ""
    if EMAIL_CLIENT == "Outlook":
        try:
            pythoncom.CoInitialize()
            try: outlook = win32com.client.GetActiveObject("Outlook.Application")
            except: outlook = win32com.client.Dispatch("Outlook.Application")
            ns = outlook.GetNamespace("MAPI")
            unread_emails_global = ns.GetDefaultFolder(6).UnReadItemCount
            cal = ns.GetDefaultFolder(9).Items; cal.Sort("[Start]"); cal.IncludeRecurrences = True
            now_dt = datetime.datetime.now()
            f_start = now_dt.strftime('%m/%d/%Y %I:%M %p')
            today_ev = cal.Restrict(f"[Start] >= '{f_start}' AND [End] <= '{(now_dt.replace(hour=23, minute=59)).strftime('%m/%d/%Y %I:%M %p')}'")
            ev_count = len(today_ev) if len(today_ev) < 100 else 0
            ev_text = ""
            for app in cal.Restrict(f"[End] >= '{f_start}'"):
                if not app.AllDayEvent: ev_text = f"Plan: {app.Start.strftime('%H:%M')} - {app.Subject}"; break
            tasks = ns.GetDefaultFolder(13).Items.Restrict("[Status] <> 2")
            return f"E-mail: {unread_emails_global} | Akce: {ev_count} | Ukoly: {len(tasks)}", ev_text[:49]
        except: return "Outlook Offline", ""
    if EMAIL_CLIENT == "Thunderbird":
        unread_emails_global = get_thunderbird_unread()
        is_running = any("thunderbird.exe" in p.name().lower() for p in psutil.process_iter())
        return f"Thunderbird ({'Aktivni' if is_running else 'Zavren'}): {unread_emails_global} mailů", ""
    return "E-mail: --", ""

# --- KOMUNIKACE DISPLEJ ---
def send_cmd(cmd):
    global ser
    if ser and ser.is_open:
        # Použijeme zámek, aby se zápis netloukl se čtením tlačítek
        with ser_lock:
            try:
                # Odeslání dat
                ser.write(cmd.encode('ascii'))
                ser.write(b'\xff\xff\xff')
                log_debug(f"Odeslán příkaz: {cmd}")
            except Exception as e:
                log_error(f"KRITICKÁ CHYBA PORTU při '{cmd}': {str(e)}")
                try:
                    ser.close()
                except:
                    pass
                ser = None
    else:
        if DEBUG_ENABLED:
            log_debug(f"Příkaz '{cmd}' neodeslán - port je zavřený.")

def update_val(obj, val, is_text=True, force=False):
    global cache, ser
    if not ser or not ser.is_open: return     
    new_val = str(val)
    if cache.get(obj) != new_val or force:
        if is_text: 
            send_cmd(f'{obj}.txt="{new_val}"')
        else: 
            send_cmd(f'{obj}.val={new_val}')
        cache[obj] = new_val

def update_meteo_page(r_json):
    if not r_json: return
    icons, t_days = ["p1","p2","p3","p4","p5","p6"], ["t3","t5","t6","t8","t10","t12"]
    t_maxs, t_mins = ["t2","t4","t7","t9","t11","t13"], ["t19","t18","t17","t16","t15","t14"]
    daily = r_json['daily']
    for i in range(6):
        send_cmd(f"{icons[i]}.pic={map_weather_to_id(daily['weather_code'][i])}")
        update_val(t_days[i], get_cz_day_name(daily['time'][i], i))
        update_val(t_maxs[i], round(daily['temperature_2m_max'][i]))
        update_val(t_mins[i], round(daily['temperature_2m_min'][i]))

# --- AKTUALIZACE SW V DISPLAYI ---
def upload_tft_file(file_path):
    global ser, running, SERIAL_PORT, BAUD_RATE
    
    # Kontrola souboru (pro jistotu)
    if not os.path.exists(file_path):
        send_pc_notification("Chyba nahrávání", "Soubor .tft nebyl nalezen.")
        globals().update(DISPLAY_MODE="PC") # Vrátit režim, aby monitor mohl pokračovat
        return

    # Najdeme port (už ho nezkoušíme zavírat, víme, že je None)
    p = SERIAL_PORT if SERIAL_PORT != "Auto" else find_nextion_port()
    if not p:
        send_pc_notification("Chyba", "Displej nenalezen.")
        globals().update(DISPLAY_MODE="PC")
        return

    try:
        file_size = os.path.getsize(file_path)
        log_info(f"Zahajuji nahrávání na portu {p} ({file_size} bajtů)...")
        
        # Otevření portu na základní rychlosti pro inicializaci [cite: 801, 802]
        ser = serial.Serial(p, BAUD_RATE, timeout=0.5, write_timeout=0.5)
        
        # --- KROK 1: Connect a inicializace whmi-wri [cite: 797, 815] ---
        ser.write(b'\x00\xff\xff\xff') 
        time.sleep(0.1)
        ser.write(b"connect\xff\xff\xff")
        time.sleep(0.3)
        ser.read_all() # Vyčistit buffer

        # Inicializace zápisu [cite: 815, 819]
        cmd_str = f"whmi-wri {file_size},{UPLOAD_BAUD},0"
        ser.write(cmd_str.encode('ascii'))
        ser.write(b'\xff\xff\xff')
        
        # Čekání na potvrzení 0x05 (displej se přepíná) [cite: 822]
        time.sleep(0.5)
        response = ser.read(ser.in_waiting or 1)
        
        if b'\x05' not in response:
            log_info("Displej nepotvrdil 0x05, zkouším pokračovat (Force Push)...")

        # --- KROK 2: Přepnutí na vysokou rychlost a přenos [cite: 820, 822] ---
        ser.close()
        time.sleep(0.5) 
        ser = serial.Serial(p, UPLOAD_BAUD, timeout=1.0, write_timeout=None)
        
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(4096) # Dokumentace vyžaduje 4096B [cite: 822]
                if not chunk: break
                
                ser.write(chunk)
                time.sleep(0.02) # Stabilizace pro HW buffer
                
                # Čekání na potvrzení bloku 0x05 [cite: 822, 944]
                start_wait = time.time()
                while ser.in_waiting == 0 and running:
                    if time.time() - start_wait > 3.0:
                        raise Exception("Displej přestal potvrzovat data. Zkontrolujte display a soubor, možná nahráváte jinou verzi FW")
                    time.sleep(0.001)
                ser.read(ser.in_waiting)

        send_pc_notification("Hotovo", "Nahrávání bylo úspěšné.")
        
    except Exception as e:
        log_error(f"Chyba při nahrávání: {e}")
        send_pc_notification("Chyba nahrávání", str(e))
    finally:
        if ser:
            try: ser.close()
            except: pass
        ser = None 
        globals().update(DISPLAY_MODE="PC") # Vrátíme režim, aby main_loop mohla znovu otevřít port

def open_terminal_isolated():
    global DISPLAY_MODE, ser

    # Uložíme původní režim
    old_mode = DISPLAY_MODE
    DISPLAY_MODE = "Uploading"

    # Zavřeme sériový port
    if ser:
        try:
            ser.close()
        except:
            pass
        ser = None

    # Wrapper, který po zavření okna vrátí režim zpět
    def run_terminal():
        try:
            standalone_terminal_window(SERIAL_PORT, BAUD_RATE)
        finally:
            # Po zavření okna se vrátí režim
            globals().update(DISPLAY_MODE=old_mode)

    # Spuštění v threadu (neblokuje tray)
    threading.Thread(target=run_terminal, daemon=True).start()
    
def standalone_terminal_window(target_port, target_baud):
    import tkinter as tk
    from tkinter import scrolledtext
    import serial
    import threading
    import time
    import serial.tools.list_ports

    # --- VNITŘNÍ FUNKCE PRO DETEKCI (pokud je port 'Auto') ---
    def get_real_port(p):
        if p != "Auto": return p
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            if any(x in port.description for x in ["USB", "Serial", "CH340", "CP2102", "FTDI", "UART"]):
                return port.device
        return None

    root = tk.Tk()
    root.title("Terminal")
    root.geometry("950x550")
    root.attributes("-topmost", True)

    display_area = scrolledtext.ScrolledText(root, height=15, font=("Consolas", 10))
    display_area.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
    display_area.tag_config("TX", foreground="blue")
    display_area.tag_config("RX", foreground="green")
    display_area.tag_config("ERR", foreground="red")

    def log(message, tag="RX"):
        try:
            if root.winfo_exists():
                display_area.config(state='normal')
                display_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n", tag)
                display_area.config(state='disabled')
                display_area.see(tk.END)
        except: pass

    # Získání skutečného názvu portu (např. COM10 místo 'Auto')
    real_p = get_real_port(target_port)
    ser_term = None

    if real_p:
        try:
            ser_term = serial.Serial(real_p, target_baud, timeout=0.1)
            log(f"Připojeno k {real_p} ({target_baud} bps)", "RX")
        except Exception as e:
            log(f"Chyba portu {real_p}: {e}", "ERR")
    else:
        log("Chyba: Nebyl nalezen žádný dostupný port!", "ERR")

    def read_thread():
        while ser_term and ser_term.is_open:
            try:
                if ser_term.in_waiting > 0:
                    data = ser_term.read(ser_term.in_waiting)
                    h = data.hex(' ').upper()
                    # Vyčištění ASCII od netisknutelných znaků (převod 0xFF na tečku) [cite: 3]
                    a = data.decode('ascii', errors='replace').replace('\xff', '.')
                    log(f"RX <- {h}  ({a})", "RX")
            except: break
            time.sleep(0.05)

    if ser_term:
        threading.Thread(target=read_thread, daemon=True).start()

    input_frame = tk.Frame(root)
    input_frame.pack(fill=tk.X, padx=10, pady=10)
    entry = tk.Entry(input_frame, font=("Consolas", 11))
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    entry.focus_force()

    def send_action(event=None):
        cmd = entry.get()
        if cmd and ser_term and ser_term.is_open:
            try:
                # Odeslání ASCII instrukce + 3x 0xFF [cite: 3, 4]
                ser_term.write(cmd.encode('ascii') + b'\xff\xff\xff')
                log(f"TX -> {cmd}", "TX")
                entry.delete(0, tk.END)
            except Exception as e:
                log(f"Chyba odesílání: {e}", "ERR")

    entry.bind("<Return>", send_action)
    tk.Button(input_frame, text="Odeslat", command=send_action, width=10).pack(side=tk.RIGHT)

    # --- TLAČÍTKA RYCHLÝCH PŘÍKAZŮ ---
    btn_frame = tk.Frame(root)
    btn_frame.pack(fill=tk.X, padx=10)
    
    # Rychlé příkazy z manuálu: rest (reset), connect (navázání), sendme (ID stránky) [cite: 7, 8, 797, 134]
    cmds = [
    ("Reset", "rest"),
    ("Connect", "connect"),
    ("ID Stránky", "sendme"),
    ("Text: Ahoj", 't1.txt="ahoj"'),
    ("Jas 50%", "dim=50"),
    ("Jas 0%", "dim=0"),
    # --- NOVÉ PŘÍKAZY ---
    ("Vyčistit (Modrá)", "cls BLUE"),
    ("Skrýt vše", "vis 255,0"),
    ("Zobrazit vše", "vis 255,1"),
    ("Vypnout dotyk", "tsw 255,0"),
    ("Spánek", "sleep=1"),
    ("Probudit", "sleep=0")
    ]
    for txt, c in cmds:
        tk.Button(btn_frame, text=txt, command=lambda cmd=c: entry.insert(0, cmd)).pack(side=tk.LEFT, padx=5)

    def on_close():
        if ser_term: ser_term.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
    
def select_and_upload():
    global ser, DISPLAY_MODE
    
    # KROK A: Okamžité zastavení monitorovací smyčky a uvolnění portu
    log_info("Příprava na nahrávání: Ukončuji monitorovací smyčku a uvolňuji port...")
    globals().update(DISPLAY_MODE="Uploading") # Zastaví logiku v main_display_loop
    
    if ser:
        try:
            ser.close()
            log_info("Port byl úspěšně uzavřen před výběrem souboru.")
        except Exception as e:
            log_error(f"Chyba při zavírání portu: {e}")
    ser = None # Důležité pro vyčištění stavu

    # KROK B: Samotný výběr souboru (port je již volný)
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    file_path = tk.filedialog.askopenfilename(
        title="Vyber zkompilovaný soubor pro displej",
        filetypes=[("TFT soubory", "*.tft")]
    )
    root.destroy()
    
    if file_path:
        # Spustíme nahrávání v novém vláknu
        threading.Thread(target=upload_tft_file, args=(file_path,), daemon=True).start()
    else:
        # Pokud uživatel výběr zrušil, vrátíme displej do PC režimu, aby se smyčka opět chytila
        log_info("Výběr souboru zrušen, vracím se k monitorování.")
        globals().update(DISPLAY_MODE="PC")
        

# --- GLOBÁLNÍ FUNKCE PRO MENU ---
def set_p(p_name):
    global SERIAL_PORT, ser, cache, last_menu_change
    name = str(p_name)
    SERIAL_PORT = name
    last_menu_change = time.time()
    if ser:
        try: ser.close()
        except: pass
        ser = None
    cache.clear()
    save_config()

def set_b(b_val, auto_mode=False):
    global BAUD_RATE, AUTO_BAUD, ser, cache, last_menu_change
    BAUD_RATE, AUTO_BAUD = int(b_val), auto_mode
    last_menu_change = time.time()
    if ser:
        try: ser.close()
        except: pass
        ser = None
    cache.clear()
    save_config()

def set_m(m):
    global DISPLAY_MODE, cache
    DISPLAY_MODE = m
    cache.clear()
    save_config()

def set_lt(t):
    global LOCK_METEO_TIME
    LOCK_METEO_TIME = t
    save_config()

def set_it(t):
    global LOOP_INTERVAL
    LOOP_INTERVAL = t
    save_config()

def set_brightness(val):
    global BRIGHTNESS
    BRIGHTNESS = val
    send_cmd(f"dim={BRIGHTNESS}")
    log_info(f"Jas Displeje nastaven na: {val}%")
    save_config()

# --- SYSTRAY MENU ---

def ask_custom_location():
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    loc_data = simpledialog.askstring("Vlastní lokace", "Zadej Město, Lat, Lon (např: Vestec, 49.99, 14.50):")
    if loc_data:
        try:
            parts = [p.strip() for p in loc_data.split(',')]
            globals().update(CITY_NAME=parts[0], CITY_LAT=float(parts[1]), CITY_LON=float(parts[2]), AUTO_GEO=False, last_weather=0)
        except: send_pc_notification("Chyba zadání", "Formát: Název, Lat, Lon")
    root.destroy()
    
def resource_path(relative_path):
    """ Získá cestu k prostředkům v PyInstalleru i v dev režimu """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def create_tray_icon():
    try: return Image.open("logo.png")
    except:
        img = Image.new('RGB', (64, 64), (30, 30, 30))
        d = ImageDraw.Draw(img); d.ellipse((5, 5, 59, 59), fill=(0, 120, 215))
        d.text((15, 18), "FP", fill=(255, 255, 255)); return img

def create_menu():
    def make_port_action(p): return lambda icon, item: set_p(p)
    def make_baud_action(b, auto): return lambda icon, item: set_b(b, auto)
    def make_mode_action(m): return lambda icon, item: set_m(m)
    def make_it_action(t): return lambda icon, item: set_it(t)
    def make_lt_action(t): return lambda icon, item: set_lt(t)
    def make_brightness_action(v): return lambda icon, item: set_brightness(v)

    ports = [p.device for p in serial.tools.list_ports.comports()]
    p_menu = [MenuItem(p, make_port_action(p), checked=lambda item, p=p: SERIAL_PORT == p) for p in ports]
    p_menu.append(Menu.SEPARATOR)
    p_menu.append(MenuItem("Auto", make_port_action("Auto"), checked=lambda item: SERIAL_PORT == "Auto"))

    bauds = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 250000, 256000, 512000, 921600]
    b_menu = [MenuItem("Auto-Baud", make_baud_action(9600, True), checked=lambda item: AUTO_BAUD)]
    b_menu += [MenuItem(str(b), make_baud_action(b, False), checked=lambda item, b=b: not AUTO_BAUD and BAUD_RATE == b) for b in bauds]

    return Menu(
        MenuItem(f"● {APP_NAME} {APP_VERSION}", lambda: None, enabled=False),
        MenuItem(f"  {COPYRIGHT}", lambda: None, enabled=False),
        Menu.SEPARATOR,
        MenuItem("Obrazovka", Menu(
            MenuItem("Zapnout displej", lambda icon, item: globals().update(FORCE_OFF=False), checked=lambda i: not FORCE_OFF),
            MenuItem("Vypnout displej (DIM 0)", lambda icon, item: globals().update(FORCE_OFF=True), checked=lambda i: FORCE_OFF)
        )),
        MenuItem("Režim", Menu(
            MenuItem("PC Monitor", make_mode_action("PC"), checked=lambda i: DISPLAY_MODE == "PC"),
            MenuItem("Meteo", make_mode_action("Meteo"), checked=lambda i: DISPLAY_MODE == "Meteo"),
            MenuItem("Media Control", make_mode_action("Media"), checked=lambda i: DISPLAY_MODE == "Media"),
            MenuItem("Graf vytížení", make_mode_action("Graph"), checked=lambda i: DISPLAY_MODE == "Graph"),
            MenuItem("Smyčka (PC Monitor/Meteo)", make_mode_action("Loop"), checked=lambda i: DISPLAY_MODE == "Loop")
        )),
        MenuItem("Jas displeje", Menu(
            MenuItem("100%", make_brightness_action(100), checked=lambda i: BRIGHTNESS == 100),
            MenuItem("80%", make_brightness_action(80), checked=lambda i: BRIGHTNESS == 80),
            MenuItem("50%", make_brightness_action(50), checked=lambda i: BRIGHTNESS == 50),
            MenuItem("20%", make_brightness_action(20), checked=lambda i: BRIGHTNESS == 20),
            MenuItem("10%", make_brightness_action(10), checked=lambda i: BRIGHTNESS == 10)
        )),
        MenuItem("Intervaly", Menu(
            MenuItem("Smyčka: 1 min", make_it_action(60), checked=lambda i: LOOP_INTERVAL == 60),
            MenuItem("Smyčka: 5 min", make_it_action(300), checked=lambda i: LOOP_INTERVAL == 300),
            Menu.SEPARATOR,
            MenuItem("Meteo po zámku: 30s", make_lt_action(30), checked=lambda i: LOCK_METEO_TIME == 30),
            MenuItem("Meteo po zámku: 2m", make_lt_action(120), checked=lambda i: LOCK_METEO_TIME == 120)
        )),
        MenuItem("Meteo lokace ", Menu(
            MenuItem("Automaticky (IP)", lambda icon, item: globals().update(AUTO_GEO=True, last_weather=0), checked=lambda i: AUTO_GEO == True),
            MenuItem("Zadat souřadnice...", lambda icon, item: ask_custom_location()),
            MenuItem(f"Aktuálně: {CITY_NAME}", lambda icon, item: None, enabled=False)
        )),
        MenuItem("Zobrazovat svatky", lambda icon, item: [globals().update(SHOW_NAMEDAY=not SHOW_NAMEDAY), save_config()], checked=lambda i: SHOW_NAMEDAY), 
        MenuItem("Emailový klient", Menu(
            MenuItem("Outlook", lambda icon, item: [globals().update(EMAIL_CLIENT="Outlook"), save_config()], checked=lambda i: EMAIL_CLIENT == "Outlook"),
            MenuItem("Thunderbird", lambda icon, item: [globals().update(EMAIL_CLIENT="Thunderbird"), save_config()], checked=lambda i: EMAIL_CLIENT == "Thunderbird"),
            MenuItem("Vypnuto", lambda icon, item: [globals().update(EMAIL_CLIENT="None"), save_config()], checked=lambda i: EMAIL_CLIENT == "None")
        )),
        MenuItem("Nastavení zámku", Menu(
            MenuItem("Zobrazit Meteo", lambda icon, item: globals().update(LOCK_SHOW_METEO=not LOCK_SHOW_METEO), checked=lambda i: LOCK_SHOW_METEO == True),
            MenuItem("Úplné vypnutí (DIM 0)", lambda icon, item: globals().update(USE_SLEEP_CMD=not USE_SLEEP_CMD), checked=lambda i: USE_SLEEP_CMD == True)
        )),
        Menu.SEPARATOR,
        MenuItem("Komunikace", lambda: None, enabled=False),
        MenuItem("Port", Menu(*p_menu)),
        MenuItem("Baudrate", Menu(*b_menu)),
        Menu.SEPARATOR,
        MenuItem("Experimentální", lambda: None, enabled=False),        
        MenuItem("Povolit debug", lambda icon, item: [globals().update(DEBUG_ENABLED=not DEBUG_ENABLED),save_config()], checked=lambda i: DEBUG_ENABLED),        
        MenuItem("Nahrát FW do displeje", lambda icon, item: select_and_upload()),
        MenuItem("Terminal", lambda icon, item: open_terminal_isolated()),
        
        Menu.SEPARATOR,
        MenuItem("Systémové", lambda: None, enabled=False),
        MenuItem("Zkontrolovat aktualizace", lambda icon, item: check_for_updates(manual=True)),
        MenuItem("Aut. aktualizace HMI", lambda icon, item: [globals().update(AUTO_HMI_UPDATE=not AUTO_HMI_UPDATE), save_config(), threading.Thread(target=check_hmi_update_flow, daemon=True).start() if AUTO_HMI_UPDATE else None], checked=lambda i: AUTO_HMI_UPDATE),
        MenuItem("Resetovat síťová maxima", lambda icon, item: globals().update(max_dn_recorded=1024*1024, max_up_recorded=1024*1024)),
        MenuItem("Spustit po startu", lambda icon, item: set_autostart(not is_autostart_enabled()), checked=lambda i: is_autostart_enabled()),
        Menu.SEPARATOR, 
        MenuItem("Ukončit", lambda icon, item: [globals().update(running=False), icon.stop()])
    )

# --- HLAVNÍ LOGIKA ---
def main_display_loop():
    global ser, cache, running, DISPLAY_MODE, meteo_data_raw, current_out_temp, \
           locked_start_time, last_dn_str, last_up_str, BAUD_RATE, last_weather, \
           LOOP_INTERVAL, LOCK_METEO_TIME, SERIAL_PORT, AUTO_BAUD, BRIGHTNESS, FORCE_OFF, \
           max_dn_recorded, max_up_recorded
    import asyncio
    log_info("Hlavní smyčka nastartována.")
    last_slow, last_weather, last_time_net, last_loop_change = 0, 0, time.time(), 0
    last_net = psutil.net_io_counters(); cpu_name = platform.processor().split(' ')[0]
    last_name_day_update = 0
    current_name_day = "Svatek: --"
    current_loop_page, last_sent_page, last_sent_dim = 1, -1, -1
    locked_mode, meteo_active = False, False

    if AUTO_GEO: get_geo_location()

    while running:
        if DISPLAY_MODE in ["Uploading", "Terminal"]:
            time.sleep(0.5)
            continue
        # --- ČTENÍ Z PORTU (Tlačítka) ---
        try:
            if ser and ser.is_open:
                # Kontrola in_waiting musí být uvnitř try, protože tady to padá
                if ser.in_waiting > 0:
                    with ser_lock:
                        raw_data = ser.read_all().decode('ascii', errors='ignore').strip()
                        if raw_data:
                            handle_media_click(raw_data)
        except serial.SerialException as se:
            log_error(f"Port odpojen (HW chyba): {se}")
            ser = None # Vynutí reconnection logiku níže v loopu
            continue
        except Exception as e:
            log_error(f"Chyba čtení portu: {e}")
        try:
            # 1. ČASOVÉ AKTUALIZACE (POČASÍ A EMAIL) - MUSÍ BÝT PRVNÍ!
            now, dt_now = time.time(), datetime.datetime.now()
            
            # Aktualizace počasí
            if now - last_weather > 900 or last_weather == 0:
                if AUTO_GEO and last_weather == 0: get_geo_location()
                try:
                    r = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={CITY_LAT}&longitude={CITY_LON}&current=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,wind_gusts_10m,uv_index&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=6", timeout=5).json()
                    meteo_data_raw = r; current_out_temp = int(r['current']['temperature_2m'])
                    weather_data["curr"] = f"Venku: {current_out_temp}*C | Vlhkost: {r['current']['relative_humidity_2m']}%"
                    weather_data["fore"] = f"Dnes: {int(r['daily']['temperature_2m_max'][0])}/{int(r['daily']['temperature_2m_min'][0])}*C"
                    weather_data["wind"] = f"Vitr: {int(r['current']['wind_speed_10m'])}km/h"
                    weather_data["det"] = f"Tlak: {int(r['current']['surface_pressure'])}hPa | UV: {r['current']['uv_index']}"
                    log_info("Počasí úspěšně aktualizováno.")
                except Exception as ex: 
                    log_error(f"Chyba počasí: {ex}")
                last_weather = now
            # Aktualizace emailů a sítě (pomalá data)
            if now - last_slow > 5:
                m, e = get_email_data()
                weather_data["emails"] = m
                weather_data["event"] = e
                my_ip, my_gw = get_network_info()
                weather_data["ip"] = f"IP: {my_ip} | GW: {my_gw}"
                if now - last_name_day_update > 3600 or last_name_day_update == 0:
                    current_name_day = get_today_name_day()
                    last_name_day_update = now
                # -----------------------------------------------------

                last_slow = now
            

            # 2. SPRÁVA PŘIPOJENÍ DISPLEJE
            if time.time() - last_menu_change < 1.5:
                time.sleep(0.1); continue

            # --- Pokud nahráváme, na port vůbec nesahej! ---
            if DISPLAY_MODE == "Uploading":
                time.sleep(0.5) 
                continue
            # --------------------------------------------------------------

            if ser is None or not ser.is_open:
                p = SERIAL_PORT if SERIAL_PORT != "Auto" else find_nextion_port()
                if p:
                    test_bauds = [9600, 19200, 38400, 57600, 115200, 230400, 250000, 256000, 512000, 921600, 1200, 2400, 4800] if AUTO_BAUD else [BAUD_RATE]
                    found = False
                    for b in test_bauds:
                        try:                   
                            log_debug(f"Pokus o připojení: {p} @ {b} bps")
                            tmp = serial.Serial(p, b, timeout=0.5, write_timeout=0.5)
                            tmp.dtr = False; tmp.rts = False
                            time.sleep(0.2) 
                            tmp.reset_input_buffer()
                            tmp.write(b'\xff\xff\xffconnect\xff\xff\xff')
                            time.sleep(0.5)
                            response = tmp.read(tmp.in_waiting)
                            if len(response) > 0:
                                log_info(f"Úspěšné spojení! Odezva: {response}")
                                ser = tmp; BAUD_RATE = b; last_sent_page = -1; cache.clear()
                                send_pc_notification("Připojeno", f"Nalezen displej na {p}\nRychlost: {b} bps")
                                if AUTO_HMI_UPDATE:
                                    log_info("Auto-Update HMI je povolen, spouštím kontrolu verze...")
                                    threading.Thread(target=check_hmi_update_flow, daemon=True).start()                                
                                found = True; break
                            else: tmp.close()
                        except Exception as e:
                            if "Access is denied" in str(e):
                                log_error(f"Port {p} je obsazen jiným programem!"); found = False; break 
                            continue
                    if not found: time.sleep(5); continue
                else: time.sleep(5); continue

            # 3. VÝPOČET ZOBRAZENÍ A ODESÍLÁNÍ DAT
            locked = is_pc_locked()
            target_page, target_dim = 1, BRIGHTNESS

            if FORCE_OFF:
                target_dim = 0
            elif locked:
                if not locked_mode: locked_start_time, locked_mode, meteo_active = now, True, LOCK_SHOW_METEO
                if meteo_active and (now - locked_start_time > LOCK_METEO_TIME): meteo_active = False
                if meteo_active: target_page, target_dim = 3, 50
                else: 
                    target_dim = 0 if USE_SLEEP_CMD else 10
                    target_page = 2 if target_dim > 0 else 1
            else:
                locked_mode = False
                if DISPLAY_MODE == "PC": target_page = 1
                elif DISPLAY_MODE == "Meteo": target_page = 3
                elif DISPLAY_MODE == "Media": target_page = 4
                elif DISPLAY_MODE == "Graph": target_page = 5
                elif DISPLAY_MODE == "Loop":
                    if now - last_loop_change > LOOP_INTERVAL: current_loop_page = 3 if current_loop_page == 1 else 1; last_loop_change = now
                    target_page = current_loop_page
                else: target_page = 1

            if target_page != last_sent_page: send_cmd(f"page page{target_page}"); last_sent_page = target_page; cache.clear()
            if target_dim != last_sent_dim: send_cmd(f"dim={target_dim}"); last_sent_dim = target_dim

            if target_dim > 0:
                if target_page == 1:
                    update_val("t1", dt_now.strftime("%H:%M:%S"))
                    cpu, ram = int(psutil.cpu_percent()), int(psutil.virtual_memory().percent)
                    try:
                        disk_p = int(psutil.disk_usage('C:').percent)
                    except:
                        disk_p = 0
                    if (dt_now.second // 2) % 2 == 0:
                        update_val("t0", dt_now.strftime("%d.%m.%Y"))
                        for k, v in {"t5":"CPU","t6":"OUT","t7":"RAM","t8":"DISK","t9":"DOWN","t10":"UP"}.items(): update_val(k, v)
                        if unread_emails_global == 0: update_val("t11", f"HW: {cpu_name} | {get_disks_info()}")
                    else:
                        upt = now - psutil.boot_time()
                        update_val("t0", f"U: {current_user}")
                        if unread_emails_global == 0: update_val("t11", f"Uptime: {int(upt//3600)}h {int((upt%3600)//60)}m")
                        disk_p = int(psutil.disk_usage('C:').percent)
                        for k, v in {"t5":f"{cpu}%","t6":f"{current_out_temp}*C","t7":f"{ram}%","t8":f"{disk_p}%","t9":last_dn_str,"t10":last_up_str}.items(): update_val(k, v)
                    
                    update_val("j0", cpu, False); send_cmd(f'j0.pco={get_color(cpu)}')
                    update_val("j1", int(current_out_temp), False); send_cmd(f'j1.pco={get_color(current_out_temp, 25, 35)}')
                    update_val("j3", ram, False); send_cmd(f'j3.pco={get_color(ram, 60, 90)}')
                    update_val("j2", disk_p, False); send_cmd(f'j2.pco={get_color(disk_p, 70, 90)}')

                    curr_net = psutil.net_io_counters(); dt_n = now - last_time_net
                    if dt_n >= 0.5:
                        # Aktuální rychlost v bajtech za sekundu
                        dn_bps = (curr_net.bytes_recv - last_net.bytes_recv) / dt_n
                        up_bps = (curr_net.bytes_sent - last_net.bytes_sent) / dt_n

                        # --- AUTO-SCALE LOGIKA ---
                        # Pokud je aktuální rychlost vyšší než dosavadní rekord, posuneme strop
                        if dn_bps > max_dn_recorded: max_dn_recorded = dn_bps
                        if up_bps > max_up_recorded: max_up_recorded = up_bps

                        last_dn_str = format_speed(dn_bps)
                        last_up_str = format_speed(up_bps)

                        # Výpočet procent vzhledem k dynamickému maximu
                        dn_perc = int((dn_bps / max_dn_recorded) * 100) if max_dn_recorded > 0 else 0
                        up_perc = int((up_bps / max_up_recorded) * 100) if max_up_recorded > 0 else 0

                        # Odeslání do bargrafů na displeji
                        update_val("j4", up_perc, False) 
                        update_val("j5", dn_perc, False)
                        
                        # Barvy zůstávají stejné
                        send_cmd(f'j4.pco={get_color(up_perc, 70, 90)}')
                        send_cmd(f'j5.pco={get_color(dn_perc, 70, 90)}')

                        last_net, last_time_net = curr_net, now
                    
                    update_val("t2", [weather_data["curr"], weather_data["fore"], weather_data["wind"], weather_data["det"]][(dt_now.second // 4) % 4])
                    update_val("t3", weather_data.get("emails", ""))
                    if unread_emails_global == 0: update_val("t4", weather_data.get("event", ""))
                    else: update_val("t12", "!!! PRISEL NOVY EMAIL !!!"); send_cmd(f"t12.pco={RED}"); update_val("t4", ""); update_val("t11", "")
                    if unread_emails_global == 0: update_val("t12", weather_data.get("ip", "")); send_cmd(f"t12.pco={WHITE}")

                elif target_page == 3:
                    update_val("t0", dt_now.strftime("%d.%m.%Y")); update_val("t1", dt_now.strftime("%H:%M:%S"))
                    if meteo_data_raw: update_meteo_page(meteo_data_raw)
                    elif target_page == 2: update_val("t0", dt_now.strftime("%d.%m.%Y")); update_val("t1", dt_now.strftime("%H:%M"))
                    if SHOW_NAMEDAY:
                        update_val("t20", current_name_day)
                    else:
                        update_val("t20", "") # Vymaže text, pokud je funkce vypnutá
                elif target_page == 4:
                    # Hodiny posíláme každou vteřinu
                    update_val("t0", dt_now.strftime("%H:%M:%S"))                    
                    # Media data (shared_media_info plní ten druhý thread)
                    m = getattr(main_display_loop, 'shared_media_info', None)
                    if m:
                        # update_val díky cache pošle t4 a t5 jen při změně písničky!
                        full_info = m.get("text", "Nic nehraje")
                        if " - " in full_info:
                            artist, title = full_info.split(" - ", 1)
                            update_val("t1", artist.strip()[:24])
                            update_val("t4", title.strip()[:45])
                        else:
                            update_val("t1", full_info[:45])
                            update_val("t4", "")

                        update_val("t2", m.get("time_str", ""))
                        update_val("t3", m.get("remaining", ""))
                        # Progress bar jen při změně procenta
                        update_val("j0", m.get("progress", 0), is_text=False)     
                        
                        status_pic = m.get("status_pic", 19)
                        if cache.get("p3_pic") != status_pic:
                            send_cmd(f"p3.pic={status_pic}")
                            cache["p3_pic"] = status_pic
                elif target_page == 5:
                    # Horní a dolní textové popisky (t0 pro čas, t1 pro info o grafu)
                    update_val("t0", dt_now.strftime("%H:%M:%S"))
                    
                    
                    # Logika střídání textu v t1 (každé 4 sekundy)
                    if dt_now.second % 8 < 4:
                        update_val("t1", "CH0: CPU Load (%) | CH1: RAM Usage (%)")
                    else:
                        update_val("t1", f"CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}%")

                    # Získání dat (0-100)
                    val0 = psutil.cpu_percent()
                    val1 = psutil.virtual_memory().percent
                    # Definice barev pro TJC (RGB565) [cite: 675]
                    # GREEN: 2016, YELLOW: 65504, ORANGE: 64495, RED: 63488

                    # Určení barvy podle vytížení val0 (CPU)
                    if val0 > 90:
                        current_color0 = 63488  # Červená
                    elif val0 > 75:
                        current_color0 = 64495  # Oranžová
                    elif val0 > 50:
                        current_color0 = 65504  # Žlutá
                    else:
                        current_color0 = 2016   # Zelená
                    
                    # Odeslání barvy do TJC pouze při změně (šetříme přenosové pásmo) 
                    if cache.get("s0_pco0") != current_color0:
                        send_cmd(f"s0.pco0={current_color0}")
                        cache["s0_pco0"] = current_color0

                    # Poznámka: Nextion vyžaduje jméno objektu pro .pco, ale ID pro .add

                    # PŘEPOČET PRO WAVEFORM (Nextion Waveform bere hodnotu 0-255)
                    # Protože graf má výšku 270, Nextion interně škáluje 0-255 na výšku objektu.
                    # Hodnotu 0-100 tedy vynásobíme 2.55.
                    send0 = int(val0 * 2.55)
                    send1 = int(val1 * 2.55)

                    # Definuj si nahoře globální proměnnou:
                    last_graph_update = 0

                    # V main_display_loop uvnitř target_page == 5:
                    if now - last_graph_update > 1: # Update grafu jen každých 500ms
                        send_cmd(f"add 3,0,{send0}")
                        send_cmd(f"add 3,1,{send1}")
                        last_graph_update = now
                        
        except Exception as global_ex:
            log_error(f"Kritická chyba v hlavní smyčce: {global_ex}")
            try: ser.close()
            except: pass
            ser = None
        time.sleep(0.1)

if __name__ == "__main__":
    load_config()
    threading.Thread(target=check_for_updates, daemon=True).start()
    threading.Thread(target=media_updater_worker, daemon=True).start()
    try:
        threading.Thread(target=main_display_loop, daemon=True).start()
        Icon("mujDISPLAY", create_tray_icon(), "mujDISPLAY Monitor", menu=create_menu()).run()
    except Exception as start_ex:
        print(f"Aplikace nenastartovala: {start_ex}")

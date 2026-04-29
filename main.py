"""
================================================================================
PROJEKT: mujDISPLAY Monitor
AUTOR:    Copyright (c) 2026 Petr Fodor, Controlsystems.cz
VERZE:    v2.1 (2026-04-29)

Permission is hereby granted, free of charge, to any person obtaining a copy...
(Full license text is in LICENSE file)
================================================================================

CHANGELOG:
v2.1 – Stability, Intelligence & UI Hotfix (2026-04-29)
----------------
Zaměřeno na eliminaci kritických chyb v komunikaci, plnou integraci Outlook dat a vylepšení stability GUI.
* Komunikace a binární protokol:
- Ochrana proti PermissionError: Vyřešena kritická chyba WriteFile failed (PermissionError 13). Pokud systém detekuje, že port je uzamčen nebo přístup odepřen, driver nyní provede čistý reset stavu (ser = None), což okamžitě aktivuje automatický pokus o znovupřipojení (reconnect).
- Robustní Serial Write: Implementována ochrana proti SerialTimeoutException. Pokud displej nestíhá odbavovat instrukce (např. při rychlém vykreslování grafů), aplikace automaticky vyčistí výstupní buffer místo pádu celého vlákna.
- Binární HMI verifikace: Přidána podpora pro dekódování binárních odpovědí displeje (protokol 0x71). Verze swver.val je nyní korektně čtena z Little-endian formátu.
- Vláknové zabezpečení (Locking): Zpřísněn threading.Lock v metodě send_command a read_buttons, čímž byly eliminovány kolize na sériovém portu mezi hlavním cyklem a TouchListenerem.
- Robustní Weather Engine: Opraveny chyby zpracování JSON (Response object subscriptable). Implementováno ošetření výpadků DNS (NameResolutionError), aplikace při ztrátě konektivity nezamrzá.
* Integrace Outlook (Smart Office):
- Kalendář a úkoly: Odstraněny statické zástupné znaky. Implementováno reálné vyčítání počtu dnešních schůzek (Folder 9) a aktivních úkolů (Folder 13) pomocí MAPI filtrů Restrict.
- Plánovač na displeji: Přidána rotace textů zobrazující čas a název nejbližší nadcházející události z kalendáře (vč. automatického odstranění diakritiky).
- Outlook Guard: Přidána detekce procesu outlook.exe před inicializací COM objektů, což radikálně zrychluje start aplikace, pokud není Outlook spuštěn.
* HMI Smart Update:
- Model-Specific Download: Implementována automatická detekce HW modelu (T135 vs T035) pomocí příkazu connect. Aplikace nyní stahuje správný .tft soubor podle identifikace panelu.
- Version Compare: Přidána logika pro porovnání verze na serveru (version_hmi.txt) s binárně vyčtenou verzí přímo z panelu.
* Vylepšení GUI a Tray Menu:
- Thread-Safe GUI: Vyřešena kritická chyba "Tcl_AsyncDelete" (deleted by the wrong thread) při zavírání Terminálu a dialogů pomocí sekvence root.quit() a root.destroy().
- Sjednocené zobrazení HW stavu: Popisky portů v menu se nyní dynamicky dotazují hardwaru. Zobrazují reálný COM port a Baudrate vyčtený ze sériové linky.
- Custom Intervals UI: Vlastní časy v menu nyní v závorkách zobrazují aktuálně nastavenou hodnotu v sekundách pro okamžitý přehled.
- Interaktivní Refresh: Metoda refresh() nyní zajišťuje okamžité překreslení zaškrtávacích políček (fajfek) v menu po jakékoliv změně nastavení.
* Opravy v logice:
- Loop Interval Fix: Opravena záměna proměnných v GUI dialogu mezi časem smyčky a zámkem meteo režimu.
- Import Fix: Opravena chybějící reference na modul datetime v provideru počasí způsobující pád při výpočtu událostí.

v2.0 – Modular Core Update (2026-04-27)
----------------
Zásadní architektonický přepis aplikace z monolitického skriptu do modulární struktury pro vyšší stabilitu a snadnější údržbu.
* Architektura a Jádro:
- Modularizace: Kód rozdělen do logických celků: DisplayDriver, WeatherProvider, SystemMonitor, AppState a TrayIcon.
- Vláknová bezpečnost: Implementace threading.Lock (ser_lock) pro zamezení kolizí na sériovém portu při paralelním čtení tlačítek a zápisu dat.
- Robustní konektivita: Přepsán detekční algoritmus portů; aplikace je nyní odolnější proti náhlému odpojení USB převodníku a automaticky obnovuje spojení.
- Optimalizace zápisu: Přidána metoda update_val s inteligentní cache, která odesílá data do displeje pouze při jejich reálné změně (výrazné snížení zátěže CPU a Serial linky).
* Nové funkce:
- Mezinárodní Jmeniny: Podpora pro zobrazování svátků podle vybraného jazyka aplikace (CZ, SK, EN, DE, FR) s automatickým přepínáním API (SvatkyAPI.cz vs abalin.net).
- Dynamická lokalizace (i18n): Přidána podpora jazykových mutací pro celé rozhraní monitoru i texty na displeji.
- Pokročilý Media Engine: Media worker přesunut do samostatného asynchronního vlákna pro plynulejší aktualizaci Progress Baru bez blokování hlavní smyčky.
- Vylepšený Debug Mode: Implementováno hloubkové trasování (logging) do souboru debug.log s identifikací vláken pro snadnější diagnostiku HW chyb.
* Opravy a vylepšení:
- Oprava Auto-Update: Stabilizován proces nahrávání .tft souborů (firmware) s vynuceným uvolněním portu a korektním resetem displeje po flashování.
- Ošetření Outlooku: Implementována izolovaná inicializace COM objektů (pythoncom), která brání zamrzání aplikace při startu bez spuštěného Outlooku.
- Auto-scale sítě: Opraven algoritmus pro výpočet procentuálního vytížení sítě; maxima jsou nyní dynamicky ukládána a lze je resetovat z menu.

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
import threading
import logging
import ctypes
from pathlib import Path

from config_manager import ConfigManager
from app_state import AppState
from display_driver import DisplayDriver
from system_monitor import SystemMonitor
from weather_provider import WeatherProvider
from media_provider import MediaProvider
from tray_icon import TrayIcon

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('mujDISPLAY.Monitor.2.1')
except Exception:
    pass

def setup_logging(app_state: AppState):
    base_path = Path(sys.argv[0]).parent
    log_file = base_path / "debug.log"
    logger = logging.getLogger()
    
    # Nastavíme úroveň podle stavu aplikace
    level = logging.DEBUG if app_state.debug_enabled else logging.INFO
    logger.setLevel(logging.DEBUG) # Zachytáváme vše, filtrovat budeme na výstupes

    # Formát s názvem vlákna a modulu pro snadnou orientaci
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s: %(message)s')

    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    logging.info("--- LOGOVÁNÍ INICIALIZOVÁNO ---")

def main():
    config = ConfigManager()
    app_state = AppState(config)
    setup_logging(app_state)
    logger = logging.getLogger(__name__)

    system = SystemMonitor()
    weather = WeatherProvider(app_state)
    media = MediaProvider(app_state)
    driver = DisplayDriver(app_state)

    threading.Thread(target=driver.main_loop, args=(system, weather, media),
                     daemon=True, name="DisplayLoop").start()
    threading.Thread(target=media.start, daemon=True, name="MediaUpdater").start()
    if app_state.auto_hmi_update:
        threading.Thread(target=driver.check_hmi_update, daemon=True, name="HMIUpdater").start()

    tray = TrayIcon(app_state, driver, config)
    tray.run()

if __name__ == "__main__":
    main()

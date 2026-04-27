# config_manager.py
"""Správa konfiguračního souboru config.ini."""

import configparser
from pathlib import Path

class ConfigManager:
    CONFIG_FILE = Path("config.ini")
    DEFAULTS = {
        'Settings': {
            'Port': 'Auto',
            'BaudRate': '9600',
            'AutoBaud': 'True',
            'DisplayMode': 'PC',
            'EmailClient': 'Outlook',
            'LockShowMeteo': 'True',
            'LockMeteoTime': '120',
            'LoopInterval': '60',
            'UseSleepCmd': 'False',
            'AutoGeo': 'True',
            'Brightness': '100',
            'DebugEnabled': 'False',
            'ShowNameday': 'True',
            'AutoHmiUpdate': 'False',
            'Language': 'CZ',
            'NamedaySource': 'cz',
        },
        'Location': {
            'CityName': 'Praha',
            'Lat': '50.08',
            'Lon': '14.43',
        }
    }

    def __init__(self):
        self.data = configparser.ConfigParser()
        self._load_or_create()

    def _load_or_create(self):
        if not self.CONFIG_FILE.exists():
            self.data.read_dict(self.DEFAULTS)
            self.save()
        self.data.read(self.CONFIG_FILE, encoding='utf-8')

    def save(self):
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            self.data.write(f)

    # --- Vlastnosti ---
    @property
    def port(self) -> str:
        return self.data.get('Settings', 'Port', fallback='Auto')
    @port.setter
    def port(self, value: str):
        self.data.set('Settings', 'Port', str(value))
        self.save()

    @property
    def baud_rate(self) -> int:
        return self.data.getint('Settings', 'BaudRate', fallback=9600)
    @baud_rate.setter
    def baud_rate(self, value: int):
        self.data.set('Settings', 'BaudRate', str(value))
        self.save()

    @property
    def auto_baud(self) -> bool:
        return self.data.getboolean('Settings', 'AutoBaud', fallback=True)
    @auto_baud.setter
    def auto_baud(self, value: bool):
        self.data.set('Settings', 'AutoBaud', str(value))
        self.save()

    @property
    def display_mode(self) -> str:
        mode = self.data.get('Settings', 'DisplayMode', fallback='PC')
        # Tady máš logiku, která vrací PC, pokud se nahrává nebo je terminál
        if mode in ("Terminal", "Uploading"):
            mode = 'PC'
        return mode

    # TATO ČÁST TI CHYBÍ - DOPLŇ JI:
    @display_mode.setter
    def display_mode(self, value: str):
        self.data.set('Settings', 'DisplayMode', str(value))
        self.save()

    @property
    def email_client(self) -> str:
        return self.data.get('Settings', 'EmailClient', fallback='Outlook')
    @email_client.setter
    def email_client(self, value: str):
        self.data.set('Settings', 'EmailClient', str(value))
        self.save()

    @property
    def lock_show_meteo(self) -> bool:
        return self.data.getboolean('Settings', 'LockShowMeteo', fallback=True)
    @lock_show_meteo.setter
    def lock_show_meteo(self, value: bool):
        self.data.set('Settings', 'LockShowMeteo', str(value))
        self.save()

    @property
    def lock_meteo_time(self) -> int:
        return self.data.getint('Settings', 'LockMeteoTime', fallback=120)
    @lock_meteo_time.setter
    def lock_meteo_time(self, value: int):
        self.data.set('Settings', 'LockMeteoTime', str(value))
        self.save()

    @property
    def loop_interval(self) -> int:
        return self.data.getint('Settings', 'LoopInterval', fallback=60)
    @loop_interval.setter
    def loop_interval(self, value: int):
        self.data.set('Settings', 'LoopInterval', str(value))
        self.save()

    @property
    def use_sleep_cmd(self) -> bool:
        return self.data.getboolean('Settings', 'UseSleepCmd', fallback=False)
    @use_sleep_cmd.setter
    def use_sleep_cmd(self, value: bool):
        self.data.set('Settings', 'UseSleepCmd', str(value))
        self.save()

    @property
    def auto_geo(self) -> bool:
        return self.data.getboolean('Settings', 'AutoGeo', fallback=True)
    @auto_geo.setter
    def auto_geo(self, value: bool):
        self.data.set('Settings', 'AutoGeo', str(value))
        self.save()

    @property
    def brightness(self) -> int:
        return self.data.getint('Settings', 'Brightness', fallback=100)
    @brightness.setter
    def brightness(self, value: int):
        self.data.set('Settings', 'Brightness', str(value))
        self.save()

    @property
    def debug_enabled(self) -> bool:
        return self.data.getboolean('Settings', 'DebugEnabled', fallback=False)
    @debug_enabled.setter
    def debug_enabled(self, value: bool):
        self.data.set('Settings', 'DebugEnabled', str(value))
        self.save()

    @property
    def show_nameday(self) -> bool:
        return self.data.getboolean('Settings', 'ShowNameday', fallback=True)
    @show_nameday.setter
    def show_nameday(self, value: bool):
        self.data.set('Settings', 'ShowNameday', str(value))
        self.save()

    @property
    def auto_hmi_update(self) -> bool:
        return self.data.getboolean('Settings', 'AutoHmiUpdate', fallback=False)
    @auto_hmi_update.setter
    def auto_hmi_update(self, value: bool):
        self.data.set('Settings', 'AutoHmiUpdate', str(value))
        self.save()

    @property
    def language(self) -> str:
        return self.data.get('Settings', 'Language', fallback='CZ')
    @language.setter
    def language(self, value: str):
        self.data.set('Settings', 'Language', str(value))
        self.save()

    @property
    def nameday_source(self) -> str:
        return self.data.get('Settings', 'NamedaySource', fallback='cz')
    @nameday_source.setter
    def nameday_source(self, value: str):
        self.data.set('Settings', 'NamedaySource', str(value))
        self.save()

    # Location
    @property
    def city_name(self) -> str:
        return self.data.get('Location', 'CityName', fallback='Praha')
    @city_name.setter
    def city_name(self, value: str):
        self.data.set('Location', 'CityName', str(value))
        self.save()

    @property
    def lat(self) -> float:
        return self.data.getfloat('Location', 'Lat', fallback=50.08)
    @lat.setter
    def lat(self, value: float):
        self.data.set('Location', 'Lat', str(value))
        self.save()

    @property
    def lon(self) -> float:
        return self.data.getfloat('Location', 'Lon', fallback=14.43)
    @lon.setter
    def lon(self, value: float):
        self.data.set('Location', 'Lon', str(value))
        self.save()

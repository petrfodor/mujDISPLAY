# app_state.py
"""Sdílený stav aplikace s vláknovou bezpečností."""

import threading
from config_manager import ConfigManager
from i18n import load_language

class AppState:
    def __init__(self, config: ConfigManager):
        self._lock = threading.Lock()
        self._config = config
        self._running = True

        self._display_mode = config.display_mode
        self._force_off = False
        self._brightness = config.brightness
        self._debug_enabled = config.debug_enabled
        self._show_nameday = config.show_nameday
        self._auto_hmi_update = config.auto_hmi_update

        self._city_name = config.city_name
        self._lat = config.lat
        self._lon = config.lon
        self._auto_geo = config.auto_geo

        self._port = config.port
        self._baud_rate = config.baud_rate
        self._auto_baud = config.auto_baud
        self._lock_show_meteo = config.lock_show_meteo
        self._lock_meteo_time = config.lock_meteo_time
        self._loop_interval = config.loop_interval
        self._use_sleep_cmd = config.use_sleep_cmd

        self._language = config.language
        self._nameday_source = config.nameday_source

        load_language(self._language)
        self.mode_changed = threading.Event()

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def shutdown(self):
        with self._lock:
            self._running = False

    # --- Vlastnosti ---
    @property
    def display_mode(self): return self._display_mode
    @display_mode.setter
    def display_mode(self, val):
        with self._lock:
            if self._display_mode != val:
                self._display_mode = val
                self._config.display_mode = val
                self.mode_changed.set()

    @property
    def force_off(self): return self._force_off
    @force_off.setter
    def force_off(self, val):
        with self._lock: self._force_off = val

    @property
    def brightness(self): return self._brightness
    @brightness.setter
    def brightness(self, val):
        with self._lock:
            if val != self._brightness:
                self._brightness = val
                self._config.brightness = val

    @property
    def debug_enabled(self): return self._debug_enabled
    @debug_enabled.setter
    def debug_enabled(self, val):
        with self._lock: self._debug_enabled = val; self._config.debug_enabled = val

    @property
    def show_nameday(self): return self._show_nameday
    @show_nameday.setter
    def show_nameday(self, val):
        with self._lock: self._show_nameday = val; self._config.show_nameday = val

    @property
    def auto_hmi_update(self): return self._auto_hmi_update
    @auto_hmi_update.setter
    def auto_hmi_update(self, val):
        with self._lock: self._auto_hmi_update = val; self._config.auto_hmi_update = val

    @property
    def port(self): return self._port
    @port.setter
    def port(self, val):
        with self._lock: self._port = val; self._config.port = val

    @property
    def baud_rate(self): return self._baud_rate
    @baud_rate.setter
    def baud_rate(self, val):
        with self._lock: self._baud_rate = val; self._config.baud_rate = val

    @property
    def auto_baud(self): return self._auto_baud
    @auto_baud.setter
    def auto_baud(self, val):
        with self._lock: self._auto_baud = val; self._config.auto_baud = val

    @property
    def lock_show_meteo(self): return self._lock_show_meteo
    @lock_show_meteo.setter
    def lock_show_meteo(self, val):
        with self._lock: self._lock_show_meteo = val; self._config.lock_show_meteo = val

    @property
    def lock_meteo_time(self): return self._lock_meteo_time
    @lock_meteo_time.setter
    def lock_meteo_time(self, val):
        with self._lock: self._lock_meteo_time = val; self._config.lock_meteo_time = val

    @property
    def loop_interval(self): return self._loop_interval
    @loop_interval.setter
    def loop_interval(self, val):
        with self._lock: self._loop_interval = val; self._config.loop_interval = val

    @property
    def use_sleep_cmd(self): return self._use_sleep_cmd
    @use_sleep_cmd.setter
    def use_sleep_cmd(self, val):
        with self._lock: self._use_sleep_cmd = val; self._config.use_sleep_cmd = val

    def set_location(self, name, lat, lon):
        with self._lock:
            self._city_name = name
            self._lat = lat
            self._lon = lon
            self._auto_geo = False
            self._config.city_name = name
            self._config.lat = lat
            self._config.lon = lon
            self._config.auto_geo = False
            self._config.save()

    @property
    def location(self):
        with self._lock:
            return self._city_name, self._lat, self._lon, self._auto_geo

    @property
    def language(self): return self._language
    @language.setter
    def language(self, val):
        with self._lock:
            if val != self._language:
                self._language = val
                self._config.language = val
                load_language(val)
                self.mode_changed.set()

    @property
    def nameday_source(self): return self._nameday_source
    @nameday_source.setter
    def nameday_source(self, val):
        with self._lock: self._nameday_source = val; self._config.nameday_source = val

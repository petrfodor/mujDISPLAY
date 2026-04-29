# tray_icon.py
"""Systray ikona a menu - Full Restoration."""

import time
import threading
import webbrowser
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import serial.tools.list_ports
from tkinter import simpledialog, Tk, messagebox

from app_state import AppState
from display_driver import DisplayDriver
from config_manager import ConfigManager
import i18n

class TrayIcon:
    def __init__(self, state: AppState, driver: DisplayDriver, config: ConfigManager):
        self.state = state
        self.driver = driver
        self.config = config

    def _create_icon_image(self):
        try:
            return Image.open("logo.png")
        except:
            img = Image.new('RGB', (64, 64), (30, 30, 30))
            d = ImageDraw.Draw(img)
            d.ellipse((5, 5, 59, 59), fill=(0, 120, 215))
            d.text((15, 18), "mD", fill=(255, 255, 255))
            return img

    def _build_menu(self, icon=None):
        def refresh():
            if icon: icon.update_menu()

        # Pomocné akce
        def set_port(p):
            self.driver.last_menu_change = time.time()
            self.state.port = p
            self.driver.disconnect()
            self.driver.cache.clear()
            refresh()

        def set_baud(b, auto):
            self.driver.last_menu_change = time.time()
            self.state.auto_baud = auto
            if not auto: self.state.baud_rate = b
            self.driver.disconnect()
            self.driver.cache.clear()
            refresh()

        def ask_location():
            root = Tk(); root.withdraw(); root.attributes("-topmost", True)
            inp = simpledialog.askstring(i18n._("location_custom"), i18n._("location_custom"))
            root.destroy()
            if inp:
                try:
                    parts = [p.strip() for p in inp.split(',')]
                    if len(parts) == 3:
                        self.state.set_location(parts[0], float(parts[1]), float(parts[2]))
                        if hasattr(self.state, 'auto_geo'): self.state.auto_geo = False
                        refresh()
                except: pass

        def ask_custom_lock_time():
            root = Tk(); root.withdraw(); root.attributes("-topmost", True)
            val = simpledialog.askinteger(i18n._("meteo_lock_custom"), i18n._("meteo_lock_custom_desc"), 
                                          initialvalue=self.state.lock_meteo_time, minvalue=1, maxvalue=3600)
            root.destroy()
            if val:
                self.state.lock_meteo_time = val
                refresh()

        def ask_custom_loop_time():
            root = Tk(); root.withdraw(); root.attributes("-topmost", True)
            val = simpledialog.askinteger(i18n._("loop_custom"), i18n._("loop_custom_desc"), 
                                          initialvalue=self.state.loop_interval, minvalue=1, maxvalue=3600)
            root.destroy()
            if val:
                self.state.loop_interval = val
                refresh()

        # --- Podmenu pro Porty a Baudy ---
        ports = [p.device for p in serial.tools.list_ports.comports()]
        port_menu = [MenuItem(p, (lambda pv: lambda i, it: set_port(pv))(p),
                             checked=(lambda pv: lambda it: self.state.port == pv)(p)) for p in ports]
        port_menu.append(Menu.SEPARATOR)
        port_menu.append(MenuItem("Auto", lambda i, it: set_port("Auto"), checked=lambda it: self.state.port == "Auto"))

        bauds = [9600, 19200, 38400, 57600, 115200, 230400, 921600]
        baud_menu = [MenuItem("Auto-Baud", lambda i, it: set_baud(9600, True), checked=lambda it: self.state.auto_baud)]
        for b in bauds:
            baud_menu.append(MenuItem(str(b), (lambda bv: lambda i, it: set_baud(bv, False))(b),
                                      checked=(lambda bv: lambda it: not self.state.auto_baud and self.state.baud_rate == bv)(b)))

        # --- Podmenu pro Smyčky (VRÁCENO KOMPLETNÍ) ---
        loop_interval_menu = [
            MenuItem("30s", lambda i, it: [setattr(self.state, 'loop_interval', 30), refresh()], checked=lambda it: self.state.loop_interval == 30),
            MenuItem("1 min", lambda i, it: [setattr(self.state, 'loop_interval', 60), refresh()], checked=lambda it: self.state.loop_interval == 60),
            MenuItem("2 min", lambda i, it: [setattr(self.state, 'loop_interval', 120), refresh()], checked=lambda it: self.state.loop_interval == 120),
            MenuItem("5 min", lambda i, it: [setattr(self.state, 'loop_interval', 300), refresh()], checked=lambda it: self.state.loop_interval == 300),
            Menu.SEPARATOR,
            MenuItem(lambda item: f"{i18n._('loop_custom')} ({self.state.loop_interval}s)", lambda i, it: ask_custom_loop_time(), 
                     checked=lambda it: self.state.loop_interval not in [30, 60, 120, 300])
        ]

        lock_meteo_menu = [
            MenuItem("30s", lambda i, it: [setattr(self.state, 'lock_meteo_time', 30), refresh()], checked=lambda it: self.state.lock_meteo_time == 30),
            MenuItem("1 min", lambda i, it: [setattr(self.state, 'lock_meteo_time', 60), refresh()], checked=lambda it: self.state.lock_meteo_time == 60),
            MenuItem("2 min", lambda i, it: [setattr(self.state, 'lock_meteo_time', 120), refresh()], checked=lambda it: self.state.lock_meteo_time == 120),
            MenuItem("5 min", lambda i, it: [setattr(self.state, 'lock_meteo_time', 300), refresh()], checked=lambda it: self.state.lock_meteo_time == 300),
            Menu.SEPARATOR,
            MenuItem(lambda item: f"{i18n._('meteo_lock_custom')} ({self.state.lock_meteo_time}s)", lambda i, it: ask_custom_lock_time(),
                     checked=lambda it: self.state.lock_meteo_time not in [30, 60, 120, 300])
        ]

        # --- HLAVNÍ STRUKTURA ---
        return Menu(
            MenuItem(lambda item: f"🖥️ {i18n._('app_name')} {self.state.version if hasattr(self.state, 'version') else i18n._('version')}", lambda i, it: None, enabled=False, default=True),
            MenuItem(f"🌐 GitHub", lambda i, it: webbrowser.open("https://github.com/petrfodor/mujDISPLAY")),
            MenuItem(i18n._("copyright"), lambda i, it: None, enabled=False),
            Menu.SEPARATOR,
            
            MenuItem(i18n._("menu_screen"), Menu(
                MenuItem(i18n._("menu_turn_on"), lambda i, it: [setattr(self.state, 'force_off', False), refresh()], checked=lambda it: not self.state.force_off),
                MenuItem(i18n._("menu_turn_off"), lambda i, it: [setattr(self.state, 'force_off', True), refresh()], checked=lambda it: self.state.force_off),
            )),
            
            MenuItem(i18n._("menu_mode"), Menu(
                MenuItem(i18n._("mode_pc"), lambda i, it: [setattr(self.state, 'display_mode', "PC"), refresh()], checked=lambda it: self.state.display_mode == "PC"),
                MenuItem(i18n._("mode_meteo"), lambda i, it: [setattr(self.state, 'display_mode', "Meteo"), refresh()], checked=lambda it: self.state.display_mode == "Meteo"),
                MenuItem(i18n._("mode_media"), lambda i, it: [setattr(self.state, 'display_mode', "Media"), refresh()], checked=lambda it: self.state.display_mode == "Media"),
                MenuItem(i18n._("mode_graph"), lambda i, it: [setattr(self.state, 'display_mode', "Graph"), refresh()], checked=lambda it: self.state.display_mode == "Graph"),
                MenuItem(i18n._("mode_loop"), lambda i, it: [setattr(self.state, 'display_mode', "Loop"), refresh()], checked=lambda it: self.state.display_mode == "Loop"),
            )),

            MenuItem(i18n._("menu_brightness"), Menu(
                *[MenuItem(f"{v}%", (lambda val: lambda i, it: [setattr(self.state, 'brightness', val), self.driver.set_dim(val), refresh()])(v),
                           checked=(lambda val: lambda it: self.state.brightness == val)(v)) for v in [100, 80, 50, 20, 10]]
            )),
            
            MenuItem(i18n._("menu_intervals"), Menu(
                MenuItem(lambda item: f"{i18n._('loop')[:6]} ({self.state.loop_interval}s)", Menu(*loop_interval_menu)),
                MenuItem(lambda item: f"{i18n._('meteo_lock')[:8]} ({self.state.lock_meteo_time}s)", Menu(*lock_meteo_menu)),
            )),
            
            MenuItem(i18n._("menu_location"), Menu(
                MenuItem(i18n._("location_auto"), lambda i, it: [setattr(self.state, 'auto_geo', True), refresh()] if hasattr(self.state, 'auto_geo') else [setattr(self.state, 'location', self.state.location[:3] + (True,)), refresh()], 
                         checked=lambda it: getattr(self.state, 'auto_geo', self.state.location[3] if hasattr(self.state, 'location') else False)),
                MenuItem(i18n._("location_custom"), lambda i, it: ask_location()),
                MenuItem(lambda item: i18n._("location_current", city=self.state.location[0] if hasattr(self.state, 'location') else "---"), lambda i, it: None, enabled=False),
            )),
            
            MenuItem(i18n._("menu_nameday"), lambda i, it: [setattr(self.state, 'show_nameday', not self.state.show_nameday), refresh()], checked=lambda it: self.state.show_nameday),
            
            MenuItem(i18n._("menu_email_client"), Menu(
                MenuItem("Outlook", lambda i, it: [setattr(self.config, 'email_client', 'Outlook'), refresh()], checked=lambda it: self.config.email_client == 'Outlook'),
                MenuItem("Thunderbird", lambda i, it: [setattr(self.config, 'email_client', 'Thunderbird'), refresh()], checked=lambda it: self.config.email_client == 'Thunderbird'),
                MenuItem(i18n._("email_off"), lambda i, it: [setattr(self.config, 'email_client', 'None'), refresh()], checked=lambda it: self.config.email_client == 'None'),
            )),
            
            MenuItem(i18n._("menu_lock_settings"), Menu(
                MenuItem(i18n._("lock_show_meteo"), lambda i, it: [setattr(self.state, 'lock_show_meteo', not self.state.lock_show_meteo), refresh()], checked=lambda it: self.state.lock_show_meteo),
                MenuItem(i18n._("lock_dim0"), lambda i, it: [setattr(self.state, 'use_sleep_cmd', not self.state.use_sleep_cmd), refresh()], checked=lambda it: self.state.use_sleep_cmd),
            )),
            
            Menu.SEPARATOR,
            MenuItem(i18n._("menu_communication"), Menu(
                MenuItem(lambda item: f"{i18n._('menu_port')} ({self.driver.ser.port if self.driver.is_connected() and self.driver.ser else self.state.port}{' [Auto]' if self.state.port == 'Auto' and not self.driver.is_connected() else ''})", Menu(*port_menu)),
                MenuItem(lambda item: f"{i18n._('menu_baudrate')} ({self.driver.ser.baudrate if self.driver.is_connected() and self.driver.ser else self.state.baud_rate} bps{' [Auto]' if self.state.auto_baud else ''})", Menu(*baud_menu)),
            )),
            
            MenuItem(i18n._("menu_language"), Menu(
                *[MenuItem(lang, (lambda l: lambda i, it: [setattr(self.state, 'language', l), refresh()])(lang), checked=(lambda l: lambda it: self.state.language == l)(lang)) for lang in i18n.LANGUAGES]
            )),
            
            Menu.SEPARATOR,
            MenuItem(i18n._("menu_experimental"), Menu(
                MenuItem(i18n._("debug_toggle"), lambda i, it: [setattr(self.state, 'debug_enabled', not self.state.debug_enabled), refresh()], checked=lambda it: self.state.debug_enabled),
                MenuItem(i18n._("upload_fw"), lambda i, it: self.driver.select_and_upload()),
                MenuItem(i18n._("terminal"), lambda i, it: self.driver.open_terminal()),
                MenuItem(i18n._("reset_net_max"), lambda i, it: [setattr(self.driver, 'max_dn', 1048576), setattr(self.driver, 'max_up', 1048576), refresh()]),
            )),
            
            Menu.SEPARATOR,
            MenuItem(i18n._("menu_system"), Menu(
                MenuItem(i18n._("check_updates"), lambda i, it: None),
                MenuItem(i18n._("auto_hmi_update"), action=lambda i, it: [setattr(self.state, 'auto_hmi_update', not self.state.auto_hmi_update), refresh()], checked=lambda it: self.state.auto_hmi_update),
                MenuItem(i18n._("autostart"), lambda i, it: None, checked=lambda it: False),
            )),
            
            Menu.SEPARATOR,
            MenuItem(i18n._("menu_exit"), lambda i, it: [self.state.shutdown(), i.stop()])
        )

    def run(self):
        icon = Icon("mujDISPLAY", self._create_icon_image(), i18n._("app_name"))
        icon.menu = self._build_menu(icon)
        icon.run()

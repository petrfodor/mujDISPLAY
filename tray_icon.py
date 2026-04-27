# tray_icon.py
"""Systray ikona a menu."""

import time
import threading
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import serial.tools.list_ports
from tkinter import simpledialog, Tk

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
        img = Image.new('RGB', (64, 64), (30, 30, 30))
        d = ImageDraw.Draw(img)
        d.ellipse((5, 5, 59, 59), fill=(0, 120, 215))
        d.text((15, 18), "mD", fill=(255, 255, 255))
        return img

    def _build_menu(self, icon=None):
        # Pomocné akce – vnitřní funkce (lze volat z lambd)
        def set_port(p):
            self.driver.last_menu_change = time.time()
            self.state.port = p
            self.driver.disconnect()
            self.driver.cache.clear()

        def set_baud(b, auto):
            self.driver.last_menu_change = time.time()
            if auto:
                self.state.auto_baud = True
            else:
                self.state.auto_baud = False
                self.state.baud_rate = b
            self.driver.disconnect()
            self.driver.cache.clear()

        def set_mode(m):
            self.state.display_mode = m
            self.driver.cache.clear()

        def set_brightness(v):
            self.state.brightness = v
            self.driver.set_dim(v)

        def ask_location():
            root = Tk(); root.withdraw(); root.attributes("-topmost", True)
            inp = simpledialog.askstring(i18n._("location_custom"), i18n._("location_custom"))
            root.destroy()
            if inp:
                parts = [p.strip() for p in inp.split(',')]
                if len(parts) == 3:
                    self.state.set_location(parts[0], float(parts[1]), float(parts[2]))

        def toggle_nameday():
            self.state.show_nameday = not self.state.show_nameday

        def toggle_debug():
            self.state.debug_enabled = not self.state.debug_enabled

        def set_language(lang):
            self.state.language = lang
            if icon:
                icon.menu = self._build_menu(icon)
                icon.update_menu()

        # ----- Port menu -----
        ports = [p.device for p in serial.tools.list_ports.comports()]
        port_menu = []
        for p in ports:
            port_menu.append(
                MenuItem(
                    p,
                    action=(lambda port: lambda icon, item: set_port(port))(p),
                    checked=lambda item, port=p: self.state.port == port
                )
            )
        port_menu.append(Menu.SEPARATOR)
        port_menu.append(
            MenuItem(
                "Auto",
                lambda icon, item: set_port("Auto"),
                checked=lambda item: self.state.port == "Auto"
            )
        )

        # Baud menu
        bauds = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 250000, 256000, 512000, 921600]
        baud_menu = [
            MenuItem(
                "Auto-Baud",
                lambda icon, item: set_baud(9600, True),
                checked=lambda item: self.state.auto_baud
            )
        ]
        for b in bauds:
            baud_menu.append(
                MenuItem(
                    str(b),
                    action=(lambda baud: lambda icon, item: set_baud(baud, False))(b),
                    checked=lambda item, baud=b: not self.state.auto_baud and self.state.baud_rate == baud
                )
            )

        # Režim
        mode_menu = [
            MenuItem(i18n._("mode_pc"), action=lambda icon, item: set_mode("PC"),
                     checked=lambda item: self.state.display_mode == "PC"),
            MenuItem(i18n._("mode_meteo"), action=lambda icon, item: set_mode("Meteo"),
                     checked=lambda item: self.state.display_mode == "Meteo"),
            MenuItem(i18n._("mode_media"), action=lambda icon, item: set_mode("Media"),
                     checked=lambda item: self.state.display_mode == "Media"),
            MenuItem(i18n._("mode_graph"), action=lambda icon, item: set_mode("Graph"),
                     checked=lambda item: self.state.display_mode == "Graph"),
            MenuItem(i18n._("mode_loop"), action=lambda icon, item: set_mode("Loop"),
                     checked=lambda item: self.state.display_mode == "Loop"),
        ]

        # Jas
        bright_menu = [
            MenuItem(i18n._("brightness_100"), action=lambda icon, item: set_brightness(100),
                     checked=lambda item: self.state.brightness == 100),
            MenuItem(i18n._("brightness_80"), action=lambda icon, item: set_brightness(80),
                     checked=lambda item: self.state.brightness == 80),
            MenuItem(i18n._("brightness_50"), action=lambda icon, item: set_brightness(50),
                     checked=lambda item: self.state.brightness == 50),
            MenuItem(i18n._("brightness_20"), action=lambda icon, item: set_brightness(20),
                     checked=lambda item: self.state.brightness == 20),
            MenuItem(i18n._("brightness_10"), action=lambda icon, item: set_brightness(10),
                     checked=lambda item: self.state.brightness == 10),
        ]

        # Intervaly
        loop_menu = [
            MenuItem(i18n._("loop_1min"), action=lambda icon, item: setattr(self.state, 'loop_interval', 60),
                     checked=lambda item: self.state.loop_interval == 60),
            MenuItem(i18n._("loop_5min"), action=lambda icon, item: setattr(self.state, 'loop_interval', 300),
                     checked=lambda item: self.state.loop_interval == 300),
        ]
        lock_meteo_menu = [
            MenuItem(i18n._("meteo_lock_30s"), action=lambda icon, item: setattr(self.state, 'lock_meteo_time', 30),
                     checked=lambda item: self.state.lock_meteo_time == 30),
            MenuItem(i18n._("meteo_lock_2min"), action=lambda icon, item: setattr(self.state, 'lock_meteo_time', 120),
                     checked=lambda item: self.state.lock_meteo_time == 120),
        ]

        # E-mail klient
        email_menu = [
            MenuItem(i18n._("email_outlook"), action=lambda icon, item: setattr(self.config, 'email_client', 'Outlook'),
                     checked=lambda item: self.config.email_client == 'Outlook'),
            MenuItem(i18n._("email_thunderbird"), action=lambda icon, item: setattr(self.config, 'email_client', 'Thunderbird'),
                     checked=lambda item: self.config.email_client == 'Thunderbird'),
            MenuItem(i18n._("email_off"), action=lambda icon, item: setattr(self.config, 'email_client', 'None'),
                     checked=lambda item: self.config.email_client == 'None'),
        ]

        # Jazyk – použijeme tovární lambdu pro zachycení jazyka
        lang_menu = []
        for lang in i18n.LANGUAGES:
            lang_menu.append(
                MenuItem(
                    lang,
                    action=(lambda l: lambda icon, item: set_language(l))(lang),
                    checked=lambda item, l=lang: self.state.language == l
                )
            )

        return Menu(
            MenuItem(f"{i18n._('app_name')} {i18n._('version')}", None, enabled=False),
            MenuItem(i18n._("copyright"), None, enabled=False),
            Menu.SEPARATOR,
            MenuItem(i18n._("menu_screen"), Menu(
                MenuItem(i18n._("menu_turn_on"), lambda icon, item: setattr(self.state, 'force_off', False),
                         checked=lambda item: not self.state.force_off),
                MenuItem(i18n._("menu_turn_off"), lambda icon, item: setattr(self.state, 'force_off', True),
                         checked=lambda item: self.state.force_off),
            )),
            MenuItem(i18n._("menu_mode"), Menu(*mode_menu)),
            MenuItem(i18n._("menu_brightness"), Menu(*bright_menu)),
            MenuItem(i18n._("menu_intervals"), Menu(
                MenuItem(i18n._("loop_1min")[:6], Menu(*loop_menu)),
                Menu.SEPARATOR,
                MenuItem(i18n._("meteo_lock_30s")[:8], Menu(*lock_meteo_menu)),
            )),
            MenuItem(i18n._("menu_location"), Menu(
                MenuItem(i18n._("location_auto"), lambda icon, item: setattr(self.state, 'auto_geo', True),
                         checked=lambda item: self.state.location[3]),
                MenuItem(i18n._("location_custom"), lambda icon, item: ask_location()),
                MenuItem(i18n._("location_current", city=self.state.location[0]), None, enabled=False),
            )),
            MenuItem(i18n._("menu_nameday"), lambda icon, item: toggle_nameday(),
                     checked=lambda item: self.state.show_nameday),
            MenuItem(i18n._("menu_email_client"), Menu(*email_menu)),
            MenuItem(i18n._("menu_lock_settings"), Menu(
                MenuItem(i18n._("lock_show_meteo"), lambda icon, item: setattr(self.state, 'lock_show_meteo', not self.state.lock_show_meteo),
                         checked=lambda item: self.state.lock_show_meteo),
                MenuItem(i18n._("lock_dim0"), lambda icon, item: setattr(self.state, 'use_sleep_cmd', not self.state.use_sleep_cmd),
                         checked=lambda item: self.state.use_sleep_cmd),
            )),
            Menu.SEPARATOR,
            MenuItem(i18n._("menu_communication"), Menu(
                MenuItem(i18n._("menu_port"), Menu(*port_menu)),
                MenuItem(i18n._("menu_baudrate"), Menu(*baud_menu)),
            )),
            Menu.SEPARATOR,
            MenuItem(i18n._("menu_language"), Menu(*lang_menu)),
            Menu.SEPARATOR,
            MenuItem(i18n._("menu_experimental"), Menu(
                MenuItem(i18n._("debug_toggle"), lambda icon, item: toggle_debug(),
                         checked=lambda item: self.state.debug_enabled),
                MenuItem(i18n._("upload_fw"), lambda icon, item: self.driver.select_and_upload()),
                MenuItem(i18n._("terminal"), lambda icon, item: self.driver.open_terminal()),
                MenuItem(i18n._("reset_net_max"), lambda icon, item: setattr(self.driver, 'max_dn', 1024*1024) or setattr(self.driver, 'max_up', 1024*1024)),
            )),
            Menu.SEPARATOR,
            MenuItem(i18n._("menu_system"), Menu(
                MenuItem(i18n._("check_updates"), lambda icon, item: None),
                MenuItem(i18n._("auto_hmi_update"), lambda icon, item: setattr(self.state, 'auto_hmi_update', not self.state.auto_hmi_update),
                         checked=lambda item: self.state.auto_hmi_update),
                MenuItem(i18n._("autostart"), lambda icon, item: None, checked=lambda item: False),
            )),
            Menu.SEPARATOR,
            MenuItem(i18n._("menu_exit"), lambda icon, item: self._shutdown(icon))
        )

    def _shutdown(self, icon):
        self.state.shutdown()
        icon.stop()

    def run(self):
        icon = Icon("mujDISPLAY", self._create_icon_image(), i18n._("app_name"))
        icon.menu = self._build_menu(icon)
        icon.run()

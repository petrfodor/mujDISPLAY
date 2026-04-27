# display_driver.py (finální – s integrovaným media workerem)
"""Ovladač pro Nextion displej."""

import time
import datetime
import threading
import logging
import os
import serial
import serial.tools.list_ports
from typing import Optional, Dict, Any
import i18n
import psutil
import asyncio
import unicodedata

from app_state import AppState
from system_monitor import SystemMonitor, is_pc_locked
from weather_provider import WeatherProvider
import warnings
warnings.filterwarnings("ignore", message=".*async handler deleted by the wrong thread.*")

logger = logging.getLogger(__name__)

# ----- Asynchronní media info (zkopírováno z původního kódu) -----
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager

def remove_diacritics(text):
    return "".join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn')

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
            diff = (datetime.datetime.now(datetime.timezone.utc) - timeline.last_updated_time).total_seconds()
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
            "status_pic": status_pic
        }
    except Exception as e:
        logger.error(f"Media Info Error: {e}")
        return {"text": "Chyba Media API", "progress": 0, "time_str": "--:-- / --:--", "remaining": "--:--", "status_pic": 19}

class DisplayDriver:
    GREEN  = 2016
    YELLOW = 65504
    ORANGE = 64495
    RED    = 63488
    BLUE   = 31
    WHITE  = 65535
    MODES = ["PC", "Meteo", "Media", "Graph", "Loop"]

    def __init__(self, app_state: AppState):
        self.state = app_state
        self.ser: Optional[serial.Serial] = None
        self.lock = threading.Lock()
        self.cache: Dict[str, Any] = {}
        self.last_menu_change = time.time() - 10.0
        self.max_dn = 1024 * 1024
        self.max_up = 1024 * 1024
        self._last_graph_update = 0.0
        self._last_dn_str = "0B/s"
        self._last_up_str = "0B/s"
        self.shared_media_info = None   # sem bude ukládat media worker

    # ----- Správa portu (převzato) -----
    def _find_nextion_port(self) -> Optional[str]:
        for port in serial.tools.list_ports.comports():
            if any(x in port.description for x in ["USB", "CH340", "CP2102", "FTDI", "UART", "Serial"]):
                return port.device
        return None

    def _test_connection(self, port: str, baud: int) -> Optional[serial.Serial]:
        try:
            tmp = serial.Serial(port, baud, timeout=0.5, write_timeout=0.5)
            tmp.dtr = False
            tmp.rts = False
            time.sleep(0.2)
            tmp.reset_input_buffer()
            tmp.write(b'\xff\xff\xffconnect\xff\xff\xff')
            time.sleep(0.5)
            if tmp.in_waiting:
                resp = tmp.read(tmp.in_waiting)
                logger.info(f"Odpověď na connect: {resp}")
                return tmp
            tmp.close()
        except Exception as e:
            logger.debug(f"Pokus {port}@{baud} selhal: {e}")
        return None

    def connect(self) -> bool:
        port = self.state.port if self.state.port != "Auto" else self._find_nextion_port()
        logger.debug(f"Pokus o připojení k portu: {port}")
        if not port:
            logger.warning("Nebyl nalezen žádný vhodný COM port.")
            return False
        
        baud_rates = [self.state.baud_rate] if not self.state.auto_baud else \
        [9600, 19200, 38400, 115200, 921600]
        
        for b in baud_rates:
            logger.debug(f"Testování baudrate: {b}")
            ser_conn = self._test_connection(port, b)
            if ser_conn:
               logger.info(f"ÚSPĚCH: Připojeno na {port} @ {b} bps")
               ser_conn.timeout = 0.1
               ser_conn.write_timeout = 0.5
               self.ser = ser_conn
               self.state.baud_rate = b
               self.cache.clear()
               return True  
        logger.error("Selhaly všechny pokusy o připojení k displeji.")
        return False

    def disconnect(self):
        with self.lock:
            if self.ser and self.ser.is_open:
                try: self.ser.close()
                except: pass
            self.ser = None

    def is_connected(self) -> bool:
        with self.lock:
            return self.ser is not None and self.ser.is_open

    def send_command(self, cmd: str):
        if self.state.display_mode == "Uploading":
            return
        if not self.is_connected(): 
            return
        try:
            full_cmd = cmd.encode('ascii') + b'\xff\xff\xff'
            self.ser.write(full_cmd)
            self.ser.flush()  
            if self.state.debug_enabled:
                logger.debug(f"TX -> {cmd}")
        except Exception as e:
            logger.exception(f"Chyba při odesílání příkazu '{cmd}': {e}")
            self.disconnect()

    def update_val(self, obj: str, val, is_text=True, force=False):
        new_val = str(val)
        if is_text:
            new_val = remove_diacritics(new_val)
        
        cache_key = f"{obj}:{'txt' if is_text else 'val'}"
        cached = self.cache.get(cache_key)
        
        # POKROČILÝ DEBUG: Výpis hodnoty před odesláním
        if self.state.debug_enabled:
            logger.debug(f"Příprava dat: {obj} -> '{new_val}' (Původní v cache: '{cached}')")

        if cached != new_val or force:
            if is_text:
                cmd = f'{obj}.txt="{new_val}"'
            else:
                cmd = f'{obj}.val={new_val}'
            
            self.send_command(cmd)
            self.cache[cache_key] = new_val
        elif self.state.debug_enabled:
            # logger.debug(f"Data pro {obj} se nezměnila, přeskakuji odesílání.")
            pass

    def set_dim(self, percent: int):
        self.send_command(f"dim={percent}")

    def set_page(self, page_id: int):
        logger.debug("Změna stránky")
        self.send_command(f"page page{page_id}")
        logger.debug("Změna stránky dokončena")

    def _bar_color(self, value: int, warn: int, crit: int) -> int:
        if value >= crit: return self.RED
        if value >= warn: return self.YELLOW
        return self.GREEN

    # ----- Media worker (běží v samostatném vlákně) -----
    def _media_worker(self):
        async def update():
            while self.state.running:
                if self.state.display_mode in ("Media", "Loop") or self._target_page == 4:
                    try:
                        info = await get_extended_media_info()
                        self.shared_media_info = info
                    except:
                        pass
                await asyncio.sleep(1)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(update())

    # ----- Hlavní smyčka -----
    def main_loop(self, system: SystemMonitor, weather: WeatherProvider, media=None):
        logger.info("Hlavní smyčka spuštěna.")
        # Spustíme media worker
        threading.Thread(target=self.read_buttons_worker, daemon=True, name="TouchListener").start()
        threading.Thread(target=self._media_worker, daemon=True, name="MediaWorker").start()
        
        last_weather = 0.0
        last_net_time = time.time()
        last_net = system.get_net_io()
        last_slow = 0.0
        last_page = -1
        last_dim = -1
        locked_mode = False
        locked_start_time = 0.0
        meteo_active = False
        self._loop_page = 1
        self._loop_switch = 0.0
        self._target_page = 1   # pro media worker

        while self.state.running:
            try:
                if self.state.display_mode in ("Uploading", "Terminal"):
                    time.sleep(0.5)
                    continue

                if time.time() - self.last_menu_change < 1.5:
                    time.sleep(0.1)
                    continue
                if not self.is_connected():
                    self.connect()
                    if not self.is_connected():
                        time.sleep(5)
                        continue

                now = time.time()
                dt_now = datetime.datetime.now()

                if now - last_slow > 5:
                    weather.update_email_and_ip()
                    if now - last_weather > 900 or last_weather == 0:
                        weather.fetch_weather()
                        last_weather = now
                    last_slow = now

                locked = is_pc_locked()
                target_page, target_dim = 1, self.state.brightness

                if self.state.force_off:
                    target_dim = 0
                elif locked:
                    if not locked_mode:
                        locked_start_time = now
                        locked_mode = True
                        meteo_active = self.state.lock_show_meteo
                    if meteo_active and (now - locked_start_time > self.state.lock_meteo_time):
                        meteo_active = False
                    if meteo_active:
                        target_page, target_dim = 3, 50
                    else:
                        target_dim = 0 if self.state.use_sleep_cmd else 10
                        target_page = 2 if target_dim > 0 else 1
                else:
                    
                    locked_mode = False
                    mode = self.state.display_mode
                    if mode == "PC": target_page = 1
                    elif mode == "Meteo": target_page = 3
                    elif mode == "Media": target_page = 4
                    elif mode == "Graph": target_page = 5
                    elif mode == "Loop":
                        if now - self._loop_switch > self.state.loop_interval:
                            self._loop_page = 3 if self._loop_page == 1 else 1
                            self._loop_switch = now
                        target_page = self._loop_page
                self._target_page = target_page
                if target_page != last_page:
                    self.set_page(target_page)
                    last_page = target_page
                    self.cache.clear()
                if target_dim != last_dim:
                    self.set_dim(target_dim)
                    last_dim = target_dim
                    

                if target_dim > 0:
                    self._update_page(target_page, system, weather, dt_now, now,
                                      last_net, last_net_time)
                    if target_page == 1:
                        curr_net = system.get_net_io()
                        dt = now - last_net_time
                        if dt >= 0.5:
                            dn_bps = (curr_net.bytes_recv - last_net.bytes_recv) / dt
                            up_bps = (curr_net.bytes_sent - last_net.bytes_sent) / dt
                            if dn_bps > self.max_dn: self.max_dn = dn_bps
                            if up_bps > self.max_up: self.max_up = up_bps
                            dn_perc = int((dn_bps / self.max_dn) * 100) if self.max_dn else 0
                            up_perc = int((up_bps / self.max_up) * 100) if self.max_up else 0
                            self.update_val("j4", up_perc, False)
                            self.update_val("j5", dn_perc, False)
                            self.send_command(f'j4.pco={self._bar_color(up_perc, 70, 90)}')
                            self.send_command(f'j5.pco={self._bar_color(dn_perc, 70, 90)}')
                            self._last_dn_str = self._format_speed(dn_bps)
                            self._last_up_str = self._format_speed(up_bps)
                            last_net = curr_net
                            last_net_time = now
                time.sleep(0.1)
            except Exception as e:
                logger.exception(f"Chyba v hlavní smyčce: {e}")
                time.sleep(1)

    def _handle_touch(self, raw: str):
        import pyautogui
        
        # 1. Přepínání stránek (Plus/Minus)
        if "pageplus" in raw or "pageminus" in raw:
            current_mode = self.state.display_mode
            try:
                idx = self.MODES.index(current_mode)
            except ValueError:
                idx = 0
            
            if "pageplus" in raw:
                new_idx = (idx + 1) % len(self.MODES)
            else:
                new_idx = (idx - 1) % len(self.MODES)
            
            new_mode = self.MODES[new_idx]
            logger.info(f"Touch Switch: {current_mode} -> {new_mode}")
            self.state.display_mode = new_mode
            self.cache.clear() # Vynutit překreslení nové stránky
            return

        # 2. Media ovládání
        actions = {
            "play": "playpause", "stop": "stop", 
            "prev": "prevtrack", "next": "nexttrack", 
            "vup": "volumeup", "vdown": "volumedown"
        }
        for key, action in actions.items():
            if key in raw:
                logger.info(f"Touch Media: {action}")
                pyautogui.press(action)
                return

    def read_buttons_worker(self):
        logger.info("TouchListener spuštěn.")
        rx_buffer = ""
        while self.state.running:
            if self.state.display_mode == "Uploading":
                time.sleep(1); continue

            if not self.is_connected():
                time.sleep(0.5); continue

            try:
                if self.ser.in_waiting > 0:
                    with self.lock:
                        data = self.ser.read(self.ser.in_waiting)
                        rx_buffer += data.decode('ascii', errors='ignore')

                    if rx_buffer:
                        self._handle_touch(rx_buffer)
                        rx_buffer = "" 
            except:
                time.sleep(0.1)
            time.sleep(0.05)      

    @staticmethod
    def _format_speed(bytes_per_sec):
        for unit in ['B', 'KB', 'MB']:
            if bytes_per_sec < 1024: return f"{int(bytes_per_sec)}{unit}/s"
            bytes_per_sec /= 1024
        return f"{int(bytes_per_sec)}GB/s"

    # ----- Stránky -----
    def _update_page(self, page, system, weather, dt_now, now, last_net, last_net_time):
        # DEBUG: Logování vstupu do vykreslovací rutiny
        if self.state.debug_enabled:
            logger.debug(f"--- VYKRESLOVÁNÍ STRÁNKY {page} ---")
            
        if page == 1:
            cpu = system.cpu_percent()
            ram = system.ram_percent()
            disk = system.disk_percent()
            
            # Kontrola e-mailů pro debug
            if self.state.debug_enabled:
                logger.debug(f"Systémová data: CPU:{cpu}%, RAM:{ram}%, E-maily:{weather.unread_emails}")

            self.update_val("t1", dt_now.strftime("%H:%M:%S"))
            if (dt_now.second // 2) % 2 == 0:
                self.update_val("t0", dt_now.strftime("%d.%m.%Y"))
                self.update_val("t5", i18n._("cpu_label"))
                self.update_val("t6", i18n._("out_label"))
                self.update_val("t7", i18n._("ram_label"))
                self.update_val("t8", i18n._("disk_label"))
                self.update_val("t9", i18n._("down_label"))
                self.update_val("t10", i18n._("up_label"))
                if weather.unread_emails == 0:
                    self.update_val("t11", f"HW: {system.cpu_name()} | {system.disks_info()}")
            else:
                upt = now - psutil.boot_time()
                self.update_val("t0", f"U: {os.getlogin()}")
                if weather.unread_emails == 0:
                    self.update_val("t11", i18n._("uptime", h=int(upt//3600), m=int((upt%3600)//60)))
                self.update_val("t5", f"{cpu}%")
                self.update_val("t6", f"{weather.current_temp}*C")
                self.update_val("t7", f"{ram}%")
                self.update_val("t8", f"{disk}%")
                self.update_val("t9", self._last_dn_str)
                self.update_val("t10", self._last_up_str)

            self.update_val("j0", cpu, False); self.send_command(f'j0.pco={self._bar_color(cpu, 50, 80)}')
            self.update_val("j1", weather.current_temp, False); self.send_command(f'j1.pco={self._bar_color(weather.current_temp, 25, 35)}')
            self.update_val("j3", ram, False); self.send_command(f'j3.pco={self._bar_color(ram, 60, 90)}')
            self.update_val("j2", disk, False); self.send_command(f'j2.pco={self._bar_color(disk, 70, 90)}')

            idx = (dt_now.second // 4) % 4
            texts = [weather.weather_texts["curr"], weather.weather_texts["fore"],
                     weather.weather_texts["wind"], weather.weather_texts["det"]]
            self.update_val("t2", texts[idx])
            self.update_val("t3", weather.weather_texts.get("emails", ""))
            if weather.unread_emails > 0:
                self.update_val("t12", i18n._("email_new"))
                self.send_command("t12.pco=" + str(self.RED))
                self.update_val("t4", "")
                self.update_val("t11", "")
            else:
                self.update_val("t12", weather.weather_texts.get("ip", ""))
                self.send_command("t12.pco=" + str(self.WHITE))
                self.update_val("t4", weather.weather_texts.get("event", ""))

        elif page == 3:
            self.update_val("t0", dt_now.strftime("%d.%m.%Y"))
            self.update_val("t1", dt_now.strftime("%H:%M:%S"))
            if weather.meteo_raw:
                daily = weather.meteo_raw['daily']
                icons = ["p1","p2","p3","p4","p5","p6"]
                t_days = ["t3","t5","t6","t8","t10","t12"]
                t_maxs = ["t2","t4","t7","t9","t11","t13"]
                t_mins = ["t19","t18","t17","t16","t15","t14"]
                for i in range(6):
                    wmo = daily['weather_code'][i]
                    pic = weather.map_weather_to_id(wmo)
                    self.send_command(f"{icons[i]}.pic={pic}")
                    self.update_val(t_days[i], weather.get_day_name(daily['time'][i], i))
                    self.update_val(t_maxs[i], round(daily['temperature_2m_max'][i]))
                    self.update_val(t_mins[i], round(daily['temperature_2m_min'][i]))
            if self.state.show_nameday:
                self.update_val("t20", weather.get_name_day())
            else:
                self.update_val("t20", "")

        elif page == 4:
            self.update_val("t0", dt_now.strftime("%H:%M:%S"))
            m = self.shared_media_info
            if m:
                full_info = m.get("text", "")
                if " - " in full_info:
                    artist, title = full_info.split(" - ", 1)
                    self.update_val("t1", artist.strip()[:24])
                    self.update_val("t4", title.strip()[:45])
                else:
                    self.update_val("t1", full_info[:45])
                    self.update_val("t4", "")
                self.update_val("t2", m.get("time_str", ""))
                self.update_val("t3", m.get("remaining", ""))
                self.update_val("j0", m.get("progress", 0), False)
                if self.cache.get("p3_pic") != m["status_pic"]:
                    self.send_command(f"p3.pic={m['status_pic']}")
                    self.cache["p3_pic"] = m["status_pic"]
            else:
                self.update_val("t1", i18n._("media_nothing"))

        elif page == 5:
            self.update_val("t0", dt_now.strftime("%H:%M:%S"))
            if dt_now.second % 8 < 4:
                self.update_val("t1", i18n._("graph_title"))
            else:
                self.update_val("t1", i18n._("graph_cpu_ram", cpu=system.cpu_percent(), ram=system.ram_percent()))
            val0 = system.cpu_percent()
            val1 = system.ram_percent()
            if val0 > 90: col0 = self.RED
            elif val0 > 75: col0 = self.ORANGE
            elif val0 > 50: col0 = self.YELLOW
            else: col0 = self.GREEN
            if self.cache.get("s0_pco0") != col0:
                self.send_command(f"s0.pco0={col0}")
                self.cache["s0_pco0"] = col0
            if now - self._last_graph_update > 1:
                self.send_command(f"add 3,0,{int(val0 * 2.55)}")
                self.send_command(f"add 3,1,{int(val1 * 2.55)}")
                self._last_graph_update = now

    # ----- Nahrávání HMI a firmware (ponecháno) -----
    def upload_tft_file(self, file_path):

    
        time.sleep(1.0)
        if not os.path.exists(file_path):
            logger.error("Soubor .tft nenalezen.")
            return
        port = self.state.port if self.state.port != "Auto" else self._find_nextion_port()
        if not port:
            logger.error("Nenalezen port.")
            return
        old_mode = self.state.display_mode      
        self.state.display_mode = "Uploading"
        self.disconnect()
        with self.lock:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.ser = None 
        time.sleep(1)
        try:
            file_size = os.path.getsize(file_path)
            ser = serial.Serial(port, self.state.baud_rate, timeout=0.5, write_timeout=0.5)
            ser.write(b'\x00\xff\xff\xff')
            time.sleep(0.1)
            ser.write(b"connect\xff\xff\xff")
            time.sleep(0.3)
            ser.read_all()
            cmd_str = f"whmi-wri {file_size},{921600},0"
            ser.write(cmd_str.encode('ascii') + b'\xff\xff\xff')
            time.sleep(0.5)
            resp = ser.read(ser.in_waiting or 1)
            if b'\x05' not in resp:
                logger.info("Displej nepotvrdil 0x05, zkouším nahrávat - kontrolujte display.")
            ser.close()
            time.sleep(0.5)
            ser = serial.Serial(port, 921600, timeout=1.0, write_timeout=None)
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk: break
                    ser.write(chunk)
                    time.sleep(0.02)
                    start_wait = time.time()
                    while ser.in_waiting == 0 and self.state.running:
                        if time.time() - start_wait > 3.0:
                            raise Exception("Displej přestal potvrzovat data.")
                        time.sleep(0.001)
                    ser.read(ser.in_waiting)
            logger.info("Nahrávání dokončeno.")
        except Exception as e:
            logger.exception(f"Chyba nahrávání: {e}")
        finally:
            if 'ser' in locals() and ser.is_open:
                ser.close()
            self.state.display_mode = old_mode
            self.cache.clear()

    def select_and_upload(self):
        import tkinter as tk
        from tkinter import filedialog
        def _run_dialog():
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            file_path = filedialog.askopenfilename(filetypes=[("TFT soubory", "*.tft")])
            root.destroy()
            if file_path:
                threading.Thread(target=self.upload_tft_file, args=(file_path,), daemon=True).start()
        threading.Timer(0.1, _run_dialog).start()

    def check_hmi_update(self):
        pass

    def open_terminal(self):
        def _run_terminal():
            old_mode = self.state.display_mode
            self.state.display_mode = "Terminal"
            self.disconnect()
            try:
                self.standalone_terminal_window()
            finally:
                self.state.display_mode = old_mode    
        threading.Timer(0.1, _run_terminal).start()

    def standalone_terminal_window(self):
        import tkinter as tk
        from tkinter import scrolledtext

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
            if root.winfo_exists():
                display_area.config(state='normal')
                display_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n", tag)
                display_area.config(state='disabled')
                display_area.see(tk.END)

        port = self.state.port if self.state.port != "Auto" else self._find_nextion_port()
        ser_term = None
        if port:
            try:
                ser_term = serial.Serial(port, self.state.baud_rate, timeout=0.1)
                log(f"Připojeno k {port} ({self.state.baud_rate} bps)", "RX")
            except Exception as e:
                log(f"Chyba portu: {e}", "ERR")
        else:
            log("Nebyl nalezen žádný dostupný port!", "ERR")

        def read_thread():
            while ser_term and ser_term.is_open:
                try:
                    if ser_term.in_waiting > 0:
                        data = ser_term.read(ser_term.in_waiting)
                        h = data.hex(' ').upper()
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
                    ser_term.write(cmd.encode('ascii') + b'\xff\xff\xff')
                    log(f"TX -> {cmd}", "TX")
                    entry.delete(0, tk.END)
                except Exception as e:
                    log(f"Chyba odesílání: {e}", "ERR")
        entry.bind("<Return>", send_action)
        tk.Button(input_frame, text="Odeslat", command=send_action, width=10).pack(side=tk.RIGHT)

        btn_frame = tk.Frame(root)
        btn_frame.pack(fill=tk.X, padx=10)
        cmds = [ ("Reset", "rest"), ("Connect", "connect"), ("ID Stránky", "sendme"),
                 ("Text: Ahoj", 't1.txt="ahoj"'), ("Jas 50%", "dim=50"), ("Jas 0%", "dim=0"),
                 ("Vyčistit (Modrá)", "cls BLUE"), ("Skrýt vše", "vis 255,0"),
                 ("Zobrazit vše", "vis 255,1"), ("Vypnout dotyk", "tsw 255,0"),
                 ("Spánek", "sleep=1"), ("Probudit", "sleep=0") ]
        for txt, c in cmds:
            tk.Button(btn_frame, text=txt, command=lambda cmd=c: entry.insert(0, cmd)).pack(side=tk.LEFT, padx=5)

        def on_close():
            if ser_term: ser_term.close()
            root.destroy()
        root.protocol("WM_DELETE_WINDOW", on_close)
        root.mainloop()

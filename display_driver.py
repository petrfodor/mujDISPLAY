# display_driver.py
"""Ovladač pro Nextion displej - Full Version with HMI Auto-Update and Terminal."""

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
import requests
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext

from app_state import AppState
from system_monitor import SystemMonitor, is_pc_locked
from weather_provider import WeatherProvider
import warnings
warnings.filterwarnings("ignore", message=".*async handler deleted by the wrong thread.*")

logger = logging.getLogger(__name__)

# ----- Asynchronní media info -----
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
            "text": title, "progress": progress, "time_str": f"{fmt_time(pos)} / {fmt_time(end)}",
            "remaining": f"-{fmt_time(rem)}", "status_pic": status_pic
        }
    except Exception as e:
        logger.error(f"Media Info Error: {e}")
        return {"text": "Chyba Media API", "progress": 0, "time_str": "--:-- / --:--", "remaining": "--:--", "status_pic": 19}

class DisplayDriver:
    GREEN, YELLOW, ORANGE, RED, BLUE, WHITE = 2016, 65504, 64495, 63488, 31, 65535
    MODES = ["PC", "Meteo", "Media", "Graph", "Loop"]
    BASE_URL = "https://www.controlsystems.cz/downloads/mujdisplay/"
    COMPATIBLE_HMI_VERSION = 1600 # Referenční verze pro Python kód

    def __init__(self, app_state: AppState):
        self.state = app_state
        self.ser: Optional[serial.Serial] = None
        self.lock = threading.Lock()
        self.cache: Dict[str, Any] = {}
        self.last_menu_change = time.time() - 10.0
        self.max_dn = self.max_up = 1024 * 1024
        self._last_graph_update = 0.0
        self._last_dn_str = self._last_up_str = "0B/s"
        self.shared_media_info = None
        self._target_page = 1

    def _find_nextion_port(self) -> Optional[str]:
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            if any(x in port.description for x in ["USB", "CH340", "CP2102", "FTDI", "UART", "Serial"]):
                return port.device
        return None

    def _test_connection(self, port: str, baud: int) -> Optional[serial.Serial]:
        try:
            tmp = serial.Serial(port, baud, timeout=0.5, write_timeout=0.5)
            tmp.dtr = tmp.rts = False
            time.sleep(0.2)
            tmp.reset_input_buffer()
            tmp.write(b'\xff\xff\xffconnect\xff\xff\xff')
            time.sleep(0.6)
            if tmp.in_waiting:
                resp = tmp.read(tmp.in_waiting).decode('ascii', errors='ignore').lower()
                if "comok" in resp or "ok" in resp:
                    logger.info(f"Validní displej na {port}@{baud}")
                    return tmp
            tmp.close()
        except: pass
        return None

    def connect(self) -> bool:
        port = self.state.port if self.state.port != "Auto" else self._find_nextion_port()
        if not port: return False
        baud_rates = [self.state.baud_rate]
        if self.state.auto_baud:
            baud_rates = [9600, 115200, 19200, 38400, 57600, 921600]
            if self.state.baud_rate in baud_rates:
                baud_rates.remove(self.state.baud_rate)
            baud_rates.insert(0, self.state.baud_rate)
        
        for b in baud_rates:
            ser_conn = self._test_connection(port, b)
            if ser_conn:
                ser_conn.timeout, ser_conn.write_timeout = 0.1, 0.5
                self.ser = ser_conn
                self.state.baud_rate = b
                self.cache.clear()
                # Start HMI check if enabled
                if self.state.auto_hmi_update:
                    threading.Thread(target=self.check_hmi_update, daemon=True, name="HMI_Check").start()
                return True
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
        if self.state.display_mode in ("Uploading", "Terminal") or not self.is_connected():
            return
        
        with self.lock:
            try:
                self.ser.write(cmd.encode('ascii') + b'\xff\xff\xff')
            except (serial.SerialException, PermissionError, OSError) as e:
                logger.error(f"Port error při zápisu ({e}). Vynucuji reconnect.")
                try:
                    self.ser.close()
                except:
                    pass
                self.ser = None  # Toto aktivuje reconnect v main_loop

    def update_val(self, obj: str, val, is_text=True, force=False):
        new_val = remove_diacritics(str(val)) if is_text else str(val)
        cache_key = f"{obj}:{'txt' if is_text else 'val'}"
        if self.cache.get(cache_key) != new_val or force:
            cmd = f'{obj}.txt="{new_val}"' if is_text else f'{obj}.val={new_val}'
            self.send_command(cmd)
            self.cache[cache_key] = new_val

    def set_dim(self, percent: int): self.send_command(f"dim={percent}")
    def set_page(self, page_id: int): self.send_command(f"page page{page_id}")
    def _bar_color(self, v, w, c): return self.RED if v >= c else (self.YELLOW if v >= w else self.GREEN)

    def _handle_touch(self, raw: str):
        import pyautogui
        if "pageplus" in raw or "pageminus" in raw:
            try:
                idx = self.MODES.index(self.state.display_mode)
                new_mode = self.MODES[(idx + 1) % len(self.MODES)] if "pageplus" in raw else self.MODES[(idx - 1) % len(self.MODES)]
                self.state.display_mode = new_mode
                self.cache.clear()
            except ValueError: pass
            return
        
        acts = {"play":"playpause","stop":"stop","prev":"prevtrack","next":"nexttrack","vup":"volumeup","vdown":"volumedown"}
        for k, a in acts.items():
            if k in raw: pyautogui.press(a); return

    def read_buttons_worker(self):
        logger.info("TouchListener spuštěn.")
        buffer = ""
        while self.state.running:
            if self.state.display_mode == "Uploading" or not self.is_connected():
                time.sleep(0.5); continue
            try:
                if self.ser.in_waiting > 0:
                    with self.lock:
                        data = self.ser.read(self.ser.in_waiting)
                        buffer += data.decode('ascii', errors='ignore')
                    if buffer: 
                        self._handle_touch(buffer)
                        buffer = ""
            except (serial.SerialException, PermissionError, OSError):
                logger.warning("Ztráta spojení v TouchListeneru.")
                self.ser = None # Necháme main_loop provést reconnect
            except Exception as e:
                logger.debug(f"Chyba čtení: {e}")
            
            time.sleep(0.05)

    def _media_worker(self):
        async def update():
            while self.state.running:
                if self.state.display_mode in ("Media", "Loop") or self._target_page == 4:
                    self.shared_media_info = await get_extended_media_info()
                await asyncio.sleep(1)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(update())

    def main_loop(self, system: SystemMonitor, weather: WeatherProvider, media=None):
        logger.info("Hlavní smyčka spuštěna.")
        threading.Thread(target=self.read_buttons_worker, daemon=True, name="TouchListener").start()
        threading.Thread(target=self._media_worker, daemon=True, name="MediaWorker").start()
        
        last_weather = last_slow = 0.0
        last_net_time = time.time()
        last_net = system.get_net_io()
        last_page = last_dim = -1
        self._loop_page = 1
        self._loop_switch = 0.0

        while self.state.running:
            try:
                if self.state.display_mode in ("Uploading", "Terminal"):
                    time.sleep(0.5); last_page = -1; continue
                
                if not self.is_connected():
                    logger.info("Pokouším se obnovit spojení s displejem...")
                    if self.connect():
                        logger.info("Spojení obnoveno.")
                        last_page = -1 # Vynutí překreslení aktuální stránky
                        self.cache.clear()
                    else:
                        time.sleep(2) # Počkáme 2 sekundy před dalším pokusem
                        continue

                now, dt_now = time.time(), datetime.datetime.now()
                
                # Periodická data
                if now - last_slow > 5:
                    weather.update_email_and_ip()
                    if now - last_weather > 900 or last_weather == 0:
                        weather.fetch_weather()
                        last_weather = now
                    last_slow = now

                locked = is_pc_locked()
                t_page, t_dim = 1, self.state.brightness
                
                if self.state.force_off:
                    t_dim = 0
                elif locked:
                    if self.state.lock_show_meteo: 
                        t_page, t_dim = 3, 50
                    else: 
                        t_dim = 0 if self.state.use_sleep_cmd else 10
                        t_page = 2 if t_dim > 0 else 1
                else:
                    m = self.state.display_mode
                    if m == "PC": t_page = 1
                    elif m == "Meteo": t_page = 3
                    elif m == "Media": t_page = 4
                    elif m == "Graph": t_page = 5
                    elif m == "Loop":
                        if now - self._loop_switch > self.state.loop_interval:
                            self._loop_page = 3 if self._loop_page == 1 else 1
                            self._loop_switch = now
                        t_page = self._loop_page

                self._target_page = t_page
                
                if t_page != last_page:
                    self.set_page(t_page)
                    last_page = t_page
                    self.cache.clear()
                
                if t_dim != last_dim:
                    self.set_dim(t_dim)
                    last_dim = t_dim

                if t_dim > 0:
                    self._update_page(t_page, system, weather, dt_now, now)
                    if t_page == 1:
                        curr_net = system.get_net_io()
                        dt = now - last_net_time
                        if dt >= 0.5:
                            dn_bps = (curr_net.bytes_recv - last_net.bytes_recv) / dt
                            up_bps = (curr_net.bytes_sent - last_net.bytes_sent) / dt
                            if dn_bps > self.max_dn: self.max_dn = dn_bps
                            if up_bps > self.max_up: self.max_up = up_bps
                            self.update_val("j4", int((up_bps/self.max_up)*100), False)
                            self.update_val("j5", int((dn_bps/self.max_dn)*100), False)
                            self._last_dn_str, self._last_up_str = self._format_speed(dn_bps), self._format_speed(up_bps)
                            last_net, last_net_time = curr_net, now
                
                time.sleep(0.1)
            except Exception as e:
                logger.exception(f"Loop Error: {e}")
                time.sleep(1)

    @staticmethod
    def _format_speed(bps):
        for unit in ['B','KB','MB']:
            if bps < 1024: return f"{int(bps)}{unit}/s"
            bps /= 1024
        return f"{int(bps)}GB/s"

    def _update_page(self, page, system, weather, dt_now, now):
        if page == 1:
            cpu, ram, disk = system.cpu_percent(), system.ram_percent(), system.disk_percent()
            self.update_val("t1", dt_now.strftime("%H:%M:%S"))
            if (dt_now.second // 2) % 2 == 0:
                self.update_val("t0", dt_now.strftime("%d.%m.%Y"))
                for i, k in enumerate(["cpu","out","ram","disk","down","up"]):
                    self.update_val(f"t{i+5}", i18n._(f"{k}_label"))
                if weather.unread_emails == 0:
                    self.update_val("t11", f"HW: {system.cpu_name()} | {system.disks_info()}")
            else:
                upt = now - psutil.boot_time()
                self.update_val("t0", f"U: {os.getlogin()}")
                if weather.unread_emails == 0:
                    self.update_val("t11", i18n._("uptime", h=int(upt//3600), m=int((upt%3600)//60)))
                for i, v in enumerate([f"{cpu}%", f"{weather.current_temp}*C", f"{ram}%", f"{disk}%", self._last_dn_str, self._last_up_str]):
                    self.update_val(f"t{i+5}", v)
            
            self.update_val("j0", cpu, False); self.send_command(f'j0.pco={self._bar_color(cpu, 50, 80)}')
            self.update_val("j1", weather.current_temp, False); self.send_command(f'j1.pco={self._bar_color(weather.current_temp, 25, 35)}')
            self.update_val("j3", ram, False); self.send_command(f'j3.pco={self._bar_color(ram, 60, 90)}')
            self.update_val("j2", disk, False); self.send_command(f'j2.pco={self._bar_color(disk, 70, 90)}')
            
            w_txts = [weather.weather_texts["curr"], weather.weather_texts["fore"], weather.weather_texts["wind"], weather.weather_texts["det"]]
            self.update_val("t2", w_txts[(dt_now.second // 4) % 4])
            self.update_val("t3", weather.weather_texts.get("emails", ""))
            
            if weather.unread_emails > 0:
                self.update_val("t12", i18n._("email_new")); self.send_command(f"t12.pco={self.RED}"); self.update_val("t4", ""); self.update_val("t11", "")
            else:
                self.update_val("t12", weather.weather_texts.get("ip", "")); self.send_command(f"t12.pco={self.WHITE}"); self.update_val("t4", weather.weather_texts.get("event", ""))

        elif page == 3:
            self.update_val("t0", dt_now.strftime("%d.%m.%Y")); self.update_val("t1", dt_now.strftime("%H:%M:%S"))
            if weather.meteo_raw:
                daily = weather.meteo_raw['daily']
                for i in range(6):
                    self.send_command(f"p{i+1}.pic={weather.map_weather_to_id(daily['weather_code'][i])}")
                    self.update_val(["t3","t5","t6","t8","t10","t12"][i], weather.get_day_name(daily['time'][i], i))
                    self.update_val(["t2","t4","t7","t9","t11","t13"][i], round(daily['temperature_2m_max'][i]))
                    self.update_val(["t19","t18","t17","t16","t15","t14"][i], round(daily['temperature_2m_min'][i]))
            self.update_val("t20", weather.get_name_day() if self.state.show_nameday else "")

        elif page == 4:
            self.update_val("t0", dt_now.strftime("%H:%M:%S"))
            m = self.shared_media_info
            if m:
                if " - " in m["text"]:
                    artist, title = m["text"].split(" - ", 1)
                    self.update_val("t1", artist.strip()[:24]); self.update_val("t4", title.strip()[:45])
                else: 
                    self.update_val("t1", m["text"][:45]); self.update_val("t4", "")
                self.update_val("t2", m["time_str"]); self.update_val("t3", m["remaining"]); self.update_val("j0", m["progress"], False)
                if self.cache.get("p3_pic") != m["status_pic"]:
                    self.send_command(f"p3.pic={m['status_pic']}")
                    self.cache["p3_pic"] = m["status_pic"]
            else: self.update_val("t1", i18n._("media_nothing"))

        elif page == 5:
            self.update_val("t0", dt_now.strftime("%H:%M:%S"))
            self.update_val("t1", i18n._("graph_title") if dt_now.second % 8 < 4 else i18n._("graph_cpu_ram", cpu=system.cpu_percent(), ram=system.ram_percent()))
            v0, v1 = system.cpu_percent(), system.ram_percent()
            col = self.RED if v0 > 90 else (self.ORANGE if v0 > 75 else (self.YELLOW if v0 > 50 else self.GREEN))
            if self.cache.get("s0_pco0") != col: self.send_command(f"s0.pco0={col}"); self.cache["s0_pco0"] = col
            if now - self._last_graph_update > 1:
                self.send_command(f"add 3,0,{int(v0 * 2.55)}"); self.send_command(f"add 3,1,{int(v1 * 2.55)}"); self._last_graph_update = now

    def check_hmi_update(self):
        """Reálná logika pro kontrolu verze a modelu na serveru."""
        if not self.is_connected() or self.state.display_mode == "Uploading": return
        try:
            with self.lock:
                self.ser.reset_input_buffer()
                self.ser.write(b'connect\xff\xff\xff')
                time.sleep(0.4)
                resp = self.ser.read(self.ser.in_waiting).decode('ascii', errors='ignore')
            
            model = "Unknown"
            if "TJC" in resp:
                parts = resp.split(',')
                if len(parts) > 2: model = parts[2]
            if model == "Unknown": return

            with self.lock:
                self.ser.write(b'get swver.val\xff\xff\xff')
                time.sleep(0.2)
                res = self.ser.read(self.ser.in_waiting)
            
            cur_v = 0
            if len(res) >= 5 and res[0] == 0x71:
                cur_v = int.from_bytes(res[1:5], byteorder='little')

            srv_resp = requests.get(f"{self.BASE_URL}version_hmi.txt", timeout=5)
            srv_v = int(srv_resp.text.strip())
            logger.info(f"Kontrola verze HMI - {cur_v}. Verze na serveru - {srv_v}. ")
            if srv_v > cur_v:
                root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
                if messagebox.askyesno("Update", f"Nová grafika verze {srv_v} pro {model} k dispozici. V displayi máte aktuálně verzi {cur_v}. Nahrát?"):
                    path = os.path.join(os.getcwd(), f"update_{model}.tft")
                    r = requests.get(f"{self.BASE_URL}{model}.tft", stream=True)
                    with open(path, 'wb') as f:
                        for chunk in r.iter_content(8192): f.write(chunk)
                    threading.Thread(target=self.upload_tft_file, args=(path,), daemon=True).start()
                root.destroy()
            else:
                logger.info(f"HMI je aktuální.")
        except Exception as e:
            logger.error(f"HMI check fail: {e}")
            
    def get_hmi_version(self):
        if not self.is_connected():
            return 0
    
        with self.lock:
            self.ser.reset_input_buffer()
            # Pošleme dotaz
            self.ser.write(b'get swver.val\xff\xff\xff')
            time.sleep(0.2) # Počkáme na odpověď
            res = self.ser.read(self.ser.in_waiting)
        
            # Odpověď musí mít 8 bytů a začínat 0x71
            if len(res) >= 5 and res[0] == 0x71:
                # Vezmeme byty na indexu 1 až 4 a převedeme je
                # 'little' znamená, že nejméně významný byte je první (to co vidíš v logu)
                version = int.from_bytes(res[1:5], byteorder='little')
                logger.info(f"Zjištěná verze z displeje: {version}")
                return version
            else:
                logger.warning(f"Neočekávaná odpověď z displeje: {res.hex(' ')}")
                return 0


    def upload_tft_file(self, file_path):
        if not os.path.exists(file_path): return
        port = self.state.port if self.state.port != "Auto" else self._find_nextion_port()
        if not port: return
        old = self.state.display_mode; self.state.display_mode = "Uploading"; self.disconnect(); time.sleep(1.5)
        try:
            sz = os.path.getsize(file_path)
            with serial.Serial(port, self.state.baud_rate, timeout=0.5) as s:
                s.write(b'\x00\xff\xff\xffconnect\xff\xff\xff'); time.sleep(0.5); s.read_all()
                s.write(f"whmi-wri {sz},921600,0".encode('ascii') + b'\xff\xff\xff'); time.sleep(0.5)
            with serial.Serial(port, 921600, timeout=1.0) as s:
                with open(file_path, 'rb') as f:
                    while chunk := f.read(4096):
                        s.write(chunk); time.sleep(0.02)
                        st = time.time()
                        while s.in_waiting == 0:
                            if time.time() - st > 3.0: raise Exception("Timeout")
                        s.read(s.in_waiting)
            logger.info("Upload OK")
        except Exception as e: logger.error(f"Upload fail: {e}")
        finally: self.state.display_mode = old; self.cache.clear()

    def open_terminal(self):
        threading.Thread(target=self.standalone_terminal_window, daemon=True).start()

    def standalone_terminal_window(self):
        old = self.state.display_mode
        self.state.display_mode = "Terminal"
        self.disconnect()
        
        root = tk.Tk()
        root.title("mujDISPLAY Nextion/TJC Terminal")
        root.geometry("900x550")
        root.attributes("-topmost", True)
        
        area = scrolledtext.ScrolledText(root, bg="black", fg="white", font=("Consolas", 10))
        area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        area.tag_config("TX", foreground="#00AAFF")
        area.tag_config("RX", foreground="#00FF00")
        area.tag_config("ERR", foreground="red")

        def log(msg, tag="RX"):
            area.config(state='normal')
            area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n", tag)
            area.config(state='disabled')
            area.see(tk.END)

        p = self.state.port if self.state.port != "Auto" else self._find_nextion_port()
        ser_term = None
        if p:
            try:
                ser_term = serial.Serial(p, self.state.baud_rate, timeout=0.1)
                log(f"Připojeno k {p} @ {self.state.baud_rate} bps")
            except Exception as e: log(f"Chyba: {e}", "ERR")
        else: log("Port nenalezen!", "ERR")

        def read_loop():
            while ser_term and ser_term.is_open and root.winfo_exists():
                try:
                    if ser_term.in_waiting:
                        d = ser_term.read(ser_term.in_waiting)
                        h = d.hex(' ').upper()
                        a = d.decode('ascii', errors='replace').replace('\xff', '.')
                        log(f"RX <- {h}  ({a})")
                except: break
                time.sleep(0.05)

        if ser_term: threading.Thread(target=read_loop, daemon=True).start()
        
        ent = tk.Entry(root, font=("Consolas", 11)); ent.pack(fill=tk.X, padx=5, pady=5); ent.focus_set()
        
        def send(ev=None):
            cmd = ent.get()
            if cmd and ser_term:
                ser_term.write(cmd.encode('ascii') + b'\xff\xff\xff')
                log(f"TX -> {cmd}", "TX")
                ent.delete(0, tk.END)
        ent.bind("<Return>", send)

        btn_f = tk.Frame(root); btn_f.pack(fill=tk.X)
        cmds = [("Reset","rest"),("Connect","connect"),("ID Stránky","sendme"),("Jas 100","dim=100"),("Spánek","sleep=1")]
        for t, c in cmds:
            tk.Button(btn_f, text=t, command=lambda cmd=c: [ent.delete(0, tk.END), ent.insert(0, cmd), send()]).pack(side=tk.LEFT, padx=2)

        def close():
            if ser_term: ser_term.close()
            self.state.display_mode = old
            try:
                root.quit()
                root.destroy()
            except:
                pass
        root.protocol("WM_DELETE_WINDOW", close)
        try:
            root.mainloop()
        except UnicodeDecodeError:
            # Občas se stane při RX datech z displeje v terminálu
            pass

    def select_and_upload(self):
        def _run():
            r = tk.Tk(); r.withdraw(); r.attributes("-topmost", True)
            path = filedialog.askopenfilename(filetypes=[("TFT soubory", "*.tft")])
            r.destroy()
            if path: threading.Thread(target=self.upload_tft_file, args=(path,), daemon=True).start()
        threading.Timer(0.1, _run).start()

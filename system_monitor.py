# system_monitor.py
"""Sběr systémových dat."""

import psutil
import socket
import subprocess
import platform

class SystemMonitor:
    def cpu_percent(self) -> int:
        return int(psutil.cpu_percent())

    def ram_percent(self) -> int:
        return int(psutil.virtual_memory().percent)

    def disk_percent(self) -> int:
        try:
            return int(psutil.disk_usage('C:').percent)
        except:
            return 0

    def cpu_name(self) -> str:
        return platform.processor().split(' ')[0]

    def disks_info(self) -> str:
        parts = psutil.disk_partitions()
        info = ""
        for p in parts:
            if 'cdrom' in p.opts or p.fstype == '': continue
            usage = psutil.disk_usage(p.mountpoint)
            info += f"{p.device[0]}: {int(usage.free / (1024**3))}G "
        return info.strip()

    def get_net_io(self):
        return psutil.net_io_counters()

    def get_ip_and_gateway(self):
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
            return f"{ip}/24", gw
        except:
            return "Offline", "?.?.?.?"

def is_pc_locked() -> bool:
    for p in psutil.process_iter(attrs=['name']):
        if p.info['name'] == "LogonUI.exe":
            return True
    return False

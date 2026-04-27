# utils.py
import psutil

def is_pc_locked() -> bool:
    for p in psutil.process_iter(attrs=['name']):
        if p.info['name'] == "LogonUI.exe":
            return True
    return False

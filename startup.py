import os
import sys
import winreg
from typing import Optional


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "AirDropPlus"


def _build_startup_command(entry_script: Optional[str] = None) -> str:
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"'
    script_path = os.path.abspath(entry_script or sys.argv[0])
    return f'"{sys.executable}" "{script_path}"'


def is_startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except FileNotFoundError:
        return False


def set_startup_enabled(enabled: bool, entry_script: Optional[str] = None):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _build_startup_command(entry_script))
            return
        try:
            winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass

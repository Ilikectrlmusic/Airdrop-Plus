import ctypes
from ctypes import wintypes
import os
import subprocess
import sys


ELEVATED_TASK_FLAG = "--airdropplus-elevated-task"
TASK_WRITE_CONFIG = "write-config"
TASK_CONFIGURE_FIREWALL = "configure-firewall"

SEE_MASK_NOCLOSEPROCESS = 0x00000040
SW_HIDE = 0
INFINITE = 0xFFFFFFFF
ERROR_CANCELLED = 1223


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


def is_windows_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _get_python_launcher() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable

    current = os.path.abspath(sys.executable)
    current_name = os.path.basename(current).lower()
    if current_name == "pythonw.exe":
        return current

    pythonw = os.path.join(os.path.dirname(current), "pythonw.exe")
    if os.path.exists(pythonw):
        return pythonw
    return current


def _get_entry_script() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base_dir, "AirDropPlus.py")
    if os.path.exists(candidate):
        return candidate
    return os.path.abspath(sys.argv[0])


def _build_elevated_command(task_name: str, task_args: list[str]) -> tuple[str, str, str]:
    if getattr(sys, "frozen", False):
        executable = os.path.abspath(sys.executable)
        parameters = [ELEVATED_TASK_FLAG, task_name, *task_args]
        working_dir = os.path.dirname(executable)
    else:
        executable = _get_python_launcher()
        entry_script = _get_entry_script()
        parameters = [entry_script, ELEVATED_TASK_FLAG, task_name, *task_args]
        working_dir = os.path.dirname(entry_script)

    return executable, subprocess.list2cmdline(parameters), working_dir


def run_elevated_task(task_name: str, *task_args: str) -> int:
    if os.name != "nt":
        raise OSError("Elevation is only supported on Windows.")

    executable, parameters, working_dir = _build_elevated_command(task_name, [str(x) for x in task_args])
    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32

    shell_execute_ex = shell32.ShellExecuteExW
    shell_execute_ex.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
    shell_execute_ex.restype = wintypes.BOOL

    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait_for_single_object.restype = wintypes.DWORD

    get_exit_code_process = kernel32.GetExitCodeProcess
    get_exit_code_process.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    get_exit_code_process.restype = wintypes.BOOL

    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    sei = SHELLEXECUTEINFOW()
    sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    sei.fMask = SEE_MASK_NOCLOSEPROCESS
    sei.lpVerb = "runas"
    sei.lpFile = executable
    sei.lpParameters = parameters
    sei.lpDirectory = working_dir
    sei.nShow = SW_HIDE

    if not shell_execute_ex(ctypes.byref(sei)):
        error_code = ctypes.windll.kernel32.GetLastError()
        if error_code == ERROR_CANCELLED:
            raise PermissionError("Administrator permission was cancelled by user.")
        raise OSError(f"Failed to start elevated task (error code {error_code}).")

    if not sei.hProcess:
        return 0

    try:
        wait_for_single_object(sei.hProcess, INFINITE)
        exit_code = wintypes.DWORD(0)
        if not get_exit_code_process(sei.hProcess, ctypes.byref(exit_code)):
            raise OSError("Failed to query elevated process exit code.")
        return int(exit_code.value)
    finally:
        close_handle(sei.hProcess)

import os
import re
import socket
import time

import psutil
import imghdr


def avoid_duplicate_filename(save_path, filename):
    base_filename, extension = os.path.splitext(filename)
    counter = 1
    while os.path.exists(os.path.join(save_path, filename)):
        filename = f"{base_filename} ({counter}){extension}"
        counter += 1
    return filename

def is_program_running():
    program_name = "AirDropPlus.exe"
    count: int = 0
    for process in psutil.process_iter((['name'])):
        if process.info['name'] == program_name:
            count += 1
            if count >= 2:  # 自身也占用一个
                return True
    return False

def is_image_file(file_path):
    image_type = imghdr.what(file_path)
    if image_type is not None:
        return True
    else:
        return False


def get_local_ipv4() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and ip != '0.0.0.0':
                return ip
    except Exception:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return '127.0.0.1'


def wait_for_parent_restart_exit(env_key: str = 'AIRDROPPLUS_RESTART_PARENT_PID', timeout_seconds: float = 12.0):
    raw_pid = os.environ.pop(env_key, '').strip()
    if not raw_pid.isdigit():
        return
    parent_pid = int(raw_pid)
    deadline = time.time() + max(timeout_seconds, 0.0)
    while time.time() < deadline:
        if not psutil.pid_exists(parent_pid):
            return
        time.sleep(0.2)

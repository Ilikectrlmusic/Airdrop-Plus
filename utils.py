import os
import re
import socket
import time
import ipaddress

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


def _is_valid_ipv4(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address((ip or '').strip())
    except ValueError:
        return False
    return addr.version == 4 and not addr.is_loopback and not addr.is_unspecified


def _get_preferred_route_ipv4() -> str | None:
    for probe in ("8.8.8.8", "1.1.1.1", "223.5.5.5"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((probe, 80))
                ip = s.getsockname()[0]
                if _is_valid_ipv4(ip):
                    return ip
        except Exception:
            continue
    return None


def get_local_ipv4_candidates() -> list[str]:
    preferred_ip = _get_preferred_route_ipv4()
    active_ips: set[str] = set()

    try:
        iface_stats = psutil.net_if_stats()
        iface_addrs = psutil.net_if_addrs()
        for iface_name, addrs in iface_addrs.items():
            stat = iface_stats.get(iface_name)
            if stat is not None and not stat.isup:
                continue
            for addr in addrs:
                if addr.family != socket.AF_INET:
                    continue
                ip = (addr.address or '').strip()
                if _is_valid_ipv4(ip):
                    active_ips.add(ip)
    except Exception:
        pass

    try:
        host_ip = socket.gethostbyname(socket.gethostname())
        if _is_valid_ipv4(host_ip):
            active_ips.add(host_ip)
    except Exception:
        pass

    ordered: list[str] = []
    if preferred_ip is not None:
        ordered.append(preferred_ip)

    for ip in sorted(active_ips):
        if ip not in ordered:
            ordered.append(ip)

    if not ordered:
        ordered.append('127.0.0.1')
    return ordered


def get_local_ipv4() -> str:
    candidates = get_local_ipv4_candidates()
    return candidates[0] if candidates else '127.0.0.1'


def get_network_signature() -> tuple[str, ...]:
    candidates = get_local_ipv4_candidates()
    if not candidates:
        return tuple()
    primary = candidates[0]
    extras = sorted(set(candidates[1:]))
    return tuple([primary, *extras])


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

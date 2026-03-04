import os
import signal
import sys
import threading
import time
import urllib.request

from PIL import Image
from pystray import Icon, MenuItem

from config import Config, write_config_content_from_file
from firewall import configure_public_network_permission, ensure_public_network_permission
from first_run_guide import show_first_run_guide
import utils
from mdns import MdnsAdvertiser
from notifier import create_notifier
from server import Server
from settings_ui import show_settings_window
from startup import set_startup_enabled
from win_elevate import ELEVATED_TASK_FLAG, TASK_CONFIGURE_FIREWALL, TASK_WRITE_CONFIG


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _handle_elevated_task_mode():
    if len(sys.argv) < 3 or sys.argv[1] != ELEVATED_TASK_FLAG:
        return

    task_name = sys.argv[2]
    try:
        if task_name == TASK_WRITE_CONFIG:
            if len(sys.argv) != 5:
                raise ValueError("Invalid arguments for elevated config write.")
            write_config_content_from_file(sys.argv[3], sys.argv[4])
            sys.exit(0)

        if task_name == TASK_CONFIGURE_FIREWALL:
            if len(sys.argv) != 4:
                raise ValueError("Invalid arguments for elevated firewall setup.")
            configure_public_network_permission(sys.argv[3])
            sys.exit(0)

        raise ValueError(f"Unknown elevated task: {task_name}")
    except Exception:
        sys.exit(1)


_handle_elevated_task_mode()

config_file_path = os.path.join(SCRIPT_DIR, 'config', 'config.ini')
config = Config(config_file_path)
notifier = create_notifier(config.basic_notifier, config.language)
mdns_advertiser: MdnsAdvertiser | None = None
mdns_lock = threading.Lock()
stop_event = threading.Event()
server_thread: threading.Thread | None = None
recovery_thread: threading.Thread | None = None


def _t(zh: str, en: str) -> str:
    return en if str(config.language).lower().startswith('en') else zh


def _refresh_mdns(local_ip: str | None = None) -> tuple[str, str | None]:
    global mdns_advertiser

    if local_ip is None:
        local_ip = utils.get_local_ipv4()

    with mdns_lock:
        old_advertiser = mdns_advertiser
        mdns_advertiser = None
        if old_advertiser is not None:
            try:
                old_advertiser.stop()
            except Exception:
                pass

        try:
            advertiser = MdnsAdvertiser(config.device_id, config.port, local_ip)
            advertiser.start()
            mdns_advertiser = advertiser
            return local_ip, None
        except Exception as e:
            mdns_advertiser = None
            return local_ip, str(e)


def _run_http_server():
    try:
        server = Server(config, notifier)
        server.run(host='0.0.0.0', port=config.port)
    except Exception as e:
        notifier.notify(_t('启动失败', 'Startup failed'), _t(f'错误信息: {e}', f'Error: {e}'))


def _start_http_server_thread():
    global server_thread
    if server_thread is not None and server_thread.is_alive():
        return
    server_thread = threading.Thread(
        target=_run_http_server,
        name='AirDropPlus-HTTPServer',
        daemon=True,
    )
    server_thread.start()


def _is_http_server_healthy(timeout_seconds: float = 2.0) -> bool:
    try:
        url = f'http://127.0.0.1:{config.port}/device/info'
        req = urllib.request.Request(url, headers={'Connection': 'close'})
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            status = getattr(resp, 'status', 200)
            return int(status) == 200
    except Exception:
        return False


def _recovery_monitor(initial_ip: str):
    check_interval = 8.0
    last_tick = time.monotonic()
    last_ip = initial_ip
    failed_health_checks = 0

    while not stop_event.wait(check_interval):
        now = time.monotonic()
        woke_from_sleep = (now - last_tick) > (check_interval * 3)
        last_tick = now

        current_ip = utils.get_local_ipv4()
        ip_changed = current_ip != last_ip
        if woke_from_sleep or ip_changed:
            _, mdns_error = _refresh_mdns(current_ip)
            if mdns_error is not None:
                notifier.notify(
                    _t('网络恢复失败', 'Resume recovery failed'),
                    _t(f'mDNS 刷新失败: {mdns_error}', f'Failed to refresh mDNS: {mdns_error}'),
                )
            last_ip = current_ip

        if _is_http_server_healthy():
            failed_health_checks = 0
            continue

        failed_health_checks += 1
        if failed_health_checks >= 3:
            if server_thread is None or not server_thread.is_alive():
                _start_http_server_thread()
            failed_health_checks = 0


def _start_recovery_monitor(initial_ip: str):
    global recovery_thread
    if recovery_thread is not None and recovery_thread.is_alive():
        return

    recovery_thread = threading.Thread(
        target=lambda: _recovery_monitor(initial_ip),
        name='AirDropPlus-RecoveryMonitor',
        daemon=True,
    )
    recovery_thread.start()


def run_first_run_guide_if_needed():
    if not config.is_first_run:
        return
    try:
        auto_start, save_path = show_first_run_guide(
            device_id=config.device_id,
            static_dir=os.path.join(SCRIPT_DIR, 'static'),
            default_auto_start=config.auto_start,
            default_save_path=config.save_path,
            language=config.language,
        )
        config.save_settings(
            key=config.key,
            port=config.port,
            save_path=save_path,
            auto_start=auto_start,
            elevate=True,
            persist_device_id=True,
        )
        set_startup_enabled(auto_start, os.path.abspath(__file__))
        try:
            ensure_public_network_permission(os.path.abspath(sys.executable))
        except Exception as network_e:
            notifier.notify(
                _t('网络权限申请失败', 'Network permission request failed'),
                str(network_e),
            )
    except Exception as e:
        notifier.notify(_t('首次引导失败', 'First-run guide failed'), str(e))


def create_icon():
    is_en = str(config.language).lower().startswith('en')
    menu_settings_text = 'Settings' if is_en else '设置'
    menu_exit_text = 'Exit' if is_en else '退出'

    def on_exit(icon, item):
        global mdns_advertiser
        stop_event.set()
        with mdns_lock:
            if mdns_advertiser is not None:
                mdns_advertiser.stop()
            mdns_advertiser = None
        icon.stop()
        os.kill(os.getpid(), signal.SIGINT)

    def on_edit_config(icon, item):
        show_settings_window(
            config=config,
            notifier=notifier,
            script_dir=SCRIPT_DIR,
            entry_script=os.path.abspath(__file__),
            language=config.language,
        )

    menu = (
        MenuItem(text=menu_settings_text, action=on_edit_config),
        MenuItem(text=menu_exit_text, action=on_exit),
    )
    image = Image.open(os.path.join(SCRIPT_DIR, 'static', 'icon.ico'))
    icon = Icon('AirDrop Plus', image, 'AirDrop Plus', menu)
    icon.run()


def start_server():
    if not os.path.exists(config.save_path):
        notifier.notify(
            _t('启动失败', 'Startup failed'),
            _t(
                f'文件保存路径: "{config.save_path}" 不存在，请检查配置文件 "{config_file_path}"',
                f'Save path "{config.save_path}" does not exist. Check config file "{config_file_path}".',
            ),
        )
        sys.exit()

    if utils.is_program_running():
        notifier.notify(_t('启动失败', 'Startup failed'), _t('请不要重复启动', 'Application is already running'))
        sys.exit()

    try:
        stop_event.clear()
        _start_http_server_thread()
        local_ip, mdns_error = _refresh_mdns()
        _start_recovery_monitor(local_ip)

        startup_msg = (
            _t(f'主机: {config.device_id}', f'Host: {config.device_id}')
            + '\n'
            + _t(f'连接地址: http://{local_ip}:{config.port}', f'URL: http://{local_ip}:{config.port}')
            + '\n'
            + _t(f'文件保存路径: {config.save_path}', f'Save path: {config.save_path}')
        )
        if mdns_error is not None:
            startup_msg += _t(f'\nmDNS 广播失败: {mdns_error}', f'\nmDNS broadcast failed: {mdns_error}')

        if config.startup_notify:
            notifier.notify(_t('启动成功', 'Startup succeeded'), startup_msg)
    except Exception as e:
        notifier.notify(_t('启动失败', 'Startup failed'), _t(f'错误信息: {e}', f'Error: {e}'))


if __name__ == '__main__':
    utils.wait_for_parent_restart_exit()
    run_first_run_guide_if_needed()
    start_server()
    create_icon()

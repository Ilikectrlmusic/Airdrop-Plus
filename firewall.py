import os
import subprocess

from win_elevate import TASK_CONFIGURE_FIREWALL, is_windows_admin, run_elevated_task

RULE_INBOUND = "AirDrop Plus Public Inbound"
RULE_OUTBOUND = "AirDrop Plus Public Outbound"


def _run_netsh(arguments: list[str], check: bool = False):
    creationflags = 0
    startupinfo = None
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    completed = subprocess.run(
        ["netsh", *arguments],
        capture_output=True,
        text=True,
        creationflags=creationflags,
        startupinfo=startupinfo,
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        if detail:
            raise RuntimeError(detail)
        raise RuntimeError(f"netsh failed with exit code {completed.returncode}")
    return completed


def configure_public_network_permission(program_path: str):
    if os.name != "nt":
        return

    app_path = os.path.abspath(program_path or "")
    if app_path == "" or not os.path.exists(app_path):
        raise FileNotFoundError(f"Program not found: {app_path}")

    _run_netsh(
        ["advfirewall", "firewall", "delete", "rule", f"name={RULE_INBOUND}", f"program={app_path}"],
        check=False,
    )
    _run_netsh(
        ["advfirewall", "firewall", "delete", "rule", f"name={RULE_OUTBOUND}", f"program={app_path}"],
        check=False,
    )

    _run_netsh(
        [
            "advfirewall",
            "firewall",
            "add",
            "rule",
            f"name={RULE_INBOUND}",
            "dir=in",
            "action=allow",
            f"program={app_path}",
            "profile=public",
            "enable=yes",
        ],
        check=True,
    )
    _run_netsh(
        [
            "advfirewall",
            "firewall",
            "add",
            "rule",
            f"name={RULE_OUTBOUND}",
            "dir=out",
            "action=allow",
            f"program={app_path}",
            "profile=public",
            "enable=yes",
        ],
        check=True,
    )


def ensure_public_network_permission(program_path: str):
    if os.name != "nt":
        return

    app_path = os.path.abspath(program_path or "")
    if app_path == "" or not os.path.exists(app_path):
        raise FileNotFoundError(f"Program not found: {app_path}")

    if is_windows_admin():
        configure_public_network_permission(app_path)
        return

    exit_code = run_elevated_task(TASK_CONFIGURE_FIREWALL, app_path)
    if exit_code != 0:
        raise PermissionError(
            f"Failed to request public network access with administrator rights (exit code {exit_code})."
        )

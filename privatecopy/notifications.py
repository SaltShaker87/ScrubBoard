"""Desktop notifications. Messages carry counts/status only — never clipboard text."""
from __future__ import annotations

import platform
import shutil
import subprocess

_tray_icon = None


def attach_tray(icon) -> None:
    """Route notifications through the pystray icon when its backend supports them."""
    global _tray_icon
    _tray_icon = icon


def notify(title: str, message: str) -> None:
    icon = _tray_icon
    if icon is not None and getattr(icon, "HAS_NOTIFICATION", False):
        try:
            icon.notify(message, title)
            return
        except Exception:
            pass
    system = platform.system()
    try:
        if system == "Darwin":
            script = f"display notification {_as_str(message)} with title {_as_str(title)}"
            subprocess.run(["osascript", "-e", script], check=False, timeout=5, capture_output=True)
            return
        if system == "Linux" and shutil.which("notify-send"):
            subprocess.run(["notify-send", "-a", "PrivateCopy", title, message],
                           check=False, timeout=5, capture_output=True)
            return
    except (OSError, subprocess.SubprocessError):
        pass
    print(f"[{title}] {message}")


def _as_str(s: str) -> str:
    """AppleScript string literal."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

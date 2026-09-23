"""Desktop notifications. Messages carry counts/status only — never clipboard text."""
from __future__ import annotations

import platform
import shutil
import subprocess

_tray_icon = None
_holding = False
_pending: list[tuple[str, str]] = []


def hold_until_tray() -> None:
    """Queue notifications until attach_tray(): on Windows they can only be shown
    through the tray icon, and a windowed app has no console to print to."""
    global _holding
    _holding = True


def attach_tray(icon) -> None:
    """Route notifications through the pystray icon (None = no tray; flush to fallbacks)."""
    global _tray_icon, _holding
    _tray_icon = icon
    _holding = False
    queued, _pending[:] = list(_pending), []
    for title, message in queued:
        notify(title, message)


def notify(title: str, message: str) -> None:
    icon = _tray_icon
    if icon is not None and getattr(icon, "HAS_NOTIFICATION", False):
        try:
            icon.notify(message, title)
            return
        except Exception:
            pass
    system = platform.system()
    if icon is None and _holding and system == "Windows":
        _pending.append((title, message))
        return
    try:
        if system == "Darwin":
            script = f"display notification {_as_str(message)} with title {_as_str(title)}"
            subprocess.run(["osascript", "-e", script], check=False, timeout=5, capture_output=True)
            return
        if system == "Linux" and shutil.which("notify-send"):
            subprocess.run(["notify-send", "-a", "Scrubboard", "-i", "scrubboard", title, message],
                           check=False, timeout=5, capture_output=True)
            return
        if system == "Windows" and icon is None:
            _message_box(title, message)
            return
    except (OSError, subprocess.SubprocessError):
        pass
    print(f"[{title}] {message}")


def _message_box(title: str, message: str) -> None:
    import ctypes
    MB_ICONINFORMATION, MB_TOPMOST = 0x40, 0x40000
    ctypes.windll.user32.MessageBoxW(None, message, title, MB_ICONINFORMATION | MB_TOPMOST)


def _as_str(s: str) -> str:
    """AppleScript string literal."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

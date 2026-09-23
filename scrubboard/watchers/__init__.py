"""Clipboard backends: pick the one that can watch this session's clipboard."""
from __future__ import annotations

import os
import platform

from scrubboard.watchers.base import ClipboardBackend, ClipboardEvent

__all__ = ["ClipboardBackend", "ClipboardEvent", "create_backend", "detect_backend_name"]


def detect_backend_name() -> str:
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Windows":
        return "windows"
    wayland = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or (
        os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY"))
    if wayland:
        # Mutter implements no data-control protocol, so on GNOME only the Shell
        # extension can see clipboard changes.
        return "gnome" if "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper() else "wlclipboard"
    return "x11"


def create_backend(name: str | None = None) -> ClipboardBackend:
    name = name or detect_backend_name()
    if name == "macos":
        from scrubboard.watchers.macos import MacClipboard
        return MacClipboard()
    if name == "windows":
        from scrubboard.watchers.windows import WindowsClipboard
        return WindowsClipboard()
    if name == "x11":
        from scrubboard.watchers.x11 import X11Clipboard
        return X11Clipboard()
    if name in ("wlclipboard", "gnome"):
        from scrubboard.watchers.wlclipboard import WlClipboard
        return WlClipboard(watch=name == "wlclipboard")
    raise ValueError(f"unknown clipboard backend {name!r}")

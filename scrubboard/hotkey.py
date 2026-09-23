"""Optional global hotkey (pip install 'scrubboard[hotkey]'): triggers
"Redact clipboard now". Off by default — copy interception needs no hotkey.
Canonical form: e.g. 'ctrl+alt+r', 'cmd+shift+r'."""
from __future__ import annotations

from collections.abc import Callable

CANON = {"command": "cmd", "meta": "cmd", "control": "ctrl", "escape": "esc", "return": "enter"}
MODIFIERS = ("ctrl", "cmd", "alt", "shift")


def canonicalize(hotkey: str) -> str:
    parts = [CANON.get(p.strip().lower(), p.strip().lower()) for p in hotkey.split("+") if p.strip()]
    mods = [p for p in parts if p in MODIFIERS]
    keys = [p for p in parts if p not in MODIFIERS]
    return "+".join(mods + keys)


class HotkeyListener:
    """Thin wrapper over pynput; raises a helpful error if unavailable."""

    def __init__(self, hotkey: str, callback: Callable[[], None]):
        self.hotkey = canonicalize(hotkey)
        self.callback = callback
        self._listener = None

    def _to_pynput(self) -> str:
        return "+".join(f"<{p}>" if p in MODIFIERS else p for p in self.hotkey.split("+"))

    def start(self) -> None:
        try:
            from pynput import keyboard
        except ImportError as e:
            raise RuntimeError("global hotkeys need pynput: pip install 'scrubboard[hotkey]'") from e
        hot = keyboard.HotKey(keyboard.HotKey.parse(self._to_pynput()), self.callback)
        listener = keyboard.Listener(on_press=hot.press, on_release=hot.release)
        listener.daemon = True
        listener.start()
        self._listener = listener

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

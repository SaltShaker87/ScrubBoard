"""Global hotkey helpers. Canonical form: e.g. 'ctrl+shift+c', 'cmd+shift+c'."""
from __future__ import annotations

import platform
from collections.abc import Callable

CANON = {"command": "cmd", "meta": "cmd", "control": "ctrl", "escape": "esc", "return": "enter"}


def canonicalize(hotkey: str) -> str:
    parts = [CANON.get(p.strip().lower(), p.strip().lower()) for p in hotkey.split("+") if p.strip()]
    mods = [p for p in parts if p in ("ctrl", "cmd", "alt", "shift")]
    keys = [p for p in parts if p not in ("ctrl", "cmd", "alt", "shift")]
    return "+".join(mods + keys)


def default_hotkey() -> str:
    return "cmd+shift+c" if platform.system() == "Darwin" else "ctrl+shift+c"


class HotkeyListener:
    """Thin wrapper over pynput; raises a helpful error if unavailable."""

    def __init__(self, hotkey: str, callback: Callable[[], None]):
        self.hotkey = canonicalize(hotkey)
        self.callback = callback
        self._listener = None

    def _to_pynput(self) -> str:
        from pynput import keyboard
        mapping = {"ctrl": keyboard.Key.ctrl, "cmd": keyboard.Key.cmd,
                   "alt": keyboard.Key.alt, "shift": keyboard.Key.shift}
        parts = []
        for p in self.hotkey.split("+"):
            parts.append(f"<{mapping[p].name}>" if p in mapping else p)
        return "+".join(parts)

    def start(self) -> None:
        try:
            from pynput import keyboard
        except ImportError as e:
            raise RuntimeError("global hotkeys need pynput: pip install pynput") from e
        combo = keyboard.HotKey.parse(self._to_pynput())
        hot = keyboard.HotKey(combo, lambda: self.callback())
        lis = keyboard.Listener(on_press=hot.press, on_release=hot.release)
        lis.daemon = True
        lis.start()
        self._listener = lis

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

"""Wayland compositors with a data-control protocol (KDE Plasma, wlroots):
`wl-paste --watch` as the change stream, wl-paste / wl-copy for I/O.

On GNOME (no data-control) this backend is used for reads/writes only; change
events come from the GNOME Shell extension instead."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import threading
from collections import deque

from scrubboard.watchers.base import ClipboardBackend, ClipboardEvent, OnChange

PASSWORD_HINT_TYPE = "x-kde-passwordManagerHint"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


class WlClipboard(ClipboardBackend):
    name = "wlclipboard"

    def __init__(self, watch: bool = True) -> None:
        self.supports_watch = watch
        self._written: deque[str] = deque(maxlen=4)
        self._proc: subprocess.Popen | None = None

    @staticmethod
    def _require() -> None:
        if not (shutil.which("wl-paste") and shutil.which("wl-copy")):
            raise RuntimeError("install wl-clipboard (e.g. sudo apt install wl-clipboard)")

    def read_text(self) -> str | None:
        self._require()
        r = subprocess.run(["wl-paste", "--no-newline", "--type", "text"], capture_output=True, timeout=5)
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None

    def _types(self) -> set[str]:
        r = subprocess.run(["wl-paste", "--list-types"], capture_output=True, timeout=5)
        return set(r.stdout.decode("utf-8", "replace").split()) if r.returncode == 0 else set()

    def write_text(self, text: str, *, transient: bool = False) -> None:
        self._require()
        self._written.append(_digest(text))
        subprocess.run(["wl-copy", "--type", "text/plain;charset=utf-8"], input=text.encode("utf-8"),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=True)

    def start(self, on_change: OnChange) -> None:
        self._require()
        # wl-paste runs the command on every change; it prints one line per change.
        self._proc = subprocess.Popen(
            ["wl-paste", "--watch", "sh", "-c", "cat >/dev/null; echo changed"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        threading.Thread(target=self._loop, args=(self._proc, on_change),
                         name="scrubboard-wl-clipboard", daemon=True).start()

    def stop(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            self._proc = None

    def _loop(self, proc: subprocess.Popen, on_change: OnChange) -> None:
        assert proc.stdout is not None
        for _line in proc.stdout:
            try:
                concealed = PASSWORD_HINT_TYPE in self._types()
                text = None if concealed else self.read_text()
                own = text is not None and _digest(text) in self._written
                on_change(ClipboardEvent(None if own else text, own=own, concealed=concealed))
            except Exception:
                pass

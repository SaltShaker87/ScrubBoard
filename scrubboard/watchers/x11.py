"""X11 (and XWayland sessions): XFixes selection-owner notifications via
python-xlib; reads/writes go through xclip or xsel."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import threading
import time
from collections import deque

from scrubboard.watchers.base import ClipboardBackend, ClipboardEvent, OnChange

PASSWORD_HINT_TARGET = "x-kde-passwordManagerHint"  # set by KeePassXC and others


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


class X11Clipboard(ClipboardBackend):
    name = "x11"

    def __init__(self) -> None:
        self._tool = next((t for t in ("xclip", "xsel") if shutil.which(t)), None)
        self._written: deque[str] = deque(maxlen=4)  # digests of our recent writes
        self._stop = threading.Event()
        self._display = None

    def _require_tool(self) -> str:
        if not self._tool:
            raise RuntimeError("install xclip or xsel (e.g. sudo apt install xclip)")
        return self._tool

    def read_text(self) -> str | None:
        tool = self._require_tool()
        cmd = (["xclip", "-selection", "clipboard", "-o", "-t", "UTF8_STRING"] if tool == "xclip"
               else ["xsel", "--clipboard", "--output"])
        r = subprocess.run(cmd, capture_output=True, timeout=5)
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None

    def _targets(self) -> set[str]:
        if self._tool != "xclip":
            return set()
        r = subprocess.run(["xclip", "-selection", "clipboard", "-o", "-t", "TARGETS"],
                           capture_output=True, timeout=5)
        return set(r.stdout.decode("utf-8", "replace").split()) if r.returncode == 0 else set()

    def write_text(self, text: str, *, transient: bool = False) -> None:
        tool = self._require_tool()
        self._written.append(_digest(text))
        cmd = (["xclip", "-selection", "clipboard", "-i"] if tool == "xclip"
               else ["xsel", "--clipboard", "--input"])
        # The tool forks to serve the selection; don't wait on its output pipes.
        subprocess.run(cmd, input=text.encode("utf-8"), stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=5, check=True)

    def start(self, on_change: OnChange) -> None:
        self._require_tool()
        try:
            from Xlib import display as xdisplay
            from Xlib.ext import xfixes
        except ImportError as e:
            raise RuntimeError("python-xlib is required to watch the X11 clipboard") from e
        d = xdisplay.Display()
        if not d.has_extension("XFIXES"):
            raise RuntimeError("the X server lacks the XFIXES extension")
        d.xfixes_query_version()
        d.screen().root.xfixes_select_selection_input(d.get_atom("CLIPBOARD"),
                                                      xfixes.XFixesSetSelectionOwnerNotifyMask)
        self._display = d
        threading.Thread(target=self._loop, args=(d, on_change), name="scrubboard-x11-clipboard",
                         daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        if self._display is not None:
            try:
                self._display.close()
            except Exception:
                pass

    def _loop(self, d, on_change: OnChange) -> None:
        while not self._stop.is_set():
            try:
                event = d.next_event()
            except Exception:
                return
            if (event.type, getattr(event, "sub_code", None)) != d.extension_event.SetSelectionNotify:
                continue
            time.sleep(0.05)  # let the new owner start serving
            try:
                concealed = PASSWORD_HINT_TARGET in self._targets()
                text = None if concealed else self.read_text()
                own = text is not None and _digest(text) in self._written
                on_change(ClipboardEvent(None if own else text, own=own, concealed=concealed))
            except Exception:
                pass

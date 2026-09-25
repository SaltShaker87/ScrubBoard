"""Tray icon + menu (pystray). Falls back to a console loop without a tray host."""
from __future__ import annotations

import os
import platform
import sys
import threading

from scrubboard.notifications import attach_tray

GREEN, GREY, RED = (46, 160, 67, 255), (140, 140, 140, 255), (218, 54, 51, 255)


def _icon_path() -> str | None:
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.path.join(getattr(sys, "_MEIPASS", ""), "assets", "scrubboard-tray.png"),
                      os.path.join(here, "..", "assets", "scrubboard-tray.png")):
        if os.path.exists(candidate):
            return candidate
    return None


def make_icon(color: tuple[int, int, int, int]):
    from PIL import Image, ImageDraw

    path = _icon_path()
    if path:
        img = Image.open(path).convert("RGBA").resize((64, 64), Image.LANCZOS)
    else:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle([6, 6, 58, 58], radius=10, fill=(15, 107, 102, 255))
    ImageDraw.Draw(img).ellipse([42, 42, 63, 63], fill=color, outline=(255, 255, 255, 255), width=3)
    return img


class TrayApp:
    def __init__(self, app):
        self.app = app
        self._icon = None
        app.on_change = self.refresh

    def _color(self):
        a = self.app
        if not a.protected:
            return RED
        return GREEN

    def refresh(self) -> None:
        icon = self._icon
        if icon is None:
            return
        if platform.system() == "Darwin" and threading.current_thread() is not threading.main_thread():
            # AppKit kills the app if the status item is changed off the main thread.
            from PyObjCTools import AppHelper
            AppHelper.callAfter(self.refresh)
            return
        try:
            icon.icon = make_icon(self._color())
            icon.title = f"Scrubboard: {self.app.status_line()}"
            icon.update_menu()
        except Exception:
            pass

    def _menu(self):
        import pystray

        a = self.app
        item = pystray.MenuItem
        auto_on = lambda _: a.config.intercept_enabled  # noqa: E731
        return pystray.Menu(
            item(lambda _: a.status_line(), None, enabled=False),
            item(lambda _: a.last_result or "Nothing cleaned yet", None, enabled=False),
            pystray.Menu.SEPARATOR,
            # default=True: a left-click on the Windows tray icon runs this.
            item("Clean my clipboard", lambda *_: a.redact_now(), default=True),
            pystray.Menu.SEPARATOR,
            item("Clean every copy automatically", lambda *_: a.set_intercept(not a.config.intercept_enabled),
                 checked=auto_on),
            item(lambda _: "Resume automatic cleaning" if a.controller.paused else "Pause for 5 minutes",
                 lambda *_: a.resume() if a.controller.paused else a.pause(), visible=auto_on),
            item("Extra-careful mode (slower; one-time 400 MB download)",
                 lambda *_: a.set_llm(not a.config.llm_enabled), checked=lambda _: a.config.llm_enabled),
            item("Retry", lambda *_: a.retry(), visible=lambda _: not a.protected),
            pystray.Menu.SEPARATOR,
            item("How to use Scrubboard…", lambda *_: a.open_help()),
            item("Quit Scrubboard", lambda icon, _item: icon.stop()),
        )

    def _setup(self, icon) -> None:
        icon.visible = True
        attach_tray(icon)

    def run(self) -> None:
        try:
            import pystray

            self._icon = pystray.Icon("Scrubboard", make_icon(self._color()),
                                      f"Scrubboard: {self.app.status_line()}", self._menu())
            self._icon.run(setup=self._setup)
        except Exception as e:  # no GUI session / tray host
            attach_tray(None)
            print(f"Tray unavailable ({e}).")
            self._console()

    def _console(self) -> None:
        a = self.app
        print("Scrubboard is running without a tray icon.\n"
              "Commands: [c] clean my clipboard, [a] toggle automatic cleaning, [s] status, [q] quit")
        try:
            while True:
                cmd = input("> ").strip().lower()
                if cmd == "c":
                    a.redact_now()
                elif cmd == "a":
                    a.set_intercept(not a.config.intercept_enabled)
                    print(a.status_line())
                elif cmd == "s":
                    print(a.status_line())
                elif cmd == "q":
                    return
        except (EOFError, KeyboardInterrupt):
            return

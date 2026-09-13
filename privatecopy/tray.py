"""Tray icon + menu (pystray). Falls back to a console loop without a tray host."""
from __future__ import annotations

import os
import sys

from privatecopy.notifications import attach_tray

GREEN, GREY, RED = (46, 160, 67, 255), (140, 140, 140, 255), (218, 54, 51, 255)


def _icon_path() -> str | None:
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.path.join(getattr(sys, "_MEIPASS", ""), "assets", "privatecopy-256.png"),
                      os.path.join(here, "resources", "icon.png"),
                      os.path.join(here, "..", "assets", "privatecopy-256.png")):
        if os.path.exists(candidate):
            return candidate
    return None


def make_icon(color: tuple[int, int, int, int]):
    from PIL import Image, ImageDraw

    path = _icon_path()
    if path:
        img = Image.open(path).convert("RGBA").resize((64, 64))
    else:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle([6, 6, 58, 58], radius=10, fill=(40, 40, 40, 255))
    ImageDraw.Draw(img).ellipse([40, 40, 62, 62], fill=color, outline=(255, 255, 255, 255), width=2)
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
        return GREEN if a.controller.enabled else GREY

    def refresh(self) -> None:
        icon = self._icon
        if icon is None:
            return
        try:
            icon.icon = make_icon(self._color())
            icon.title = self.app.status_line()
            icon.update_menu()
        except Exception:
            pass

    def _menu(self):
        import pystray

        a = self.app
        item = pystray.MenuItem
        return pystray.Menu(
            item(lambda _: a.status_line(), None, enabled=False),
            item(lambda _: a.last_result or "No copies redacted yet", None, enabled=False),
            pystray.Menu.SEPARATOR,
            item("Redact every copy", lambda *_: a.set_intercept(not a.config.intercept_enabled),
                 checked=lambda _: a.config.intercept_enabled),
            item(lambda _: "Resume now" if a.controller.paused else "Pause for 5 minutes",
                 lambda *_: a.resume() if a.controller.paused else a.pause()),
            item("Redact clipboard now", lambda *_: a.redact_now()),
            item("Use local LLM (thorough, slower)", lambda *_: a.set_llm(not a.config.llm_enabled),
                 checked=lambda _: a.config.llm_enabled),
            item("Retry loading model", lambda *_: a.retry(), visible=lambda _: not a.protected),
            pystray.Menu.SEPARATOR,
            item("Quit PrivateCopy", lambda icon, _item: icon.stop()),
        )

    def run(self) -> None:
        try:
            import pystray

            self._icon = pystray.Icon("PrivateCopy", make_icon(self._color()), self.app.status_line(),
                                      self._menu())
            attach_tray(self._icon)
            self._icon.run()
        except Exception as e:  # no GUI session / tray host
            print(f"Tray unavailable ({e}).")
            self._console()

    def _console(self) -> None:
        a = self.app
        print("PrivateCopy is running without a tray icon.\n"
              "Commands: [r] redact clipboard now, [t] toggle copy redaction, [s] status, [q] quit")
        try:
            while True:
                cmd = input("> ").strip().lower()
                if cmd == "r":
                    a.redact_now()
                elif cmd == "t":
                    a.set_intercept(not a.config.intercept_enabled)
                    print(a.status_line())
                elif cmd == "s":
                    print(a.status_line())
                elif cmd == "q":
                    return
        except (EOFError, KeyboardInterrupt):
            return

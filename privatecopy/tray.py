"""Tray icon + menu. Degrades to console prompt when GUI deps are missing."""
from __future__ import annotations

from collections.abc import Callable


class TrayApp:
    def __init__(self, on_copy_now: Callable[[], None], on_quit: Callable[[], None] | None = None,
                 tooltip: str = "PrivateCopy — hotkey copies redacted text"):
        self.on_copy_now = on_copy_now
        self.on_quit = on_quit or (lambda: (_ for _ in ()).throw(SystemExit(0)))
        self.tooltip = tooltip

    def _icon_image(self):
        from PIL import Image
        import os
        for candidate in (
            os.path.join("assets", "privatecopy-logo.png"),
            os.path.join(os.path.dirname(__file__), "..", "assets", "privatecopy-logo.png"),
        ):
            if os.path.exists(candidate):
                return Image.open(candidate).convert("RGB").resize((64, 64))
        from PIL import ImageDraw
        img = Image.new("RGB", (64, 64), "white")
        d = ImageDraw.Draw(img)
        d.rectangle([14, 14, 50, 50], fill="black")
        return img

    def run(self) -> None:
        try:
            import pystray

            img = self._icon_image()
            menu = pystray.Menu(
                pystray.MenuItem("PrivateCopy Now", lambda *_: self.on_copy_now()),
                pystray.MenuItem("Quit", lambda *_: (self.on_quit(), icon.stop())),
            )
            icon = pystray.Icon("PrivateCopy", img, self.tooltip, menu)
            icon.run()
        except Exception as e:
            print(f"Tray unavailable ({e}); press Enter to PrivateCopy clipboard now, Ctrl+C to quit.")
            try:
                while True:
                    input()
                    self.on_copy_now()
            except (EOFError, KeyboardInterrupt):
                self.on_quit()

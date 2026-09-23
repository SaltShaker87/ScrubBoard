# Assets

Every icon here is drawn in code by `scripts/make_icons.py` (no source artwork to keep
in sync). Change the drawing there, then regenerate:

```bash
pip install pillow
python scripts/make_icons.py
```

| File | Used by |
|------|---------|
| `scrubboard-logo.png` | README, download page (1024 px master) |
| `scrubboard-256.png` | Linux hicolor icon |
| `scrubboard-tray.png` | Tray / menu-bar icon (simplified mark; status dot added at runtime) |
| `scrubboard.ico` | Windows EXE + Inno Setup installer icon |
| `scrubboard.icns` | macOS `.app` bundle icon |
| `wizard-image.bmp` (164×314) | Inno Setup wizard sidebar |
| `wizard-small.bmp` (55×58) | Inno Setup wizard header |
| `pkg-background.png` | macOS Installer background |

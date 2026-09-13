# Assets

`privatecopy-logo.png` is the source image. The platform icons are derived from it:

```bash
pip install pillow
python scripts/make_icons.py
```

| File | Used by |
|------|---------|
| `privatecopy.ico` | Windows EXE + Inno Setup installer icon |
| `privatecopy.icns` | macOS `.app` bundle icon |
| `privatecopy-256.png` | Tray icon, Linux hicolor icon |
| `wizard-image.bmp` (164×314) | Inno Setup wizard sidebar |
| `wizard-small.bmp` (55×58) | Inno Setup wizard header |

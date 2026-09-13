# Logo source (not yet added)

Save the PrivateCopy logo image from the project chat as:

```
assets/privatecopy-logo.png
```

Then generate all platform icons:

```bash
pip install pillow
python scripts/make_icons.py
```

This produces (all committed, derived from the PNG):

| File | Used by |
|------|---------|
| `assets/privatecopy.ico` | Windows EXE + Inno Setup installer icon |
| `assets/privatecopy.icns` | macOS `.app` bundle icon |
| `assets/privatecopy-256.png` | Linux hicolor icon + fallback |
| `assets/wizard-image.bmp` (164×314) | Inno Setup wizard sidebar |
| `assets/wizard-small.bmp` (55×58) | Inno Setup wizard header |

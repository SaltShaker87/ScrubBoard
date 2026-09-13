#!/usr/bin/env python3
"""Derive all platform icons from assets/privatecopy-logo.png.

Outputs (committed):
  assets/privatecopy.ico          Windows EXE + Inno Setup
  assets/privatecopy.icns         macOS .app bundle
  assets/privatecopy-256.png      Linux hicolor 256x256
  assets/wizard-image.bmp         Inno wizard sidebar (164x314)
  assets/wizard-small.bmp         Inno wizard header (55x58)

Requires: pip install pillow
"""
from __future__ import annotations

import os
import sys

SRC = os.path.join("assets", "privatecopy-logo.png")


def main() -> int:
    if not os.path.exists(SRC):
        print(f"Missing {SRC}: save the PrivateCopy logo there first, then re-run.")
        return 1
    try:
        from PIL import Image
    except ImportError:
        print("pip install pillow, then re-run.")
        return 1

    img = Image.open(SRC).convert("RGB")

    # Windows .ico (multi-size)
    img.save(os.path.join("assets", "privatecopy.ico"),
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote assets/privatecopy.ico")

    # macOS .icns (Pillow writes icns directly)
    img.save(os.path.join("assets", "privatecopy.icns"))
    print("wrote assets/privatecopy.icns")

    # Linux 256px
    img.resize((256, 256)).save(os.path.join("assets", "privatecopy-256.png"))
    print("wrote assets/privatecopy-256.png")

    # Inno wizard images (BMP, exact sizes required by Inno Setup 6)
    img.resize((164, 314)).save(os.path.join("assets", "wizard-image.bmp"))
    img.resize((55, 58)).save(os.path.join("assets", "wizard-small.bmp"))
    print("wrote assets/wizard-image.bmp assets/wizard-small.bmp")
    return 0


if __name__ == "__main__":
    sys.exit(main())

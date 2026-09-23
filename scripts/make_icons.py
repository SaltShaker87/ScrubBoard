#!/usr/bin/env python3
"""Draw the Scrubboard logo and every platform icon from code (no source artwork).

The mark: a white clipboard on a teal tile. Its "text" lines are partly blacked out
(redaction bars), and a small sparkle means "scrubbed clean". The tray/16 px variant
drops the fine lines so it stays legible.

Outputs (committed):
  assets/scrubboard-logo.png       1024 px master (README, download page)
  assets/scrubboard-256.png        Linux hicolor icon
  assets/scrubboard-tray.png       tray icon (simplified, status dot added at runtime)
  assets/scrubboard.ico            Windows EXE + Inno Setup
  assets/scrubboard.icns           macOS .app
  assets/wizard-image.bmp          Inno wizard sidebar (164x314)
  assets/wizard-small.bmp          Inno wizard header (55x58)
  assets/pkg-background.png        macOS Installer background

Requires: pip install pillow
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
TEAL_TOP, TEAL_BOTTOM = (26, 150, 140), (12, 92, 88)
INK = (24, 38, 40)
LINE = (178, 196, 196)
CLIP = (60, 78, 82)
SPARKLE = (255, 214, 102)


def _gradient(size: tuple[int, int], top, bottom) -> Image.Image:
    w, h = size
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        grad.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)))
    return grad.resize((w, h))


def _sparkle(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill) -> None:
    """Four-point star."""
    k = r * 0.28
    d.polygon([(cx, cy - r), (cx + k, cy - k), (cx + r, cy), (cx + k, cy + k),
               (cx, cy + r), (cx - k, cy + k), (cx - r, cy), (cx - k, cy - k)], fill=fill)


def draw_logo(size: int = 1024, simple: bool = False) -> Image.Image:
    """The app icon. ``simple`` = bolder, fewer lines, for 16–32 px and the tray."""
    s = size / 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    tile = _gradient((size, size), TEAL_TOP, TEAL_BOTTOM).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    margin = 0 if simple else 64 * s  # macOS-style inset for the full icon
    ImageDraw.Draw(mask).rounded_rectangle([margin, margin, size - margin, size - margin],
                                           radius=(200 if not simple else 230) * s, fill=255)
    img.paste(tile, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # clipboard board
    bx0, by0, bx1, by1 = (250, 230, 774, 860) if not simple else (210, 190, 814, 900)
    d.rounded_rectangle([bx0 * s, by0 * s, bx1 * s, by1 * s], radius=56 * s, fill=(255, 255, 255, 255))
    # clip
    cw = 250 if not simple else 300
    cx0, cx1 = (512 - cw / 2) * s, (512 + cw / 2) * s
    d.rounded_rectangle([cx0, (by0 - 55) * s, cx1, (by0 + 60) * s], radius=36 * s, fill=CLIP)
    d.rounded_rectangle([cx0 + 70 * s, (by0 - 25) * s, cx1 - 70 * s, (by0 + 8) * s], radius=16 * s,
                        fill=(255, 255, 255, 255))

    left = (bx0 + 64) * s
    if simple:
        rows = [(390, 0.86, INK, 70), (560, 0.62, INK, 70), (730, 0.78, INK, 70)]
    else:
        rows = [(360, 0.84, LINE, 34), (440, 0.60, INK, 52), (530, 0.90, LINE, 34),
                (610, 0.46, LINE, 34), (690, 0.72, INK, 52), (780, 0.55, LINE, 34)]
    width = (bx1 - bx0 - 128) * s
    for y, frac, color, thick in rows:
        d.rounded_rectangle([left, (y - thick / 2) * s, left + width * frac, (y + thick / 2) * s],
                            radius=thick / 2 * s, fill=color)
    if not simple:
        _sparkle(d, 790 * s, 800 * s, 120 * s, SPARKLE)
        _sparkle(d, 890 * s, 690 * s, 50 * s, SPARKLE)
    return img


def _font(size: int) -> ImageFont.ImageFont:
    for path in ("/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
                 "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "C:/Windows/Fonts/segoeuib.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _centered_text(d: ImageDraw.ImageDraw, width: int, y: int, text: str, font, fill) -> None:
    w = d.textlength(text, font=font)
    d.text(((width - w) / 2, y), text, font=font, fill=fill)


def wizard_sidebar() -> Image.Image:
    w, h = 164, 314
    img = _gradient((w, h), TEAL_TOP, TEAL_BOTTOM)
    logo = draw_logo(1024).resize((112, 112), Image.LANCZOS)
    img.paste(logo, ((w - 112) // 2, 70), logo)
    d = ImageDraw.Draw(img)
    _centered_text(d, w, 196, "Scrubboard", _font(21), (255, 255, 255))
    _centered_text(d, w, 226, "clean text before", _font(12), (214, 240, 237))
    _centered_text(d, w, 242, "you paste it", _font(12), (214, 240, 237))
    return img


def wizard_small() -> Image.Image:
    img = Image.new("RGB", (55, 58), (255, 255, 255))
    logo = draw_logo(1024, simple=True).resize((48, 48), Image.LANCZOS)
    img.paste(logo, (4, 5), logo)
    return img


def pkg_background() -> Image.Image:
    """macOS Installer draws this bottom-left under the step list."""
    img = Image.new("RGBA", (620, 418), (0, 0, 0, 0))
    logo = draw_logo(1024).resize((150, 150), Image.LANCZOS)
    img.paste(logo, (18, 250), logo)
    return img


def main() -> int:
    os.makedirs(ASSETS, exist_ok=True)
    out = lambda name: os.path.join(ASSETS, name)  # noqa: E731
    full, simple = draw_logo(1024), draw_logo(1024, simple=True)

    full.save(out("scrubboard-logo.png"))
    full.resize((256, 256), Image.LANCZOS).save(out("scrubboard-256.png"))
    simple.resize((128, 128), Image.LANCZOS).save(out("scrubboard-tray.png"))

    # Windows .ico: the simple mark for small sizes, the full one for large.
    frames = [simple.resize((n, n), Image.LANCZOS) for n in (16, 24, 32)]
    frames += [full.resize((n, n), Image.LANCZOS) for n in (48, 64, 128, 256)]
    frames[-1].save(out("scrubboard.ico"), format="ICO", sizes=[f.size for f in frames],
                    append_images=frames[:-1])
    full.save(out("scrubboard.icns"))
    wizard_sidebar().save(out("wizard-image.bmp"))
    wizard_small().save(out("wizard-small.bmp"))
    pkg_background().save(out("pkg-background.png"))
    print(f"wrote icons to {os.path.normpath(ASSETS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

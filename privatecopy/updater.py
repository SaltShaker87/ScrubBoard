"""Auto-update via GitHub Releases + latest.json.

latest.json schema: {"version": "0.2.0", "notes": "...", "assets": {"windows": url, "macos": url, "linux": url}}
"""
from __future__ import annotations

import json
import platform
import urllib.request

from privatecopy import __version__

LATEST_URL = "https://github.com/YOUR_GITHUB_USER/PrivateCopy/releases/latest/download/latest.json"


def _parse(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.strip().lstrip("v").split(".") if p.isdigit())


def check_for_update(current: str = __version__, latest_url: str = LATEST_URL, timeout: int = 10) -> dict | None:
    try:
        with urllib.request.urlopen(latest_url, timeout=timeout) as r:
            data = json.load(r)
        if _parse(data.get("version", "0")) > _parse(current):
            sys = platform.system().lower()
            key = {"darwin": "macos", "windows": "windows"}.get(sys, "linux")
            data["download_url"] = (data.get("assets") or {}).get(key)
            return data
    except Exception:
        pass
    return None


def download_update(url: str, dest: str, timeout: int = 120) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest

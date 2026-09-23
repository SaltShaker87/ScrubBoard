"""Manual update check. Off unless ``update_url`` is configured — Scrubboard
never contacts the network on its own after the model download.

latest.json schema: {"version": "0.2.0", "notes": "...", "assets": {"windows": url, "macos": url, "linux": url}}
"""
from __future__ import annotations

import json
import platform
import urllib.request

from scrubboard import __version__


def _parse(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.strip().lstrip("v").split(".") if p.isdigit())


def check_for_update(latest_url: str, current: str = __version__, timeout: int = 10) -> dict | None:
    if not latest_url:
        return None
    try:
        from scrubboard.download import ssl_context
        with urllib.request.urlopen(latest_url, timeout=timeout, context=ssl_context()) as r:
            data = json.load(r)
        if _parse(data.get("version", "0")) > _parse(current):
            system = platform.system().lower()
            key = {"darwin": "macos", "windows": "windows"}.get(system, "linux")
            data["download_url"] = (data.get("assets") or {}).get(key)
            return data
    except Exception:
        pass
    return None

"""First launch. Windows and macOS users have already read the welcome text and accepted
the disclaimer in the installer. Ubuntu installs a .deb through App Center, which has no
installer screens, so the same pages are shown here with zenity (preinstalled on
Ubuntu desktop).
"""
from __future__ import annotations

import ast
import os
import platform
import shutil
import subprocess
import sys

from scrubboard import texts
from scrubboard.config import ScrubboardConfig
from scrubboard.notifications import notify

DESKTOP_ID = "scrubboard.desktop"


def first_launch(config: ScrubboardConfig) -> bool:
    """Run once per user. Returns False if the user declined the disclaimer (quit)."""
    if config.onboarding_done:
        return True
    system = platform.system()
    if system == "Linux" and not _linux_pages():
        return False
    if system == "Darwin":
        _register_login_item()
    config.onboarding_done = True
    try:
        config.save()
    except (OSError, ValueError):
        pass
    notify("Scrubboard", texts.running_notice())
    return True


# -- Linux (zenity) -----------------------------------------------------------
def _zenity(*args: str) -> int | None:
    """Run zenity; None if it isn't available (no dialog could be shown)."""
    if not shutil.which("zenity"):
        return None
    try:
        return subprocess.run(["zenity", "--width=560", *args], check=False, timeout=3600).returncode
    except (OSError, subprocess.SubprocessError):
        return None


def _linux_pages() -> bool:
    welcome = _zenity("--info", f"--title={texts.WELCOME_TITLE}", "--ok-label=Next",
                      f"--text={_markup(texts.WELCOME)}")
    if welcome is None:  # no zenity: the disclaimer is also in the help page and README
        return True
    accepted = _zenity("--question", f"--title={texts.DISCLAIMER_TITLE}", "--ok-label=I understand",
                       "--cancel-label=Quit", f"--text={_markup(texts.DISCLAIMER)}")
    if accepted != 0:
        return False
    _zenity("--info", f"--title={texts.HOW_TO_TITLE}", "--ok-label=Next",
            f"--text={_markup(texts.how_to('Linux'))}")
    if _gnome() and DESKTOP_ID not in _favorites():
        dock = _zenity("--question", "--title=Add to the dock?", "--ok-label=Add to dock",
                       "--cancel-label=No thanks",
                       "--text=Add Scrubboard to the dock on the left of your screen, so you can "
                       "start it with one click if you ever quit it?")
        if dock == 0:
            _add_favorite()
    return True


def _markup(paragraphs: list[str]) -> str:
    from html import escape
    return "\n\n".join(escape(p) for p in paragraphs)


def _gnome() -> bool:
    return "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper() and bool(shutil.which("gsettings"))


def _favorites() -> list[str]:
    try:
        out = subprocess.run(["gsettings", "get", "org.gnome.shell", "favorite-apps"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        value = ast.literal_eval(out.removeprefix("@as "))
        return [str(v) for v in value] if isinstance(value, list) else []
    except (OSError, subprocess.SubprocessError, ValueError, SyntaxError):
        return []


def _add_favorite() -> None:
    favorites = _favorites() + [DESKTOP_ID]
    subprocess.run(["gsettings", "set", "org.gnome.shell", "favorite-apps", str(favorites)],
                   check=False, timeout=5)


def enable_gnome_extension(uuid: str = "scrubboard@scrubboard.github.io") -> bool:
    """Add the extension to GNOME's enabled list (it loads at the next login).
    Returns True if it was newly enabled, i.e. the user must log out and back in."""
    if not shutil.which("gsettings"):
        return False
    try:
        out = subprocess.run(["gsettings", "get", "org.gnome.shell", "enabled-extensions"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        enabled = ast.literal_eval(out.removeprefix("@as ")) or []
        if uuid in enabled:
            return False
        subprocess.run(["gsettings", "set", "org.gnome.shell", "enabled-extensions",
                        str([*enabled, uuid])], check=False, timeout=5)
        return True
    except (OSError, subprocess.SubprocessError, ValueError, SyntaxError):
        return False


# -- macOS ------------------------------------------------------------------
def _register_login_item() -> None:
    """Start at login (macOS 13+). Only for the installed app, not a dev checkout."""
    if not getattr(sys, "frozen", False):
        return
    try:
        from ServiceManagement import SMAppService
        SMAppService.mainAppService().registerAndReturnError_(None)
    except Exception:
        pass  # older macOS or not allowed: the user can add it in System Settings

"""Cross-platform clipboard with stdlib fallbacks (pyperclip preferred)."""
from __future__ import annotations

import platform
import shutil
import subprocess


def get_text() -> str:
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except Exception:
        pass
    sys = platform.system()
    try:
        if sys == "Darwin":
            return subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5).stdout
        if sys == "Windows":
            ps = "Get-Clipboard -Raw"
            return subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                  capture_output=True, text=True, timeout=5).stdout
        for cmd in (["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]):
            if shutil.which(cmd[0]):
                return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
    except Exception:
        pass
    return ""


def set_text(text: str) -> None:
    try:
        import pyperclip
        pyperclip.copy(text)
        return
    except Exception:
        pass
    sys = platform.system()
    if sys == "Darwin":
        subprocess.run(["pbcopy"], input=text, text=True, timeout=5, check=False)
    elif sys == "Windows":
        subprocess.run(["clip"], input=text, text=True, timeout=5, check=False)
    else:
        for cmd in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
            if shutil.which(cmd[0]):
                subprocess.run(cmd, input=text, text=True, timeout=5, check=False)
                return

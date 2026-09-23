"""Real system-clipboard round trips. These overwrite the clipboard, so they only
run when SCRUBBOARD_CLIPBOARD_TESTS=1 (CI sets it; runners' clipboards are disposable)."""
import os
import threading

import pytest

from scrubboard.watchers import create_backend, detect_backend_name

pytestmark = pytest.mark.skipif(os.environ.get("SCRUBBOARD_CLIPBOARD_TESTS") != "1",
                                reason="set SCRUBBOARD_CLIPBOARD_TESTS=1 to touch the real clipboard")


def test_write_read_roundtrip():
    backend = create_backend()
    text = "Scrubboard test ünïcödé ✓ 123"
    backend.write_text(text)
    assert backend.read_text() == text


def test_watcher_reports_external_copy_and_marks_own_writes():
    if detect_backend_name() not in ("macos", "windows"):
        pytest.skip("external-copy simulation implemented for macOS/Windows only")
    backend = create_backend()
    events = []
    seen = threading.Event()

    def on_change(event):
        events.append(event)
        seen.set()

    backend.start(on_change)
    try:
        backend.write_text("own write")
        assert seen.wait(3)
        assert events[-1].own
        seen.clear()
        _external_copy("external copy")
        assert seen.wait(3)
        assert not events[-1].own
        assert events[-1].text == "external copy"
    finally:
        backend.stop()


def _external_copy(text: str) -> None:
    import subprocess
    import sys

    if sys.platform == "darwin":
        subprocess.run(["pbcopy"], input=text.encode(), check=True)
    else:
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{text}'"], check=True)

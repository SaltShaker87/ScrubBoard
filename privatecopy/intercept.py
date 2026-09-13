"""Copy interception (fail-closed).

On every clipboard change our own writes, password-manager content, excluded
apps and non-text are ignored. Otherwise the clipboard is replaced by a
placeholder at once, the text is redacted on a worker thread, and the result is
written only if the clipboard still holds our placeholder (the user may have
copied something else meanwhile). If redaction fails the clipboard stays
blocked — raw text is never put back.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable

from privatecopy.config import PrivateCopyConfig
from privatecopy.notifications import notify as _notify
from privatecopy.pipeline import NotProtectedError, RedactionResult
from privatecopy.watchers.base import ClipboardBackend, ClipboardEvent

PLACEHOLDER = "[PrivateCopy: redacting… paste again in a moment]"
FAILED = ('[PrivateCopy: redaction failed, so nothing was copied. '
          'Turn off "Redact every copy" in the tray to copy raw text.]')
OWN_PREFIX = "[PrivateCopy:"
NOTICE_INTERVAL_S = 60.0

Redactor = Callable[[str], RedactionResult]
Notifier = Callable[[str, str], None]
Reply = Callable[[dict], None]


class InterceptController:
    def __init__(self, backend: ClipboardBackend, redact: Redactor, config: PrivateCopyConfig,
                 notify: Notifier = _notify, on_result: Callable[[str], None] | None = None):
        self.backend = backend
        self.config = config
        self._redact = redact
        self._notify = notify
        self._on_result = on_result
        self._cond = threading.Condition()
        self._pending: tuple[int, str, bool] | None = None
        self._job_id = 0
        self._busy = False
        self._running = False
        self._watching = False
        self._pause_until = 0.0
        self._last_notice: dict[str, float] = {}

    # -- state -------------------------------------------------------------
    @property
    def paused(self) -> bool:
        return time.monotonic() < self._pause_until

    @property
    def enabled(self) -> bool:
        return self.config.intercept_enabled and not self.paused

    def pause(self, seconds: float) -> None:
        self._pause_until = time.monotonic() + seconds

    def resume(self) -> None:
        self._pause_until = 0.0

    def start(self, watch: bool = True) -> None:
        with self._cond:
            if not self._running:
                self._running = True
                threading.Thread(target=self._work, name="privatecopy-redact", daemon=True).start()
        if watch and not self._watching and self.backend.supports_watch:
            self.backend.start(self.on_clipboard_change)
            self._watching = True

    def stop(self) -> None:
        if self._watching:
            self.backend.stop()
            self._watching = False
        with self._cond:
            self._running = False
            self._cond.notify_all()

    def is_excluded(self, source_app: str | None) -> bool:
        if not source_app:
            return False
        app = source_app.casefold()
        return any(x.strip() and x.strip().casefold() in app for x in self.config.exclude_apps)

    def _wants(self, text: str | None, source_app: str | None) -> bool:
        return bool(text and text.strip()) and not text.startswith(OWN_PREFIX) and not self.is_excluded(source_app)

    # -- entry points ------------------------------------------------------
    def on_clipboard_change(self, event: ClipboardEvent) -> None:
        if self.enabled and not event.own and not event.concealed and self._wants(event.text, event.source_app):
            self._submit(event.text)

    def redact_now(self) -> None:
        """Tray / hotkey action: redact whatever is on the clipboard (works even
        when "Redact every copy" is off)."""
        try:
            text = self.backend.read_text()
        except Exception as e:
            self._notice(f"Could not read the clipboard ({type(e).__name__}).")
            return
        if not text or not text.strip() or text.startswith(OWN_PREFIX):
            self._notice("The clipboard has no text to redact.")
            return
        self._submit(text, announce=True)

    def handle_ipc(self, text: str, source_app: str | None, reply: Reply) -> None:
        """GNOME extension path: the extension owns the clipboard; we only redact."""
        if not self.enabled or not self._wants(text, source_app):
            reply({"status": "skip"})
            return
        reply({"status": "accepted", "placeholder": PLACEHOLDER})
        out, message, _ = self._run_redaction(text, announce=False)
        reply({"status": "done", "text": out})
        if message:
            self._notice(message)

    # -- worker ------------------------------------------------------------
    def _submit(self, text: str, announce: bool = False) -> None:
        try:
            self.backend.write_text(PLACEHOLDER, transient=True)
        except Exception as e:
            self._notice(f"Could not access the clipboard ({type(e).__name__}).")
            return
        with self._cond:
            self._job_id += 1
            self._pending = (self._job_id, text, announce)
            self._cond.notify_all()

    def wait_idle(self, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._pending is not None or self._busy:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(remaining)
        return True

    def _work(self) -> None:
        while True:
            with self._cond:
                while self._pending is None and self._running:
                    self._cond.wait()
                if not self._running:
                    return
                job_id, text, announce = self._pending
                self._pending = None
                self._busy = True
            try:
                self._process(job_id, text, announce)
            finally:
                with self._cond:
                    self._busy = False
                    self._cond.notify_all()

    def _run_redaction(self, text: str, announce: bool) -> tuple[str, str, str]:
        """Return (clipboard text, notification message, tray summary)."""
        try:
            result = self._redact(text)
        except NotProtectedError as e:
            return FAILED, f"Not protected: {e}. The clipboard was blocked.", "Not protected"
        except Exception as e:
            return FAILED, f"Redaction failed ({type(e).__name__}). The clipboard was blocked.", "Redaction failed"
        if result.llm_skipped:
            message = f"Local LLM pass skipped ({result.llm_skipped}); rules + model result used."
        elif result.truncated:
            message = f"Text longer than {self.config.max_chars:,} characters was truncated."
        elif announce:
            message = f"Redacted {result.total} item(s). Clean text is on the clipboard."
        else:
            message = ""
        return result.text, message, f"Last copy: {result.total} item(s) redacted"

    def _process(self, job_id: int, text: str, announce: bool) -> None:
        out, message, summary = self._run_redaction(text, announce)
        with self._cond:
            if job_id != self._job_id:
                return  # superseded by a newer copy
        try:
            if self.backend.read_text() != PLACEHOLDER:
                return  # the user copied something else meanwhile
            self.backend.write_text(out)
        except Exception as e:
            self._notice(f"Could not write the clipboard ({type(e).__name__}).")
            return
        if self._on_result:
            self._on_result(summary)
        if message:
            self._notice(message)

    def _notice(self, message: str) -> None:
        now = time.monotonic()
        if now - self._last_notice.get(message, float("-inf")) < NOTICE_INTERVAL_S:
            return
        self._last_notice[message] = now
        self._notify("PrivateCopy", message)

import threading

import pytest

from privatecopy.config import PrivateCopyConfig
from privatecopy.intercept import FAILED, PLACEHOLDER, InterceptController
from privatecopy.pipeline import NotProtectedError, RedactionResult
from privatecopy.watchers.base import ClipboardBackend, ClipboardEvent


class FakeBackend(ClipboardBackend):
    name = "fake"

    def __init__(self):
        self.content: str | None = None
        self.writes: list[tuple[str, bool]] = []
        self.on_change = None

    def read_text(self):
        return self.content

    def write_text(self, text, *, transient=False):
        self.content = text
        self.writes.append((text, transient))

    def start(self, on_change):
        self.on_change = on_change

    def user_copies(self, text, **kw):
        self.content = text
        self.on_change(ClipboardEvent(text, **kw))


class GatedRedactor:
    """Upper-cases text; blocks until released so tests can inspect mid-flight state."""

    def __init__(self, gate: bool = False, error: Exception | None = None):
        self.gate = threading.Event()
        if not gate:
            self.gate.set()
        self.error = error
        self.seen: list[str] = []

    def __call__(self, text):
        self.seen.append(text)
        self.gate.wait(5)
        if self.error:
            raise self.error
        return RedactionResult(text.upper(), {"X": 1}, ["rules"])


@pytest.fixture
def notes():
    return []


def make(redactor, notes, **cfg):
    backend = FakeBackend()
    ctl = InterceptController(backend, redactor, PrivateCopyConfig(**cfg),
                              notify=lambda title, msg: notes.append(msg))
    ctl.start()
    return backend, ctl


def test_placeholder_first_then_result(notes):
    red = GatedRedactor(gate=True)
    backend, ctl = make(red, notes)
    backend.user_copies("john smith")
    assert backend.content == PLACEHOLDER
    assert backend.writes[0] == (PLACEHOLDER, True)  # transient: skipped by clipboard history
    red.gate.set()
    assert ctl.wait_idle()
    assert backend.content == "JOHN SMITH"
    assert notes == []  # routine copies don't toast


def test_stale_result_is_discarded(notes):
    red = GatedRedactor(gate=True)
    backend, ctl = make(red, notes)
    backend.user_copies("first")
    backend.content = "an image the user copied meanwhile"  # non-text change, no new job
    red.gate.set()
    assert ctl.wait_idle()
    assert backend.content == "an image the user copied meanwhile"


def test_newer_copy_supersedes_older_job(notes):
    red = GatedRedactor(gate=True)
    backend, ctl = make(red, notes)
    backend.user_copies("first")
    backend.user_copies("second")
    red.gate.set()
    assert ctl.wait_idle()
    assert backend.content == "SECOND"


@pytest.mark.parametrize("error,fragment", [(RuntimeError("boom"), "Redaction failed"),
                                            (NotProtectedError("model missing"), "Not protected")])
def test_failure_keeps_clipboard_blocked(notes, error, fragment):
    backend, ctl = make(GatedRedactor(error=error), notes)
    backend.user_copies("john smith")
    assert ctl.wait_idle()
    assert backend.content == FAILED
    assert "john" not in backend.content.lower()
    assert any(fragment in n for n in notes)


@pytest.mark.parametrize("kwargs", [{"own": True}, {"concealed": True},
                                    {"source_app": "Epic Hyperspace (com.epic.hyperspace)"}])
def test_ignored_events(notes, kwargs):
    red = GatedRedactor()
    backend, ctl = make(red, notes, exclude_apps=["epic"])
    backend.user_copies("john smith", **kwargs)
    assert ctl.wait_idle()
    assert backend.writes == [] and red.seen == []


def test_status_text_and_blank_are_ignored(notes):
    red = GatedRedactor()
    backend, ctl = make(red, notes)
    backend.user_copies(PLACEHOLDER)
    backend.user_copies("   ")
    assert ctl.wait_idle()
    assert red.seen == []


def test_toggle_off_and_pause(notes):
    red = GatedRedactor()
    backend, ctl = make(red, notes, intercept_enabled=False)
    backend.user_copies("a")
    ctl.config.intercept_enabled = True
    ctl.pause(60)
    backend.user_copies("b")
    assert ctl.wait_idle()
    assert red.seen == []
    ctl.resume()
    backend.user_copies("c")
    assert ctl.wait_idle()
    assert backend.content == "C"


def test_redact_now_works_with_intercept_off(notes):
    red = GatedRedactor()
    backend, ctl = make(red, notes, intercept_enabled=False)
    backend.content = "raw text"
    ctl.redact_now()
    assert ctl.wait_idle()
    assert backend.content == "RAW TEXT"
    assert any("Redacted 1 item" in n for n in notes)


def test_ipc_handler(notes):
    backend, ctl = make(GatedRedactor(), notes)
    replies = []
    ctl.handle_ipc("john", None, replies.append)
    assert replies == [{"status": "accepted", "placeholder": PLACEHOLDER}, {"status": "done", "text": "JOHN"}]
    ctl.config.intercept_enabled = False
    replies.clear()
    ctl.handle_ipc("john", None, replies.append)
    assert replies == [{"status": "skip"}]


def test_repeated_notices_are_rate_limited(notes):
    backend, ctl = make(GatedRedactor(error=RuntimeError("x")), notes)
    for text in ("a", "b", "c"):
        backend.user_copies(text)
        assert ctl.wait_idle()
    assert len(notes) == 1

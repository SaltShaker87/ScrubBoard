"""Desktop behavior around the pipeline: one instance, bundled model lookup, the
tray's default action, first launch, and the plain-language texts."""
import os
import sys
import threading

import pytest

from scrubboard import texts
from scrubboard.app import ScrubboardApp
from scrubboard.config import ScrubboardConfig
from scrubboard.download import find_ner_dir, is_ner_downloaded
from scrubboard.models.manifest import get_ner_entry
from scrubboard.pipeline import RedactionResult
from scrubboard.single_instance import InstanceLock
from tests.test_intercept import FakeBackend


def test_second_instance_is_refused(tmp_path):
    first, second = InstanceLock(str(tmp_path / "x.lock")), InstanceLock(str(tmp_path / "x.lock"))
    assert first.acquire()
    assert not second.acquire()
    first.release()
    assert second.acquire()
    second.release()


def _fake_model(path):
    os.makedirs(path)
    for name in get_ner_entry("openmed-44m")["files"]:
        open(os.path.join(path, name), "w").close()


def test_bundled_model_is_preferred(tmp_path, monkeypatch):
    user_dir = tmp_path / "user"
    assert not is_ner_downloaded("openmed-44m", str(user_dir))
    _fake_model(tmp_path / "bundle" / "models" / "openmed-44m")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    assert find_ner_dir("openmed-44m", str(user_dir)) == str(tmp_path / "bundle" / "models" / "openmed-44m")
    assert is_ner_downloaded("openmed-44m", str(user_dir))


def test_user_download_used_without_bundle(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    _fake_model(tmp_path / "openmed-44m")
    assert find_ner_dir("openmed-44m", str(tmp_path)) == str(tmp_path / "openmed-44m")


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    notes = []
    monkeypatch.setattr("scrubboard.app.notify", lambda title, msg: notes.append(msg))
    a = ScrubboardApp(ScrubboardConfig(ner_model="none"), backend=FakeBackend())
    a.pipeline.redact = lambda text: RedactionResult(text.upper(), {"NAME": 1}, ["rules"])
    a.controller._redact = a.pipeline.redact
    a.notes = notes
    a.start()
    yield a
    a.quit()


def test_default_mode_does_not_watch(app):
    assert not app.config.intercept_enabled
    assert app.backend.on_change is None  # no clipboard watcher until auto-clean is turned on
    app.set_intercept(True)
    assert app.backend.on_change is not None


def test_services_text_is_cleaned_onto_clipboard(app):
    app.clean_text("john smith")
    assert app.controller.wait_idle()
    assert app.backend.content == "JOHN SMITH"


def test_not_ready_while_downloading(app):
    app.problem = "downloading the privacy detector (~480 MB)"
    app.backend.content = "john"
    app.redact_now()
    assert app.backend.content == "john" and any("still getting ready" in n for n in app.notes)


def test_pause_timer_does_not_block_quit(app):
    before = set(threading.enumerate())
    app.pause()
    timers = [t for t in threading.enumerate() if t not in before and isinstance(t, threading.Timer)]
    assert timers and all(t.daemon for t in timers)
    for t in timers:
        t.cancel()


def test_tray_left_click_cleans_clipboard(app):
    pystray = pytest.importorskip("pystray")
    from scrubboard.tray import TrayApp

    menu = TrayApp(app)._menu()
    defaults = [i for i in menu.items if getattr(i, "default", False)]
    assert [i.text for i in defaults] == ["Clean my clipboard"]
    assert isinstance(menu, pystray.Menu)


def test_first_launch_runs_once(monkeypatch, tmp_path):
    from scrubboard import onboarding

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(onboarding.platform, "system", lambda: "Windows")
    shown = []
    monkeypatch.setattr(onboarding, "notify", lambda title, msg: shown.append(msg))
    cfg = ScrubboardConfig()
    assert onboarding.first_launch(cfg) and cfg.onboarding_done
    assert onboarding.first_launch(cfg)
    assert len(shown) == 1 and "next to the clock" in shown[0]


def test_linux_disclaimer_decline_quits(monkeypatch, tmp_path):
    from scrubboard import onboarding

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(onboarding.platform, "system", lambda: "Linux")
    answers = iter([0, 1])  # welcome: Next; disclaimer: Quit
    monkeypatch.setattr(onboarding, "_zenity", lambda *a: next(answers))
    cfg = ScrubboardConfig()
    assert not onboarding.first_launch(cfg)
    assert not cfg.onboarding_done


@pytest.mark.parametrize("system", ["Windows", "Darwin", "Linux"])
def test_texts_cover_every_platform(system):
    steps = texts.how_to(system)
    assert any("Read it before you send it" in s for s in steps)
    assert "OpenAI" in texts.to_text(texts.WELCOME)
    assert "not perfect" in texts.to_text(texts.DISCLAIMER)
    page = texts.help_page(system)
    assert page.startswith("<!doctype html>") and "<script" not in page


def test_published_example_matches_real_output():
    """The before/after shown in the installers, help page and download page must be
    what the app really produces."""
    from scrubboard.download import is_ner_downloaded
    from scrubboard.pipeline import RedactionPipeline

    cfg = ScrubboardConfig.load()
    if not is_ner_downloaded(cfg.ner_model, cfg.models_dir):
        pytest.skip("detection model not downloaded")
    assert RedactionPipeline(cfg).redact(texts.EXAMPLE_BEFORE).text == texts.EXAMPLE_AFTER

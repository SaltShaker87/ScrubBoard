"""The daemon: tray icon, "Clean my clipboard", the macOS Services item, and optional
automatic cleaning of every copy (+ optional hotkey, local LLM)."""
from __future__ import annotations

import os
import platform
import threading
from collections.abc import Callable

from scrubboard import texts
from scrubboard.config import ScrubboardConfig, config_dir
from scrubboard.intercept import InterceptController
from scrubboard.notifications import hold_until_tray, notify
from scrubboard.pipeline import NotProtectedError, RedactionPipeline
from scrubboard.watchers.base import ClipboardBackend

PAUSE_SECONDS = 5 * 60


class ScrubboardApp:
    def __init__(self, config: ScrubboardConfig, backend: ClipboardBackend | None = None,
                 backend_name: str | None = None):
        from scrubboard.watchers import create_backend, detect_backend_name

        self.config = config
        self.backend_name = backend_name or (backend.name if backend else detect_backend_name())
        self.backend = backend or create_backend(self.backend_name)
        self.pipeline = RedactionPipeline(config)
        self.controller = InterceptController(self.backend, self.pipeline.redact, config,
                                              on_result=self._on_result)
        self.problem = ""       # why we can't clean text ("" = ready)
        self.last_result = ""
        self.llm_state = ""     # "", "downloading", "starting", or an error
        self.on_change: Callable[[], None] = lambda: None  # tray refresh hook
        self._watching = False
        self._ipc = None
        self._hotkey = None
        self._llm = None

    @property
    def protected(self) -> bool:
        return not self.problem

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> None:
        self.controller.start(watch=False)
        if self._needs_ner_download():
            self._download_ner_async()  # source installs; installers bundle the model
        elif self.check_protection():
            self._watch_if_enabled()
        if self.config.llm_enabled:
            self._enable_llm_async()
        if self.config.hotkey:
            self._start_hotkey()

    def quit(self) -> None:
        self.controller.stop()
        if self._ipc is not None:
            self._ipc.stop()
        if self._hotkey is not None:
            self._hotkey.stop()
        if self._llm is not None:
            self._llm.close()

    def check_protection(self) -> bool:
        try:
            self.pipeline.ensure_ready()
            self.problem = ""
        except NotProtectedError as e:
            self.problem = str(e)
            notify("Scrubboard", f"Scrubboard can't clean text right now: {e}. "
                                 "Try \"Retry\" in the Scrubboard menu.")
        self.on_change()
        return self.protected

    def retry(self) -> None:
        if self._needs_ner_download():
            self._download_ner_async()
        elif self.check_protection():
            self._watch_if_enabled()

    def _needs_ner_download(self) -> bool:
        from scrubboard.download import is_ner_downloaded
        return self.config.ner_model != "none" and not is_ner_downloaded(self.config.ner_model,
                                                                         self.config.models_dir)

    def _download_ner_async(self) -> None:
        def run() -> None:
            from scrubboard.download import download_ner
            from scrubboard.models.manifest import get_ner_entry

            size = get_ner_entry(self.config.ner_model)["approx_size"]
            self.problem = f"downloading the privacy detector ({size})"
            self.on_change()
            notify("Scrubboard", f"Getting ready: downloading the privacy detector ({size}). "
                                 "This happens once.")
            try:
                download_ner(self.config.ner_model, self.config.models_dir)
            except Exception as e:
                self.problem = f"the download failed ({e})"
                notify("Scrubboard", f"The download failed: {e}. Use \"Retry\" in the Scrubboard menu.")
                self.on_change()
                return
            if self.check_protection():
                self._watch_if_enabled()

        threading.Thread(target=run, name="scrubboard-ner-download", daemon=True).start()

    def _watch_if_enabled(self) -> None:
        if self.config.intercept_enabled:
            self._start_watching()

    def _start_watching(self) -> None:
        if self._watching:
            return
        try:
            if self.backend_name == "gnome":
                from scrubboard.onboarding import enable_gnome_extension
                from scrubboard.watchers.gnome_ipc import GnomeIPCServer

                self._ipc = GnomeIPCServer(self.controller.handle_ipc)
                self._ipc.start()
                if enable_gnome_extension():
                    notify("Scrubboard", "One more step for automatic cleaning: log out and back in "
                                         "once. Until then, use \"Clean my clipboard\".")
            else:
                self.controller.start(watch=True)
            self._watching = True
        except Exception as e:
            notify("Scrubboard", f"Automatic cleaning isn't available here ({e}). "
                                 "\"Clean my clipboard\" still works.")
        self.on_change()

    def _start_hotkey(self) -> None:
        try:
            from scrubboard.hotkey import HotkeyListener
            self._hotkey = HotkeyListener(self.config.hotkey, self.redact_now)
            self._hotkey.start()
        except Exception as e:
            notify("Scrubboard", f"Hotkey {self.config.hotkey} unavailable: {e}")

    # -- tray / Services actions ----------------------------------------------
    def set_intercept(self, on: bool) -> None:
        self.config.intercept_enabled = on
        self._save()
        if on and self.protected:
            self._start_watching()
        self.on_change()

    def pause(self) -> None:
        self.controller.pause(PAUSE_SECONDS)
        self.on_change()
        timer = threading.Timer(PAUSE_SECONDS + 1, self.on_change)
        timer.daemon = True  # must not keep the process alive after Quit
        timer.start()

    def resume(self) -> None:
        self.controller.resume()
        self.on_change()

    def _ready_for_request(self) -> bool:
        if self.problem.startswith("downloading"):
            notify("Scrubboard", f"Scrubboard is still getting ready ({self.problem}). Please try again soon.")
            return False
        return self.protected or self.check_protection()

    def redact_now(self) -> None:
        if self._ready_for_request():
            self.controller.redact_now()

    def clean_text(self, text: str) -> None:
        """macOS Services: clean the selected text onto the clipboard."""
        if self._ready_for_request():
            self.controller.redact_text(text)

    def open_help(self) -> None:
        import pathlib
        import webbrowser

        path = os.path.join(config_dir(), "help.html")
        try:
            os.makedirs(config_dir(), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(texts.help_page())
            webbrowser.open(pathlib.Path(path).as_uri())
        except OSError as e:
            notify("Scrubboard", f"Could not open the help page: {e}")

    def set_llm(self, on: bool) -> None:
        self.config.llm_enabled = on
        self._save()
        if on:
            self._enable_llm_async()
        else:
            self.pipeline.set_llm(None)
            if self._llm is not None:
                self._llm.close()
                self._llm = None
            self.llm_state = ""
        self.on_change()

    def _enable_llm_async(self) -> None:
        threading.Thread(target=self._enable_llm, name="scrubboard-llm-setup", daemon=True).start()

    def _enable_llm(self) -> None:
        from scrubboard.download import download_llm, is_llm_downloaded
        from scrubboard.llm import create_llm_engine
        from scrubboard.models.manifest import get_llm_entry

        cfg = self.config
        try:
            if not is_llm_downloaded(cfg.llm_model, cfg.models_dir):
                entry = get_llm_entry(cfg.llm_model)
                self.llm_state = "downloading"
                self.on_change()
                notify("Scrubboard", f"Extra-careful mode: downloading its model "
                                     f"({entry['size'] / 1e6:,.0f} MB, one time)…")
                download_llm(cfg.llm_model, cfg.models_dir)
            self.llm_state = "starting"
            self.on_change()
            engine = create_llm_engine(cfg)
            if not cfg.llm_enabled:  # toggled off while we were busy
                engine.close()
                return
            self._llm = engine
            self.pipeline.set_llm(engine)
            self.llm_state = ""
            notify("Scrubboard", "Extra-careful mode is ready.")
        except Exception as e:
            self.llm_state = f"extra-careful mode unavailable: {e}"
            notify("Scrubboard", f"Extra-careful mode isn't available: {e}")
        self.on_change()

    def _on_result(self, summary: str) -> None:
        self.last_result = summary
        self.on_change()

    def _save(self) -> None:
        try:
            self.config.save()
        except (OSError, ValueError) as e:
            notify("Scrubboard", f"Could not save settings: {e}")

    def status_line(self) -> str:
        if not self.protected:
            if self.problem.startswith("downloading"):
                return f"Getting ready: {self.problem}"
            return f"Not working: {self.problem}"
        if not self.config.intercept_enabled:
            state = "Ready: copy text, then click \"Clean my clipboard\""
        elif self.controller.paused:
            state = "Paused"
        else:
            state = "Cleaning every copy automatically"
        extra = f" ({self.llm_state})" if self.llm_state else ""
        return f"{state}{extra}"


def _pick_linux_tray_backend() -> None:
    """Ubuntu's top bar shows AppIndicator icons only; pystray's default Xorg backend is
    invisible there."""
    if platform.system() != "Linux" or "PYSTRAY_BACKEND" in os.environ:
        return
    try:
        import gi  # noqa: F401
        os.environ["PYSTRAY_BACKEND"] = "appindicator"
    except ImportError:
        pass


def run_daemon(config: ScrubboardConfig) -> int:
    from scrubboard.onboarding import first_launch
    from scrubboard.single_instance import InstanceLock

    os.environ.setdefault("HF_HUB_OFFLINE", "1")  # the daemon never downloads via HF libraries
    lock = InstanceLock()
    if not lock.acquire():
        notify("Scrubboard", texts.already_running_notice())
        return 0
    hold_until_tray()
    try:
        if config.load_warning:
            notify("Scrubboard", config.load_warning)
        if not first_launch(config):
            return 0
        _pick_linux_tray_backend()
        from scrubboard.tray import TrayApp

        app = ScrubboardApp(config)
        tray = TrayApp(app)
        if platform.system() == "Darwin":
            try:
                from scrubboard.macos_service import register
                register(app.clean_text)
            except Exception as e:
                notify("Scrubboard", f"The right-click Services item is unavailable ({type(e).__name__}).")
        app.start()
        try:
            tray.run()
        finally:
            app.quit()
        return 0
    finally:
        lock.release()

"""The daemon: tray icon + copy interception (+ optional hotkey, local LLM)."""
from __future__ import annotations

import os
import threading
from collections.abc import Callable

from privatecopy.config import PrivateCopyConfig
from privatecopy.intercept import InterceptController
from privatecopy.notifications import notify
from privatecopy.pipeline import NotProtectedError, RedactionPipeline
from privatecopy.watchers.base import ClipboardBackend

PAUSE_SECONDS = 5 * 60


class PrivateCopyApp:
    def __init__(self, config: PrivateCopyConfig, backend: ClipboardBackend | None = None,
                 backend_name: str | None = None):
        from privatecopy.watchers import create_backend, detect_backend_name

        self.config = config
        self.backend_name = backend_name or (backend.name if backend else detect_backend_name())
        self.backend = backend or create_backend(self.backend_name)
        self.pipeline = RedactionPipeline(config)
        self.controller = InterceptController(self.backend, self.pipeline.redact, config,
                                              on_result=self._on_result)
        self.problem = ""       # why we are not protected ("" = protected)
        self.last_result = ""
        self.llm_state = ""     # "", "downloading", "starting", or an error
        self.on_change: Callable[[], None] = lambda: None  # tray refresh hook
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
            self._download_ner_async()  # first start after install
        elif self.check_protection():
            self._start_watching()
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
            notify("PrivateCopy", f"Not protected: {e}. Copy interception stays off until this is fixed.")
        self.on_change()
        return self.protected

    def retry(self) -> None:
        if self._needs_ner_download():
            self._download_ner_async()
        elif self.check_protection():
            self._start_watching()

    def _needs_ner_download(self) -> bool:
        from privatecopy.download import is_ner_downloaded
        return self.config.ner_model != "none" and not is_ner_downloaded(self.config.ner_model,
                                                                         self.config.models_dir)

    def _download_ner_async(self) -> None:
        def run() -> None:
            from privatecopy.download import download_ner
            from privatecopy.models.manifest import get_ner_entry

            size = get_ner_entry(self.config.ner_model)["approx_size"]
            self.problem = f"downloading the detection model ({size})"
            self.on_change()
            notify("PrivateCopy", f"Downloading the detection model ({size}). "
                                  "Copy redaction starts when it finishes.")
            try:
                download_ner(self.config.ner_model, self.config.models_dir)
            except Exception as e:
                self.problem = f"model download failed ({e})"
                notify("PrivateCopy", f"Model download failed: {e}. Use Retry in the tray menu.")
                self.on_change()
                return
            if self.check_protection():
                self._start_watching()

        threading.Thread(target=run, name="privatecopy-ner-download", daemon=True).start()

    def _start_watching(self) -> None:
        try:
            if self.backend_name == "gnome":
                if self._ipc is None:
                    from privatecopy.watchers.gnome_ipc import GnomeIPCServer
                    self._ipc = GnomeIPCServer(self.controller.handle_ipc)
                    self._ipc.start()
            else:
                self.controller.start(watch=True)
        except Exception as e:
            self.problem = f"clipboard monitoring unavailable ({e})"
            notify("PrivateCopy", f"Copy interception unavailable: {e}")
        self.on_change()

    def _start_hotkey(self) -> None:
        try:
            from privatecopy.hotkey import HotkeyListener
            self._hotkey = HotkeyListener(self.config.hotkey, self.redact_now)
            self._hotkey.start()
        except Exception as e:
            notify("PrivateCopy", f"Hotkey {self.config.hotkey} unavailable: {e}")

    # -- tray actions --------------------------------------------------------
    def set_intercept(self, on: bool) -> None:
        self.config.intercept_enabled = on
        self._save()
        self.on_change()

    def pause(self) -> None:
        self.controller.pause(PAUSE_SECONDS)
        self.on_change()
        threading.Timer(PAUSE_SECONDS + 1, self.on_change).start()

    def resume(self) -> None:
        self.controller.resume()
        self.on_change()

    def redact_now(self) -> None:
        if self.protected or self.check_protection():
            self.controller.redact_now()

    def set_llm(self, on: bool) -> None:
        self.config.llm_enabled = on
        self._save()
        if on:
            self._enable_llm_async()
        else:
            self.pipeline.llm = None
            if self._llm is not None:
                self._llm.close()
                self._llm = None
            self.llm_state = ""
        self.on_change()

    def _enable_llm_async(self) -> None:
        threading.Thread(target=self._enable_llm, name="privatecopy-llm-setup", daemon=True).start()

    def _enable_llm(self) -> None:
        from privatecopy.download import download_llm, is_llm_downloaded
        from privatecopy.llm import create_llm_engine
        from privatecopy.models.manifest import get_llm_entry

        cfg = self.config
        try:
            if not is_llm_downloaded(cfg.llm_model, cfg.models_dir):
                entry = get_llm_entry(cfg.llm_model)
                self.llm_state = "downloading"
                self.on_change()
                notify("PrivateCopy", f"Downloading the local LLM ({entry['size'] / 1e6:,.0f} MB)…")
                download_llm(cfg.llm_model, cfg.models_dir)
            self.llm_state = "starting"
            self.on_change()
            engine = create_llm_engine(cfg)
            if not cfg.llm_enabled:  # toggled off while we were busy
                engine.close()
                return
            self._llm = engine
            self.pipeline.llm = engine
            self.llm_state = ""
            notify("PrivateCopy", "Local LLM ready.")
        except Exception as e:
            self.llm_state = f"LLM unavailable: {e}"
            notify("PrivateCopy", f"Local LLM unavailable: {e}")
        self.on_change()

    def _on_result(self, summary: str) -> None:
        self.last_result = summary
        self.on_change()

    def _save(self) -> None:
        try:
            self.config.save()
        except (OSError, ValueError) as e:
            notify("PrivateCopy", f"Could not save settings: {e}")

    def status_line(self) -> str:
        if not self.protected:
            return f"NOT PROTECTED: {self.problem}"
        engines = " + ".join(self.pipeline.engines)
        if not self.config.intercept_enabled:
            state = "Copy redaction off"
        elif self.controller.paused:
            state = "Paused"
        else:
            state = "Redacting every copy"
        extra = f" — {self.llm_state}" if self.llm_state else ""
        return f"{state} ({engines}){extra}"


def run_daemon(config: PrivateCopyConfig) -> int:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")  # the daemon never downloads via HF libraries
    if config.load_warning:
        notify("PrivateCopy", config.load_warning)
    from privatecopy.tray import TrayApp

    app = PrivateCopyApp(config)
    tray = TrayApp(app)
    app.start()
    try:
        tray.run()
    finally:
        app.quit()
    return 0

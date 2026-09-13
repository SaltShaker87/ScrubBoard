"""Core service: clipboard in -> redacted clipboard out + loopback HTTP for shims."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from privatecopy import clipboard as cb
from privatecopy.config import PrivateCopyConfig
from privatecopy.models import get_model, predict_chunked
from privatecopy.models.base import RegexFallbackModel
from privatecopy.notifications import notify
from privatecopy.redact import redact_text, truncate_text


class PrivateCopyService:
    def __init__(self, config: PrivateCopyConfig, model=None):
        self.config = config
        if model is not None:
            self._model = model
        else:
            try:
                self._model = get_model(config)
            except (FileNotFoundError, RuntimeError):
                self._model = RegexFallbackModel()

    def redact(self, text: str) -> tuple[str, int, bool]:
        clipped, was_truncated = truncate_text(text, self.config.max_chars)
        try:
            entities = predict_chunked(self._model, clipped, self.config.threshold)
        except (FileNotFoundError, RuntimeError, ImportError) as e:
            # Weights or ML deps absent (fresh install): degrade to regex
            # fallback so the pipeline stays e2e-testable. Real model is
            # used as soon as `download-model` has run.
            print(f"PrivateCopy: model unavailable ({e}); using regex fallback.")
            entities = predict_chunked(RegexFallbackModel(), clipped, self.config.threshold)
        return redact_text(clipped, entities, self.config.placeholder_style), len(entities), was_truncated

    def run_once(self, text: str | None = None) -> tuple[str, int]:
        src = text if text is not None else cb.get_text()
        if not src.strip():
            notify("PrivateCopy", "Clipboard is empty — select text first.")
            return src, 0
        clean, n, truncated = self.redact(src)
        cb.set_text(clean)
        suffix = " (truncated to 10k chars)" if truncated else ""
        notify("PrivateCopy", f"Redacted {n} item(s){suffix} — clean text on clipboard.")
        return clean, n


def serve_forever(config: PrivateCopyConfig, host: str = "127.0.0.1", port: int = 48173) -> None:
    """Loopback API so thin native shims (Automator, Explorer verb, Nautilus)
    can POST {"text": ...} without importing ML deps themselves."""
    service = PrivateCopyService(config)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
                clean, n, truncated = service.redact(payload.get("text", ""))
                body = json.dumps({"redacted": clean, "count": n, "truncated": truncated}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:  # keep daemon alive on bad input
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    httpd = HTTPServer((host, port), Handler)
    print(f"PrivateCopy service on http://{host}:{port} (model={config.model}, threshold={config.threshold})")
    httpd.serve_forever()


def serve_in_background(config: PrivateCopyConfig, **kw) -> threading.Thread:
    t = threading.Thread(target=serve_forever, args=(config,), kwargs=kw, daemon=True)
    t.start()
    return t

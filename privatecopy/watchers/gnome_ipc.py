"""Unix-socket bridge for the GNOME Shell extension. On GNOME/Wayland only the
compositor can watch the clipboard, so the extension owns the clipboard and
asks the daemon to redact. Newline-delimited JSON, one request per connection:

  -> {"text": "...", "source_app": "org.gnome.TextEditor"}
  <- {"status": "skip"}
  <- {"status": "accepted", "placeholder": "..."}  then  {"status": "done", "text": "..."}
"""
from __future__ import annotations

import json
import os
import socket
import struct
import tempfile
import threading
from collections.abc import Callable

MAX_REQUEST_BYTES = 4 * 1024 * 1024

Reply = Callable[[dict], None]
Handler = Callable[[str, "str | None", Reply], None]


def socket_path() -> str:
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir(), "privatecopy.sock")


def _same_user(conn: socket.socket) -> bool:
    peercred = getattr(socket, "SO_PEERCRED", None)
    if peercred is None:
        return True  # non-Linux: the 0600 socket permissions still apply
    creds = conn.getsockopt(socket.SOL_SOCKET, peercred, struct.calcsize("3i"))
    _pid, uid, _gid = struct.unpack("3i", creds)
    return uid == os.getuid()


class GnomeIPCServer:
    def __init__(self, handler: Handler, path: str | None = None):
        self.handler = handler
        self.path = path or socket_path()
        self._sock: socket.socket | None = None

    def start(self) -> None:
        if os.path.exists(self.path):
            os.unlink(self.path)  # stale socket from a previous run
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        old_umask = os.umask(0o177)
        try:
            sock.bind(self.path)
        finally:
            os.umask(old_umask)
        os.chmod(self.path, 0o600)
        sock.listen(8)
        self._sock = sock
        threading.Thread(target=self._serve, name="privatecopy-gnome-ipc", daemon=True).start()

    def stop(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None
        if os.path.exists(self.path):
            os.unlink(self.path)

    def _serve(self) -> None:
        sock = self._sock
        while sock is not None:
            try:
                conn, _ = sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket) -> None:
        with conn:
            if not _same_user(conn):
                return
            conn.settimeout(120)
            data = b""
            try:
                while not data.endswith(b"\n"):
                    chunk = conn.recv(65536)
                    if not chunk or len(data) + len(chunk) > MAX_REQUEST_BYTES:
                        return
                    data += chunk
                req = json.loads(data)
            except (OSError, ValueError):
                return
            text = req.get("text") if isinstance(req, dict) else None
            if not isinstance(text, str):
                return
            source = req.get("source_app")

            def reply(msg: dict) -> None:
                conn.sendall((json.dumps(msg) + "\n").encode("utf-8"))

            try:
                self.handler(text, source if isinstance(source, str) else None, reply)
            except OSError:
                pass

"""llama.cpp `llama-server` child process bound to 127.0.0.1.

Started on first use, protected by a random API key (passed via the
environment, not argv), health-checked, and stopped after ``idle_unload_s``
seconds without requests so its RAM is returned to the system.
"""
from __future__ import annotations

import http.client
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time

from scrubboard.config import config_dir


def server_exe_name() -> str:
    return "llama-server.exe" if platform.system() == "Windows" else "llama-server"


def default_install_dir() -> str:
    return os.path.join(config_dir(), "llama")


def find_llama_server(override: str = "") -> str | None:
    """Bundled binary first (installer layout), then the dev download dir, then PATH."""
    if override:
        return override if os.path.isfile(override) else None
    exe = server_exe_name()
    candidates = [os.path.join(getattr(sys, "_MEIPASS", ""), "llama", exe),
                  os.path.join(os.path.dirname(sys.executable), "llama", exe),
                  os.path.join(default_install_dir(), exe)]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return shutil.which(exe)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ChatClient:
    """Minimal streaming client for llama-server's OpenAI-compatible API.
    Streaming lets us enforce the deadline between tokens, and closing the
    connection makes the server stop generating."""

    def __init__(self, host: str, port: int, api_key: str):
        self.host, self.port, self.api_key = host, port, api_key

    def health(self, timeout: float = 1.0) -> bool:
        conn = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        try:
            conn.request("GET", "/health")
            return conn.getresponse().status == 200
        except OSError:
            return False
        finally:
            conn.close()

    def chat(self, payload: dict, deadline: float) -> str:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("LLM deadline reached")
        body = json.dumps({**payload, "stream": True}).encode("utf-8")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        conn = http.client.HTTPConnection(self.host, self.port, timeout=remaining)
        try:
            conn.request("POST", "/v1/chat/completions", body, headers)
            resp = conn.getresponse()
            if resp.status != 200:
                raise RuntimeError(f"llama-server returned HTTP {resp.status}")
            parts: list[str] = []
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("LLM deadline reached")
                if conn.sock is not None:
                    conn.sock.settimeout(remaining)
                line = resp.readline()
                if not line:
                    break
                line = line.strip()
                if not line.startswith(b"data:"):
                    continue
                data = line[5:].strip()
                if data == b"[DONE]":
                    break
                for choice in json.loads(data).get("choices", []):
                    content = (choice.get("delta") or {}).get("content")
                    if content:
                        parts.append(content)
            return "".join(parts)
        finally:
            conn.close()


class LlamaServer:
    def __init__(self, command: list[str], model_path: str, ctx_size: int, idle_unload_s: float = 600,
                 threads: int | None = None, startup_timeout: float = 120, idle_check_s: float = 15):
        self.command = command
        self.model_path = model_path
        self.ctx_size = ctx_size
        self.idle_unload_s = idle_unload_s
        self.threads = threads or _physical_cores()
        self.startup_timeout = startup_timeout
        self.port: int | None = None
        self._api_key = secrets.token_urlsafe(24)
        self._client: ChatClient | None = None
        self._proc: subprocess.Popen | None = None
        self._ready = False
        self._last_used = 0.0
        self._lock = threading.RLock()
        self._closed = threading.Event()
        self._log_file = None
        if idle_unload_s:
            threading.Thread(target=self._idle_loop, args=(idle_check_s,), name="scrubboard-llm-idle",
                             daemon=True).start()

    @property
    def pid(self) -> int | None:
        proc = self._proc
        return proc.pid if proc is not None and proc.poll() is None else None

    def _open_log(self) -> None:
        log_dir = config_dir()
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "llama-server.log")
        self._log_file = open(log_path, "w", encoding="utf-8")

    def _close_log(self) -> None:
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None

    def _spawn(self) -> None:
        self.port = _free_port()
        self._client = ChatClient("127.0.0.1", self.port, self._api_key)
        args = [*self.command, "-m", self.model_path, "--host", "127.0.0.1", "--port", str(self.port),
                "-c", str(self.ctx_size), "-np", "1", "-t", str(self.threads), "--no-webui", "--offline"]
        env = {**os.environ, "LLAMA_API_KEY": self._api_key}
        flags = 0x08000000 if platform.system() == "Windows" else 0  # CREATE_NO_WINDOW
        self._close_log()
        self._open_log()
        self._proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                      stderr=self._log_file, env=env, creationflags=flags)
        self._ready = False

    def ensure_running(self, deadline: float | None = None) -> None:
        """Start the server if needed and wait until it has loaded the model.
        With a deadline, raise TimeoutError instead of waiting past it (the
        server keeps loading, so the next request is fast)."""
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._spawn()
            self._last_used = time.monotonic()
            if self._ready:
                return
            limit = deadline if deadline is not None else time.monotonic() + self.startup_timeout
            assert self._client is not None and self._proc is not None
            while True:
                if self._proc.poll() is not None:
                    code = self._proc.returncode
                    self._proc = None
                    raise RuntimeError(f"llama-server exited with code {code}")
                if self._client.health():
                    self._ready = True
                    return
                if time.monotonic() >= limit:
                    raise TimeoutError("llama-server is still loading the model")
                time.sleep(0.2)

    def chat(self, payload: dict, deadline: float) -> str:
        self.ensure_running(deadline)
        assert self._client is not None
        try:
            return self._client.chat(payload, deadline)
        finally:
            self._last_used = time.monotonic()

    def stop(self) -> None:
        with self._lock:
            proc, self._proc, self._ready = self._proc, None, False
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(5)
            self._close_log()

    def close(self) -> None:
        self._closed.set()
        self.stop()
        self._close_log()

    def _idle_loop(self, check_s: float) -> None:
        while not self._closed.wait(check_s):
            with self._lock:
                idle = time.monotonic() - self._last_used
                if self._proc is not None and idle > self.idle_unload_s:
                    self.stop()


def _physical_cores() -> int:
    try:
        import psutil
        return psutil.cpu_count(logical=False) or os.cpu_count() or 4
    except ImportError:
        return os.cpu_count() or 4

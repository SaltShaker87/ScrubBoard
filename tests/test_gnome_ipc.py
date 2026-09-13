import json
import os
import shutil
import socket
import stat
import sys
import tempfile

import pytest

from privatecopy.watchers.gnome_ipc import GnomeIPCServer

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Unix sockets only")


@pytest.fixture
def sock_path():
    d = tempfile.mkdtemp(dir="/tmp")  # short path: AF_UNIX paths are limited to ~104 bytes
    yield os.path.join(d, "pc.sock")
    shutil.rmtree(d, ignore_errors=True)


def request(path, payload: bytes) -> list[dict]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as c:
        c.connect(path)
        c.sendall(payload)
        data = b""
        while chunk := c.recv(65536):
            data += chunk
    return [json.loads(line) for line in data.decode().splitlines()]


def test_roundtrip_and_permissions(sock_path):
    def handler(text, source, reply):
        reply({"status": "accepted"})
        reply({"status": "done", "text": text.upper(), "source": source})

    server = GnomeIPCServer(handler, sock_path)
    server.start()
    try:
        assert stat.S_IMODE(os.stat(sock_path).st_mode) == 0o600
        msgs = request(sock_path, json.dumps({"text": "john", "source_app": "gedit"}).encode() + b"\n")
        assert msgs == [{"status": "accepted"}, {"status": "done", "text": "JOHN", "source": "gedit"}]
        assert request(sock_path, b"not json\n") == []
    finally:
        server.stop()
    assert not os.path.exists(sock_path)

"""One Scrubboard per user session. Opening it from the desktop shortcut while the
start-at-login copy runs must not start a second tray icon and clipboard watcher."""
from __future__ import annotations

import os
import platform

from scrubboard.config import config_dir


class InstanceLock:
    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(config_dir(), "scrubboard.lock")
        self._fh = None

    def acquire(self) -> bool:
        """True if this process is now the only instance. The OS drops the lock when
        the process exits, so a crash never leaves a stale lock behind."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fh = open(self.path, "a+")  # noqa: SIM115 (held open for the process lifetime)
        try:
            if platform.system() == "Windows":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._fh = fh
        return True

    def release(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

"""Clipboard backend interface shared by the per-OS implementations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class ClipboardEvent:
    """One clipboard change. ``text`` is None for non-text content (and is not
    read at all for our own or concealed content)."""
    text: str | None = field(repr=False)
    own: bool = False        # written by Scrubboard
    concealed: bool = False  # password manager / "don't monitor" marker
    source_app: str | None = None


OnChange = Callable[[ClipboardEvent], None]


class ClipboardBackend(ABC):
    name = "base"
    supports_watch = True

    @abstractmethod
    def read_text(self) -> str | None:
        ...

    @abstractmethod
    def write_text(self, text: str, *, transient: bool = False) -> None:
        """Replace the whole clipboard (every format) with ``text`` and mark it
        as Scrubboard's own. ``transient`` asks clipboard-history tools to skip it."""

    def start(self, on_change: OnChange) -> None:
        raise NotImplementedError(f"{self.name} backend cannot watch the clipboard")

    def stop(self) -> None:
        return None

"""Shared model interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from privatecopy.redact import Entity


class PIIModel(ABC):
    name: str = "base"
    default_threshold: float = 0.5

    def load(self) -> None:
        """Load weights eagerly. Raises FileNotFoundError / RuntimeError when the
        model can't run, so callers can fail closed before any redaction."""
        return None

    @abstractmethod
    def predict(self, text: str, threshold: float = 0.5) -> list[Entity]:
        """Detect entities over the *whole* text (implementations window it)."""

    @property
    @abstractmethod
    def labels(self) -> list[str]:
        ...

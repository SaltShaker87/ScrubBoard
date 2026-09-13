"""Shared model interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from privatecopy.redact import Entity


class PIIModel(ABC):
    name: str = "base"

    @abstractmethod
    def predict(self, text: str, threshold: float = 0.5) -> list[Entity]:
        ...

    @property
    @abstractmethod
    def labels(self) -> list[str]:
        ...


class RegexFallbackModel(PIIModel):
    """Tiny offline fallback used in tests / when ONNX weights are absent.

    Detects email / phone / ssn-ish patterns so the pipeline is e2e-testable
    without downloading 500MB weights.
    """

    name = "regex-fallback"

    def __init__(self) -> None:
        import re
        self._pats = [
            ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
            ("PHONE_NUMBER", re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")),
            ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
        ]

    @property
    def labels(self) -> list[str]:
        return [label for label, _ in self._pats]

    def predict(self, text: str, threshold: float = 0.5) -> list[Entity]:
        del threshold
        out: list[Entity] = []
        for label, rx in self._pats:
            for m in rx.finditer(text):
                out.append(Entity(m.start(), m.end(), label, 1.0, m.group(0)))
        return sorted(out, key=lambda e: e.start)

"""Offset-safe redaction primitives. No ML here — pure text ops, fully tested."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


def normalize_label(label: str) -> str:
    return label.strip().upper().replace(" ", "_").replace("-", "_")


@dataclass
class Entity:
    start: int
    end: int
    label: str
    score: float = 1.0
    text: str = field(default="", repr=False)  # may hold PHI: never logged
    source: str = ""

    def __post_init__(self) -> None:
        self.label = normalize_label(self.label)
        if not (0 <= self.start < self.end):
            raise ValueError(f"bad span: start={self.start} end={self.end} label={self.label}")


Renderer = Callable[[Entity, str], str]


def truncate_text(text: str, max_chars: int = 20_000) -> tuple[str, bool]:
    """Return (possibly truncated text, was_truncated)."""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def resolve_overlaps(entities: list[Entity]) -> list[Entity]:
    """Merge overlapping spans into their union.

    Redaction must never leave part of a detected span visible, so overlaps are
    unioned rather than dropped. The merged span takes the label of the
    higher-scoring (then longer) member.
    """
    merged: list[Entity] = []
    for ent in sorted(entities, key=lambda e: (e.start, -e.end)):
        if merged and ent.start < merged[-1].end:
            cur = merged[-1]
            best = cur if (cur.score, cur.end - cur.start) >= (ent.score, ent.end - ent.start) else ent
            merged[-1] = Entity(cur.start, max(cur.end, ent.end), best.label,
                                max(cur.score, ent.score), source=best.source)
        else:
            merged.append(ent)
    return merged


def expand_to_word_boundaries(text: str, entities: list[Entity]) -> list[Entity]:
    """Grow spans that start/end mid-word (sub-word tokens) to whole words and
    trim surrounding whitespace, so no fragment of an identifier survives."""
    out: list[Entity] = []
    n = len(text)
    for ent in entities:
        s, e = ent.start, min(ent.end, n)
        if s >= e:
            continue
        while s > 0 and text[s - 1].isalnum() and text[s].isalnum():
            s -= 1
        while e < n and text[e].isalnum() and text[e - 1].isalnum():
            e += 1
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if s < e:
            out.append(Entity(s, e, ent.label, ent.score, source=ent.source))
    return out


def placeholder_for(label: str, style: str = "[LABEL]") -> str:
    if style == "[REDACTED]":
        return "[REDACTED]"
    if style == "BLOCK":
        return "███"
    return f"[{normalize_label(label)}]"  # "[LABEL]" default


def redact_text(text: str, entities: list[Entity], style: str = "[LABEL]",
                render: Renderer | None = None) -> str:
    """Replace entity spans with placeholders. Offsets refer to *original* text.

    ``render(entity, original_span)`` may supply the replacement (used for the
    Safe Harbor transforms); otherwise ``placeholder_for`` is used.
    """
    parts: list[str] = []
    pos = 0
    for ent in resolve_overlaps(list(entities)):
        s, e = max(ent.start, pos), min(len(text), ent.end)
        if s >= e:
            continue
        parts.append(text[pos:s])
        parts.append(render(ent, text[s:e]) if render else placeholder_for(ent.label, style))
        pos = e
    parts.append(text[pos:])
    return "".join(parts)

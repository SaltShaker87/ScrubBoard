"""Offset-safe redaction primitives. No ML here — pure text ops, fully tested."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Entity:
    start: int
    end: int
    label: str
    score: float = 1.0
    text: str = ""

    def __post_init__(self) -> None:
        self.label = self.label.strip().upper().replace(" ", "_")
        if not (0 <= self.start < self.end):
            raise ValueError(f"bad span: {self!r}")


def truncate_text(text: str, max_chars: int = 10_000) -> tuple[str, bool]:
    """Return (possibly truncated text, was_truncated)."""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def resolve_overlaps(entities: list[Entity]) -> list[Entity]:
    """Drop spans fully contained in a higher-scoring span; clip partial overlaps.

    Deterministic: sort by (start, -score, -length).
    """
    ordered = sorted(entities, key=lambda e: (e.start, -e.score, -(e.end - e.start)))
    kept: list[Entity] = []
    for ent in ordered:
        conflict = False
        for k in kept:
            if ent.start >= k.start and ent.end <= k.end:
                conflict = True  # fully inside a better span
                break
            if ent.start < k.end and ent.end > k.start:
                # partial overlap: shrink current entity to non-overlapping part
                if ent.start < k.start:
                    ent = Entity(k.end if k.end > ent.start else ent.start, ent.end,
                                 ent.label, ent.score, ent.text)
                    if ent.start >= ent.end:
                        conflict = True
                        break
                else:
                    conflict = True
                    break
        if not conflict and ent.start < ent.end:
            kept.append(ent)
    return sorted(kept, key=lambda e: e.start)


def placeholder_for(label: str, style: str = "[LABEL]") -> str:
    if style == "[REDACTED]":
        return "[REDACTED]"
    if style == "BLOCK":
        return "███"
    return f"[{label.strip().upper().replace(' ', '_')}]"  # "[LABEL]" default


def redact_text(text: str, entities: list[Entity], style: str = "[LABEL]") -> str:
    """Replace entity spans with placeholders. Offsets refer to *original* text."""
    resolved = resolve_overlaps(list(entities))
    out = text
    for ent in sorted(resolved, key=lambda e: e.start, reverse=True):
        s, e = max(0, ent.start), min(len(out), ent.end)
        if s >= e:
            continue
        out = out[:s] + placeholder_for(ent.label, style) + out[e:]
    return out

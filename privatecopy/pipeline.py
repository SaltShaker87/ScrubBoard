"""Redaction pipeline: Safe Harbor rules + NER (+ optional LLM) -> policy ->
word-boundary expansion -> span union -> Safe Harbor rendering.

There is no silent fallback: if the configured NER model can't run,
``NotProtectedError`` is raised and nothing is written anywhere.
"""
from __future__ import annotations

import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from privatecopy.config import PrivateCopyConfig
from privatecopy.models.base import PIIModel
from privatecopy.redact import Entity, expand_to_word_boundaries, redact_text, resolve_overlaps, truncate_text
from privatecopy.safe_harbor import SafeHarborPolicy, SafeHarborRules

TRUNCATION_MARKER = "\n[PrivateCopy: truncated at {n} characters]"


class NotProtectedError(RuntimeError):
    """The configured detection engine is unavailable; nothing was redacted."""


class LLMEngine(Protocol):
    name: str

    def predict(self, text: str, deadline: float) -> list[Entity]:
        """Detect entities; raise TimeoutError once time.monotonic() passes deadline."""


@dataclass
class RedactionResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)
    engines: list[str] = field(default_factory=list)
    llm_skipped: str = ""  # why the LLM pass didn't contribute ("" = ran or disabled)
    truncated: bool = False

    @property
    def total(self) -> int:
        return sum(self.counts.values())


class RedactionPipeline:
    def __init__(self, config: PrivateCopyConfig, ner: PIIModel | None = None,
                 llm: LLMEngine | None = None):
        self.config = config
        self.rules = SafeHarborRules()
        self.llm = llm
        self._ner = ner
        self._ner_loaded = ner is not None
        self._lock = threading.Lock()

    def ensure_ready(self) -> None:
        """Load the NER model once; raise NotProtectedError if it can't run."""
        if self.config.ner_model == "none" or self._ner_loaded:
            return
        from privatecopy.models import load_ner
        try:
            self._ner = load_ner(self.config)
        except (FileNotFoundError, RuntimeError, ImportError, OSError) as e:
            raise NotProtectedError(f"{self.config.ner_model} is unavailable: {e}") from e
        self._ner_loaded = True

    @property
    def engines(self) -> list[str]:
        names = ["rules"]
        if self._ner is not None:
            names.append(self._ner.name)
        if self.config.llm_enabled and self.llm is not None:
            names.append(self.llm.name)
        return names

    def redact(self, text: str) -> RedactionResult:
        with self._lock:
            self.ensure_ready()
            cfg = self.config
            clipped, truncated = truncate_text(text, cfg.max_chars)
            entities = self.rules.predict(clipped)
            engines = ["rules"]
            if self._ner is not None:
                threshold = cfg.threshold if cfg.threshold is not None else self._ner.default_threshold
                entities += self._ner.predict(clipped, threshold)
                engines.append(self._ner.name)
            llm_skipped = ""
            if cfg.llm_enabled:
                if self.llm is None:
                    llm_skipped = "local LLM not available"
                else:
                    try:
                        entities += self.llm.predict(clipped, deadline=time.monotonic() + cfg.llm_timeout_s)
                        engines.append(self.llm.name)
                    except TimeoutError:
                        llm_skipped = f"timed out after {cfg.llm_timeout_s:g}s"
                    except Exception as e:  # LLM is additive; rules+NER already cover the text
                        llm_skipped = f"error ({type(e).__name__})"

            policy = SafeHarborPolicy(keep_year=cfg.keep_year, keep_zip3=cfg.keep_zip3,
                                      extra_keep_labels=cfg.extra_keep_labels,
                                      style=cfg.placeholder_style)
            spans = resolve_overlaps(expand_to_word_boundaries(clipped, policy.filter(clipped, entities)))
            out = redact_text(clipped, spans, render=policy.render)
            if truncated:
                out += TRUNCATION_MARKER.format(n=cfg.max_chars)
            return RedactionResult(out, dict(Counter(e.label for e in spans)), engines,
                                   llm_skipped, truncated)

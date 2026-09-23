"""NVIDIA GLiNER-PII via the optional `gliner` package (pip install 'scrubboard[gliner]')."""
from __future__ import annotations

import os
import re

from scrubboard.models.base import PIIModel
from scrubboard.models.manifest import GLINER_LABELS
from scrubboard.redact import Entity

# GLiNER truncates at 384 words; stay well under and overlap the windows so no
# text is ever skipped.
WINDOW_WORDS = 300
STRIDE_WORDS = 250


class GlinerModel(PIIModel):
    name = "nvidia-gliner"
    default_threshold = 0.3  # NVIDIA's reported evaluation threshold

    def __init__(self, model_dir: str):
        self.model_dir = model_dir
        self._model = None

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            from gliner import GLiNER
        except ImportError as e:
            raise RuntimeError("nvidia-gliner needs the gliner package: pip install 'scrubboard[gliner]'") from e
        if not (os.path.isdir(self.model_dir) and os.listdir(self.model_dir)):
            raise FileNotFoundError(f"GLiNER weights not found in {self.model_dir}. "
                                    "Run: scrubboard download-model --ner nvidia-gliner")
        self._model = GLiNER.from_pretrained(self.model_dir)

    @property
    def labels(self) -> list[str]:
        return list(GLINER_LABELS)

    def predict(self, text: str, threshold: float = 0.3) -> list[Entity]:
        self.load()
        assert self._model is not None
        words = list(re.finditer(r"\S+", text))
        out: list[Entity] = []
        for i in range(0, max(len(words), 1), STRIDE_WORDS):
            window = words[i:i + WINDOW_WORDS]
            if not window:
                break
            offset = window[0].start()
            chunk = text[offset:window[-1].end()]
            for r in self._model.predict_entities(chunk, GLINER_LABELS, threshold=threshold):
                s, e = offset + int(r["start"]), offset + int(r["end"])
                if s < e:
                    out.append(Entity(s, e, str(r["label"]), float(r.get("score", 1.0)),
                                      source=self.name))
            if i + WINDOW_WORDS >= len(words):
                break
        return out

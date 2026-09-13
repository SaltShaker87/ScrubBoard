"""Model factory + sliding-window chunking for long selections."""
from __future__ import annotations

import os

from privatecopy.config import PrivateCopyConfig
from privatecopy.models.base import PIIModel, RegexFallbackModel
from privatecopy.models.gliner import GlinerONNXModel
from privatecopy.models.manifest import get_entry
from privatecopy.models.openmed import OpenMedONNXModel
from privatecopy.redact import Entity


def get_model(config: PrivateCopyConfig, allow_fallback: bool = False) -> PIIModel:
    get_entry(config.model)  # validates id
    model_dir = os.path.join(config.models_dir, config.model)
    try:
        if config.model == "nvidia-gliner":
            return GlinerONNXModel(model_dir)
        return OpenMedONNXModel(model_dir)
    except (FileNotFoundError, RuntimeError):
        if allow_fallback:
            return RegexFallbackModel()
        raise


def predict_chunked(model: PIIModel, text: str, threshold: float,
                    window: int = 4000, overlap: int = 400) -> list[Entity]:
    """Slide a char window so 10k-char inputs don't blow model context.

    Keeps entities fully inside a window (drops edge-clipped spans, re-found
    in the neighboring window thanks to overlap).
    """
    if len(text) <= window:
        return model.predict(text, threshold)
    out: list[Entity] = []
    step = window - overlap
    for start in range(0, len(text), step):
        chunk = text[start:start + window]
        for ent in model.predict(chunk, threshold):
            gs, ge = ent.start + start, ent.end + start
            if ent.start == 0 and start > 0:
                continue  # likely clipped on the left; next window has it whole
            if ent.end == len(chunk) and start + window < len(text):
                continue  # clipped on the right
            out.append(Entity(gs, ge, ent.label, ent.score, text[gs:ge]))
    return sorted(out, key=lambda e: e.start)

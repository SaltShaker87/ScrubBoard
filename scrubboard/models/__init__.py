"""NER model factory. Imports are lazy so the ML deps load only when used."""
from __future__ import annotations

from scrubboard.config import ScrubboardConfig
from scrubboard.models.base import PIIModel
from scrubboard.models.manifest import get_ner_entry


def ner_model_dir(config: ScrubboardConfig) -> str:
    from scrubboard.download import find_ner_dir
    return find_ner_dir(config.ner_model, config.models_dir)


def load_ner(config: ScrubboardConfig) -> PIIModel | None:
    """Return the loaded NER model, or None for the explicit rules-only mode.

    Raises FileNotFoundError / RuntimeError when the configured model can't run.
    """
    if config.ner_model == "none":
        return None
    entry = get_ner_entry(config.ner_model)
    model_dir = ner_model_dir(config)
    model: PIIModel
    if config.ner_model == "openmed-44m":
        from scrubboard.models.openmed import OpenMedONNXModel
        model = OpenMedONNXModel(model_dir, onnx_file=entry["onnx_file"],
                                 max_tokens=entry["max_tokens"])
    else:
        from scrubboard.models.gliner import GlinerModel
        model = GlinerModel(model_dir)
    model.load()
    return model

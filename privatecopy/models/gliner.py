"""NVIDIA GLiNER-PII via the `gliner` library (PyTorch or pre-exported ONNX)."""
from __future__ import annotations

import os

from privatecopy.models.base import PIIModel
from privatecopy.models.manifest import GLINER_LABELS
from privatecopy.redact import Entity


class GlinerONNXModel(PIIModel):
    name = "nvidia-gliner"

    def __init__(self, model_dir: str, use_onnx: bool = True):
        self.model_dir = model_dir
        self.use_onnx = use_onnx
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from gliner import GLiNER
        except ImportError as e:
            raise RuntimeError(
                "nvidia-gliner needs the gliner package. pip install 'privatecopy[gliner]'"
            ) from e
        onnx_path = os.path.join(self.model_dir, "model.onnx")
        if self.use_onnx and os.path.exists(onnx_path):
            self._model = GLiNER.from_pretrained(
                self.model_dir, runtime="onnxruntime", runtime_model_file="model.onnx")
        elif os.path.isdir(self.model_dir) and os.listdir(self.model_dir):
            self._model = GLiNER.from_pretrained(self.model_dir)
        else:
            raise FileNotFoundError(
                f"GLiNER weights not found in {self.model_dir}. "
                "Run: python scripts/download_models.py --model nvidia-gliner"
            )

    @property
    def labels(self) -> list[str]:
        return list(GLINER_LABELS)

    def predict(self, text: str, threshold: float = 0.5) -> list[Entity]:
        self._ensure_loaded()
        assert self._model is not None
        raw = self._model.predict_entities(text, GLINER_LABELS, threshold=threshold)
        return [Entity(int(r["start"]), int(r["end"]), str(r["label"]),
                       float(r.get("score", 1.0)), r.get("text", "")) for r in raw]

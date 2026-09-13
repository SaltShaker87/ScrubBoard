"""OpenMed 44M (DeBERTa-v3-small token-classification) via ONNX Runtime.

Requires at build/download time: transformers, optimum[onnx], torch (for export).
At inference time only: onnxruntime + tokenizers + exported model dir.
"""
from __future__ import annotations

import os

from privatecopy.models.base import PIIModel
from privatecopy.redact import Entity


class OpenMedONNXModel(PIIModel):
    name = "openmed-44m"

    def __init__(self, model_dir: str):
        self.model_dir = model_dir
        self._session = None
        self._tokenizer = None
        self._id2label: dict[int, str] = {}

    def _ensure_loaded(self) -> None:
        if self._session is not None:
            return
        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer
        except ImportError as e:
            raise RuntimeError(
                "openmed-44m needs onnxruntime + transformers. "
                "pip install 'privatecopy[openmed]' or run scripts/download_models.py"
            ) from e
        onnx_path = os.path.join(self.model_dir, "model.onnx")
        if not os.path.exists(onnx_path):
            raise FileNotFoundError(
                f"ONNX model not found at {onnx_path}. Run: python scripts/download_models.py --model openmed-44m"
            )
        import json
        cfg = os.path.join(self.model_dir, "config.json")
        if os.path.exists(cfg):
            with open(cfg, encoding="utf-8") as f:
                self._id2label = {int(k): v for k, v in json.load(f).get("id2label", {}).items()}
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_dir)
        providers = ["CPUExecutionProvider"]
        self._session = ort.InferenceSession(onnx_path, providers=providers)

    @property
    def labels(self) -> list[str]:
        return sorted(set(self._id2label.values())) if self._id2label else ["*"]

    def predict(self, text: str, threshold: float = 0.5) -> list[Entity]:
        import numpy as np

        self._ensure_loaded()
        assert self._tokenizer is not None and self._session is not None
        # Simple single-chunk path; chunking for >384 tokens handled by caller windowing
        enc = self._tokenizer(text, return_tensors="np", truncation=True, max_length=384,
                              return_offsets_mapping=True)
        offsets = enc.pop("offset_mapping")[0]
        ort_inputs = {k: v for k, v in enc.items() if k in {i.name for i in self._session.get_inputs()}}
        logits = self._session.run(None, {k: np.asarray(v) for k, v in ort_inputs.items()})[0][0]
        exp = np.exp(logits - logits.max(axis=-1, keepdims=True))
        probs = exp / exp.sum(axis=-1, keepdims=True)
        pred_ids = probs.argmax(axis=-1)
        out: list[Entity] = []
        for idx, (pid, (s, e)) in enumerate(zip(pred_ids, offsets)):
            if s == e == 0:
                continue
            label = self._id2label.get(int(pid), f"LABEL_{pid}")
            if label.upper() == "O":
                continue
            clean = label[2:] if label[:2] in ("B-", "I-") else label
            score = float(probs[idx, int(pid)])
            if score < threshold:
                continue
            # Merge I- continuation into previous span
            if label.startswith("I-") and out and out[-1].label == clean.upper() and out[-1].end == int(s):
                prev = out[-1]
                out[-1] = Entity(prev.start, int(e), prev.label, min(prev.score, score), text[prev.start:int(e)])
            else:
                out.append(Entity(int(s), int(e), clean, score, text[int(s):int(e)]))
        return out

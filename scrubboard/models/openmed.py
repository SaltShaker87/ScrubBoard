"""OpenMed PII (DeBERTa-v3 token classification) on ONNX Runtime + tokenizers.

No torch/transformers at inference. Long inputs are split into overlapping
token windows so every character is scanned, however long the text.
"""
from __future__ import annotations

import json
import os

from scrubboard.models.base import PIIModel
from scrubboard.redact import Entity

STRIDE_TOKENS = 64  # overlap between consecutive windows


class OpenMedONNXModel(PIIModel):
    name = "openmed-44m"
    default_threshold = 0.5

    def __init__(self, model_dir: str, onnx_file: str = "model_int8.onnx", max_tokens: int = 384):
        self.model_dir = model_dir
        self.onnx_file = onnx_file
        self.max_tokens = max_tokens
        self._session = None
        self._tokenizer = None
        self._input_names: set[str] = set()
        self._id2label: dict[int, str] = {}

    def load(self) -> None:
        if self._session is not None:
            return
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as e:
            raise RuntimeError("openmed-44m needs onnxruntime, tokenizers and numpy") from e
        paths = {name: os.path.join(self.model_dir, name)
                 for name in (self.onnx_file, "tokenizer.json", "id2label.json")}
        for path in paths.values():
            if not os.path.exists(path):
                raise FileNotFoundError(f"{os.path.basename(path)} missing in {self.model_dir}. "
                                        "Run: scrubboard download-model --ner openmed-44m")
        with open(paths["id2label.json"], encoding="utf-8") as f:
            self._id2label = {int(k): v for k, v in json.load(f).items()}
        tokenizer = Tokenizer.from_file(paths["tokenizer.json"])
        tokenizer.no_padding()
        tokenizer.enable_truncation(max_length=self.max_tokens, stride=STRIDE_TOKENS)
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        # Measured: ~80 MB less RSS with no latency cost; matters on 8 GB PCs.
        opts.enable_cpu_mem_arena = False
        opts.enable_mem_pattern = False
        session = ort.InferenceSession(paths[self.onnx_file], sess_options=opts,
                                       providers=["CPUExecutionProvider"])
        self._input_names = {i.name for i in session.get_inputs()}
        self._tokenizer, self._session = tokenizer, session

    @property
    def labels(self) -> list[str]:
        return sorted({v[2:] if v[:2] in ("B-", "I-") else v for v in self._id2label.values()} - {"O"})

    def predict(self, text: str, threshold: float = 0.5) -> list[Entity]:
        self.load()
        assert self._tokenizer is not None
        enc = self._tokenizer.encode(text)
        out: list[Entity] = []
        for window in [enc, *enc.overflowing]:
            out.extend(self._predict_window(text, window, threshold))
        return out

    def _predict_window(self, text: str, enc, threshold: float) -> list[Entity]:
        import numpy as np

        assert self._session is not None
        ids = np.asarray([enc.ids], dtype=np.int64)
        feeds = {"input_ids": ids, "attention_mask": np.asarray([enc.attention_mask], dtype=np.int64),
                 "token_type_ids": np.zeros_like(ids)}
        logits = self._session.run(None, {k: v for k, v in feeds.items() if k in self._input_names})[0][0]
        exp = np.exp(logits - logits.max(axis=-1, keepdims=True))
        probs = exp / exp.sum(axis=-1, keepdims=True)
        spans: list[list] = []  # [start, end, tag, score]
        for idx, (pid, (s, e), special) in enumerate(zip(probs.argmax(axis=-1), enc.offsets,
                                                         enc.special_tokens_mask, strict=True)):
            if special or s >= e:
                continue
            label = self._id2label.get(int(pid), "O")
            score = float(probs[idx, int(pid)])
            if label == "O" or score < threshold:
                continue
            tag = label[2:] if label[:2] in ("B-", "I-") else label
            if spans and spans[-1][2] == tag and not text[spans[-1][1]:s].strip():
                spans[-1][1] = e
                spans[-1][3] = min(spans[-1][3], score)
            else:
                spans.append([s, e, tag, score])
        return [Entity(s, e, tag, score, source=self.name) for s, e, tag, score in spans]

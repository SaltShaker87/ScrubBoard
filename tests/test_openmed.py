"""OpenMed windowing/aggregation with a fake tokenizer + session (no weights needed)."""
import re

import numpy as np

from scrubboard.models.openmed import OpenMedONNXModel


class FakeEncoding:
    def __init__(self, ids, offsets):
        self.ids = ids
        self.attention_mask = [1] * len(ids)
        self.offsets = offsets
        self.special_tokens_mask = [0] * len(ids)
        self.overflowing: list = []


class FakeTokenizer:
    """Whitespace tokenizer that windows like `tokenizers` truncation + stride."""

    def __init__(self, max_tokens: int, stride: int):
        self.max_tokens, self.stride = max_tokens, stride

    def encode(self, text: str) -> FakeEncoding:
        toks = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
        windows = []
        for i in range(0, max(len(toks), 1), self.max_tokens - self.stride):
            w = toks[i:i + self.max_tokens]
            windows.append(FakeEncoding([1 if text[s:e] == "SECRET" else 0 for s, e in w], w))
            if i + self.max_tokens >= len(toks):
                break
        first, *rest = windows
        first.overflowing = rest
        return first


class FakeSession:
    def run(self, _outputs, feeds):
        ids = feeds["input_ids"][0]
        logits = np.zeros((1, len(ids), 3), dtype=np.float32)
        logits[0, :, 0] = 5.0
        logits[0, ids == 1, 0] = 0.0
        logits[0, ids == 1, 1] = 5.0  # B-ssn
        return [logits]


def make_model() -> OpenMedONNXModel:
    m = OpenMedONNXModel("/nonexistent")
    m._tokenizer = FakeTokenizer(384, 64)
    m._session = FakeSession()
    m._input_names = {"input_ids", "attention_mask"}
    m._id2label = {0: "O", 1: "B-ssn", 2: "I-ssn"}
    return m


def test_every_window_is_scanned():
    words = ["w"] * 2000
    words[5] = words[1999] = "SECRET"
    text = " ".join(words)
    ents = make_model().predict(text)
    starts = {e.start for e in ents}
    assert text.index("SECRET") in starts
    assert text.rindex("SECRET") in starts
    assert all(text[e.start:e.end] == "SECRET" for e in ents)


def test_adjacent_same_label_tokens_merge():
    text = "id SECRET SECRET , SECRET"
    ents = make_model().predict(text)
    assert [text[e.start:e.end] for e in ents] == ["SECRET SECRET", "SECRET"]
    assert {e.label for e in ents} == {"SSN"}

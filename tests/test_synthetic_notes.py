"""Rules-only gate over the synthetic notes: every structured identifier must be
removed and every clinical keep-item must survive. (Contextual identifiers need
the NER model; scripts/eval_recall.py checks those.)"""
import json
import pathlib

import pytest

from privatecopy.config import PrivateCopyConfig
from privatecopy.pipeline import RedactionPipeline

NOTES = sorted((pathlib.Path(__file__).parent / "data" / "synthetic_notes").glob("*.txt"))


@pytest.mark.parametrize("note", NOTES, ids=lambda p: p.stem)
def test_rules_catch_structured_identifiers(note):
    gold = json.loads(note.with_suffix(".gold.json").read_text(encoding="utf-8"))
    out = RedactionPipeline(PrivateCopyConfig(ner_model="none")).redact(note.read_text(encoding="utf-8")).text
    assert [s for s in gold["structured"] if s in out] == []
    assert [s for s in gold["keep"] if s not in out] == []

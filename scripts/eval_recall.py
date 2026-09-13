"""Recall check over tests/data/synthetic_notes (invented PHI only).

    python scripts/eval_recall.py --ner openmed-44m
    python scripts/eval_recall.py --ner openmed-44m --llm qwen3-0.6b-pii-q4km
    python scripts/eval_recall.py --ner none --fail-on-miss

Reports, per note, which gold identifiers leaked and which clinical items were
wrongly removed, plus latency. Use it to compare engines/LLMs before switching.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from privatecopy.config import NER_MODELS, PrivateCopyConfig  # noqa: E402
from privatecopy.models.manifest import LLM_CATALOG  # noqa: E402
from privatecopy.pipeline import RedactionPipeline  # noqa: E402

NOTES_DIR = ROOT / "tests" / "data" / "synthetic_notes"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ner", choices=NER_MODELS, default=None)
    parser.add_argument("--llm", choices=sorted(LLM_CATALOG), default=None)
    parser.add_argument("--fail-on-miss", action="store_true")
    args = parser.parse_args()

    cfg = PrivateCopyConfig.load()
    if args.ner:
        cfg.ner_model = args.ner
    llm = None
    if args.llm:
        from privatecopy.llm import create_llm_engine
        cfg.llm_model, cfg.llm_enabled, cfg.llm_timeout_s = args.llm, True, 120.0
        llm = create_llm_engine(cfg)
    pipeline = RedactionPipeline(cfg, llm=llm)
    pipeline.ensure_ready()

    total = found = keep_total = keep_ok = 0
    misses = 0
    try:
        for note in sorted(NOTES_DIR.glob("*.txt")):
            gold = json.loads(note.with_suffix(".gold.json").read_text(encoding="utf-8"))
            start = time.perf_counter()
            result = pipeline.redact(note.read_text(encoding="utf-8"))
            ms = (time.perf_counter() - start) * 1000
            targets = gold["structured"] + gold["contextual"]
            leaked = [s for s in targets if s in result.text]
            removed = [s for s in gold["keep"] if s not in result.text]
            total += len(targets)
            found += len(targets) - len(leaked)
            keep_total += len(gold["keep"])
            keep_ok += len(gold["keep"]) - len(removed)
            misses += len(leaked)
            skipped = f"  LLM skipped: {result.llm_skipped}" if result.llm_skipped else ""
            print(f"{note.stem}: {ms:,.0f} ms, engines={'+'.join(result.engines)}{skipped}")
            for s in leaked:
                print(f"    LEAKED   {s!r}")
            for s in removed:
                print(f"    REMOVED  {s!r} (clinical content)")
    finally:
        if llm is not None:
            llm.close()
    print(f"\nIdentifier recall: {found}/{total} ({found / max(total, 1):.0%})   "
          f"clinical content kept: {keep_ok}/{keep_total}")
    return 1 if args.fail_on_miss and misses else 0


if __name__ == "__main__":
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    sys.exit(main())

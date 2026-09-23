"""Build step: fetch the pinned, SHA256-verified privacy detector (NER model) into
installer/build/models/ so PyInstaller bundles it (see scrubboard.spec). Users then
never download anything: hospital networks often block or inspect that download."""
import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from scrubboard.download import download_ner, print_progress  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="openmed-44m")
    args = parser.parse_args()
    dest_root = os.path.join(ROOT, "installer", "build", "models")
    print(f"-> {download_ner(args.model, dest_root, print_progress)}")

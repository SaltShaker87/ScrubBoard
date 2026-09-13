"""Build step: fetch the pinned, SHA256-verified llama.cpp server into
installer/build/llama/ so PyInstaller bundles it (see privatecopy.spec)."""
import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from privatecopy.download import print_progress  # noqa: E402
from privatecopy.llm.binaries import fetch_llama_server, platform_key  # noqa: E402
from privatecopy.models.manifest import LLAMA_CPP_ASSETS  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", choices=sorted(LLAMA_CPP_ASSETS), default=platform_key())
    args = parser.parse_args()
    print(f"-> {fetch_llama_server(os.path.join(ROOT, 'installer', 'build', 'llama'), args.key, print_progress)}")

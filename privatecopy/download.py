"""Model downloads (first run, or when the user opts into the LLM).

The only network access PrivateCopy performs. Files come from immutable HF
commits and large files are SHA256-verified before they are used.
"""
from __future__ import annotations

import hashlib
import os
import ssl
import urllib.parse
import urllib.request
from collections.abc import Callable

from privatecopy import __version__
from privatecopy.models.manifest import get_llm_entry, get_ner_entry

Progress = Callable[[str, int, int], None]  # (filename, bytes_done, bytes_total)


def hf_url(repo: str, revision: str, filename: str) -> str:
    return f"https://huggingface.co/{repo}/resolve/{revision}/{urllib.parse.quote(filename)}"


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: str, sha256: str | None = None, progress: Progress | None = None) -> str:
    """Download url -> dest atomically; skip if dest already matches."""
    name = os.path.basename(dest)
    if os.path.exists(dest) and (sha256 is None or sha256_of(dest) == sha256):
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = f"{dest}.part"
    h = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": f"PrivateCopy/{__version__}"})
    with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if progress:
                progress(name, done, total)
    if sha256 and h.hexdigest() != sha256:
        os.remove(tmp)
        raise RuntimeError(f"checksum mismatch for {name}; download discarded")
    os.replace(tmp, dest)
    return dest


def ner_dir(model_id: str, models_dir: str) -> str:
    return os.path.join(models_dir, model_id)


def is_ner_downloaded(model_id: str, models_dir: str) -> bool:
    entry = get_ner_entry(model_id)
    return all(os.path.exists(os.path.join(ner_dir(model_id, models_dir), f)) for f in entry["files"])


def download_ner(model_id: str, models_dir: str, progress: Progress | None = None) -> str:
    entry = get_ner_entry(model_id)
    dest = ner_dir(model_id, models_dir)
    for filename, sha in entry["files"].items():
        fetch(hf_url(entry["hf_repo"], entry["revision"], filename), os.path.join(dest, filename),
              sha, progress)
    _write_notice(dest, entry)
    return dest


def llm_model_path(key: str, models_dir: str) -> str:
    return os.path.join(models_dir, "llm", get_llm_entry(key)["file"])


def is_llm_downloaded(key: str, models_dir: str) -> bool:
    return os.path.exists(llm_model_path(key, models_dir))


def download_llm(key: str, models_dir: str, progress: Progress | None = None) -> str:
    entry = get_llm_entry(key)
    path = fetch(hf_url(entry["hf_repo"], entry["revision"], entry["file"]),
                 llm_model_path(key, models_dir), entry["sha256"], progress)
    _write_notice(os.path.dirname(path), entry)
    return path


def _write_notice(dest: str, entry: dict) -> None:
    with open(os.path.join(dest, "NOTICE.txt"), "w", encoding="utf-8") as f:
        f.write(f"Model: {entry.get('upstream', entry['hf_repo'])} (files from {entry['hf_repo']}"
                f"@{entry['revision']})\nLicense: {entry['license']}\n")
        if "NVIDIA" in entry["license"]:
            f.write("Licensed by NVIDIA Corporation under the NVIDIA Open Model License.\n")


def print_progress(name: str, done: int, total: int) -> None:
    if total:
        print(f"\r  {name}: {done / 1e6:,.0f} / {total / 1e6:,.0f} MB", end="", flush=True)
        if done >= total:
            print()

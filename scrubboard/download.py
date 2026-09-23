"""Model downloads (first run, or when the user opts into the LLM).

The only network access Scrubboard performs. Files come from immutable HF
commits and large files are SHA256-verified before they are used.
"""
from __future__ import annotations

import hashlib
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

from scrubboard import __version__
from scrubboard.models.manifest import get_llm_entry, get_ner_entry

Progress = Callable[[str, int, int], None]  # (filename, bytes_done, bytes_total)
_MAX_RETRIES = 3


def hf_url(repo: str, revision: str, filename: str) -> str:
    return f"https://huggingface.co/{repo}/resolve/{revision}/{urllib.parse.quote(filename)}"


def ssl_context() -> ssl.SSLContext:
    """The OS trust store first: hospital networks often inspect TLS with their
    own root CA, which certifi's bundle doesn't contain."""
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except (ImportError, OSError, ssl.SSLError):
        pass
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
    """Download url -> dest atomically; skip if dest already matches.
    Retries up to _MAX_RETRIES times on transient network errors."""
    name = os.path.basename(dest)
    if os.path.exists(dest) and (sha256 is None or sha256_of(dest) == sha256):
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = f"{dest}.part"
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            h = hashlib.sha256()
            req = urllib.request.Request(url, headers={"User-Agent": f"Scrubboard/{__version__}"})
            with urllib.request.urlopen(req, timeout=60, context=ssl_context()) as r, open(tmp, "wb") as f:
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
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"download failed after {_MAX_RETRIES} attempts: {last_error}")


def bundled_models_dir() -> str | None:
    """Models shipped inside the installed app (PyInstaller data dir "models")."""
    base = getattr(sys, "_MEIPASS", None)
    return os.path.join(base, "models") if base else None


def ner_dir(model_id: str, models_dir: str) -> str:
    """Where download_ner writes the model."""
    return os.path.join(models_dir, model_id)


def _has_ner_files(path: str, model_id: str) -> bool:
    return all(os.path.exists(os.path.join(path, f)) for f in get_ner_entry(model_id)["files"])


def find_ner_dir(model_id: str, models_dir: str) -> str:
    """The copy bundled with the installer first, then the user's download dir."""
    bundled = bundled_models_dir()
    if bundled and _has_ner_files(os.path.join(bundled, model_id), model_id):
        return os.path.join(bundled, model_id)
    return ner_dir(model_id, models_dir)


def is_ner_downloaded(model_id: str, models_dir: str) -> bool:
    return _has_ner_files(find_ner_dir(model_id, models_dir), model_id)


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

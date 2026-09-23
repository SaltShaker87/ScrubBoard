"""Fetch the pinned, SHA256-verified official llama.cpp server build.

Installers bundle it at build time; `scrubboard download-model --llama-server`
uses the same code for pip/dev installs.
"""
from __future__ import annotations

import os
import platform
import shutil
import stat
import tarfile
import tempfile
import zipfile

from scrubboard.download import Progress, fetch
from scrubboard.llm.runtime import default_install_dir, server_exe_name
from scrubboard.models.manifest import LLAMA_CPP_ASSETS, LLAMA_CPP_BUILD, LLAMA_CPP_URL


def platform_key() -> str:
    system = platform.system()
    arm = platform.machine().lower() in ("arm64", "aarch64")
    if system == "Darwin":
        return "macos-arm64" if arm else "macos-x64"
    if system == "Windows":
        return "win-cpu-arm64" if arm else "win-cpu-x64"
    return "ubuntu-arm64" if arm else "ubuntu-x64"


def _extract(archive: str, dest: str) -> None:
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
        return
    with tarfile.open(archive) as t:
        t.extractall(dest, filter="data")


def _is_runtime_file(name: str) -> bool:
    return (name.startswith("llama-server") or name.endswith((".dll", ".dylib", ".so", ".metal"))
            or ".so." in name)


def fetch_llama_server(dest: str | None = None, key: str | None = None,
                       progress: Progress | None = None) -> str:
    key = key or platform_key()
    asset, sha256 = LLAMA_CPP_ASSETS[key]
    dest = dest or default_install_dir()
    exe = server_exe_name()
    with tempfile.TemporaryDirectory() as tmp:
        archive = fetch(LLAMA_CPP_URL.format(build=LLAMA_CPP_BUILD, asset=asset), os.path.join(tmp, asset),
                        sha256, progress)
        root = os.path.join(tmp, "x")
        _extract(archive, root)
        found = [os.path.join(d, exe) for d, _, files in os.walk(root) if exe in files]
        if not found:
            raise RuntimeError(f"{exe} not found in {asset}")
        src = os.path.dirname(found[0])
        os.makedirs(dest, exist_ok=True)
        for name in os.listdir(src):
            path = os.path.join(src, name)
            if os.path.isfile(path) and _is_runtime_file(name):
                shutil.copy2(path, os.path.join(dest, name))
    target = os.path.join(dest, exe)
    os.chmod(target, os.stat(target).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return target

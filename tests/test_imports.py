"""Smoke tests: every module imports and every Python file parses (catches
syntax errors in modules no other test touches)."""
import ast
import importlib
import pathlib
import pkgutil

import privatecopy

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", "venv", "build", "dist", "node_modules", ".git"}


def test_every_module_imports():
    for info in pkgutil.walk_packages(privatecopy.__path__, "privatecopy."):
        importlib.import_module(info.name)


def test_every_python_file_parses():
    for path in ROOT.rglob("*.py"):
        if SKIP_DIRS.intersection(path.parts):
            continue
        ast.parse(path.read_text(encoding="utf-8"), str(path))

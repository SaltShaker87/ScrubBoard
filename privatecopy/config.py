"""Persistent config: ~/.privatecopy/config.json"""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import asdict, dataclass, field, fields

NER_MODELS = ("openmed-44m", "nvidia-gliner", "none")  # "none" = rules only (explicit)
PLACEHOLDER_STYLES = ("[LABEL]", "[REDACTED]", "BLOCK")
DEFAULT_MAX_CHARS = 20_000
_BOOL_FIELDS = ("intercept_enabled", "keep_year", "keep_zip3", "llm_enabled")
_LIST_FIELDS = ("exclude_apps", "extra_keep_labels")


def config_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".privatecopy")


def config_path() -> str:
    return os.path.join(config_dir(), "config.json")


@dataclass
class PrivateCopyConfig:
    ner_model: str = "openmed-44m"
    threshold: float | None = None  # None = model default from the manifest
    intercept_enabled: bool = True
    exclude_apps: list[str] = field(default_factory=list)  # app/process names never intercepted
    hotkey: str = ""  # "" = off; e.g. "ctrl+alt+r" triggers "Redact clipboard now"
    placeholder_style: str = "[LABEL]"
    keep_year: bool = True
    keep_zip3: bool = True
    extra_keep_labels: list[str] = field(default_factory=list)
    max_chars: int = DEFAULT_MAX_CHARS
    models_dir: str = field(default_factory=lambda: os.path.join(config_dir(), "models"))
    llm_enabled: bool = False
    llm_model: str = "qwen3-0.6b-pii-q4km"
    llm_timeout_s: float = 8.0
    llm_idle_unload_min: int = 10
    llm_server_path: str = ""  # override the bundled llama-server
    update_url: str = ""  # manual update check only; empty = never touches the network
    load_warning: str = field(default="", repr=False, compare=False)  # not persisted

    def validate(self) -> None:
        from privatecopy.models.manifest import LLM_CATALOG

        if self.ner_model not in NER_MODELS:
            raise ValueError(f"unknown ner_model: {self.ner_model!r}; choose from {NER_MODELS}")
        if self.threshold is not None and not (
                isinstance(self.threshold, (int, float)) and 0.0 < self.threshold < 1.0):
            raise ValueError("threshold must be in (0, 1) or null")
        if self.placeholder_style not in PLACEHOLDER_STYLES:
            raise ValueError(f"placeholder_style must be one of {PLACEHOLDER_STYLES}")
        if not isinstance(self.max_chars, int) or self.max_chars <= 0:
            raise ValueError("max_chars must be a positive integer")
        if not isinstance(self.hotkey, str) or (self.hotkey and "+" not in self.hotkey):
            raise ValueError(f"suspicious hotkey: {self.hotkey!r}")
        if self.llm_model not in LLM_CATALOG:
            raise ValueError(f"unknown llm_model: {self.llm_model!r}; choose from {sorted(LLM_CATALOG)}")
        if not isinstance(self.llm_timeout_s, (int, float)) or self.llm_timeout_s <= 0:
            raise ValueError("llm_timeout_s must be positive")
        if not isinstance(self.llm_idle_unload_min, int) or self.llm_idle_unload_min < 0:
            raise ValueError("llm_idle_unload_min must be a non-negative integer")
        for name in _BOOL_FIELDS:
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be true/false")
        for name in _LIST_FIELDS:
            value = getattr(self, name)
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ValueError(f"{name} must be a list of strings")

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("load_warning", None)
        return data

    def save(self, path: str | None = None) -> str:
        self.validate()
        p = path or config_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = f"{p}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        os.replace(tmp, p)
        return p

    @classmethod
    def load(cls, path: str | None = None) -> PrivateCopyConfig:
        """Load config; an invalid file is backed up and replaced by defaults
        (with ``load_warning`` set) instead of crashing the daemon."""
        p = path or config_path()
        if not os.path.exists(p):
            return cls()
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("config root must be a JSON object")
            names = {f.name for f in fields(cls)} - {"load_warning"}
            cfg = cls(**{k: v for k, v in _migrate(data).items() if k in names})
            cfg.validate()
            return cfg
        except (OSError, ValueError, TypeError) as e:
            backup = f"{p}.invalid-{int(time.time())}"
            try:
                shutil.copy2(p, backup)
            except OSError:
                backup = "(backup failed)"
            cfg = cls()
            cfg.load_warning = f"Config was invalid ({e}); using defaults. Backup: {backup}"
            return cfg


def _migrate(data: dict) -> dict:
    """Map v0.1 keys onto the current schema."""
    data = dict(data)
    if "model" in data and "ner_model" not in data:
        data["ner_model"] = data.pop("model")
    for dropped in ("auto_update",):
        data.pop(dropped, None)
    return data


def coerce_value(key: str, raw: str):
    """Parse a CLI string into the type of config field ``key``."""
    ftypes = {f.name: str(f.type) for f in fields(PrivateCopyConfig) if f.name != "load_warning"}
    if key not in ftypes:
        raise ValueError(f"unknown config key {key!r}; choose from {sorted(ftypes)}")
    ftype = ftypes[key]
    if key in _BOOL_FIELDS:
        low = raw.strip().lower()
        if low not in ("1", "0", "true", "false", "yes", "no", "on", "off"):
            raise ValueError(f"{key} expects true/false")
        return low in ("1", "true", "yes", "on")
    if key in _LIST_FIELDS:
        return [v.strip() for v in raw.split(",") if v.strip()]
    if "None" in ftype and raw.strip().lower() in ("", "none", "null", "default"):
        return None
    if ftype.startswith("float"):
        return float(raw)
    if ftype.startswith("int"):
        return int(raw)
    return raw

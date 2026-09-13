"""Persistent config: ~/.privatecopy/config.json"""
from __future__ import annotations

import json
import os
import platform
from dataclasses import asdict, dataclass, field

DEFAULT_THRESHOLD = 0.5
DEFAULT_MODEL = "nvidia-gliner"
DEFAULT_MAX_CHARS = 10_000

DEFAULT_HOTKEYS = {
    "Darwin": "cmd+shift+c",
    "Windows": "ctrl+shift+c",
    "Linux": "ctrl+shift+c",
}


def default_hotkey() -> str:
    return DEFAULT_HOTKEYS.get(platform.system(), "ctrl+shift+c")


def config_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".privatecopy")


def config_path() -> str:
    return os.path.join(config_dir(), "config.json")


@dataclass
class PrivateCopyConfig:
    model: str = DEFAULT_MODEL  # "nvidia-gliner" | "openmed-44m"
    threshold: float = DEFAULT_THRESHOLD
    hotkey: str = field(default_factory=default_hotkey)
    placeholder_style: str = "[LABEL]"  # "[LABEL]" | "[REDACTED]" | "BLOCK"
    max_chars: int = DEFAULT_MAX_CHARS
    models_dir: str = field(default_factory=lambda: os.path.join(config_dir(), "models"))
    auto_update: bool = True

    def validate(self) -> None:
        if self.model not in ("nvidia-gliner", "openmed-44m"):
            raise ValueError(f"unknown model: {self.model}")
        if not 0.0 < self.threshold < 1.0:
            raise ValueError("threshold must be in (0, 1)")
        if self.max_chars <= 0:
            raise ValueError("max_chars must be positive")
        if not self.hotkey or "+" not in self.hotkey:
            raise ValueError(f"suspicious hotkey: {self.hotkey!r}")

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str | None = None) -> str:
        self.validate()
        p = path or config_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return p

    @classmethod
    def load(cls, path: str | None = None) -> "PrivateCopyConfig":
        p = path or config_path()
        if not os.path.exists(p):
            return cls()
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        cfg.validate()
        return cfg

"""Terminal setup for source installs (developers). Installed apps never need this:
the installers bundle the model and explain everything on screen."""
from __future__ import annotations

import os
import platform
from collections.abc import Callable

from scrubboard.config import NER_MODELS, ScrubboardConfig
from scrubboard.models.manifest import LLM_CATALOG, NER_CATALOG


def _ask_choice(ask: Callable[[str], str], prompt: str, choices: tuple[str, ...], default: str) -> str:
    answer = ask(prompt).strip() or default
    if answer not in choices:
        print(f"Unknown {answer!r}, keeping {default}.")
        return default
    return answer


def _ask_yes(ask: Callable[[str], str], prompt: str, default: bool) -> bool:
    answer = ask(prompt).strip().lower()
    return default if not answer else answer in ("y", "yes")


def first_run(config: ScrubboardConfig | None = None,
              ask: Callable[[str], str] = input) -> ScrubboardConfig:
    from scrubboard.download import download_llm, download_ner, print_progress

    config = config or ScrubboardConfig.load()
    print("=== Scrubboard setup ===\n")
    print("Scrubboard removes HIPAA Safe Harbor identifiers from text you copy, entirely on this")
    print("computer. Built-in Safe Harbor rules always run; pick the detection model that runs with them:\n")
    for mid, entry in NER_CATALOG.items():
        star = " (default)" if mid == "openmed-44m" else ""
        print(f"  {mid}{star}: {entry['title']}\n      {entry['approx_size']}; license: {entry['license']}")
    print("  none: rules only (weaker: structured identifiers, few names)\n")
    config.ner_model = _ask_choice(ask, f"Model [{config.ner_model}]: ", NER_MODELS, config.ner_model)

    config.intercept_enabled = _ask_yes(
        ask, "\nClean every copy automatically? Otherwise use \"Clean my clipboard\" in the tray "
             "(or the macOS Services menu) [y/N]: ", False)

    llm = LLM_CATALOG[config.llm_model]
    print(f"\nOptional local LLM: {llm['title']} ({llm['size'] / 1e6:,.0f} MB, {llm['license']}).")
    print("It adds a slower, context-aware pass; if it takes longer than "
          f"{config.llm_timeout_s:g}s the rules+model result is used instead.")
    config.llm_enabled = _ask_yes(ask, "Enable it now? [y/N]: ", False)

    path = config.save()
    print(f"\nSaved {path}")
    if config.ner_model != "none":
        print(f"Downloading {config.ner_model} (one time)...")
        download_ner(config.ner_model, config.models_dir, print_progress)
    if config.llm_enabled:
        print(f"Downloading {config.llm_model} (one time)...")
        download_llm(config.llm_model, config.models_dir, print_progress)

    if (config.intercept_enabled and platform.system() == "Linux"
            and os.environ.get("XDG_SESSION_TYPE") == "wayland"
            and "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "")):
        print("\nGNOME on Wayland: automatic cleaning needs the Scrubboard GNOME Shell extension:\n"
              "  gnome-extensions enable scrubboard@scrubboard.github.io\n"
              "then log out and back in. (Or choose 'Ubuntu on Xorg' at the login screen.)")
    print("\nDone. Start with: scrubboard")
    return config

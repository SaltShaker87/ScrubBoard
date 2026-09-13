"""First-run wizard: model pick (GLiNER default) -> hotkey confirm/remap -> download."""
from __future__ import annotations

from privatecopy.config import PrivateCopyConfig
from privatecopy.hotkey import canonicalize, default_hotkey
from privatecopy.models.manifest import MODEL_CATALOG


def first_run(config: PrivateCopyConfig | None = None) -> PrivateCopyConfig:
    config = config or PrivateCopyConfig()
    print("=== PrivateCopy first-run setup ===\n")
    print("Models (downloaded once from Hugging Face, then fully offline):")
    for mid, entry in MODEL_CATALOG.items():
        star = " (default)" if mid == "nvidia-gliner" else ""
        print(f"  [{\u2022 if mid == config.model else ' '}] {mid}{star}\n"
              f"      {entry['hf_repo']} — {entry['params']}, {entry['approx_size']}\n"
              f"      license: {entry['license']}")
    choice = input("\nWhich model? [nvidia-gliner/openmed-44m, Enter=default]: ").strip() or "nvidia-gliner"
    if choice not in MODEL_CATALOG:
        print(f"Unknown {choice!r}, keeping nvidia-gliner.")
        choice = "nvidia-gliner"
    config.model = choice

    print(f"\nDefault hotkey is {default_hotkey()}. The installer shows this same default.")
    hk = input(f"Hotkey [{config.hotkey}, Enter=keep, or type a new one like ctrl+shift+p]: ").strip()
    if hk:
        try:
            config.hotkey = canonicalize(hk)
        except Exception:
            print(f"Could not parse {hk!r}; keeping {config.hotkey}.")

    path = config.save()
    print(f"\nSaved {path}: model={config.model}, threshold={config.threshold}, hotkey={config.hotkey}")
    print("Downloading model (this can take a while for GLiNER)...")
    from scripts.download_models import download_model
    download_model(config.model, config.models_dir)
    print("Done. Run `privatecopy daemon` to start.")
    return config

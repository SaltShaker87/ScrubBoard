"""Opt-in local LLM (llama.cpp `llama-server` + a small PII-tuned GGUF)."""
from __future__ import annotations

import os

from scrubboard.config import ScrubboardConfig
from scrubboard.llm.engine import LLMEngine


def create_llm_engine(config: ScrubboardConfig, warm: bool = True,
                      startup_timeout: float = 120) -> LLMEngine:
    """Build the LLM pass for ``config.llm_model``. Raises FileNotFoundError /
    RuntimeError with an actionable message when it can't run here."""
    import psutil

    from scrubboard.download import llm_model_path
    from scrubboard.llm.runtime import LlamaServer, find_llama_server
    from scrubboard.models.manifest import get_llm_entry

    entry = get_llm_entry(config.llm_model)
    model_path = llm_model_path(config.llm_model, config.models_dir)
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"{entry['file']} is not downloaded. "
                                f"Run: scrubboard download-model --llm {config.llm_model}")
    binary = find_llama_server(config.llm_server_path)
    if not binary:
        raise RuntimeError("llama-server not found. Reinstall Scrubboard, or run: "
                           "scrubboard download-model --llama-server")
    available_mb = psutil.virtual_memory().available // (1024 * 1024)
    if available_mb < entry["min_free_ram_mb"]:
        raise RuntimeError(f"needs about {entry['min_free_ram_mb']:,} MB of free memory; "
                           f"{available_mb:,} MB available")
    server = LlamaServer([binary], model_path, entry["ctx_size"], config.llm_idle_unload_min * 60,
                         startup_timeout=startup_timeout)
    if warm:
        server.ensure_running()
    return LLMEngine(server, entry, config.llm_model, closer=server.close)

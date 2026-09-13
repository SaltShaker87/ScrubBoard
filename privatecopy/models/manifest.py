"""Model + runtime catalog. Every download is pinned to an immutable HF commit
(or llama.cpp build) and large files are SHA256-verified."""
from __future__ import annotations

GLINER_LABELS = [
    "first_name", "last_name", "date_of_birth", "age", "gender", "ssn",
    "passport_number", "driver_license", "account_number", "credit_debit_card",
    "cvv", "bank_routing_number", "employee_id", "medical_record_number",
    "health_plan_beneficiary_number", "certificate_license_number", "api_key",
    "mac_address", "ipv4", "ipv6", "device_identifier", "email", "phone_number",
    "fax_number", "url", "street_address", "city", "county", "state", "country",
    "coordinate", "zip_code", "company_name", "occupation", "education_level",
    "blood_type", "biometric_identifier", "date", "date_time", "time",
    "user_name", "password",
]

NER_CATALOG: dict[str, dict] = {
    "openmed-44m": {
        "title": "OpenMed PII SuperClinical Small (DeBERTa-v3-small, INT8 ONNX)",
        "hf_repo": "OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1-onnx-android",
        "revision": "82f57fcab68125b05f1aa9fdd41319732358311b",
        "files": {
            "model_int8.onnx": "024aee10c7141ac847d2eb91c124eb001f7a80b279b9f39617a8dd37fb60d06c",
            "tokenizer.json": None,
            "tokenizer_config.json": None,
            "id2label.json": None,
            "config.json": None,
        },
        "onnx_file": "model_int8.onnx",
        "max_tokens": 384,
        "license": "Apache-2.0",
        "approx_size": "~480 MB download, ~0.9 GB RAM",
        "default_threshold": 0.5,
    },
    "nvidia-gliner": {
        "title": "NVIDIA GLiNER-PII (570M, PyTorch; needs the 'gliner' extra)",
        "hf_repo": "nvidia/gliner-PII",
        "revision": "bd23e8ef4425fd04e34c5204ab49ffaa706eae79",
        "files": {
            "gliner_config.json": None,
            "pytorch_model.bin": None,
            "spm.model": None,
            "tokenizer.json": None,
            "tokenizer_config.json": None,
            "added_tokens.json": None,
            "special_tokens_map.json": None,
        },
        "license": "NVIDIA Open Model License",
        "approx_size": "~1.8 GB download, ~2.5 GB RAM",
        "default_threshold": 0.3,
    },
}

LLM_CATALOG: dict[str, dict] = {
    "qwen3-0.6b-pii-q4km": {
        "title": "Qwen3-0.6B PII detector (Q4_K_M)",
        "hf_repo": "mradermacher/qwen3-0.6b-pii-detector-GGUF",
        "revision": "2b1543d734fd099a86d37b8d2a59ecabfb8b85c0",
        "file": "qwen3-0.6b-pii-detector.Q4_K_M.gguf",
        "sha256": "6dece064db763288c2d6bb525f28a68e99899eb199a591dc4d04c6ead9e8d41c",
        "size": 396_703_936,
        "parser": "inline_tags",
        "ctx_size": 2048,
        "chunk_chars": 2800,  # prompt + echoed, tagged output must fit in 2048 tokens
        "min_free_ram_mb": 900,
        "upstream": "naazimsnh02/qwen3-0.6b-pii-detector",
        "license": "Apache-2.0; trained on nvidia/Nemotron-PII (CC-BY-4.0)",
    },
    "qwen3-0.6b-pii-q8": {
        "title": "Qwen3-0.6B PII detector (Q8_0)",
        "hf_repo": "mradermacher/qwen3-0.6b-pii-detector-GGUF",
        "revision": "2b1543d734fd099a86d37b8d2a59ecabfb8b85c0",
        "file": "qwen3-0.6b-pii-detector.Q8_0.gguf",
        "sha256": "fff3aac998aa40f42867a5931b72134c0014a4151085c632486bdbcc994cf2cc",
        "size": 639_446_208,
        "parser": "inline_tags",
        "ctx_size": 2048,
        "chunk_chars": 2800,
        "min_free_ram_mb": 1100,
        "upstream": "naazimsnh02/qwen3-0.6b-pii-detector",
        "license": "Apache-2.0; trained on nvidia/Nemotron-PII (CC-BY-4.0)",
    },
    "ministral-3b-pii-q4km": {
        "title": "OpenMed Ministral-3B PII Preview (Q4_K_M)",
        "hf_repo": "mradermacher/Ministral-3B-PII-Preview-GGUF",
        "revision": "e1ebca642a31efa000087ddd4055405b6e655ecc",
        "file": "Ministral-3B-PII-Preview.Q4_K_M.gguf",
        "sha256": "4f01ef250401eacfda3a951091c0676ac060039c99a6e5ec80dc8e0745f9edfc",
        "size": 2_146_494_880,
        "parser": "json_spans",
        "ctx_size": 4096,
        "chunk_chars": 5000,
        "min_free_ram_mb": 2800,
        "upstream": "OpenMed/Ministral-3B-PII-Preview",
        "license": "Apache-2.0",
    },
}

# Official llama.cpp prebuilt server binaries, bundled into installers at build time.
LLAMA_CPP_BUILD = "b10941"
LLAMA_CPP_URL = "https://github.com/ggml-org/llama.cpp/releases/download/{build}/{asset}"
LLAMA_CPP_ASSETS: dict[str, tuple[str, str]] = {
    "macos-arm64": ("llama-b10941-bin-macos-arm64.tar.gz",
                    "cfd7639e91f4cb675b8146dcd4b49afecc7666eff61b460afaee4fd2e5bf9082"),
    "macos-x64": ("llama-b10941-bin-macos-x64.tar.gz",
                  "bf96c5372abb91e66659d7a765b338e2a24c1cf038e743f75be58e278f4365f8"),
    "ubuntu-x64": ("llama-b10941-bin-ubuntu-x64.tar.gz",
                   "e4a483ec662f21ae05d6688286fb9c57906c3a61a059337c05bb7d6f45439f27"),
    "ubuntu-arm64": ("llama-b10941-bin-ubuntu-arm64.tar.gz",
                     "d1e080ef639196881a9f0ae92a668a90ea8c8e7cce179b5a27e642530fbbd63f"),
    "win-cpu-x64": ("llama-b10941-bin-win-cpu-x64.zip",
                    "033ab72aa6fc69059e7529affa383b93201b612abbe72ea39bba103560a81cc8"),
    "win-cpu-arm64": ("llama-b10941-bin-win-cpu-arm64.zip",
                      "6ae720f67259f7d27e7d85135777a21b22f2bd9bf5005c0377648cec25da6017"),
}


def get_ner_entry(model_id: str) -> dict:
    try:
        return NER_CATALOG[model_id]
    except KeyError:
        raise ValueError(f"unknown NER model {model_id!r}; choose from {sorted(NER_CATALOG)}") from None


def get_llm_entry(key: str) -> dict:
    try:
        return LLM_CATALOG[key]
    except KeyError:
        raise ValueError(f"unknown LLM model {key!r}; choose from {sorted(LLM_CATALOG)}") from None

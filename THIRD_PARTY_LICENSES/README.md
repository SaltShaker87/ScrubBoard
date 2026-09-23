# Third-party components

The default NER model (OpenMed, Apache-2.0) is bundled in the installers so users never
download anything. The optional models are downloaded only when a user turns them on. A
`NOTICE.txt` next to each model (bundled or downloaded) records its source commit and license.

**Models**
* `OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1-onnx-android` (default NER) — Apache-2.0.
  <https://huggingface.co/OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1-onnx-android>
* `nvidia/gliner-PII` (optional NER) — NVIDIA Open Model License. Commercial use is allowed.
  Redistribution requires the NOTICE attribution, and use must follow NVIDIA's Trustworthy AI
  terms, which NVIDIA may update. <https://huggingface.co/nvidia/gliner-PII>
* `naazimsnh02/qwen3-0.6b-pii-detector` (opt-in LLM; GGUF quantization by
  `mradermacher/qwen3-0.6b-pii-detector-GGUF`) — Apache-2.0. Base model Qwen/Qwen3-0.6B
  (Apache-2.0). It was trained on `nvidia/Nemotron-PII`, licensed CC-BY-4.0 by NVIDIA.
* `OpenMed/Ministral-3B-PII-Preview` (opt-in LLM; GGUF by
  `mradermacher/Ministral-3B-PII-Preview-GGUF`) — Apache-2.0.

**Software**
* llama.cpp `llama-server` (bundled in installers, pinned build `b10941`) — MIT.
  <https://github.com/ggml-org/llama.cpp>
* ONNX Runtime — MIT. Hugging Face `tokenizers` — Apache-2.0. `pystray` — LGPL-3.0.
  truststore — MIT. certifi — MPL-2.0. PyGObject (Linux builds) — LGPL-2.1.
  Pillow — MIT-CMU. psutil — BSD-3. PyObjC (macOS) — MIT. python-xlib (Linux) — LGPL-2.1.

Scrubboard's own code is MIT (`LICENSE-MIT`).

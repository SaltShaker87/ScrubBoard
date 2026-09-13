# Privacy

* All inference runs on-device via ONNX Runtime. After the one-time model
  download from Hugging Face, PrivateCopy works fully offline.
* The original selected text is only ever held in memory and on the clipboard.
  It is never written to disk, never logged, never sent over the network
  (the loopback service binds `127.0.0.1` only for local shims).
* Logs contain only entity counts, labels redacted-counts, and timings.
* No telemetry, no accounts, no analytics.

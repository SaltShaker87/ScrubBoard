# Privacy

* **On-device only.** Detection runs locally: regex rules, an ONNX Runtime model, and
  optionally a llama.cpp server bound to `127.0.0.1` with a random per-session API key.
* **Network use is limited to model downloads.** These come from pinned Hugging Face commits
  (first run, or when you enable the LLM), and the manual `update-check` command talks to a
  URL you configure. The daemon sets `HF_HUB_OFFLINE=1` and starts llama-server with
  `--offline`.
* **Clipboard text is held only in memory**, and only while it is being redacted. It is
  never written to disk, logged, or sent anywhere. Notifications contain counts and status
  only.
* **Fail-closed.** On any failure the clipboard is replaced by a status message; the
  original text is never restored.
* **What is skipped.** PrivateCopy doesn't read content that password managers mark as
  concealed. On Windows that's `ExcludeClipboardContentFromMonitorProcessing`; on macOS,
  nspasteboard.org concealed/transient types; on Linux, `x-kde-passwordManagerHint`. Its
  placeholder is marked transient so clipboard-history tools skip it.
* **GNOME extension.** It talks to the daemon over a Unix socket in `$XDG_RUNTIME_DIR` with
  mode 0600, and the daemon checks the peer's UID. If the daemon isn't running, the
  extension does nothing.
* **What PrivateCopy cannot control:**
  * Anything that copies the clipboard before PrivateCopy replaces it. This includes
    Windows Clipboard History and cloud clipboard, macOS Universal Clipboard, and
    third-party clipboard managers. Disable them on clinical machines.
  * A paste made in the few milliseconds before the placeholder is written.
* **No telemetry, no accounts, no analytics.**

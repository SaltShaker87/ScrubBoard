# Privacy

* **On-device only.** Detection runs locally: regex rules, an ONNX Runtime model, and
  optionally a llama.cpp server bound to `127.0.0.1` with a random per-session API key.
* **No network use in normal operation.** The installers include the detection model, so
  nothing is downloaded. The only downloads happen when you turn on "Extra-careful mode"
  (the optional local LLM) or run from source. They come from pinned Hugging Face commits
  and are SHA256-verified. The manual `update-check` command talks only to a URL you configure.
  The daemon sets `HF_HUB_OFFLINE=1` and starts llama-server with `--offline`.
* **Clipboard text is held only in memory**, and only while it is being redacted. It is
  never written to disk, logged, or sent anywhere. Notifications contain counts and status
  only.
* **Fail-closed.** If cleaning fails, the clipboard is replaced by a status message; the
  original text is never put back.
* **By default nothing is watched.** Scrubboard reads the clipboard only when you choose
  "Clean my clipboard" or the macOS Services item. The clipboard is watched only if you
  turn on "Clean every copy automatically".
* **What is skipped.** Scrubboard doesn't read content that password managers mark as
  concealed. On Windows that's `ExcludeClipboardContentFromMonitorProcessing`; on macOS,
  nspasteboard.org concealed/transient types; on Linux, `x-kde-passwordManagerHint`. Its
  placeholder is marked transient so clipboard-history tools skip it.
* **GNOME extension.** It talks to the daemon over a Unix socket in `$XDG_RUNTIME_DIR` with
  mode 0600, and the daemon checks the peer's UID. If the daemon isn't running, the
  extension does nothing.
* **What Scrubboard cannot control:**
  * Anything that copies the clipboard before Scrubboard replaces it: Windows Clipboard
    History and cloud clipboard, macOS Universal Clipboard, and third-party clipboard
    managers. Disable them on clinical machines. (The Windows installer offers to turn
    clipboard history off.) When you clean on request, the original text stays on the
    clipboard until you do.
  * A paste made in the few milliseconds before the placeholder is written.
* **No telemetry, no accounts, no analytics.**

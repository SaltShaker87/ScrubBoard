# PrivateCopy

![PrivateCopy logo](assets/privatecopy-logo.png)

Copy text anywhere (Ctrl/Cmd+C or right-click → Copy). PrivateCopy removes HIPAA Safe Harbor
identifiers and puts the redacted text back on the clipboard, so what you paste is clean.
Diagnoses and medications are kept. Everything runs on your computer. After the one-time model
download it never touches the network.

> Status: v0.1 — pre-release. PrivateCopy is a de-identification *aid*, not a compliance
> guarantee: Safe Harbor also requires that you have no actual knowledge the remaining
> information could identify someone. Review output before sharing it.

## How it works

```
copy ─▶ clipboard watcher ─▶ placeholder written at once ─▶ worker thread:
         (per-OS, no           "[PrivateCopy: redacting…]"    1. Safe Harbor rules (always)
          keyboard hooks)                                     2. NER model (OpenMed, default)
                                                              3. local LLM (opt-in, with timeout)
                                                              4. merge spans → Safe Harbor transforms
                        ◀── redacted text replaces the placeholder (if you haven't copied again)
```

* **Fail-closed.** If redaction fails, the clipboard keeps a "redaction failed" message. Raw
  text is never put back. If the detection model is missing, copy redaction stays off and
  the tray icon turns red. It never silently falls back to weaker rules.
* **Safe Harbor transforms.**
  * Dates keep only the year: `03/14/2024` → `[DATE 2024]`. The year is dropped too when
    it implies an age over 89.
  * Ages over 89 become `[AGE 90+]`.
  * ZIP codes keep their first three digits, or become `000` for the 17 low-population prefixes.
  * Names, addresses, phone and fax numbers, email, SSN, MRN, health-plan and account
    numbers, license, vehicle and device IDs, URLs, IPs and biometric IDs are replaced.
  * State, country, diagnoses, medications, procedures and ages ≤ 89 are kept.
* **Skipped automatically:**
  * PrivateCopy's own writes.
  * Password-manager content (the nspasteboard concealed type, Windows
    `ExcludeClipboardContentFromMonitorProcessing`, and `x-kde-passwordManagerHint`).
  * Apps you list in `exclude_apps`, for example your EHR.
* **Tray menu:**
  * Redact every copy (on/off)
  * Pause 5 minutes
  * Redact clipboard now
  * Use local LLM
  * Status

## Engines (downloaded at runtime, never bundled)

| Engine | Source | Size | License | Role |
|---|---|---|---|---|
| Safe Harbor rules | built in | — | MIT | Structured identifiers; always on |
| `openmed-44m` (default) | [OpenMed PII SuperClinical Small, INT8 ONNX](https://huggingface.co/OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1-onnx-android) | ~480 MB, ~0.9 GB RAM | Apache-2.0 | Names, places, and IDs in free text |
| `nvidia-gliner` (optional) | [NVIDIA GLiNER-PII](https://huggingface.co/nvidia/gliner-PII) | ~1.8 GB | NVIDIA Open Model License | Larger NER; `pip install 'privatecopy[gliner]'` |
| LLM `qwen3-0.6b-pii-q4km` (opt-in) | [qwen3-0.6b-pii-detector](https://huggingface.co/naazimsnh02/qwen3-0.6b-pii-detector), [GGUF](https://huggingface.co/mradermacher/qwen3-0.6b-pii-detector-GGUF) | 379 MB, <1 GB RAM | Apache-2.0 (data: Nemotron-PII, CC-BY-4.0) | Extra context-aware pass |
| LLM `ministral-3b-pii-q4km` (opt-in) | [OpenMed Ministral-3B-PII-Preview](https://huggingface.co/OpenMed/Ministral-3B-PII-Preview) | 2.0 GB, ~2.5 GB RAM | Apache-2.0 | Stronger, slower alternative |

* **Pinned downloads.** Every download is pinned to an immutable Hugging Face commit, and
  large files are SHA256-verified.
* **The LLM** runs in a bundled [llama.cpp](https://github.com/ggml-org/llama.cpp)
  `llama-server` bound to 127.0.0.1 with a random API key. It starts on demand and is
  unloaded after 10 idle minutes.
* **The LLM only finds strings.** Its output is never pasted; found strings are mapped back
  onto the original text.
* **LLM timeout.** If the LLM takes longer than `llm_timeout_s` (default 8 s), the
  rules+NER result is used and you are notified.

**Hardware:** the default engine is built for 8 GB, CPU-only PCs. The LLM is opt-in everywhere.

## Platform notes

* **macOS 12+:** the clipboard is polled; no Accessibility permission is needed. It runs as
  a menu-bar app.
* **Windows 10/11:** it uses a clipboard-format listener.
  **Windows Clipboard History (Win+V), cloud clipboard and third-party clipboard managers
  record the original text before PrivateCopy sees it.** Disable them on clinical machines
  (Group Policy: *Allow Clipboard History* = Disabled, *Allow Clipboard synchronization
  across devices* = Disabled).
* **Linux:**
  * X11 sessions need `xclip` or `xsel`.
  * KDE Plasma and wlroots Wayland need `wl-clipboard`.
  * **GNOME on Wayland** (Ubuntu's default) doesn't let apps watch the clipboard. Enable the
    bundled extension with `gnome-extensions enable privatecopy@privatecopy.org`, then log
    in again. The extension needs GNOME 45+ (Ubuntu 24.04+). On Ubuntu 22.04, choose
    "Ubuntu on Xorg" at login.
  * The tray icon on GNOME needs the AppIndicator extension, which Ubuntu ships.
* **Brief window.** On every platform, text can be pasted in the milliseconds between a copy
  and PrivateCopy writing its placeholder.

## Quick start (development)

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
privatecopy first-run              # choose engine, download the model
privatecopy run-once --stdout --text "Pt John Smith, MRN 12345678, DOB 03/14/1950"
privatecopy daemon                 # tray + copy interception (also the default with no command)
privatecopy status                 # engines, downloads, config
pytest && ruff check .
```

The local LLM from a source checkout:

```bash
privatecopy download-model --llama-server
privatecopy download-model --llm qwen3-0.6b-pii-q4km
privatecopy set llm_enabled true
```

Compare engines on the synthetic notes: `python scripts/eval_recall.py --ner openmed-44m [--llm qwen3-0.6b-pii-q4km]`.

### Config (`~/.privatecopy/config.json`, or `privatecopy set <key> <value>`)

| Key | Default | Meaning |
|---|---|---|
| `intercept_enabled` | `true` | Redact every copy |
| `ner_model` | `openmed-44m` | `openmed-44m`, `nvidia-gliner`, or `none` (rules only) |
| `exclude_apps` | `[]` | App/process names never intercepted (substring match) |
| `keep_year` / `keep_zip3` | `true` | Safe Harbor year / 3-digit ZIP retention |
| `extra_keep_labels` | `[]` | Extra labels to keep, e.g. `occupation` |
| `llm_enabled` / `llm_model` | `false` / `qwen3-0.6b-pii-q4km` | Opt-in LLM pass |
| `llm_timeout_s` | `8` | After this, the rules+NER result is used |
| `max_chars` | `20000` | Longer copies are redacted up to this, with a visible truncation marker |
| `hotkey` | `""` | Optional "redact clipboard now" hotkey (`pip install 'privatecopy[hotkey]'`) |
| `placeholder_style` | `[LABEL]` | `[LABEL]`, `[REDACTED]`, or `BLOCK` |

## Installers

* **Windows:** `installer/win/build_exe.ps1` builds the PyInstaller app, bundles
  `llama-server`, and produces an Inno Setup installer (per-user, autostart, and
  "Redact every copy" / "Enable LLM" choices).
* **macOS:** `installer/mac/notarize.sh` builds a menu-bar `.app`, signs everything, and
  produces a notarized DMG. It needs an Apple Developer ID.
* **Linux:** `installer/linux/build_linux.sh` produces a `.deb` and `.rpm` (`/opt/privatecopy`,
  autostart, GNOME extension).

On first start the app downloads the detection model and then turns copy redaction on.

## Privacy

See [docs/PRIVACY.md](docs/PRIVACY.md). There's no telemetry, no accounts, no logging of
clipboard text, and no network use after model downloads.

## Layout

* `privatecopy/`
  * `safe_harbor.py` — rules, policy, transforms
  * `pipeline.py` — rules + NER + LLM
  * `intercept.py` — the fail-closed controller
  * `watchers/` — per-OS clipboard backends and the GNOME socket
  * `llm/` — llama-server runtime and engine
  * `models/` — NER models and the pinned manifest
  * `app.py`, `tray.py`, `cli.py`
* `gnome-extension/` — GNOME Shell extension for Wayland.
* `installer/` — PyInstaller spec, llama.cpp fetch, and per-OS installers.
* `scripts/eval_recall.py` — recall comparison. `tests/data/synthetic_notes/` holds the
  invented notes it uses.

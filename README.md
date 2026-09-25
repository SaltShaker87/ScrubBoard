# Scrubboard

![Scrubboard logo](assets/scrubboard-logo.png)

Scrubboard removes the details that identify a patient (names, dates of birth, record numbers,
addresses and the other HIPAA Safe Harbor identifiers) from text you copy, so you can paste it
into an AI assistant or an email more safely. Diagnoses and medications are kept. Everything
runs on your computer, and the installers include the detection model, so it never needs the
network.

**For clinicians:** go to the download page (`https://<owner>.github.io/<repo>/`), click the
button, and run the installer. It explains every step and shows the disclaimer below.

1. Copy text as usual.
2. **Mac:** right-click selected text → Services → **Scrubboard: Copy without patient info**.
   **Windows:** click the Scrubboard icon next to the clock.
   **Ubuntu:** click the icon in the top bar → **Clean my clipboard**.
3. Paste, and **read the cleaned text before you send it.**

> Status: v0.1 — pre-release. Scrubboard is a de-identification *aid*, not a compliance
> guarantee. It can miss identifiers. Safe Harbor also requires that you have no actual
> knowledge the remaining information could identify someone. Review output before sharing it,
> and follow your organization's policy on AI tools.

## How it works

```
"Clean my clipboard" / macOS Services item / (opt-in) every copy
   ─▶ placeholder written at once ─▶ worker thread:
      "[Scrubboard: cleaning…]"       1. Safe Harbor rules (always)
                                      2. NER model (OpenMed, default)
                                                              3. local LLM (opt-in, with timeout)
                                                              4. merge spans → Safe Harbor transforms
   ◀── redacted text replaces the placeholder (if you haven't copied again)
```

* **Explicit by default.** Nothing watches the clipboard until you turn on "Clean every copy
  automatically". On Windows a left-click on the tray icon runs "Clean my clipboard".
* **Fail-closed.** If redaction fails, the clipboard keeps a "cleaning failed" message. Raw
  text is never put back. If the detection model is missing, cleaning is refused and the
  tray icon turns red. It never silently falls back to weaker rules.
* **Safe Harbor transforms.**
  * Dates keep only the year: `03/14/2024` → `[DATE 2024]`. The year is dropped too when
    it implies an age over 89.
  * Ages over 89 become `[AGE 90+]`.
  * ZIP codes keep their first three digits, or become `000` for the 17 low-population prefixes.
  * Names, addresses, phone and fax numbers, email, SSN, MRN, health-plan and account
    numbers, license, vehicle and device IDs, URLs, IPs and biometric IDs are replaced.
  * State, country, diagnoses, medications, procedures and ages ≤ 89 are kept.
* **Skipped automatically:**
  * Scrubboard's own writes.
  * Password-manager content (the nspasteboard concealed type, Windows
    `ExcludeClipboardContentFromMonitorProcessing`, and `x-kde-passwordManagerHint`).
  * Apps you list in `exclude_apps`, for example your EHR.
* **Tray menu:** status, last result, **Clean my clipboard**, Clean every copy automatically,
  Pause 5 minutes (when automatic), Extra-careful mode (the opt-in local LLM),
  How to use Scrubboard…, Quit Scrubboard.
* **One instance.** Opening Scrubboard while it is already running just says where its icon is.

## Engines

| Engine | Source | Size | License | Role |
|---|---|---|---|---|
| Safe Harbor rules | built in | — | MIT | Structured identifiers; always on |
| `openmed-44m` (default, **bundled in installers**) | [OpenMed PII SuperClinical Small, INT8 ONNX](https://huggingface.co/OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1-onnx-android) | ~480 MB, ~0.9 GB RAM | Apache-2.0 | Names, places, and IDs in free text |
| `nvidia-gliner` (optional) | [NVIDIA GLiNER-PII](https://huggingface.co/nvidia/gliner-PII) | ~1.8 GB | NVIDIA Open Model License | Larger NER; `pip install 'scrubboard[gliner]'` |
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

* **macOS 12+:** a menu-bar app with a right-click **Services** item (declared in the app's
  `Info.plist`, `NSServices`). No Accessibility permission is needed; automatic mode polls the
  clipboard. It registers itself as a login item on first launch.
* **Windows 10/11:** it uses a clipboard-format listener.
  **Windows Clipboard History (Win+V), cloud clipboard and third-party clipboard managers
  record the original text before Scrubboard sees it.** The installer offers to turn
  clipboard history off for the user. For managed machines use Group Policy (*Allow
  Clipboard History* = Disabled, *Allow Clipboard synchronization across devices* = Disabled).
* **Linux (Ubuntu 22.04+):** the `.deb` depends on `wl-clipboard`, `xclip | xsel`, `zenity`
  and the AppIndicator library. The first launch shows the welcome, disclaimer and how-to
  pages with zenity, and offers to add Scrubboard to the dock.
  * "Clean my clipboard" uses xclip/xsel on X11 and wl-clipboard on Wayland, including GNOME.
  * **Clean every copy automatically on GNOME Wayland** needs the bundled Shell extension
    (GNOME 45+, Ubuntu 24.04+). Scrubboard enables it when you turn that option on, and you
    log out and back in once. On Ubuntu 22.04 Wayland, choose "Ubuntu on Xorg" instead.
  * The tray icon on GNOME needs the AppIndicator extension, which Ubuntu ships.
* **Brief window.** On every platform, text can be pasted in the milliseconds between a copy
  and Scrubboard writing its placeholder.

## Quick start (development)

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
scrubboard first-run              # choose engine, download the model
scrubboard run-once --stdout --text "Pt John Smith, MRN 12345678, DOB 03/14/1950"
scrubboard                        # the tray app (same as `scrubboard daemon`)
scrubboard status                 # engines, downloads, config
pytest && ruff check .
```

The local LLM from a source checkout:

```bash
scrubboard download-model --llama-server
scrubboard download-model --llm qwen3-0.6b-pii-q4km
scrubboard set llm_enabled true
```

Compare engines on the synthetic notes: `python scripts/eval_recall.py --ner openmed-44m [--llm qwen3-0.6b-pii-q4km]`.

### Config (`~/.scrubboard/config.json`, or `scrubboard set <key> <value>`)

| Key | Default | Meaning |
|---|---|---|
| `intercept_enabled` | `false` | Clean every copy automatically (off = only on request) |
| `ner_model` | `openmed-44m` | `openmed-44m`, `nvidia-gliner`, or `none` (rules only) |
| `exclude_apps` | `[]` | App/process names never intercepted (substring match) |
| `keep_year` / `keep_zip3` | `true` | Safe Harbor year / 3-digit ZIP retention |
| `extra_keep_labels` | `[]` | Extra labels to keep, e.g. `occupation` |
| `llm_enabled` / `llm_model` | `false` / `qwen3-0.6b-pii-q4km` | Opt-in LLM pass |
| `llm_timeout_s` | `8` | After this, the rules+NER result is used |
| `max_chars` | `20000` | Longer copies are redacted up to this, with a visible truncation marker |
| `hotkey` | `""` | Optional "redact clipboard now" hotkey (`pip install 'scrubboard[hotkey]'`) |
| `placeholder_style` | `[LABEL]` | `[LABEL]`, `[REDACTED]`, or `BLOCK` |
| `models_dir` | `~/.scrubboard/models` | Downloaded models (installers use their bundled copy first) |
| `onboarding_done` | `false` | First-launch welcome/notice already shown |

## Installers and releases

All user-facing wording (welcome, disclaimer, how-to, installer progress text, download page)
lives in `scrubboard/texts.py`. `installer/render_texts.py` renders it for each installer,
and `--site DIR` renders the download page from `docs/site/index.template.html`. Icons are
drawn by `scripts/make_icons.py`.

Each installer bundles the privacy detector (`installer/fetch_models.py`) and `llama-server`
(`installer/fetch_llama.py`):

* **Windows:** `installer/win/build_exe.ps1` produces `dist/Scrubboard-Setup.exe` (Inno Setup
  6.3+). It's per-user with no admin rights. The pages are: welcome with the example → a
  disclaimer the user must accept → how to use it → choices (desktop shortcut, start at
  sign-in, turn off clipboard history) → install → finish. Signing is optional
  (`SIGNTOOL_ARGS`); unsigned builds show SmartScreen's "More info → Run anyway".
* **macOS:** `installer/mac/build_pkg.sh` produces a signed, notarized `dist/Scrubboard.pkg`.
  The macOS Installer shows welcome → how to use it → disclaimer (Agree) → install → done
  (macOS always puts the Read Me page before the license).
  It needs **Developer ID Application** *and* **Developer ID Installer** certificates.
  `SKIP_NOTARIZE=1` is for local tests.
* **Ubuntu:** `installer/linux/build_linux.sh` produces `dist/scrubboard_amd64.deb`, which
  opens in App Center, plus an `.rpm`. The app shows the same pages on first launch.

**One-link download:** push a tag (`git tag v0.1.0 && git push origin v0.1.0`) and
`.github/workflows/release.yml` builds all three and publishes a GitHub Release with stable
file names. `.github/workflows/pages.yml` publishes the download page, which picks the
right installer for the visitor's computer from `releases/latest/download/`. Enable Pages
with Settings → Pages → Source: GitHub Actions. The secrets needed are listed at the top of
`release.yml`.

## Privacy

See [docs/PRIVACY.md](docs/PRIVACY.md). There's no telemetry, no accounts, no logging of
clipboard text, and no network use (unless you turn on extra-careful mode, which downloads
its model once).

## Layout

* `scrubboard/`
  * `safe_harbor.py` — rules, policy, transforms
  * `pipeline.py` — rules + NER + LLM
  * `intercept.py` — the fail-closed controller
  * `watchers/` — per-OS clipboard backends and the GNOME socket
  * `llm/` — llama-server runtime and engine
  * `models/` — NER models and the pinned manifest
  * `app.py`, `tray.py`, `cli.py`
  * `texts.py` — every user-facing sentence (app, installers, download page)
  * `macos_service.py` — right-click → Services handler; `onboarding.py` — first launch
  * `single_instance.py` — one app per user session
* `gnome-extension/` — GNOME Shell extension for Wayland.
* `installer/` — PyInstaller spec, model/llama.cpp fetch, text rendering, and per-OS installers.
* `docs/site/` — the download page template.
* `scripts/eval_recall.py` — recall comparison. `tests/data/synthetic_notes/` holds the
  invented notes it uses.

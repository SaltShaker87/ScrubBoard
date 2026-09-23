"""`scrubboard` CLI."""
from __future__ import annotations

import argparse
import sys

from scrubboard import __version__
from scrubboard.config import NER_MODELS, ScrubboardConfig, coerce_value
from scrubboard.models.manifest import LLM_CATALOG


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="scrubboard",
                                description="Scrubboard: removes patient identifiers from copied text, locally")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd")  # no command = daemon (double-clicked app, autostart)

    r = sub.add_parser("run-once", help="redact the clipboard (or --text/--file) once")
    r.add_argument("--text", default=None)
    r.add_argument("--file", default=None, help="redact a text file's contents")
    r.add_argument("--stdout", action="store_true", help="print the result instead of writing the clipboard")
    r.add_argument("--ner", default=None, choices=NER_MODELS)
    r.add_argument("--threshold", type=float, default=None)
    r.add_argument("--llm", action="store_true", help="also run the local LLM pass")

    sub.add_parser("daemon", help="the tray app (default when no command is given)")
    sub.add_parser("first-run", help="choose engines, download models")
    sub.add_parser("status", help="show engines, downloaded models and config")

    d = sub.add_parser("download-model", help="download a model without the wizard")
    g = d.add_mutually_exclusive_group(required=True)
    g.add_argument("--ner", choices=[m for m in NER_MODELS if m != "none"])
    g.add_argument("--llm", choices=sorted(LLM_CATALOG))
    g.add_argument("--llama-server", action="store_true",
                   help="fetch the pinned llama.cpp server build (bundled in installers)")

    s = sub.add_parser("set", help="update a config value (see `scrubboard status`)")
    s.add_argument("key")
    s.add_argument("value")

    u = sub.add_parser("update-check", help="check a latest.json URL for a newer version")
    u.add_argument("--json-url", default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.cmd = args.cmd or "daemon"
    cfg = ScrubboardConfig.load()
    if cfg.load_warning:
        print(f"Scrubboard: {cfg.load_warning}", file=sys.stderr)

    if args.cmd == "first-run":
        from scrubboard.first_run import first_run
        first_run(cfg)
        return 0
    if args.cmd == "download-model":
        from scrubboard.download import download_llm, download_ner, print_progress
        if args.ner:
            print(f"-> {download_ner(args.ner, cfg.models_dir, print_progress)}")
        elif args.llama_server:
            from scrubboard.llm.binaries import fetch_llama_server
            print(f"-> {fetch_llama_server(progress=print_progress)}")
        else:
            print(f"-> {download_llm(args.llm, cfg.models_dir, print_progress)}")
        return 0
    if args.cmd == "set":
        return _cmd_set(cfg, args.key, args.value)
    if args.cmd == "status":
        return _cmd_status(cfg)
    if args.cmd == "update-check":
        from scrubboard.updater import check_for_update
        url = args.json_url or cfg.update_url
        if not url:
            print("No update URL configured (scrubboard set update_url <url>).")
            return 1
        upd = check_for_update(url)
        print(f"Update available: {upd['version']} -> {upd.get('download_url')}" if upd else "Up to date.")
        return 0
    if args.cmd == "run-once":
        return _cmd_run_once(cfg, args)
    if args.cmd == "daemon":
        from scrubboard.app import run_daemon
        return run_daemon(cfg)
    return 1


def _cmd_set(cfg: ScrubboardConfig, key: str, raw: str) -> int:
    try:
        value = coerce_value(key, raw)
        if key == "hotkey" and value:
            from scrubboard.hotkey import canonicalize
            value = canonicalize(value)
        setattr(cfg, key, value)
        cfg.save()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    print(f"Set {key}={value!r}")
    return 0


def _cmd_status(cfg: ScrubboardConfig) -> int:
    from scrubboard.download import is_llm_downloaded, is_ner_downloaded
    from scrubboard.pipeline import NotProtectedError, RedactionPipeline

    for key, value in cfg.to_dict().items():
        print(f"{key} = {value!r}")
    if cfg.ner_model != "none":
        print(f"NER model files: {'present' if is_ner_downloaded(cfg.ner_model, cfg.models_dir) else 'MISSING'}")
    print(f"LLM model files ({cfg.llm_model}): "
          f"{'present' if is_llm_downloaded(cfg.llm_model, cfg.models_dir) else 'not downloaded'}")
    try:
        RedactionPipeline(cfg).ensure_ready()
        print("Protection: ready")
        return 0
    except NotProtectedError as e:
        print(f"Protection: NOT PROTECTED — {e}")
        return 2


def _cmd_run_once(cfg: ScrubboardConfig, args) -> int:
    from scrubboard.pipeline import NotProtectedError, RedactionPipeline

    if args.ner:
        cfg.ner_model = args.ner
    if args.threshold is not None:
        cfg.threshold = args.threshold
    llm = None
    if args.llm:
        from scrubboard.llm import create_llm_engine
        cfg.llm_enabled = True
        llm = create_llm_engine(cfg, startup_timeout=cfg.llm_timeout_s)

    backend = None
    if args.text is not None:
        text = args.text
    elif args.file:
        with open(args.file, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    else:
        from scrubboard.watchers import create_backend
        backend = create_backend()
        text = backend.read_text() or ""
    if not text.strip():
        print("Nothing to redact.", file=sys.stderr)
        return 1

    try:
        result = RedactionPipeline(cfg, llm=llm).redact(text)
    except NotProtectedError as e:
        print(f"NOT PROTECTED: {e}\nNothing was redacted or written.", file=sys.stderr)
        return 2
    finally:
        if llm is not None:
            llm.close()

    if args.stdout:
        print(result.text)
    else:
        if backend is None:
            from scrubboard.watchers import create_backend
            backend = create_backend()
        backend.write_text(result.text)
    note = f" (LLM skipped: {result.llm_skipped})" if result.llm_skipped else ""
    print(f"redacted={result.total} engines={','.join(result.engines)}{note}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

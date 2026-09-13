"""`privatecopy` CLI."""
from __future__ import annotations

import argparse
import sys

from privatecopy import __version__
from privatecopy.config import PrivateCopyConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="privatecopy", description="PrivateCopy: local PII redaction to clipboard")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run-once", help="redact clipboard (or --text/--file) immediately")
    r.add_argument("--text", default=None)
    r.add_argument("--file", default=None, help="redact file contents (used by Explorer/file-manager verbs)")
    r.add_argument("--model", default=None, choices=["nvidia-gliner", "openmed-44m"])
    r.add_argument("--threshold", type=float, default=None)

    sub.add_parser("daemon", help="tray + global hotkey + loopback service")
    sub.add_parser("first-run", help="model picker + hotkey confirm + download")

    d = sub.add_parser("download-model", help="pre-fetch weights without wizard")
    d.add_argument("--model", default="nvidia-gliner", choices=["nvidia-gliner", "openmed-44m"])

    s = sub.add_parser("set", help="update a config value")
    s.add_argument("key", choices=["model", "threshold", "hotkey", "placeholder_style"])
    s.add_argument("value")

    u = sub.add_parser("update-check", help="check GitHub Releases for a newer version")
    u.add_argument("--json-url", default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = PrivateCopyConfig.load()

    if args.cmd == "first-run":
        from privatecopy.first_run import first_run
        first_run(cfg)
        return 0
    if args.cmd == "download-model":
        from scripts.download_models import download_model
        download_model(args.model, cfg.models_dir)
        return 0
    if args.cmd == "set":
        val = float(args.value) if args.key == "threshold" else args.value
        setattr(cfg, args.key, val)
        cfg.save()
        print(f"Set {args.key}={val!r}")
        return 0
    if args.cmd == "update-check":
        from privatecopy.updater import LATEST_URL, check_for_update
        upd = check_for_update(latest_url=args.json_url or LATEST_URL)
        print(f"Update available: {upd['version']} -> {upd.get('download_url')}" if upd else "Up to date.")
        return 0
    if args.cmd == "run-once":
        if args.model:
            cfg.model = args.model
        if args.threshold:
            cfg.threshold = args.threshold
        from privatecopy.service import PrivateCopyService
        text = args.text
        if text is None and args.file:
            with open(args.file, encoding="utf-8", errors="replace") as fh:
                text = fh.read(cfg.max_chars)
        _, n = PrivateCopyService(cfg).run_once(text)
        print(f"redacted={n}")
        return 0
    if args.cmd == "daemon":
        from privatecopy.hotkey import HotkeyListener
        from privatecopy.service import PrivateCopyService, serve_in_background
        from privatecopy.tray import TrayApp
        from privatecopy.updater import check_for_update
        service = PrivateCopyService(cfg)
        serve_in_background(cfg)
        upd = check_for_update() if cfg.auto_update else None
        if upd:
            print(f"Update available: {upd['version']} — {upd.get('download_url')}")
        try:
            HotkeyListener(cfg.hotkey, lambda: service.run_once()).start()
            print(f"Hotkey armed: {cfg.hotkey}. Tray running; trigger to redact clipboard.")
        except RuntimeError as e:
            print(f"Hotkey unavailable: {e}")
        TrayApp(on_copy_now=lambda: service.run_once()).run()
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

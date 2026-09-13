#!/usr/bin/env python3
"""macOS Services shim: posts selected text to the PrivateCopy loopback service
and replaces the selection with redacted text. Wired via Info.plist NSServices."""
import json
import subprocess
import sys
import urllib.request


def pb_get() -> str:
    return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout


def pb_set(text: str) -> None:
    subprocess.run(["pbcopy"], input=text, text=True, check=False)


def main() -> int:
    text = sys.argv[1] if len(sys.argv) > 1 else pb_get()
    req = urllib.request.Request("http://127.0.0.1:48173",
                                 data=json.dumps({"text": text}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
    except Exception as e:
        print(f"PrivateCopy daemon not running ({e}). Launch PrivateCopy first.", file=sys.stderr)
        return 1
    pb_set(body.get("redacted", text))
    print(f"PrivateCopy: redacted {body.get('count', 0)} item(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

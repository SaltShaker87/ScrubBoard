#!/usr/bin/env python3
"""Nautilus extension shim: right-click file -> PrivateCopy (redact to clipboard)."""
try:
    from gi.repository import Nautilus, GObject
    import json
    import urllib.request

    class PrivateCopyExtension(GObject.GObject, Nautilus.MenuProvider):
        def get_file_items(self, files):
            item = Nautilus.MenuItem(name="PrivateCopy::redact", label="PrivateCopy (redact to clipboard)")
            item.connect("activate", self._run, files)
            return [item]

        def _run(self, menu, files):
            paths = [f.get_location().get_path() for f in files]
            texts = []
            for p in paths:
                try:
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        texts.append(fh.read(10_000))
                except OSError:
                    pass
            body = json.dumps({"text": "\n\n".join(texts)}).encode()
            req = urllib.request.Request("http://127.0.0.1:48173/", data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                redacted = json.load(r)["redacted"]
            import subprocess
            subprocess.run(["xclip", "-selection", "clipboard"], input=redacted, text=True, check=False)
except ImportError:
    pass

# -*- mode: python -*-
# PyInstaller spec for every platform:
#   python installer/fetch_llama.py     # bundle the pinned llama.cpp server (opt-in LLM)
#   python installer/fetch_models.py    # bundle the privacy detector (required)
#   pyinstaller --noconfirm --clean installer/scrubboard.spec
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 (SPECPATH is set by PyInstaller)
sys.path.insert(0, ROOT)
from scrubboard import __version__  # noqa: E402
from scrubboard.texts import SERVICE_TITLE  # noqa: E402

BUILD = os.path.join(ROOT, "installer", "build")
datas = [(os.path.join(ROOT, "assets", "scrubboard-tray.png"), "assets"),
         (os.path.join(ROOT, "assets", "scrubboard-256.png"), "assets")]

MODELS_DIR = os.path.join(BUILD, "models")
if os.path.isdir(MODELS_DIR):
    datas.append((MODELS_DIR, "models"))
elif os.environ.get("SCRUBBOARD_ALLOW_NO_MODEL") != "1":
    raise SystemExit("installer/build/models missing: run `python installer/fetch_models.py` first "
                     "(or set SCRUBBOARD_ALLOW_NO_MODEL=1 for a build that downloads it on first start).")

LLAMA_DIR = os.path.join(BUILD, "llama")
if os.path.isdir(LLAMA_DIR):
    datas.append((LLAMA_DIR, "llama"))
else:
    print("WARNING: installer/build/llama missing; extra-careful mode will not work in this build.")

hiddenimports = collect_submodules("pystray") + ["truststore"]
if sys.platform.startswith("linux"):
    # Ubuntu's top bar only shows AppIndicator icons; these pull in the GObject typelibs.
    hiddenimports += collect_submodules("Xlib") + ["gi", "gi.repository.Gtk", "gi.repository.AyatanaAppIndicator3"]
if sys.platform == "darwin":
    hiddenimports += ["ServiceManagement"]
icon = {"darwin": "scrubboard.icns", "win32": "scrubboard.ico"}.get(sys.platform)

a = Analysis(  # noqa: F821
    [os.path.join(ROOT, "scrubboard", "__main__.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "torch", "transformers", "gliner"],
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz, a.scripts, [], exclude_binaries=True, name="Scrubboard", console=False,
    icon=os.path.join(ROOT, "assets", icon) if icon else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Scrubboard")  # noqa: F821

if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        coll, name="Scrubboard.app", icon=os.path.join(ROOT, "assets", "scrubboard.icns"),
        bundle_identifier="org.scrubboard.app",
        info_plist={
            "CFBundleName": "Scrubboard",
            "CFBundleDisplayName": "Scrubboard",
            "LSUIElement": True,  # menu-bar app: no Dock icon while running
            "LSMinimumSystemVersion": "12.0",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHumanReadableCopyright": "MIT License",
            # Right-click selected text → Services → "Scrubboard: Copy without patient info".
            "NSServices": [{
                "NSMenuItem": {"default": SERVICE_TITLE},
                "NSMessage": "cleanText",
                "NSPortName": "Scrubboard",
                "NSSendTypes": ["NSStringPboardType", "public.utf8-plain-text"],
                "NSRequiredContext": {},
            }],
        },
    )

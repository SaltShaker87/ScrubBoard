# -*- mode: python -*-
# PyInstaller spec for every platform:
#   python installer/fetch_llama.py            # bundle the pinned llama.cpp server
#   pyinstaller --noconfirm --clean installer/privatecopy.spec
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 (SPECPATH is set by PyInstaller)
sys.path.insert(0, ROOT)
from privatecopy import __version__  # noqa: E402

LLAMA_DIR = os.path.join(ROOT, "installer", "build", "llama")
datas = [(os.path.join(ROOT, "assets", "privatecopy-256.png"), "assets"),
         (os.path.join(ROOT, "gnome-extension"), "gnome-extension")]
if os.path.isdir(LLAMA_DIR):
    datas.append((LLAMA_DIR, "llama"))
else:
    print("WARNING: installer/build/llama missing; the local LLM option will not work in this build.")

hiddenimports = collect_submodules("pystray")
if sys.platform.startswith("linux"):
    hiddenimports += collect_submodules("Xlib")
icon = {"darwin": "privatecopy.icns", "win32": "privatecopy.ico"}.get(sys.platform)

a = Analysis(  # noqa: F821
    [os.path.join(ROOT, "privatecopy", "__main__.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "torch", "transformers", "gliner"],
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz, a.scripts, [], exclude_binaries=True, name="PrivateCopy", console=False,
    icon=os.path.join(ROOT, "assets", icon) if icon else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="PrivateCopy")  # noqa: F821

if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        coll, name="PrivateCopy.app", icon=os.path.join(ROOT, "assets", "privatecopy.icns"),
        bundle_identifier="org.privatecopy.app",
        info_plist={
            "LSUIElement": True,  # menu-bar app: no Dock icon
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHumanReadableCopyright": "MIT License",
        },
    )

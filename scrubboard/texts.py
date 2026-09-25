"""Plain-language text shown to users. Single source for the app (Linux first-launch
dialogs, the "How to use" page) and the installers (installer/render_texts.py turns
it into Inno Setup messages and macOS Installer pages).

Written for someone who has never used an AI tool: short sentences, no jargon.
"""
from __future__ import annotations

import html
import platform

APP = "Scrubboard"
SERVICE_TITLE = "Scrubboard: Copy without patient info"  # macOS right-click → Services item

WELCOME_TITLE = "Welcome to Scrubboard"
WELCOME = [
    "Scrubboard removes details that identify a patient, such as names, dates of birth, "
    "record numbers, phone numbers and addresses, from text you copy. You can then paste "
    "the cleaned text somewhere else.",
    "Why this matters: AI assistants are now easy to reach. For example, OpenAI offers "
    "clinicians free access to an AI tool. It's easy to paste part of a patient note into "
    "one of these tools and accidentally share protected health information (PHI).",
    "Scrubboard adds a safety layer: Copy text, let Scrubboard clean it, then Paste. "
    "PHI is removed.",
    "Everything happens on this computer. Scrubboard never sends your text anywhere, and "
    "it works without an internet connection.",
]

# The same message, short enough for the first page of the Windows installer.
WELCOME_SHORT = [
    "Scrubboard removes details that identify a patient (names, dates of birth, record "
    "numbers, phone numbers, addresses) from text you copy, so you can paste it more safely "
    "somewhere else.",
    "For example, OpenAI offers clinicians free access to an AI tool. Before you paste part of "
    "a patient note into it, let Scrubboard clean the text.",
    "Everything happens on this computer. Nothing is sent anywhere.",
]

DISCLAIMER_TITLE = "Important: please read"
DISCLAIMER = [
    "Scrubboard is not perfect. It uses automatic pattern matching and a small AI model "
    "that runs on this computer, and it can miss identifying details, especially unusual "
    "names, nicknames, rare conditions, or details written in an unexpected way.",
    "Always read the cleaned text yourself before you share or paste it anywhere. You are "
    "responsible for what you share.",
    "Scrubboard is a helper. It does not guarantee HIPAA compliance or make text "
    "\"de-identified\" by law.",
    "Follow your organization's rules about using AI tools and sharing patient "
    "information. Some organizations don't allow clinical text in outside AI tools at all, "
    "even after cleaning.",
    "Scrubboard is free, open-source software provided \"as is\", without warranty of any "
    "kind (MIT License).",
]
DISCLAIMER_ACCEPT = "I understand that Scrubboard can miss things and I will check the text myself"

# Real output of the bundled model (tests/test_app_ux.py checks it when the model is present).
EXAMPLE_BEFORE = ("Pt John Smith (DOB 03/14/1950, MRN: 12345678) has type 2 diabetes and takes metformin. "
                  "Call 617-555-0100.")
EXAMPLE_AFTER = ("Pt [NAME] [NAME] (DOB [DATE 1950], MRN: [MRN]) has type 2 diabetes and takes metformin. "
                 "Call [PHONE].")

_ICON_WHERE = {
    "Windows": "in the bottom-right corner of the screen, next to the clock. If you don't see it, "
               "click the small ^ arrow there",
    "Darwin": "in the menu bar at the top-right of the screen",
    "Linux": "in the top bar at the top-right of the screen",
}

_STEPS = {
    "Windows": [
        "Select the text and copy it as usual (Ctrl+C, or right-click and choose Copy).",
        "Click the Scrubboard icon near the clock. The copied text is cleaned in a second or two, "
        "and a message tells you how many details were removed.",
        "Paste (Ctrl+V) where you want it. Read it before you send it.",
    ],
    "Darwin": [
        "Select the text, right-click it, and choose Services, then "
        f"\"{SERVICE_TITLE}\". Or copy it as usual (⌘C), click the Scrubboard icon "
        "in the menu bar, and choose \"Clean my clipboard\".",
        "A small message appears in the top-right corner for a few seconds, telling you how "
        "many details were removed.",
        "Paste (⌘V) where you want it. Read it before you send it.",
    ],
    "Linux": [
        "Select the text and copy it as usual (Ctrl+C, or right-click and choose Copy).",
        "Click the Scrubboard icon in the top bar and choose \"Clean my clipboard\". "
        "A message tells you how many details were removed.",
        "Paste (Ctrl+V) where you want it. Read it before you send it.",
    ],
}

HOW_TO_TITLE = "How to use Scrubboard"
QUIT_HINT = "To stop Scrubboard, click its icon and choose \"Quit Scrubboard\"."
AUTO_HINT = ("If you prefer, turn on \"Clean every copy automatically\" in the Scrubboard menu. "
             "Then everything you copy is cleaned without any clicks.")


def _system(system: str | None) -> str:
    system = system or platform.system()
    return system if system in _STEPS else "Linux"


def icon_where(system: str | None = None) -> str:
    return _ICON_WHERE[_system(system)]


def how_to(system: str | None = None) -> list[str]:
    """Numbered steps + tips for this OS, as paragraphs."""
    s = _system(system)
    steps = [f"{i}. {step}" for i, step in enumerate(_STEPS[s], 1)]
    return [f"Scrubboard runs quietly in the background. Its icon is {_ICON_WHERE[s]}.", *steps,
            f"Example. Before: {EXAMPLE_BEFORE}", f"After: {EXAMPLE_AFTER}", AUTO_HINT, QUIT_HINT]


def running_notice(system: str | None = None) -> str:
    return f"Scrubboard is running. Its icon is {icon_where(system)}."


def already_running_notice(system: str | None = None) -> str:
    return f"Scrubboard is already running. Its icon is {icon_where(system)}."


def to_text(paragraphs: list[str]) -> str:
    return "\n\n".join(paragraphs)


def to_html(title: str, paragraphs: list[str]) -> str:
    body = "\n".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)
    return f"<h2>{html.escape(title)}</h2>\n{body}"


def help_page(system: str | None = None) -> str:
    """Stand-alone HTML page for the tray's "How to use Scrubboard…" item."""
    sections = "\n".join(to_html(t, p) for t, p in ((HOW_TO_TITLE, how_to(system)),
                                                     (WELCOME_TITLE.replace("Welcome to", "About"), WELCOME),
                                                     (DISCLAIMER_TITLE, DISCLAIMER)))
    return ("<!doctype html><html><head><meta charset='utf-8'><title>Scrubboard help</title>"
            "<style>body{font:16px/1.55 -apple-system,Segoe UI,Ubuntu,sans-serif;max-width:40em;"
            "margin:2em auto;padding:0 1em;color:#1d2b2a}h2{color:#0f6b66}</style></head>"
            f"<body>{sections}</body></html>")

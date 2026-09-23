"""macOS right-click → Services → "Scrubboard: Copy without patient info".

The Info.plist NSServices entry (installer/scrubboard.spec) routes the selected text
to ``cleanText:userData:error:`` here. The text goes through the same fail-closed path
as a copy: the clipboard gets a placeholder at once, then the cleaned text.
"""
from __future__ import annotations

from collections.abc import Callable

_provider = None  # keep the provider alive for the app's lifetime


def register(clean: Callable[[str], None]) -> None:
    """Install the Services provider. Call on the main thread before the run loop starts."""
    global _provider
    import objc
    from AppKit import NSApplication, NSPasteboardTypeString, NSUpdateDynamicServices
    from Foundation import NSObject

    class ScrubboardServiceProvider(NSObject):
        @objc.typedSelector(b"v@:@@o^@")
        def cleanText_userData_error_(self, pboard, _user_data, _error):
            try:
                text = pboard.stringForType_(NSPasteboardTypeString)
                clean("" if text is None else str(text))
            except Exception as e:  # never raise into AppKit
                return f"Scrubboard could not clean the text ({type(e).__name__})."
            return None

    _provider = ScrubboardServiceProvider.alloc().init()
    NSApplication.sharedApplication().setServicesProvider_(_provider)
    NSUpdateDynamicServices()

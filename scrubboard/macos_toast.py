"""macOS: a small message in the top-right corner that fades out by itself.

Drawn by Scrubboard in a click-through panel, so it needs no notification permission,
takes no focus and needs no click. Must run inside the app's AppKit run loop (the tray).
"""
from __future__ import annotations

SECONDS = 3.5
WIDTH = 340
MARGIN = 12

_panel = None  # the toast on screen, if any


def show(title: str, message: str) -> None:
    """Show a toast. Safe to call from any thread."""
    from PyObjCTools import AppHelper
    AppHelper.callAfter(_show, title, message)


def _show(title: str, message: str) -> None:
    global _panel
    import AppKit
    from PyObjCTools import AppHelper

    if _panel is not None:
        _panel.orderOut_(None)
    screen = AppKit.NSScreen.mainScreen()
    if screen is None:
        return

    pad, icon_size = 14, 36
    text_w = WIDTH - 3 * pad - icon_size
    head = AppKit.NSTextField.labelWithString_(title)
    head.setFont_(AppKit.NSFont.boldSystemFontOfSize_(13))
    body = AppKit.NSTextField.wrappingLabelWithString_(message)
    body.setFont_(AppKit.NSFont.systemFontOfSize_(12))
    body.setPreferredMaxLayoutWidth_(text_w)
    head_h = head.fittingSize().height
    body_h = body.fittingSize().height
    height = max(icon_size, head_h + 2 + body_h) + 2 * pad

    area = screen.visibleFrame()  # below the menu bar
    frame = AppKit.NSMakeRect(area.origin.x + area.size.width - WIDTH - MARGIN,
                              area.origin.y + area.size.height - height - MARGIN, WIDTH, height)
    panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        frame, AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
        AppKit.NSBackingStoreBuffered, False)
    panel.setLevel_(AppKit.NSStatusWindowLevel)
    panel.setOpaque_(False)
    panel.setBackgroundColor_(AppKit.NSColor.clearColor())
    panel.setHasShadow_(True)
    panel.setIgnoresMouseEvents_(True)
    panel.setReleasedWhenClosed_(False)
    panel.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                                 | AppKit.NSWindowCollectionBehaviorStationary
                                 | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)

    bg = AppKit.NSVisualEffectView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, WIDTH, height))
    bg.setMaterial_(AppKit.NSVisualEffectMaterialPopover)
    bg.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
    bg.setState_(AppKit.NSVisualEffectStateActive)
    bg.setWantsLayer_(True)
    bg.layer().setCornerRadius_(12)
    bg.layer().setMasksToBounds_(True)
    panel.setContentView_(bg)

    icon = AppKit.NSImageView.imageViewWithImage_(AppKit.NSApplication.sharedApplication().applicationIconImage())
    icon.setFrame_(AppKit.NSMakeRect(pad, height - pad - icon_size, icon_size, icon_size))
    head.setFrame_(AppKit.NSMakeRect(2 * pad + icon_size, height - pad - head_h, text_w, head_h))
    body.setFrame_(AppKit.NSMakeRect(2 * pad + icon_size, height - pad - head_h - 2 - body_h, text_w, body_h))
    for view in (icon, head, body):
        bg.addSubview_(view)

    panel.setAlphaValue_(0.0)
    panel.orderFrontRegardless()
    panel.animator().setAlphaValue_(1.0)
    _panel = panel
    AppHelper.callLater(SECONDS + len(message) / 60, _fade, panel)


def _fade(panel) -> None:
    global _panel
    if panel is not _panel:
        return  # a newer toast replaced it
    import AppKit
    from PyObjCTools import AppHelper

    AppKit.NSAnimationContext.beginGrouping()
    AppKit.NSAnimationContext.currentContext().setDuration_(0.4)
    panel.animator().setAlphaValue_(0.0)
    AppKit.NSAnimationContext.endGrouping()
    AppHelper.callLater(0.5, _close, panel)


def _close(panel) -> None:
    global _panel
    if panel is _panel:
        panel.orderOut_(None)
        _panel = None

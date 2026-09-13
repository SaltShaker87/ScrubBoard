"""Desktop notifications (plyer preferred, stdout fallback)."""
from __future__ import annotations


def notify(title: str, message: str) -> None:
    try:
        from plyer import notification
        notification.notify(title=title, message=message, app_name="PrivateCopy", timeout=5)
        return
    except Exception:
        pass
    print(f"[{title}] {message}")

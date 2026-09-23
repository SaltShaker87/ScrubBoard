#!/bin/sh
# Refresh the icon and app-grid caches so Scrubboard shows up right away.
gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database -q /usr/share/applications 2>/dev/null || true
exit 0

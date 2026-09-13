#!/bin/bash
# Linux: PyInstaller onedir -> .deb/.rpm via fpm + AppImage stub. Run on Ubuntu 22.04.
set -euo pipefail
VERSION="${1:-0.1.0}"
STAGE="installer/linux/stage"
rm -rf "$STAGE" && mkdir -p "$STAGE/usr/bin" "$STAGE/usr/share/applications" "$STAGE/usr/share/privatecopy" \
  "$STAGE/usr/share/icons/hicolor/256x256/apps"

if [ ! -f assets/privatecopy-256.png ] && [ -f assets/privatecopy-logo.png ]; then
  (pip install -q pillow && python scripts/make_icons.py) || echo "icon generation skipped"
fi

pyinstaller --noconfirm --clean --onedir --name privatecopy privatecopy/cli.py
cp -r dist/privatecopy/* "$STAGE/usr/bin/"
cp native/linux/privatecopy.desktop "$STAGE/usr/share/applications/"
cp native/linux/nautilus/privatecopy_nautilus.py native/linux/nemo/privatecopy.nemo_action "$STAGE/usr/share/privatecopy/" || true
[ -f assets/privatecopy-256.png ] && cp assets/privatecopy-256.png "$STAGE/usr/share/icons/hicolor/256x256/apps/privatecopy.png"

command -v fpm >/dev/null || gem install --no-document fpm
fpm -s dir -t deb -n privatecopy -v "$VERSION" -C "$STAGE" \
  --description "PrivateCopy: local PII redaction" --license MIT --maintainer "PrivateCopy" \
  -p "dist/privatecopy_${VERSION}_amd64.deb" usr
fpm -s dir -t rpm -n privatecopy -v "$VERSION" -C "$STAGE" \
  --description "PrivateCopy: local PII redaction" --license MIT \
  -p "dist/privatecopy-${VERSION}.x86_64.rpm" usr
echo "Built deb + rpm in dist/. AppImage: wrap $STAGE with appimagetool + update-info for auto-update."

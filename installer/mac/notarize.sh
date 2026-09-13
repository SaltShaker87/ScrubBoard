#!/bin/bash
# macOS: stage PrivateCopy.app, codesign, build DMG, notarize. Needs Apple Developer ID.
set -euo pipefail
VERSION="${1:-0.1.0}"
IDENTITY="${APPLE_DEVELOPER_IDENTITY:?set APPLE_DEVELOPER_IDENTITY}"
STAGE="installer/mac/stage"

echo "-> icons (build .icns from assets/privatecopy-logo.png if needed)"
if [ ! -f assets/privatecopy.icns ] && [ -f assets/privatecopy-logo.png ]; then
  (pip install -q pillow && python scripts/make_icons.py) || echo "icon generation skipped"
fi

echo "-> PyInstaller onedir (expects pyproject installed)"
ICON_ARGS=()
[ -f assets/privatecopy.icns ] && ICON_ARGS=(--icon assets/privatecopy.icns)
pyinstaller --noconfirm --clean --onedir --windowed --name PrivateCopy \
  "${ICON_ARGS[@]}" --add-data "native/mac/Info.plist:." --add-data "assets/privatecopy-logo.png:assets" \
  -c "from privatecopy.cli import main; main(['daemon'])" 2>/dev/null || \
pyinstaller --noconfirm --clean --onedir --windowed --name PrivateCopy "${ICON_ARGS[@]}" privatecopy/cli.py

if [ -f assets/privatecopy.icns ]; then
  echo "-> bundle icon"
  cp assets/privatecopy.icns dist/PrivateCopy.app/Contents/Resources/PrivateCopy.icns
fi

echo "-> codesign"
codesign --deep --force --verify --verbose --sign "$IDENTITY" --options runtime dist/PrivateCopy.app

echo "-> DMG"
mkdir -p "$STAGE" dist/dmg
cp -R dist/PrivateCopy.app "$STAGE/"
ln -sfn /Applications "$STAGE/Applications"
hdiutil create -volname "PrivateCopy $VERSION" -srcfolder "$STAGE" -ov -format UDZO "dist/dmg/PrivateCopy-$VERSION.dmg"

echo "-> notarize"
xcrun notarytool submit "dist/dmg/PrivateCopy-$VERSION.dmg" --wait \
  --apple-id "${APPLE_ID:?}" --team-id "${APPLE_TEAM_ID:?}" --password "${APPLE_APP_PASSWORD:?}"
xcrun stapler staple "dist/dmg/PrivateCopy-$VERSION.dmg"
echo OK

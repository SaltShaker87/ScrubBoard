#!/bin/bash
# macOS: build PrivateCopy.app (menu-bar only, bundles llama-server), sign every
# Mach-O inside-out with the hardened runtime, then build + notarize the DMG.
# Needs: APPLE_DEVELOPER_IDENTITY, APPLE_ID, APPLE_TEAM_ID, APPLE_APP_PASSWORD.
set -euo pipefail
IDENTITY="${APPLE_DEVELOPER_IDENTITY:?set APPLE_DEVELOPER_IDENTITY}"
STAGE="installer/mac/stage"

python3 -m pip install -e . pyinstaller
VERSION="$(python3 -c 'import privatecopy; print(privatecopy.__version__)')"
python3 installer/fetch_llama.py
pyinstaller --noconfirm --clean installer/privatecopy.spec
APP="dist/PrivateCopy.app"
find "$APP" -name llama-server -exec chmod +x {} +

echo "-> codesign (nested code first)"
find "$APP/Contents" -type f \( -name "*.dylib" -o -name "*.so" -o -name "llama-server" \) -print0 |
  xargs -0 -n1 codesign --force --options runtime --timestamp --sign "$IDENTITY"
codesign --force --options runtime --timestamp --sign "$IDENTITY" "$APP"
codesign --verify --strict --verbose=2 "$APP"

echo "-> DMG"
rm -rf "$STAGE" && mkdir -p "$STAGE" dist/dmg
cp -R "$APP" "$STAGE/"
ln -sfn /Applications "$STAGE/Applications"
DMG="dist/dmg/PrivateCopy-$VERSION.dmg"
hdiutil create -volname "PrivateCopy $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
codesign --force --timestamp --sign "$IDENTITY" "$DMG"

echo "-> notarize"
xcrun notarytool submit "$DMG" --wait \
  --apple-id "${APPLE_ID:?}" --team-id "${APPLE_TEAM_ID:?}" --password "${APPLE_APP_PASSWORD:?}"
xcrun stapler staple "$DMG"
echo "OK: $DMG"

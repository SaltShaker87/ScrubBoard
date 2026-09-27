#!/bin/bash
# macOS: build Scrubboard.app (menu-bar app with the right-click Services item and the
# bundled privacy detector), sign it, wrap it in an Installer package whose pages explain
# each step, then sign + notarize the package.
#
# Needs two certificates from the same Apple Developer account, plus notary credentials:
#   APPLE_DEVELOPER_IDENTITY  "Developer ID Application: Name (TEAMID)"  (signs the app)
#   APPLE_INSTALLER_IDENTITY  "Developer ID Installer: Name (TEAMID)"    (signs the .pkg)
#   APPLE_ID, APPLE_TEAM_ID, APPLE_APP_PASSWORD                          (notarytool)
# SKIP_NOTARIZE=1 builds and signs without notarizing (local testing).
# NOTARY_PROFILE=<name> notarizes with credentials saved by `xcrun notarytool store-credentials`.
# UNSIGNED=1 ad-hoc signs the app and leaves the .pkg unsigned (local testing, no certificates).
set -euo pipefail
if [ "${UNSIGNED:-0}" = "1" ]; then
  APP_IDENTITY="-"; SIGN_FLAGS=(); PKG_SIGN=(); SKIP_NOTARIZE=1
else
  APP_IDENTITY="${APPLE_DEVELOPER_IDENTITY:?set APPLE_DEVELOPER_IDENTITY}"
  SIGN_FLAGS=(--options runtime --timestamp)
  PKG_SIGN=(--sign "${APPLE_INSTALLER_IDENTITY:?set APPLE_INSTALLER_IDENTITY}")
fi
PY="${PYTHON:-python3}"
PIP="${PIP:-$PY -m pip}"  # e.g. PIP="uv pip" for a uv-made venv
BUILD="installer/build/mac"

$PIP install -e . pyinstaller
VERSION="$("$PY" -c 'import scrubboard; print(scrubboard.__version__)')"
"$PY" installer/fetch_llama.py
"$PY" installer/fetch_models.py
"$PY" installer/render_texts.py
pyinstaller --noconfirm --clean installer/scrubboard.spec
APP="dist/Scrubboard.app"
find "$APP" -name llama-server -exec chmod +x {} +

echo "-> codesign the app (nested code first)"
sign() { codesign --force ${SIGN_FLAGS[@]+"${SIGN_FLAGS[@]}"} --sign "$APP_IDENTITY" "$@"; }
# Every Mach-O file, whatever its name (e.g. Python.framework/Versions/3.11/Python has no
# extension), then framework bundles, then the app itself.
find "$APP/Contents" -type f -print0 | while IFS= read -r -d '' f; do
  if file -b "$f" | grep -q "Mach-O"; then sign "$f"; fi
done
find "$APP/Contents" -type d -path "*.framework/Versions/*" -prune ! -name Current -print0 |
  while IFS= read -r -d '' v; do sign "$v"; done
codesign --force ${SIGN_FLAGS[@]+"${SIGN_FLAGS[@]}"} --sign "$APP_IDENTITY" "$APP"
codesign --verify --strict --verbose=2 "$APP"

echo "-> component package"
rm -rf "$BUILD" && mkdir -p "$BUILD/root/Applications" "$BUILD/resources"
cp -R "$APP" "$BUILD/root/Applications/"
pkgbuild --analyze --root "$BUILD/root" "$BUILD/component.plist"
plutil -replace 0.BundleIsRelocatable -bool NO "$BUILD/component.plist"  # always /Applications
pkgbuild --root "$BUILD/root" --component-plist "$BUILD/component.plist" \
  --identifier org.scrubboard.app --version "$VERSION" --install-location / \
  --scripts installer/mac/scripts "$BUILD/Scrubboard-component.pkg"

echo "-> installer package"
cp installer/build/text/mac/*.html assets/pkg-background.png "$BUILD/resources/"
sed "s/@ARCH@/$(uname -m)/" installer/mac/distribution.xml > "$BUILD/distribution.xml"
PKG="dist/Scrubboard.pkg"
productbuild --distribution "$BUILD/distribution.xml" --resources "$BUILD/resources" \
  --package-path "$BUILD" --version "$VERSION" ${PKG_SIGN[@]+"${PKG_SIGN[@]}"} "$PKG"

if [ "${SKIP_NOTARIZE:-0}" != "1" ]; then
  echo "-> notarize"
  if [ -n "${NOTARY_PROFILE:-}" ]; then  # xcrun notarytool store-credentials <name>
    AUTH=(--keychain-profile "$NOTARY_PROFILE")
  else
    AUTH=(--apple-id "${APPLE_ID:?}" --team-id "${APPLE_TEAM_ID:?}" --password "${APPLE_APP_PASSWORD:?}")
  fi
  RESULT="$(xcrun notarytool submit "$PKG" --wait --output-format json "${AUTH[@]}" || true)"
  echo "$RESULT"
  if ! grep -q '"status" *: *"Accepted"' <<<"$RESULT"; then
    ID="$(sed -n 's/.*"id" *: *"\([^"]*\)".*/\1/p' <<<"$RESULT")"
    [ -n "$ID" ] && xcrun notarytool log "$ID" "${AUTH[@]}"  # Apple's reasons
    echo "Notarization failed." >&2
    exit 1
  fi
  xcrun stapler staple "$PKG"
fi
echo "OK: $PKG"

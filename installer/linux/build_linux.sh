#!/bin/bash
# Linux: PyInstaller onedir -> /opt/privatecopy, packaged as .deb and .rpm with fpm.
# Run on Ubuntu 22.04+. Build deps:
#   sudo apt install ruby-dev libgirepository1.0-dev libcairo2-dev && sudo gem install fpm
set -euo pipefail
STAGE="installer/linux/stage"

python3 -m pip install -e . pyinstaller PyGObject
VERSION="$(python3 -c 'import privatecopy; print(privatecopy.__version__)')"
python3 installer/fetch_llama.py
pyinstaller --noconfirm --clean installer/privatecopy.spec
find dist/PrivateCopy -name llama-server -exec chmod +x {} +

rm -rf "$STAGE"
mkdir -p "$STAGE/opt/privatecopy" "$STAGE/usr/bin" "$STAGE/usr/share/applications" \
  "$STAGE/etc/xdg/autostart" "$STAGE/usr/share/icons/hicolor/256x256/apps" \
  "$STAGE/usr/share/gnome-shell/extensions"
cp -r dist/PrivateCopy/* "$STAGE/opt/privatecopy/"
ln -s /opt/privatecopy/PrivateCopy "$STAGE/usr/bin/privatecopy"
cp installer/linux/privatecopy.desktop "$STAGE/usr/share/applications/"
cp installer/linux/privatecopy.desktop "$STAGE/etc/xdg/autostart/"
cp assets/privatecopy-256.png "$STAGE/usr/share/icons/hicolor/256x256/apps/privatecopy.png"
cp -r gnome-extension/privatecopy@privatecopy.org "$STAGE/usr/share/gnome-shell/extensions/"

DESC="PrivateCopy: removes HIPAA Safe Harbor identifiers from copied text, locally"
fpm -s dir -t deb -n privatecopy -v "$VERSION" -C "$STAGE" --license MIT \
  --maintainer "PrivateCopy contributors" --description "$DESC" \
  --depends "xclip | xsel" --depends wl-clipboard --depends libnotify-bin \
  --depends gir1.2-ayatanaappindicator3-0.1 \
  -p "dist/privatecopy_${VERSION}_amd64.deb" .
fpm -s dir -t rpm -n privatecopy -v "$VERSION" -C "$STAGE" --license MIT --description "$DESC" \
  --depends xclip --depends wl-clipboard --depends libnotify \
  -p "dist/privatecopy-${VERSION}.x86_64.rpm" .
echo "Built dist/privatecopy_${VERSION}_amd64.deb and the .rpm."
echo "GNOME on Wayland: users run 'gnome-extensions enable privatecopy@privatecopy.org' and log in again."

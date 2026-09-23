#!/bin/bash
# Ubuntu: PyInstaller onedir -> /opt/scrubboard, packaged as dist/scrubboard_amd64.deb
# (double-click opens it in App Center). First launch shows the welcome, disclaimer and
# how-to pages (scrubboard/onboarding.py). Also builds an .rpm for other distros.
# Run on Ubuntu 22.04. Build deps:
#   sudo apt install ruby-dev libgirepository1.0-dev libcairo2-dev \
#     gir1.2-ayatanaappindicator3-0.1 && sudo gem install fpm
set -euo pipefail
STAGE="installer/linux/stage"

# PyGObject 3.51+ needs girepository-2.0, which Ubuntu 22.04 lacks.
python3 -m pip install -e . pyinstaller "PyGObject<3.51"
VERSION="$(python3 -c 'import scrubboard; print(scrubboard.__version__)')"
python3 installer/fetch_llama.py
python3 installer/fetch_models.py
pyinstaller --noconfirm --clean installer/scrubboard.spec
find dist/Scrubboard -name llama-server -exec chmod +x {} +

rm -rf "$STAGE"
mkdir -p "$STAGE/opt/scrubboard" "$STAGE/usr/bin" "$STAGE/usr/share/applications" \
  "$STAGE/etc/xdg/autostart" "$STAGE/usr/share/icons/hicolor/256x256/apps" \
  "$STAGE/usr/share/gnome-shell/extensions"
cp -r dist/Scrubboard/* "$STAGE/opt/scrubboard/"
ln -s /opt/scrubboard/Scrubboard "$STAGE/usr/bin/scrubboard"
cp installer/linux/scrubboard.desktop "$STAGE/usr/share/applications/"
cp installer/linux/scrubboard.desktop "$STAGE/etc/xdg/autostart/"
cp assets/scrubboard-256.png "$STAGE/usr/share/icons/hicolor/256x256/apps/scrubboard.png"
# Only used if "Clean every copy automatically" is turned on (GNOME on Wayland).
cp -r "gnome-extension/scrubboard@scrubboard.github.io" "$STAGE/usr/share/gnome-shell/extensions/"

DESC="Scrubboard: removes patient details from copied text before you paste it. Runs only on this computer."
fpm -s dir -t deb -n scrubboard -v "$VERSION" -C "$STAGE" --license MIT \
  --maintainer "Scrubboard contributors" --description "$DESC" --category utils \
  --depends "xclip | xsel" --depends wl-clipboard --depends zenity --depends libnotify-bin \
  --depends gir1.2-ayatanaappindicator3-0.1 \
  --after-install installer/linux/after-install.sh \
  -p "dist/scrubboard_amd64.deb" .
fpm -s dir -t rpm -n scrubboard -v "$VERSION" -C "$STAGE" --license MIT --description "$DESC" \
  --depends xclip --depends wl-clipboard --depends zenity --depends libnotify \
  --after-install installer/linux/after-install.sh \
  -p "dist/scrubboard.x86_64.rpm" .
echo "Built dist/scrubboard_amd64.deb and dist/scrubboard.x86_64.rpm"

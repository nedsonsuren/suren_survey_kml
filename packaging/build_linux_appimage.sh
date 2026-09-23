#!/usr/bin/env bash
# Builds Survey-to-KML.AppImage — a single double-clickable file for any
# x86_64 Linux desktop, no Python install required on the target machine.
#
# Run this ON A LINUX MACHINE from the repo root:
#   bash packaging/build_linux_appimage.sh
#
# Output: Survey-to-KML-<version>-x86_64.AppImage in the repo root.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "$(uname -s)" != "Linux" ]; then
    echo "This script builds a Linux AppImage — run it on a Linux machine." >&2
    exit 1
fi

VERSION=$(python3 -c "from version import __version__; print(__version__)")
APPDIR="AppDir"
BIN_NAME="survey-to-kml"

echo "==> Setting up a build venv"
python3 -m venv .build-venv
# shellcheck disable=SC1091
source .build-venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt pyinstaller

echo "==> Building the onefile binary with PyInstaller"
pyinstaller survey_to_kml.spec --noconfirm

echo "==> Assembling the AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp "dist/Survey-to-KML" "$APPDIR/usr/bin/$BIN_NAME"
chmod +x "$APPDIR/usr/bin/$BIN_NAME"

cp packaging/survey-to-kml.desktop "$APPDIR/survey-to-kml.desktop"
cp assets/icon.png "$APPDIR/survey-to-kml.png"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/survey-to-kml" "$@"
EOF
chmod +x "$APPDIR/AppRun"

echo "==> Fetching appimagetool (if not already present)"
if [ ! -x appimagetool.AppImage ]; then
    curl -L -o appimagetool.AppImage \
        https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool.AppImage
fi

echo "==> Building the AppImage"
./appimagetool.AppImage "$APPDIR" "Survey-to-KML-${VERSION}-x86_64.AppImage"

deactivate
echo "==> Done: Survey-to-KML-${VERSION}-x86_64.AppImage"

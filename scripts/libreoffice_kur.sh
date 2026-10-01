#!/usr/bin/env bash
# Render's native Python runtime has no apt; install a portable LibreOffice for PPTX conversion.
set -euo pipefail
DEST="${LIBREOFFICE_DIR:-$PWD/.libreoffice}"
URL="${LIBREOFFICE_APPIMAGE_URL:-https://appimages.libreitalia.org/LibreOffice-still.basic-x86_64.AppImage}"
if compgen -G "$DEST/squashfs-root/opt/libreoffice*/program/soffice" > /dev/null; then
  echo "LibreOffice zaten kurulu: $DEST"
  exit 0
fi
rm -rf "$DEST"
mkdir -p "$DEST"
cd "$DEST"
curl -fL --retry 3 --retry-delay 5 -o libreoffice.AppImage "$URL"
chmod +x libreoffice.AppImage
./libreoffice.AppImage --appimage-extract > /dev/null
rm -f libreoffice.AppImage
echo "LibreOffice kuruldu: $(ls -d "$DEST"/squashfs-root/opt/libreoffice*/program/soffice)"

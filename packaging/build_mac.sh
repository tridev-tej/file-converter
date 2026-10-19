#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src"
export PYINSTALLER_CONFIG_DIR="$PWD/build/pyinstaller-cache"
export XDG_CACHE_HOME="$PWD/build/cache"
export FC_CONFIG_DIR="$PWD/build/frozen-config"
export FC_WORKSPACE="$PWD/build/frozen-work"
export TMPDIR="$PWD/build/tmp"
mkdir -p "$TMPDIR" build/tools
for tool in /usr/bin/codesign /usr/bin/hdiutil /usr/bin/iconutil; do
    test -x "$tool" || { echo "Missing build tool: $tool" >&2; exit 1; }
done
test -x .venv/bin/python || { echo "Missing existing .venv" >&2; exit 1; }
.venv/bin/python packaging/preflight.py
.venv/bin/python packaging/make_icons.py
.venv/bin/python packaging/collect_licenses.py
.venv/bin/python packaging/copy_ffmpeg.py build/tools/ffmpeg
chmod +x build/tools/ffmpeg vendor/pandoc/pandoc
.venv/bin/python -m PyInstaller --noconfirm --clean --workpath build/pyinstaller packaging/file_converter.spec
/usr/bin/codesign --force --deep -s - dist/FileConverter.app
/usr/bin/codesign --verify --deep --strict dist/FileConverter.app
dist/FileConverter.app/Contents/MacOS/FileConverter self-test build/selftest-app
.venv/bin/python packaging/frozen_smoke.py dist/FileConverter.app/Contents/MacOS/FileConverter
mkdir -p build/dmg
rm -rf build/dmg/FileConverter.app
ditto dist/FileConverter.app build/dmg/FileConverter.app
test -L build/dmg/Applications || ln -s /Applications build/dmg/Applications
/usr/bin/hdiutil create -volname FileConverter -srcfolder build/dmg -ov -format UDZO dist/FileConverter-macOS-arm64.dmg
test -s dist/FileConverter-macOS-arm64.dmg

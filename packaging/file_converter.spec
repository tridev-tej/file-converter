"""One-folder native GUI and console launchers sharing the same application."""

import sys
from pathlib import Path

import PySide6
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

root = Path(SPECPATH).parent
sys.path.insert(0, str(root / "src"))

mac = sys.platform == "darwin"
suffix = "" if mac else ".exe"
pandoc = root / "vendor/pandoc" / ("pandoc" + suffix)
if not pandoc.is_file():
    raise RuntimeError("Missing verified native vendor/pandoc executable")
staged_ffmpeg = root / "build/tools" / ("ffmpeg" + suffix)
if not staged_ffmpeg.is_file():
    raise RuntimeError("Run build script to stage FFmpeg")
binaries = [(str(staged_ffmpeg), "tools"), (str(pandoc), "tools")]
datas = [(str(root / "build/licenses"), "licenses")]
for package in ("docx", "pptx", "pypdfium2", "pypdfium2_raw", "pillow_heif"):
    datas += collect_data_files(package)
    binaries += collect_dynamic_libs(package)
hiddenimports = collect_submodules("file_converter") + collect_submodules("PIL")
hiddenimports += ["odf.opendocument", "odf.table", "py7zr", "xlrd", "openpyxl", "lxml.etree"]
if mac:
    hiddenimports += ["Quartz", "ApplicationServices", "AppKit", "Foundation", "Vision", "CoreML", "CoreText"]
else:
    hiddenimports += ["pynput.keyboard._win32", "pynput.mouse._win32"]
needed_qt = {"QtCore", "QtGui", "QtWidgets", "QtNetwork"}
excludes = ["PySide6." + name for name in PySide6.__all__ if name.startswith("Qt") and name not in needed_qt]
excludes += ["tkinter", "matplotlib", "numpy", "pypandoc", "pytest", "file_converter.platform.gesture_win" if mac else "file_converter.platform.gesture_mac"]
excludes += ["pynput"] if mac else ["Quartz", "AppKit", "Foundation", "Vision", "objc", "ApplicationServices", "CoreML", "CoreText"]
analysis = Analysis([str(root / "packaging/entry_gui.py"), str(root / "packaging/entry_cli.py")], pathex=[str(root / "src")], binaries=binaries, datas=datas, hiddenimports=hiddenimports, excludes=excludes, hookspath=[str(root / "packaging/hooks")], noarchive=False)
pyz = PYZ(analysis.pure)
gui_scripts = [script for script in analysis.scripts if script[0] != "entry_cli"]
cli_scripts = [script for script in analysis.scripts if script[0] != "entry_gui"]
gui = EXE(pyz, gui_scripts, exclude_binaries=True, name="FileConverter", console=False, icon=str(root / "build/icons" / ("FileConverter.icns" if mac else "FileConverter.ico")), target_arch="arm64" if mac else None)
if mac:
    collection = COLLECT(gui, analysis.binaries, analysis.datas, strip=False, upx=False, name="FileConverter")
    bundle = BUNDLE(collection, name="FileConverter.app", icon=str(root / "build/icons/FileConverter.icns"), bundle_identifier="com.tejeshvaish.fileconverter", info_plist={"LSUIElement": True, "NSAppleEventsUsageDescription": "FileConverter opens Terminal in the selected folder when you choose Open terminal.", "CFBundleShortVersionString": "1.0.0", "NSHighResolutionCapable": True})
else:
    cli = EXE(pyz, cli_scripts, exclude_binaries=True, name="file-converter", console=True, icon=str(root / "build/icons/FileConverter.ico"))
    collection = COLLECT(gui, cli, analysis.binaries, analysis.datas, strip=False, upx=False, name="FileConverter")

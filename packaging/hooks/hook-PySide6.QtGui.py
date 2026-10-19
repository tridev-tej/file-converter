from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, destination) for source, destination in binaries if "virtualkeyboard" not in source.lower() and "tuiotouch" not in source.lower()]

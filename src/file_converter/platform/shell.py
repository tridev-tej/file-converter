"""Native shell operations with argument arrays and no filename interpolation."""

import os
import subprocess
import sys
from pathlib import Path


def open_path(path):
    if sys.platform == "darwin":
        subprocess.run(["/usr/bin/open", str(path)], check=True)
    elif sys.platform == "win32":
        os.startfile(str(path))
    else:
        raise RuntimeError("Unsupported platform")


def reveal(path):
    if sys.platform == "darwin":
        subprocess.run(["/usr/bin/open", "-R", str(path)], check=True)
    elif sys.platform == "win32":
        subprocess.Popen(["explorer.exe", "/select," + str(path)])
    else:
        raise RuntimeError("Unsupported platform")


def terminal(directory):
    if sys.platform == "darwin":
        script = 'on run argv\n tell application "Terminal"\n activate\n do script "cd " & quoted form of item 1 of argv\n end tell\nend run'
        subprocess.run(["/usr/bin/osascript", "-e", script, str(directory)], check=True, capture_output=True)
    elif sys.platform == "win32":
        subprocess.Popen(["cmd.exe", "/K"], cwd=directory, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        raise RuntimeError("Unsupported platform")


def clipboard(text):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        app.clipboard().setText(text)
        if app.clipboard().text() != text:
            raise RuntimeError("Clipboard did not retain the text")
        return
    if sys.platform == "darwin":
        subprocess.run(["/usr/bin/pbcopy"], input=text.encode("utf-8"), check=True)
    elif sys.platform == "win32":
        windows_clipboard(text)
    else:
        raise RuntimeError("Unsupported clipboard platform")


def windows_clipboard(text):
    import ctypes
    from ctypes import wintypes
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalLock.restype = ctypes.c_void_p
    kernel.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    user.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user.SetClipboardData.restype = wintypes.HANDLE
    data = (text + "\x00").encode("utf-16-le")
    handle = kernel.GlobalAlloc(0x42, len(data))
    if not handle:
        raise OSError("Could not allocate clipboard storage")
    pointer = kernel.GlobalLock(handle)
    if not pointer:
        raise OSError("Could not lock clipboard storage")
    ctypes.memmove(pointer, data, len(data))
    kernel.GlobalUnlock(handle)
    if not user.OpenClipboard(None):
        raise OSError("Could not open clipboard")
    try:
        if not user.EmptyClipboard() or not user.SetClipboardData(13, handle):
            raise OSError("Could not write clipboard")
    finally:
        user.CloseClipboard()


def apply_effects(result):
    handlers = {"reveal": reveal, "terminal": terminal}
    if result.clipboard_text:
        clipboard(result.clipboard_text)
    for name, path in result.effects:
        handlers[name](Path(path))

"""Explicit registration of this application's own login entry."""

import os
import plistlib
import subprocess
import sys
from pathlib import Path

IDENTITY = "com.tejeshvaish.fileconverter"


def program_arguments():
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).resolve()), "--tray-only"]
    return [str(Path(sys.executable).absolute()), str(Path(__file__).resolve().parents[3] / "packaging/dev_entry.py"), "--tray-only"]


def set_enabled(enabled):
    if os.environ.get("FC_CONFIG_DIR"):
        raise RuntimeError("Login registration is blocked while FC_CONFIG_DIR is set")
    if sys.platform == "darwin":
        mac_register(enabled)
    elif sys.platform == "win32":
        windows_register(enabled)
    else:
        raise RuntimeError("Unsupported login registration platform")


def mac_register(enabled):
    target = Path.home() / "Library/LaunchAgents" / (IDENTITY + ".plist")
    if enabled:
        target.parent.mkdir(parents=True, exist_ok=True)
        data = dict(Label=IDENTITY, ProgramArguments=program_arguments(), RunAtLoad=True, WorkingDirectory=str(Path(__file__).resolve().parents[3]))
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(plistlib.dumps(data))
        temporary.replace(target)
    elif target.exists():
        target.unlink()


def windows_register(enabled):
    import winreg
    name = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, name, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, "FileConverter", 0, winreg.REG_SZ, subprocess.list2cmdline(program_arguments()))
        else:
            try:
                winreg.QueryValueEx(key, "FileConverter")
            except FileNotFoundError:
                return
            winreg.DeleteValue(key, "FileConverter")

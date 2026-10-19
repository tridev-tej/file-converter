"""Release-blocking native binary and selected capability preflight."""

import importlib.metadata
import json
import platform
import struct
import sys
from pathlib import Path

from file_converter.core.processes import run_process
from file_converter.core.tools import discover_tools


def binary_architecture(path):
    data = path.read_bytes()[:4096]
    if data[:4] == b"\xcf\xfa\xed\xfe":
        return {0x0100000C: "arm64", 0x01000007: "x86_64"}.get(struct.unpack_from("<I", data, 4)[0], "unknown")
    if data[:2] == b"MZ":
        offset = struct.unpack_from("<I", data, 60)[0]
        return {0x8664: "x86_64", 0xAA64: "arm64"}.get(struct.unpack_from("<H", data, offset + 4)[0], "unknown")
    raise RuntimeError(f"Unsupported executable header: {path}")


def main():
    tools = discover_tools()
    expected = "arm64" if sys.platform == "darwin" else "x86_64"
    observed = {}
    for name in ("ffmpeg", "pandoc"):
        tool = getattr(tools, name)
        if not tool.available:
            raise RuntimeError(tool.reason)
        arch = binary_architecture(tool.path)
        if arch != expected:
            raise RuntimeError(f"{name}: expected {expected}, found {arch}: {tool.path}")
        observed[name] = dict(path=str(tool.path), architecture=arch, version=tool.version)
    if sys.platform == "darwin" and platform.machine() != "arm64":
        raise RuntimeError("macOS release must be built natively on arm64")
    observed["python"] = dict(version=sys.version, architecture=platform.machine())
    observed["dependencies"] = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    path = Path("build/preflight.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(observed, indent=2))
    print(json.dumps(observed, indent=2))


if __name__ == "__main__":
    main()

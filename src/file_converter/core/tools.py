"""Deterministic tool discovery and capability snapshots."""

import os
import platform
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from .operations import Availability
from .processes import run_process


@dataclass(frozen=True)
class Tool:
    path: Path | None = None
    version: str = ""
    reason: str = ""
    capabilities: frozenset[str] = frozenset()

    @property
    def available(self):
        return self.path is not None and not self.reason


@dataclass(frozen=True)
class ToolSnapshot:
    ffmpeg: Tool = field(default_factory=lambda: Tool(reason="needs bundled FFmpeg"))
    pandoc: Tool = field(default_factory=lambda: Tool(reason="needs Pandoc"))
    office: Tool = field(default_factory=lambda: Tool(reason="needs LibreOffice"))
    system: str = sys.platform
    image_readers: frozenset[str] = frozenset()
    image_writers: frozenset[str] = frozenset()

    def as_dict(self):
        return asdict(self)


def bundle_root():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[3]


def ffmpeg_path():
    if getattr(sys, "frozen", False):
        name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        return bundle_root() / "tools" / name
    import imageio_ffmpeg
    return Path(imageio_ffmpeg.get_ffmpeg_exe())


def pandoc_path():
    if getattr(sys, "frozen", False):
        name = "pandoc.exe" if sys.platform == "win32" else "pandoc"
        return bundle_root() / "tools" / name
    if sys.platform == "darwin":
        return bundle_root() / "vendor/pandoc/pandoc"
    found = shutil.which("pandoc")
    return Path(found) if found else None


def office_path():
    paths = [Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")]
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        if os.environ.get(variable):
            paths.append(Path(os.environ[variable]) / "LibreOffice/program/soffice.exe")
    found = shutil.which("soffice")
    if found:
        paths.append(Path(found))
    return next((path for path in paths if path.is_file()), None)


def probe(path, name):
    if path is None or not path.is_file():
        return Tool(reason=f"needs {name}")
    try:
        result = run_process([path, "--version" if name != "FFmpeg" else "-version"], timeout=15)
        version = (result.stdout + result.stderr).splitlines()[0]
        capabilities = frozenset()
        if name == "FFmpeg":
            encoders = run_process([path, "-hide_banner", "-encoders"], timeout=15).stdout
            capabilities = frozenset(re.findall(r"^ [VAS][A-Z.]{5}\s+(\S+)", encoders, re.M))
        if sys.platform == "darwin":
            verify_macho(path)
        return Tool(path.resolve(), version, "", capabilities)
    except (RuntimeError, OSError, TimeoutError) as error:
        return Tool(path, reason=f"{name}: {error}")


def verify_macho(path):
    result = run_process(["/usr/bin/file", path], timeout=10).stdout
    if platform.machine() == "arm64" and "arm64" not in result:
        raise RuntimeError(f"Native arm64 executable required: {result.strip()}")


@lru_cache(maxsize=1)
def discover_tools():
    from PIL import Image
    import pillow_heif
    pillow_heif.register_heif_opener()
    Image.init()
    normalize = {"JPEG": "jpg", "HEIF": "heic"}
    readers = frozenset(normalize.get(name, name.lower()) for name in Image.OPEN)
    writers = frozenset(normalize.get(name, name.lower()) for name in Image.SAVE)
    if not pillow_heif.libheif_info().get("HEIF"):
        writers = writers - {"heic"}
    return ToolSnapshot(probe(ffmpeg_path(), "FFmpeg"), probe(pandoc_path(), "Pandoc"), probe(office_path(), "LibreOffice"), sys.platform, readers, writers)


def refresh_tools():
    discover_tools.cache_clear()
    return discover_tools()


def document_route(source, target):
    if source == "doc":
        return "office-pandoc" if target in {"md", "epub"} else "office"
    if target == "pdf":
        return "pandoc-office" if source in {"md", "epub"} else "office"
    return "pandoc"


def routes_for(op, items):
    if op.id.startswith("doc.to."):
        return tuple(document_route(item.format, op.target_format) for item in items if item.format != op.target_format)
    return ("-".join(op.requires) or "native",)


def image_reasons(op, items, tools):
    if not op.id.startswith("image."):
        return []
    targets = {op.target_format} if op.target_format else {item.format for item in items}
    if op.id == "image.merge.pdf":
        targets = {"pdf"}
    reasons = [f"No image encoder for {fmt.upper()}" for fmt in targets if fmt not in tools.image_writers]
    reasons.extend(f"No image decoder for {item.format.upper()}" for item in items if item.format not in tools.image_readers)
    return reasons


def operation_availability(op, items, tools):
    routes = routes_for(op, items)
    needed = set(op.requires)
    for route in routes:
        needed.update(part for part in route.split("-") if part in {"pandoc", "office", "ffmpeg"})
    reasons = [getattr(tools, name).reason for name in sorted(needed) if not getattr(tools, name).available]
    reasons.extend(image_reasons(op, items, tools))
    if op.id == "tools.ocr" and tools.system != "darwin":
        reasons.append("OCR is not available on Windows in v1.")
    reasons.extend(encoder_reasons(op, items, needed, tools))
    return Availability(not reasons, tuple(reasons), ", ".join(dict.fromkeys(routes)))


def encoder_reasons(op, items, needed, tools):
    if "ffmpeg" not in needed or not tools.ffmpeg.available:
        return []
    from ..backends.ffmpeg import required_encoders
    missing = required_encoders(op, items) - tools.ffmpeg.capabilities
    return [f"FFmpeg needs encoder {name}" for name in sorted(missing)]

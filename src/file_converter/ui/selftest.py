"""Deterministic offscreen production-widget rendering without desktop effects."""

import json
import os
from dataclasses import replace
from pathlib import Path


def scenarios(catalog, tools):
    from ..core.formats import FileItem
    from ..core.wheel_layout import Slice, slices_for
    from ..core.operations import Availability
    for theme in ("light", "dark"):
        for fmt in ("png", "wav", "mp4", "pdf", "md", "pptx", "xlsx", "srt", "zip", "unknown"):
            item = FileItem(Path("/synthetic/input." + fmt), "input." + fmt, "input", fmt)
            for wheel in ("Convert", "Tools", "Actions"):
                yield f"{theme}-{fmt}-{wheel.lower()}", theme, slices_for(catalog, wheel, (item,), tools), [item.path], wheel, False, -1, 1
        yield f"{theme}-empty", theme, (), [], "Convert", False, -1, 1
        items = tuple(FileItem(Path(f"/synthetic/image{n}.png"), f"image{n}.png", f"image{n}", "png") for n in (1, 2))
        slices = slices_for(catalog, "Tools", items, tools)
        yield f"{theme}-image-tools-full", theme, slices, [i.path for i in items], "Tools", False, 0, 1
        yield f"{theme}-high-dpi", theme, slices, [i.path for i in items], "Tools", False, 3, 2
        operation = catalog[0]
        yield from repeat_scenarios(theme, operation, items)
    from ..core.tools import ToolSnapshot
    windows = replace(tools, system="win32")
    item = FileItem(Path("/synthetic/input.png"), "input.png", "input", "png")
    disabled = slices_for(catalog, "Tools", (item,), windows)
    index = next(n for n, segment in enumerate(disabled) if segment.operation.id == "tools.ocr")
    yield "windows-ocr-disabled-hover", "light", disabled, [item.path], "Tools", False, index, 1


def repeat_scenarios(theme, operation, items):
    from ..core.wheel_layout import Slice
    from ..core.operations import Availability
    for available in (True, False):
        availability = Availability(available, () if available else ("Last operation does not apply to these files",))
        yield f"{theme}-repeat-{available}", theme, (Slice(operation, availability),), [items[0].path], "Convert", True, 0, 1


def render_selftest(outdir):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QImage, QPainter
    from .wheel import Wheel
    from ..core.catalog import build_catalog
    from ..core.tools import Tool, ToolSnapshot
    from ..core.formats import IMAGES
    app = QApplication.instance() or QApplication(["FileConverter self-test"])
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    tools = ToolSnapshot(Tool(Path("/bundled/ffmpeg"), "synthetic", capabilities=frozenset("libx264 aac libvpx-vp9 libopus libmp3lame pcm_s16le pcm_s16be flac libvorbis gif png".split())), Tool(Path("/bundled/pandoc"), "synthetic"), Tool(reason="needs LibreOffice"), "darwin", IMAGES, IMAGES | {"pdf"})
    manifest = []
    wheel = Wheel()
    for name, theme, slices, inputs, kind, repeat, selected, scale in scenarios(build_catalog(), tools):
        wheel.theme = theme
        wheel.set_model(slices, inputs, kind, repeat)
        wheel.selected = selected
        image = QImage(wheel.width() * scale, wheel.height() * scale, QImage.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(scale)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        try:
            wheel.render(painter, QPoint())
        finally:
            painter.end()
        path = outdir / (name + ".png")
        if not image.save(str(path)):
            raise RuntimeError(f"Could not save self-test image {path}")
        manifest.append(dict(name=name, file=path.name, theme=theme, wheel=kind, scale=scale, slices=[dict(id=s.operation.id, enabled=s.availability.enabled, reasons=s.availability.reasons) for s in slices]))
    (outdir / "manifest.json").write_text(json.dumps(dict(schema_version=1, scenarios=manifest), indent=2))
    wheel.close()
    return len(manifest)

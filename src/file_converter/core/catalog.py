"""Ordered 82-operation source catalog and six application operations."""

from . import formats as f
from .operations import Operation


def backend(module):
    def dispatch(operation, items, context):
        from importlib import import_module
        return import_module(f"file_converter.{module}").run(operation, items, context)
    return dispatch


def conversions(prefix, targets, inputs, module, requires=()):
    return [Operation(f"{prefix}.to.{target}", "Convert", target.upper(), "", inputs, requires, backend(module), target_format=target) for target in targets.split()]


def tools(prefix, definitions, inputs, module, requires=()):
    result = []
    for name, label, subtitle in definitions:
        parameters = ("start", "end") if name == "trim" else ()
        result.append(Operation(f"{prefix}.{name}", "Tools", label, subtitle, inputs, requires, backend(module), parameters=parameters))
    return result


def aggregate(identifier, label, inputs, module, requires=(), minimum=2):
    return Operation(identifier, "Tools", label, "", inputs, requires, backend(module), mode="aggregate", minimum=minimum)


def build_catalog():
    ops = image_catalog() + audio_catalog() + video_catalog() + pdf_catalog()
    ops += conversions("doc", "docx pdf odt md html txt epub rtf", f.DOCUMENTS, "backends.pandoc")
    ops += conversions("slides", "pdf png jpg pptx odp", f.SLIDES, "backends.office", ("office",))
    ops += sheet_catalog()
    ops += conversions("subs", "srt vtt txt", f.SUBTITLES, "backends.subtitle")
    ops += [Operation("archive.extract", "Convert", "Extract", "", f.ARCHIVES, (), backend("backends.archive"))]
    ops += conversions("archive", "zip tar tar.gz", f.ARCHIVES, "backends.archive")
    ops += [aggregate("pack." + target, target.upper(), None, "backends.archive", minimum=1) for target in ("zip", "tar.gz")]
    ops += [Operation("tools.ocr", "Tools", "Recognize text", "English OCR", f.IMAGES | {"pdf"}, (), backend("backends.ocr_mac"))]
    ops += actions_catalog()
    return tuple(ops)


def image_catalog():
    ops = conversions("image", "jpg png webp avif tiff ico pdf", f.IMAGES, "backends.image")
    ops += conversions("gif", "mp4 webm", frozenset({"gif"}), "backends.ffmpeg", ("ffmpeg",))
    edits = [("compress", "Compress", ""), ("half", "Shrink", "50%"), ("max1920", "Max 1920 px", "for web"), ("rotate.right", "Rotate right", "90°"), ("rotate.left", "Rotate left", "90°"), ("flip", "Mirror", "horizontal"), ("square", "Square", "center crop"), ("grayscale", "Grayscale", ""), ("strip", "No metadata", "GPS, EXIF")]
    ops += tools("image", edits, f.IMAGES, "backends.image")
    return ops + [aggregate("image.merge.pdf", "Merge to PDF", f.IMAGES, "backends.image")]


def audio_catalog():
    ops = conversions("audio", "mp3 m4a wav flac ogg opus aiff", f.AUDIO, "backends.ffmpeg", ("ffmpeg",))
    edits = [("compress", "Compress", "MP3 128k"), ("normalize", "Normalize", "loudness"), ("trim", "Trim", "start / end")]
    ops += tools("audio", edits, f.AUDIO, "backends.ffmpeg", ("ffmpeg",))
    return ops + [aggregate("audio.concat", "Join audio", f.AUDIO, "backends.ffmpeg", ("ffmpeg",))]


def video_catalog():
    ops = conversions("video", "mp4 mov mkv webm gif mp3", f.VIDEO, "backends.ffmpeg", ("ffmpeg",))
    edits = [("compress", "Compress", "H.264"), ("720p", "720p", "downscale"), ("mute", "Mute", "remove audio"), ("trim", "Trim", "start / end"), ("rotate", "Rotate right", "90°"), ("speed2", "Speed up", "2×"), ("thumbnail", "Thumbnail", "PNG frame")]
    return ops + tools("video", edits, f.VIDEO, "backends.ffmpeg", ("ffmpeg",))


def pdf_catalog():
    ops = conversions("pdf", "docx jpg png pptx txt md html epub", frozenset({"pdf"}), "backends.pdf")
    from dataclasses import replace
    ops = [replace(op, requires=("pandoc",)) if op.target_format in {"html", "epub"} else op for op in ops]
    ops += [aggregate("pdf.merge", "Merge PDFs", frozenset({"pdf"}), "backends.pdf")]
    return ops + tools("pdf", [("split", "Split", "one PDF per page"), ("rotate", "Rotate right", "90°"), ("optimize", "Optimize", "content streams")], frozenset({"pdf"}), "backends.pdf")


def sheet_catalog():
    from dataclasses import replace
    ops = conversions("sheet", "xlsx csv tsv ods pdf", f.SHEETS, "backends.spreadsheet")
    return [replace(op, requires=("office",)) if op.target_format in {"ods", "pdf"} else op for op in ops]


def actions_catalog():
    ops = []
    for name, label in [("copy", "Copy to…"), ("move", "Move to…"), ("path", "Copy path"), ("terminal", "Open terminal"), ("reveal", "Reveal")]:
        params = ("destination",) if name in {"copy", "move"} else ()
        ops.append(Operation("action." + name, "Actions", label, "", None, (), backend("platform.actions"), mode="aggregate", parameters=params))
    return ops

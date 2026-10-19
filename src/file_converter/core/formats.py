"""File classification without filesystem mutation."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

ALIASES = dict(jpeg="jpg", jpe="jpg", jfif="jpg", tif="tiff", heif="heic", htm="html", markdown="md", aif="aiff", oga="ogg", tgz="tar.gz", m4v="mp4")
IMAGES = frozenset("jpg png webp heic tiff avif bmp gif ico".split())
AUDIO = frozenset("mp3 m4a aac wav flac ogg opus aiff wma".split())
VIDEO = frozenset("mp4 mov mkv webm avi wmv flv mpg mpeg 3gp ts mts".split())
DOCUMENTS = frozenset("docx doc odt rtf md txt html epub".split())
SLIDES = frozenset("pptx ppt odp".split())
SHEETS = frozenset("xlsx xlsm xls ods csv tsv".split())
SUBTITLES = frozenset(("srt", "vtt"))
ARCHIVES = frozenset("zip tar tar.gz gz tar.bz2 bz2 tar.xz xz 7z".split())


@dataclass(frozen=True)
class FileItem:
    path: Path
    display_name: str
    basename: str
    format: str
    is_directory: bool = False


def extension(name):
    lower = str(name).lower()
    for compound in ("tar.gz", "tar.bz2", "tar.xz"):
        if lower.endswith("." + compound):
            return compound
    return ALIASES.get(Path(lower).suffix[1:], Path(lower).suffix[1:])


def basename(path):
    name = Path(path).name
    fmt = extension(name)
    if not fmt:
        return name
    if fmt.startswith("tar.") and name.lower().endswith("." + fmt):
        return name[: -len(fmt) - 1]
    return Path(name).stem


def file_item(path):
    absolute = Path(os.path.abspath(os.path.expanduser(path)))
    directory = absolute.is_dir()
    return FileItem(absolute, absolute.name, absolute.name if directory else basename(absolute), "" if directory else extension(absolute), directory)


def natural_key(value):
    return tuple((1, int(part)) if part.isdigit() else (0, part.casefold()) for part in re.split(r"(\d+)", str(value)))


def sorted_items(items):
    return sorted(items, key=lambda item: natural_key(item.path))


def safe_name(name):
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if not clean:
        raise ValueError("The output name is empty after removing unsupported characters")
    return clean

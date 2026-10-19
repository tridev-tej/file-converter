"""Timed cue parsing and explicit subtitle serialization."""

import html
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Cue:
    start: int
    end: int
    text: str


def timestamp(value):
    match = re.fullmatch(r"(?:(\d+):)?(\d{2}):(\d{2})[,.](\d{3})", value.strip())
    if not match:
        raise ValueError(f"Invalid subtitle timestamp: {value}")
    hours, minutes, seconds, milliseconds = match.groups()
    if int(minutes) > 59 or int(seconds) > 59:
        raise ValueError(f"Invalid subtitle timestamp: {value}")
    return ((int(hours or 0) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(milliseconds)


def cue_block(block):
    lines = block.splitlines()
    if not lines or lines[0].startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
        return None
    timing_index = next((index for index, line in enumerate(lines[:2]) if "-->" in line), None)
    if timing_index is None:
        raise ValueError("Subtitle block has no valid timing line")
    timing = re.fullmatch(r"\s*(\S+)\s+-->\s+(\S+)(?:\s+.*)?", lines[timing_index])
    if not timing:
        raise ValueError("Malformed subtitle timing line")
    start, end = timestamp(timing[1]), timestamp(timing[2])
    if end <= start:
        raise ValueError("Subtitle cue end must come after start")
    body = "\n".join(lines[timing_index + 1:]).strip()
    if not body:
        raise ValueError("Subtitle cue has no text")
    return Cue(start, end, body)


def parse(path):
    text = Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    cues = [cue for block in re.split(r"\n\s*\n", text.strip()) if (cue := cue_block(block)) is not None]
    if not cues:
        raise ValueError("No valid timed subtitle cues found")
    return cues


def format_time(value, separator):
    seconds, milliseconds = divmod(value, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}{separator}{milliseconds:03}"


def plain_text(cues):
    lines = []
    for cue in cues:
        text = html.unescape(re.sub(r"<[^>]*>", "", cue.text))
        text = " ".join(text.split())
        if not lines or lines[-1] != text:
            lines.append(text)
    return "\n".join(lines) + "\n"


def serialize(cues, target):
    if target == "txt":
        return plain_text(cues)
    if target not in {"srt", "vtt"}:
        raise ValueError(f"Unsupported subtitle output: {target}")
    blocks = []
    separator = "," if target == "srt" else "."
    for index, cue in enumerate(cues, 1):
        number = f"{index}\n" if target == "srt" else ""
        blocks.append(f"{number}{format_time(cue.start, separator)} --> {format_time(cue.end, separator)}\n{cue.text}")
    prefix = "WEBVTT\n\n" if target == "vtt" else ""
    return prefix + "\n\n".join(blocks) + "\n"


def run(op, items, context):
    item = items[0]
    text = serialize(parse(item.path), op.target_format)
    return [context.produce(item, op.target_format, lambda path: path.write_text(text, encoding="utf-8"))]

"""Explicit media profiles, stream inspection and cancellable FFmpeg execution."""

import math
import re
from dataclasses import dataclass

from ..core.formats import sorted_items
from ..core.processes import run_process

AUDIO_CODECS = {"mp3": ["-vn", "-c:a", "libmp3lame", "-q:a", "2"], "m4a": ["-vn", "-c:a", "aac", "-b:a", "192k"], "aac": ["-vn", "-c:a", "aac", "-b:a", "192k"], "wav": ["-vn", "-c:a", "pcm_s16le"], "aiff": ["-vn", "-c:a", "pcm_s16be"], "flac": ["-vn", "-c:a", "flac"], "ogg": ["-vn", "-c:a", "libvorbis", "-q:a", "5"], "opus": ["-vn", "-c:a", "libopus", "-b:a", "128k"]}
SAFE = dict.fromkeys("avi wmv flv mpg mpeg 3gp ts mts".split(), "mp4") | {"wma": "mp3"}
EVEN = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
GIF_FILTER = "fps=12,scale='min(640,iw)':-2:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4"
SUFFIXES = dict(compress="compressed", normalize="normalized", trim="trimmed", concat="joined", mute="muted", rotate="rotated", speed2="2×", thumbnail="thumbnail") | {"720p": "720p"}


@dataclass(frozen=True)
class MediaInfo:
    duration: float | None
    audio: bool
    video: bool
    width: int = 0
    height: int = 0


def parse_time(value):
    text = str(value).strip().replace(",", ".")
    parts = text.split(":")
    validate_time_parts(parts, value)
    numbers = [float(part) for part in parts]
    total = 0.0
    for number in numbers:
        total = total * 60 + number
    return total


def validate_time_parts(parts, value):
    if not 1 <= len(parts) <= 3 or any(not re.fullmatch(r"\d+(?:\.\d+)?", part) for part in parts):
        raise ValueError(f"Invalid timestamp: {value}")
    validate_time_components(parts)


def validate_time_components(parts):
    numbers = [float(part) for part in parts]
    if not all(math.isfinite(number) for number in numbers):
        raise ValueError("Timestamp must be finite")
    if len(parts) > 1 and any(number >= 60 for number in numbers[1:]):
        raise ValueError("Minutes and seconds must be below 60")
    if any("." in part for part in parts[:-1]):
        raise ValueError("Only seconds can have a fractional component")


def inspect(path, context):
    result = run_process([context.tools.ffmpeg.path, "-hide_banner", "-nostdin", "-i", path], context.token, timeout=30, check=False)
    text = result.stderr
    if "Stream #" not in text:
        raise ValueError(f"Cannot read media: {text[-2000:]}")
    duration = re.search(r"Duration:\s*(\d+:\d+:\d+(?:\.\d+)?)", text)
    size = re.search(r"Video:.*?\b(\d{2,6})x(\d{2,6})\b", text)
    width, height = (int(size[1]), int(size[2])) if size else (0, 0)
    return MediaInfo(parse_time(duration[1]) if duration else None, bool(re.search(r"Stream #.*Audio:", text)), bool(re.search(r"Stream #.*Video:", text)), width, height)


def h264(crf=23, preset="medium", filter_name="", bitrate="160k", faststart=True):
    vf = filter_name + "," + EVEN if filter_name else EVEN
    args = ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-vf", vf, "-c:a", "aac", "-b:a", bitrate]
    if faststart:
        args += ["-movflags", "+faststart"]
    return args


def codec_args(target, settings):
    if target in AUDIO_CODECS:
        return list(AUDIO_CODECS[target])
    if target in {"mp4", "mov", "mkv"}:
        return h264(settings.video_crf, faststart=target == "mp4")
    if target == "webm":
        return ["-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p", "-crf", "32", "-b:v", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "4", "-c:a", "libopus", "-b:a", "128k"]
    if target == "gif":
        return ["-filter_complex", GIF_FILTER, "-loop", "0"]
    raise ValueError(f"Unsupported media target: {target}")


def output_format(op, item):
    if op.target_format:
        return op.target_format
    name = op.id.split(".", 1)[1]
    if name == "thumbnail":
        return "png"
    if op.id == "audio.compress":
        return "mp3"
    if op.id.startswith("video.") and name != "mute":
        return "mp4"
    return SAFE.get(item.format, item.format)


def required_encoders(op, items):
    target = output_format(op, items[0])
    video = {"mp4": "libx264", "mov": "libx264", "mkv": "libx264", "webm": "libvpx-vp9", "gif": "gif", "png": "png"}
    if target in AUDIO_CODECS:
        args = AUDIO_CODECS[target]
        return {args[args.index("-c:a") + 1]}
    if op.id == "video.mute" and target == items[0].format:
        return set()
    encoder = video.get(target)
    return {encoder, "libopus" if target == "webm" else "aac"} if target in {"mp4", "mov", "mkv", "webm"} else {encoder}


def tool_args(op, item, info, context):
    target = output_format(op, item)
    name = op.id.split(".", 1)[1]
    if op.target_format:
        return codec_args(target, context.settings)
    if op.id.startswith("audio."):
        return audio_tool_args(name, target, context.settings)
    return video_tool_args(name, item, info, context)


def audio_tool_args(name, target, settings):
    if name == "compress":
        return ["-vn", "-c:a", "libmp3lame", "-b:a", "128k"]
    args = codec_args(target, settings)
    if name == "normalize":
        args += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
    return args


def video_tool_args(name, item, info, context):
    if name == "thumbnail":
        return ["-vf", "thumbnail=150", "-frames:v", "1", "-update", "1", "-an"]
    if name == "mute" and item.format == SAFE.get(item.format, item.format):
        return ["-map", "0:v:0", "-c:v", "copy", "-an"]
    filters = {"720p": "scale=-2:'min(720,ih)'", "rotate": "transpose=1", "speed2": "setpts=0.5*PTS"}
    crf = context.settings.compress_video_crf if name == "compress" else context.settings.video_crf
    args = h264(crf, "slow" if name == "compress" else "medium", filters.get(name, ""), "128k" if name == "compress" else "160k")
    if name == "mute":
        args += ["-an"]
    if name == "speed2" and info.audio:
        args += ["-af", "atempo=2.0"]
    return args


class ProgressParser:
    def __init__(self, context, duration):
        self.context = context
        self.duration = duration
        self.text = ""

    def feed(self, text):
        self.text = (self.text + text)[-2048:]
        matches = re.findall(r"time=(\d+:\d+:\d+(?:\.\d+)?)", self.text)
        if not matches or not self.duration:
            self.context.progress(None, "Converting media")
            return
        seconds = parse_time(matches[-1])
        self.context.progress(min(0.99, seconds / self.duration), "Converting media")


def execute_ffmpeg(inputs, args, output, context, duration=None, input_options=()):
    command = [context.tools.ffmpeg.path, "-hide_banner", "-nostdin", "-y", *input_options]
    for path in inputs:
        command += ["-i", path]
    command += [*args, output]
    parser = ProgressParser(context, duration)
    run_process(command, context.token, timeout=86400, stderr_callback=parser.feed)
    if not output.is_file() or not output.stat().st_size:
        raise RuntimeError("FFmpeg did not create a non-empty output")


def trim_options(info, context):
    start = parse_time(context.parameters.get("start", "0"))
    end = context.parameters.get("end", "").strip()
    ending = parse_time(end) if end else info.duration
    if info.duration and (start >= info.duration or (ending is not None and ending > info.duration + 0.02)):
        raise ValueError("Trim interval is outside the media duration")
    if ending is not None and ending <= start:
        raise ValueError("Trim end must come after start")
    length = ending - start if ending is not None else None
    return ["-ss", str(start)], ["-t", str(length)] if length is not None else [], length


def run(op, items, context):
    if op.id == "audio.concat":
        return concatenate(items, context)
    item = items[0]
    info = inspect(item.path, context)
    target = output_format(op, item)
    if target in AUDIO_CODECS and not info.audio:
        raise ValueError("This media has no audio stream")
    args = tool_args(op, item, info, context)
    options, extra, duration = [], [], info.duration
    if op.id.endswith(".trim"):
        options, extra, duration = trim_options(info, context)
    if op.id == "video.speed2" and duration:
        duration /= 2
    suffix = SUFFIXES.get(op.id.split(".", 1)[1], "")
    output = context.produce(item, target, lambda path: execute_ffmpeg([item.path], [*args, *extra], path, context, duration, options), suffix)
    return [output]


def concatenate(items, context):
    ordered = sorted_items(items)
    infos = [inspect(item.path, context) for item in ordered]
    if not all(info.audio for info in infos):
        raise ValueError("Every join input must contain an audio stream")
    filters = [f"[{index}:a:0]aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{index}]" for index in range(len(items))]
    graph = ";".join(filters) + ";" + "".join(f"[a{i}]" for i in range(len(items))) + f"concat=n={len(items)}:v=0:a=1[out]"
    target = SAFE.get(ordered[0].format, ordered[0].format)
    args = ["-filter_complex", graph, "-map", "[out]", *codec_args(target, context.settings)]
    duration = sum(info.duration for info in infos) if all(info.duration for info in infos) else None
    output = context.produce(ordered[0], target, lambda path: execute_ffmpeg([item.path for item in ordered], args, path, context, duration), "joined")
    return [output]

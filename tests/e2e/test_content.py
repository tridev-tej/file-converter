"""Consumption-boundary assertions for visual, media and filesystem semantics."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def convert(identifier, inputs, params=None, token=None, progress=None):
    from file_converter.core.operations import OperationRequest
    from file_converter.core.runner import execute
    from file_converter.core.settings import Settings
    return execute(OperationRequest(identifier, tuple(inputs), params or {}, Settings()), token=token, progress=progress)


def output(identifier, path, params=None):
    result = convert(identifier, [path], params)
    assert result.state == "succeeded", result.errors
    return result.outputs[0]


def test_image_pixels(samples):
    from PIL import Image
    right = output("image.rotate.right", samples / "one.png")
    left = output("image.rotate.left", samples / "one.png")
    mirrored = output("image.flip", samples / "one.png")
    with Image.open(right) as image:
        assert image.size == (64, 96)
        assert image.getpixel((50, 10))[:3] == (255, 0, 0)
    with Image.open(left) as image:
        assert image.getpixel((10, 80))[:3] == (255, 0, 0)
    with Image.open(mirrored) as image:
        assert image.getpixel((80, 10))[:3] == (255, 0, 0)
    with Image.open(output("image.square", samples / "one.png")) as image:
        assert image.size == (64, 64)
    with Image.open(output("image.half", samples / "one.png")) as image:
        assert image.size == (48, 32)
    with Image.open(output("image.to.jpg", samples / "alpha.png")) as image:
        assert all(value > 245 for value in image.getpixel((10, 10)))
    with Image.open(output("image.to.webp", samples / "alpha.png")) as image:
        assert image.getpixel((10, 10))[3] == 0


def test_pdf_structure(samples):
    from pypdf import PdfReader
    rotated = PdfReader(output("pdf.rotate", samples / "one.pdf"))
    assert all(page.rotation == 90 for page in rotated.pages)
    merged = convert("pdf.merge", [samples / "two.pdf", samples / "one.pdf"])
    assert len(PdfReader(merged.outputs[0]).pages) == 4
    text = output("pdf.to.txt", samples / "one.pdf").read_text()
    assert text.index("page 1") < text.index("page 2")
    pages = output("pdf.to.png", samples / "one.pdf")
    from PIL import Image, ImageStat
    for path in pages.iterdir():
        with Image.open(path) as image:
            assert image.height == 750
            assert 1000 <= image.width <= 1001
            assert min(ImageStat.Stat(image).extrema[0]) < 100


def media_info(path):
    import imageio_ffmpeg
    import re
    from file_converter.backends.ffmpeg import parse_time
    result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    duration = re.search(r"Duration: (\d+:\d+:\d+\.\d+)", result.stderr)
    return parse_time(duration[1]), result.stderr


def test_media_semantics(samples):
    duration, text = media_info(output("video.speed2", samples / "clip.mp4"))
    assert 0.6 < duration < 0.9
    duration, text = media_info(output("video.trim", samples / "clip.mp4", {"start": "0.2", "end": "0.8"}))
    assert 0.5 < duration < 0.8
    duration, text = media_info(output("video.mute", samples / "clip.mp4"))
    assert "Audio:" not in text
    duration, text = media_info(output("video.rotate", samples / "clip.mp4"))
    assert "64x96" in text
    for identifier in ["video.compress", "video.rotate", "video.speed2", "video.trim", "video.mute"]:
        result = convert(identifier, [samples / "silent.mp4"])
        assert result.state == "succeeded", result.errors
    joined = convert("audio.concat", [samples / "two.wav", samples / "one.wav"])
    duration, text = media_info(joined.outputs[0])
    assert 2.6 < duration < 3.0


def test_spreadsheet_identifiers(samples):
    from file_converter.backends.spreadsheet import read_workbook
    xlsx = output("sheet.to.xlsx", samples / "data.csv")
    rows = read_workbook(xlsx, "xlsx")[0].rows
    assert rows[1] == ["00123", "42", "café, tea"]
    converted = convert("sheet.to.csv", [samples / "book.xlsx"])
    assert len(converted.outputs) == 2
    assert all(path.read_bytes().startswith(b"\xef\xbb\xbf") for path in converted.outputs)


def test_formula_failure(tmp_path):
    from openpyxl import Workbook
    path = tmp_path / "formula.xlsx"
    book = Workbook()
    book.active.append(["=1+2"])
    book.save(path)
    result = convert("sheet.to.csv", [path])
    assert result.state == "failed"
    assert "cached" in result.errors[0]["error"]


def test_archive_content(samples):
    import tarfile
    tar = output("archive.to.tar", samples / "sample.zip")
    with tarfile.open(tar) as archive:
        assert archive.extractfile("nested/text.txt").read().decode() == "archive contents café"
        assert archive.getmember("empty").isdir()
    directory = output("archive.extract", samples / "sample.zip")
    assert (directory / "nested/text.txt").read_text() == "archive contents café"
    assert (directory / "empty").is_dir()


@pytest.mark.parametrize("member", ["../outside", "/absolute", "C:/drive", "folder/../../outside", "a\\\\..\\\\outside", "file:stream"])
def test_unsafe_archives(tmp_path, member):
    import zipfile
    path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, "unsafe")
    result = convert("archive.extract", [path])
    assert result.state == "failed"
    assert not result.outputs


def test_cancel_preserves_completed(samples):
    from file_converter.core.operations import CancellationToken
    token = CancellationToken()
    def progress(value, message):
        if value == 0.5:
            token.cancel()
    result = convert("image.to.jpg", [samples / "one.png", samples / "alpha.png"], token=token, progress=progress)
    assert result.state == "cancelled"
    assert len(result.outputs) == 1
    assert result.outputs[0].exists()


def test_copy_move_and_recursion(samples, tmp_path):
    import shutil
    source = tmp_path / "source"
    shutil.copytree(samples / "folder", source)
    result = convert("action.copy", [source], {"destination": str(source)})
    assert result.state == "failed"
    target = tmp_path / "target"
    target.mkdir()
    first = output("action.copy", source, {"destination": str(target)})
    second = output("action.copy", source, {"destination": str(target)})
    assert first != second
    assert (first / "file.txt").read_bytes() == (source / "file.txt").read_bytes()
    moved = output("action.move", source, {"destination": str(target)})
    assert not source.exists()
    assert (moved / "file.txt").read_text() == "copied bytes"


def test_process_cancel(tmp_path):
    import threading
    from file_converter.core.operations import CancellationToken, Cancelled
    from file_converter.core.processes import run_process
    token = CancellationToken()
    timer = threading.Timer(0.2, token.cancel)
    timer.start()
    with pytest.raises(Cancelled):
        run_process([sys.executable, "-c", "import time; time.sleep(20)"], token)
    timer.join()


def test_concurrent_publication(samples):
    import concurrent.futures
    env = dict(os.environ, PYTHONPATH=str(Path("src").absolute()))
    command = [sys.executable, "-m", "file_converter", "run", "image.to.jpg", str(samples / "one.png"), "--json"]
    def run_one():
        import json
        result = subprocess.run(command, capture_output=True, text=True, env=env)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)["outputs"][0]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(lambda _: run_one(), range(4)))
    assert len(set(paths)) == 4


def test_pandoc_media(samples):
    import re
    docx = output("doc.to.docx", samples / "notes.md")
    markdown = output("doc.to.md", docx)
    text = markdown.read_text()
    assert "Known Unicode" in text
    for resource in re.findall(r"!\\?\[.*?\]\\?\((.*?)\\?\)", text):
        assert (markdown.parent / resource).exists(), text


def test_selftest(tmp_path):
    from file_converter.ui.selftest import render_selftest
    assert render_selftest(tmp_path) >= 71
    from PIL import Image
    with Image.open(tmp_path / "dark-high-dpi.png") as image:
        assert image.size == (884, 884)


@pytest.mark.parametrize("text", ["{}", '{"schema_version": 1}'])
def test_incomplete_settings(tmp_path, text):
    from file_converter.core.settings import load_settings
    path = tmp_path / "settings.json"
    path.write_text(text)
    with pytest.raises(ValueError, match="Incomplete settings"):
        load_settings(path)

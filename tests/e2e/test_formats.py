"""Real reader/codec coverage beyond the primary operation matrix."""

import bz2
import gzip
import lzma
import tarfile
from pathlib import Path

import pytest

from test_content import convert, output


@pytest.mark.parametrize("fmt", "jpg png webp heic tiff avif bmp gif ico".split())
def test_image_readers(samples, tmp_path, fmt):
    from PIL import Image
    image = Image.open(samples / "one.png")
    target = tmp_path / ("source." + fmt)
    names = {"jpg": "JPEG", "heic": "HEIF", "tiff": "TIFF"}
    image.save(target, names.get(fmt, fmt.upper()))
    image.close()
    result = output("image.to.pdf", target)
    from pypdf import PdfReader
    assert len(PdfReader(result).pages) == 1


def test_image_metadata_orientation(tmp_path):
    from PIL import Image
    image = Image.new("RGB", (80, 40), "red")
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "FileConverter private metadata"
    path = tmp_path / "oriented.jpg"
    image.save(path, exif=exif)
    image.close()
    with Image.open(output("image.to.png", path)) as converted:
        assert converted.size == (40, 80)
    stripped = output("image.strip", path)
    with Image.open(stripped) as converted:
        assert not converted.getexif()
        assert converted.size == (40, 80)


@pytest.mark.parametrize("fmt", "tar tar.gz tar.bz2 tar.xz 7z gz bz2 xz".split())
def test_archive_readers(tmp_path, fmt):
    source = tmp_path / "payload.txt"
    source.write_text("archive reader café")
    path = tmp_path / ("payload." + fmt)
    if fmt.startswith("tar"):
        mode = {"tar": "w", "tar.gz": "w:gz", "tar.bz2": "w:bz2", "tar.xz": "w:xz"}[fmt]
        with tarfile.open(path, mode) as archive:
            archive.add(source, arcname="payload.txt")
    elif fmt == "7z":
        import py7zr
        with py7zr.SevenZipFile(path, "w") as archive:
            archive.write(source, arcname="payload.txt")
    else:
        opener = {"gz": gzip.open, "bz2": bz2.open, "xz": lzma.open}[fmt]
        with opener(path, "wb") as stream:
            stream.write(source.read_bytes())
    result = output("archive.extract", path)
    assert result.read_bytes() == source.read_bytes()


def test_xls_reader(tmp_path):
    from legacy_xls import write_xls
    from file_converter.backends.spreadsheet import read_workbook
    path = tmp_path / "legacy.xls"
    write_xls(path)
    sheets = read_workbook(path, "xls")
    assert sheets[0].name == "Data"
    assert sheets[0].rows == [["ID", "Name"], ["00123", "café"]]
    converted = output("sheet.to.xlsx", path)
    assert read_workbook(converted, "xlsx")[0].rows == sheets[0].rows


def test_ods_reader(tmp_path):
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table, TableRow, TableCell
    from odf.text import P
    from file_converter.backends.spreadsheet import read_workbook
    book = OpenDocumentSpreadsheet()
    table = Table(name="Values")
    row = TableRow()
    for value in ("00123", "café"):
        cell = TableCell(valuetype="string")
        cell.addElement(P(text=value))
        row.addElement(cell)
    table.addElement(row)
    table.addElement(TableRow(numberrowsrepeated=2))
    row = TableRow()
    row.addElement(TableCell(valuetype="boolean", booleanvalue="true"))
    table.addElement(row)
    book.spreadsheet.addElement(table)
    path = tmp_path / "book.ods"
    book.save(str(path))
    rows = read_workbook(path, "ods")[0].rows
    assert rows == [["00123", "café"], [], [], [True]]
    assert output("sheet.to.xlsx", path).is_file()


@pytest.mark.parametrize("fmt", "docx odt rtf html epub".split())
def test_document_readers(samples, fmt):
    document = output("doc.to." + fmt, samples / "notes.md")
    plain = output("doc.to.txt", document).read_text()
    assert "Known Unicode café text" in plain


def test_subtitle_timing_and_markup(samples):
    from file_converter.backends.subtitle import parse
    converted = output("subs.to.vtt", samples / "captions.srt")
    cues = parse(converted)
    assert [(cue.start, cue.end) for cue in cues] == [(0, 500), (500, 1200)]
    assert cues[0].text == "<b>Hello</b>\nworld"
    text = output("subs.to.txt", samples / "captions.vtt").read_text()
    assert text == "Hello world\nAgain\n"


def test_aliases_and_mixed_inputs(samples, tmp_path):
    from file_converter.core.formats import file_item
    from file_converter.core.operations import OperationRequest
    from file_converter.core.runner import validate_request
    from file_converter.core.settings import Settings
    assert file_item(tmp_path / "archive.TAR.GZ").format == "tar.gz"
    assert file_item(tmp_path / "PHOTO.JPEG").format == "jpg"
    result = convert("image.to.jpg", [samples / "one.png", samples / "two.jpg"])
    assert result.state == "succeeded"
    assert len(result.skipped) == 1
    with pytest.raises(ValueError):
        validate_request(OperationRequest("image.to.png", (samples / "one.png",), {}, Settings()))


def test_actions_keep_filename(samples, tmp_path):
    source = tmp_path / "a.JPEG"
    source.write_bytes((samples / "two.jpg").read_bytes())
    directory = tmp_path / "destination"
    directory.mkdir()
    result = output("action.copy", source, {"destination": str(directory)})
    assert result.name == "a.JPEG"

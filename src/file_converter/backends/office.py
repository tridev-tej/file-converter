"""Isolated headless LibreOffice conversions with explicit export filters."""

import shutil
import uuid
import zipfile

from ..core.formats import file_item
from ..core.processes import run_process

WRITER = dict(pdf="writer_pdf_Export", docx="Office Open XML Text", odt="writer8", rtf="Rich Text Format", txt="Text (encoded)", html="HTML (StarWriter)")
IMPRESS = dict(pdf="impress_pdf_Export", pptx="Impress MS PowerPoint 2007 XML", odp="impress8")
CALC = dict(pdf="calc_pdf_Export", ods="calc8")


def export_filter(item, target):
    from ..core.formats import SLIDES, SHEETS
    mapping = WRITER
    if item.format in SLIDES:
        mapping = IMPRESS
    elif item.format in SHEETS:
        mapping = CALC
    if target not in mapping:
        raise ValueError(f"Unsupported LibreOffice export: {item.format} → {target}")
    return mapping[target]


def validate_output(path, target):
    if not path.is_file() or not path.stat().st_size:
        raise RuntimeError(f"LibreOffice did not create expected output: {path.name}")
    header = path.read_bytes()[:8]
    if target == "pdf" and not header.startswith(b"%PDF-"):
        raise RuntimeError("LibreOffice output is not a PDF")
    if target in {"docx", "pptx", "odt", "odp", "ods"}:
        with zipfile.ZipFile(path) as archive:
            required = {"docx": "word/document.xml", "pptx": "ppt/presentation.xml"}.get(target, "content.xml")
            if required not in archive.namelist() or archive.testzip():
                raise RuntimeError(f"LibreOffice output is not valid {target}")


def convert_temp(item, target, context):
    root = context.workspace / ("office-" + uuid.uuid4().hex)
    outdir = root / "output"
    profile = root / "profile"
    outdir.mkdir(parents=True)
    args = [context.tools.office.path, "-env:UserInstallation=" + profile.as_uri(), "--headless", "--nologo", "--nodefault", "--nofirststartwizard", "--convert-to", target + ":" + export_filter(item, target), "--outdir", outdir, item.path]
    run_process(args, context.token, timeout=600)
    output = outdir / (item.path.stem + "." + target)
    validate_output(output, target)
    return output


def convert_to_output(item, target, context):
    temporary = convert_temp(item, target, context)
    return [context.produce(item, target, lambda path: shutil.copyfile(temporary, path))]


def run(op, items, context):
    item = items[0]
    if op.target_format in {"png", "jpg"}:
        from .pdf import render
        temporary = convert_temp(item, "pdf", context)
        return render(item, op.target_format, context, source_path=temporary)
    return convert_to_output(item, op.target_format, context)

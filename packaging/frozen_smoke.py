"""Run real conversions through the frozen launcher and inspect every output."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def invoke(executable, arguments):
    result = subprocess.run([str(executable), *arguments], capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f"Frozen command failed ({result.returncode}): {arguments}\n{result.stderr}\n{result.stdout}")
    return json.loads(result.stdout)


def check_tools(executable, info):
    for name in ("ffmpeg", "pandoc"):
        tool = info["tools"][name]
        if tool["reason"]:
            raise RuntimeError(f"Frozen {name}: {tool['reason']}")
        path = Path(tool["path"]).resolve()
        root = executable.parent.parent if sys.platform == "darwin" else executable.parent
        if not path.is_relative_to(root):
            raise RuntimeError(f"Frozen tool escaped bundle: {path}")
    if not info["frozen"]:
        raise RuntimeError("Smoke target is not a frozen executable")


def main():
    root = Path(__file__).resolve().parents[1]
    executable = Path(sys.argv[1]).resolve()
    os.environ["FC_CONFIG_DIR"] = str(root / "build/frozen-smoke/config")
    os.environ["FC_WORKSPACE"] = str(root / "build/frozen-smoke/work")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    sys.path.insert(0, str(root / "tests/e2e"))
    from fixtures import generate
    from test_operations import inspect_output
    from file_converter.core.catalog import build_catalog
    fixtures = root / "build/frozen-smoke/fixtures"
    if fixtures.exists():
        shutil.rmtree(fixtures)
    fixtures.mkdir(parents=True, exist_ok=True)
    generate(fixtures)
    diagnostics = invoke(executable, ["diagnostics"])
    check_tools(executable, diagnostics)
    cases = smoke_cases()
    report = dict(schema_version=1, diagnostics=diagnostics, frozen=[])
    operations = {op.id: op for op in build_catalog()}
    for identifier, filename in cases:
        started = time.monotonic()
        row = dict(id=identifier, status="failed", outputs=[])
        report["frozen"].append(row)
        try:
            arguments = ["run", identifier, str(fixtures / filename), "--json"]
            if identifier in {"action.copy", "action.move"}:
                arguments += ["--param", "destination=" + str(fixtures / "destination")]
            result = invoke(executable, arguments)
            inspect_result(result, operations[identifier], inspect_output)
            row.update(status="passed", outputs=result["outputs"])
        except Exception as error:
            row["error"] = str(error)
            raise
        finally:
            row["duration"] = time.monotonic() - started
            (root / "build/frozen-report.json").write_text(json.dumps(report, indent=2))
    print(f"Frozen smoke: {len(cases)} backend cases passed")


def smoke_cases():
    cases = [("image.to.jpg", "one.png"), ("video.to.webm", "clip.mp4"), ("pdf.to.docx", "one.pdf"), ("pdf.to.png", "one.pdf"), ("doc.to.docx", "notes.md"), ("sheet.to.csv", "book.xlsx"), ("subs.to.vtt", "captions.srt"), ("archive.to.tar", "sample.zip"), ("action.copy", "folder"), ("action.move", "notes.txt")]
    if sys.platform == "darwin":
        cases.append(("tools.ocr", "ocr.png"))
    return cases


def inspect_result(result, operation, inspector):
    for value in result["outputs"]:
        path = Path(value)
        inspector(path, operation)
        if operation.id == "action.copy":
            assert (path / "file.txt").read_text() == "copied bytes"
        if operation.id == "action.move":
            assert path.read_text() == "FileConverter plain document"
        if operation.id == "tools.ocr":
            assert "FILE CONVERTER TEST 123" in path.read_text().upper()


if __name__ == "__main__":
    main()

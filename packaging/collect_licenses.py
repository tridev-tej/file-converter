"""Collect installed component license files and a reproducible bundle inventory."""

import importlib.metadata
import json
import shutil
import sys
import sysconfig
from pathlib import Path

BUNDLED = frozenset("pyside6 pyside6_addons pyside6_essentials shiboken6 pillow pillow_heif imageio-ffmpeg pypdf pypdfium2 python-docx python-pptx openpyxl xlrd odfpy py7zr texttable pycryptodomex brotli psutil backports.zstd pyppmd pybcj multivolumefile inflate64 lxml typing_extensions et_xmlfile defusedxml pynput six pyinstaller".split())


def license_entry(entry):
    path = Path(entry)
    if path.suffix.lower() in {".so", ".dylib", ".dll", ".pyd", ".py", ".pyc"}:
        return False
    if any(part.lower().endswith(".dsym") for part in path.parts):
        return False
    parents = {part.lower() for part in path.parts[:-1]}
    name = path.name.upper()
    return bool(parents & {"licenses", "license", "build_licenses"}) or name in {"COPYING", "COPYRIGHT", "LICENSE"} or name.startswith(("LICENSE.", "COPYING.", "COPYRIGHT."))


def distribution_licenses(distribution, root):
    name = distribution.metadata["Name"]
    selected = []
    for entry in distribution.files or []:
        if license_entry(entry):
            source = distribution.locate_file(entry)
            if source.is_file():
                target = root / name / str(entry)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                selected.append(str(target.relative_to(root)))
    return dict(name=name, version=distribution.version, license=distribution.metadata.get("License-Expression") or distribution.metadata.get("License"), files=selected)


def main():
    root = Path("build/licenses")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    inventory = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        if name.lower() in BUNDLED or name.startswith("pyobjc"):
            inventory.append(distribution_licenses(distribution, root))
    for name in ("LICENSE", "NOTICE", "THIRD-PARTY-NOTICES.md", "CORRESPONDING-SOURCE.md"):
        shutil.copyfile(name, root / name)
    shutil.copyfile("src/file_converter/resources/GPL-2.0.txt", root / "GPL-2.0.txt")
    shutil.copyfile(python_license(), root / "Python-LICENSE.txt")
    for notice in Path("vendor/pandoc").iterdir():
        if notice.name.upper() in {"COPYRIGHT", "COPYING", "LICENSE"}:
            shutil.copyfile(notice, root / ("Pandoc-" + notice.name))
    (root / "inventory.json").write_text(json.dumps(inventory, indent=2))


def python_license():
    candidates = [Path(sys.base_prefix) / "LICENSE.txt", Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"]
    found = next((path for path in candidates if path.is_file()), None)
    if found is None:
        raise RuntimeError("Missing license for the bundled Python runtime")
    return found


if __name__ == "__main__":
    main()

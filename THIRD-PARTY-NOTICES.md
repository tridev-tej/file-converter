# Bundled components

FileConverter source is MIT. The complete executable bundle is not MIT-only.

| Component | Terms |
| --- | --- |
| FileAction design and catalog | MIT; original notice in NOTICE |
| CPython | Python Software Foundation License |
| PySide6 / Qt / shiboken6 | LGPL-3.0 / GPL-3.0 / commercial, with component exceptions; dynamically linked, replaceable frameworks |
| Pillow | HPND and bundled codec notices |
| pillow-heif / libheif | BSD-3-Clause / LGPL-3.0, plus actual codec notices |
| imageio-ffmpeg wrapper | BSD-2-Clause |
| Bundled FFmpeg | GPL, configured with `--enable-gpl`; executable and codec terms apply |
| Pandoc 3.12.1 | GPL-2.0-or-later; John MacFarlane and contributors |
| pypdf | BSD-3-Clause |
| pypdfium2 / PDFium | Apache-2.0 / BSD-3-Clause plus bundled third-party notices |
| python-docx / python-pptx | MIT |
| openpyxl | MIT |
| xlrd | BSD |
| odfpy | Apache-2.0 / GPL-2.0 / LGPL-2.1 alternatives |
| py7zr and compression libraries | LGPL-2.1-or-later and component-specific BSD / MIT / public-domain terms |
| PyObjC | MIT |
| pynput | LGPL-3.0 |
| PyInstaller bootloader | GPL with the bootloader distribution exception |

`packaging/collect_licenses.py` copies the installed distributions' actual license
files, including PDFium codec notices, into `build/licenses`. The packaging spec
ships these as `licenses/`, together with a version/license inventory. The GPL v2
text is shipped in `file_converter/resources/GPL-2.0.txt`. CI also retains official
Pandoc archive copyright files. LibreOffice is optional and is not bundled.

Source code for the GPL and LGPL components bundled in the release builds is listed
in CORRESPONDING-SOURCE.md.

Windows-only PyInstaller dependencies (`pefile`, `pywin32-ctypes`) resolve from
the pinned PyInstaller requirements on Windows. Their versions are recorded in
CI, not claimed as locally observed locks.

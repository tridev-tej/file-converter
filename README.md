# FileConverter

A radial conversion menu for macOS arm64 and Windows x64, adapted from
[FileAction](https://github.com/Metamorfolog/file_action).

Drag files in Finder or Explorer, tap a modifier, then drop onto an operation.
Shift opens Convert, Control opens Tools, Option/Alt opens Actions. Tap the same
modifier again, or R, to repeat the last successful action. Tap another modifier
to switch wheels. Drop in the center or press Escape to cancel.

The tray provides Open drop wheel, Settings, Jobs and Quit. Closing windows keeps
the tray running. A single conversion worker queues jobs; each card offers Open,
Reveal, Cancel and error details. Already completed outputs survive batch errors
and cancellation. Repeat revalidates inputs, tools and saved parameters.

## Run from source

Requires Python 3.12 and the existing pinned `.venv`. No runtime installation or
downloading occurs. Linux, Intel macOS and Windows ARM are outside v1 scope.

```sh
export PYTHONPATH="$PWD/src"
.venv/bin/python -m file_converter
.venv/bin/python -m file_converter list photo.png --json
.venv/bin/python -m file_converter run image.to.jpg photo.png --json
.venv/bin/python -m file_converter run video.trim clip.mp4 --param start=0:02 --param end=0:04
.venv/bin/python -m file_converter run action.copy folder --param destination=/absolute/destination
.venv/bin/python -m file_converter wheel photo.png
.venv/bin/python -m file_converter self-test build/selftest
.venv/bin/python -m file_converter diagnostics
```

`list`, `run` and `self-test` do not start global hooks, login items or a tray.
Explicit path/OCR actions publish clipboard text; terminal/reveal actions affect
the desktop. All other conversions leave the clipboard alone. GUI clipboard
publication occurs on the main thread after outputs are created.

CLI exits: 0 success, 1 failure/partial result, 2 invalid request, 3 missing
capability, 130 cancellation. Progress and diagnostics go to stderr; `--json`
returns structured operation lists or results. No successful exit for partial
failure. Headless conversions persist repeat state only after complete success.

## Dependencies and permissions

macOS uses the verified native `vendor/pandoc/pandoc`, never pypandoc's x86_64
executable. Frozen builds use the packaged copy. Windows source execution finds
Pandoc on PATH; CI stages the verified official executable there. FFmpeg comes
from imageio-ffmpeg in source runs and the bundled tool directory when frozen.
Native architecture preflight rejects mismatches. `vendor/` is ignored.

LibreOffice is optional and is never installed by the app. Routes needing it
remain visible and disabled with a reason. DOC and all slide routes use it.
Document PDF output uses LibreOffice, with a Pandoc DOCX intermediate for MD/EPUB.
ODS reading is native; ODS/PDF writing uses LibreOffice. Failed conversions never
switch backends automatically.

On macOS, grant Input Monitoring and Accessibility in System Settings, then quit
and reopen the app. Settings includes permission help. The `.app` and development
Python host need separate grants. Tap creation is the decisive gesture check;
the tray shows any gesture error. The explicit drop wheel remains available.
Windows hooks use pynput; Finder gestures use a main-thread Quartz event tap.
Elevated Explorer drag compatibility is not supported.

Settings live in `~/Library/Application Support/FileConverter/settings.json` on
macOS and `%APPDATA%\FileConverter\settings.json` on Windows. Malformed files
raise an error. Launch at login is off until explicitly enabled in Settings.
Login startup is tray-only. Modifier remapping permits Shift/Control/Alt with
unique assignments; Command is excluded on macOS.

## Outputs and limits

Outputs go beside each input with exclusive publication. `photo.jpg` collisions
become `photo (2).jpg`. Tool names include `photo (compressed).jpg`. Multiple PDF
pages go into `name (pages)/`; multiple spreadsheet sheets become separate files.
Unsafe archive paths, links, devices, conflicts and encryption fail explicitly.
Copy and move never overwrite. Cross-volume moves copy and verify before source
removal; cancellation preserves completed transfers.

Images use their EXIF-oriented first frame. Only GIF-to-video operations retain
animation. JPG/PDF flatten transparency onto white. AVIF uses Pillow's native
codec; HEIC uses pillow-heif. Image edits retain the normalized original format
and need its encoder. Compression and PDF optimization can increase file size.
PDF DOCX is text-only; PPTX uses rendered page images. Text extraction never
silently invokes OCR. Password-protected PDFs are unsupported. macOS OCR uses
Vision, English only; Windows OCR is disabled in v1.

Spreadsheets preserve values, sheet order, leading-zero identifiers and dates,
not macros/charts/styles or formula evaluation. Missing cached XLSX/ODS formula
values fail. CSV/TSV use UTF-8; CSV delimiters must be unambiguous. Outputs use a
UTF-8 BOM and CRLF. TXT-to-timed-subtitles is unsupported.

Cut: SVG, RAR, Windows OCR, floating shelf/share, new output IDs outside the
reference catalog, PDF layout reconstruction, automatic OCR, parallel jobs,
persistent history, auto-updates and Finder/Explorer extensions. No notarization
or paid signing; ad-hoc macOS signing does not remove installation warnings.

## Verification and packaging

All verification output belongs in ignored `build/`. Tests use configuration and
workspace overrides there and do not change real settings, clipboard or login
items. Offscreen screenshots do not prove native drag/permission behavior.

```sh
export PYTHONPATH="$PWD/src"
export FC_CONFIG_DIR="$PWD/build/test-state/config"
export FC_WORKSPACE="$PWD/build/test-state/work"
export FC_E2E_REPORT="$PWD/build/e2e-report.json"
.venv/bin/python -m pytest tests/e2e -q
.venv/bin/python -m file_converter self-test build/selftest
bash packaging/build_mac.sh
dist/FileConverter.app/Contents/MacOS/FileConverter self-test build/selftest-app
```

Windows: run `packaging/build_win.ps1` in PowerShell with an existing `.venv` and
Inno Setup installed. It builds separate GUI and console launchers in one folder.
The installer is per-user; adding the CLI to PATH is an explicit option.

Exact assets: `FileConverter-macOS-arm64.dmg`,
`FileConverter-Windows-x64-Setup.exe`, `FileConverter-Windows-x64.zip`.
CI installs dependencies only on runners, verifies native Pandoc archive hashes,
runs E2E/screenshots/frozen backend smoke tests, and requires both OS builds plus
Office validation for tagged releases. See CORRESPONDING-SOURCE.md: public release
also requires matching native-source materials and notices.

## Registered operations

82 source operations plus OCR and five Actions. Order matches the source catalog.
Applicable operations with unavailable capabilities remain visible but disabled.

### Convert / Tools

```text
image.to.jpg
image.to.png
image.to.webp
image.to.avif
image.to.tiff
image.to.ico
image.to.pdf
gif.to.mp4
gif.to.webm
image.compress
image.half
image.max1920
image.rotate.right
image.rotate.left
image.flip
image.square
image.grayscale
image.strip
image.merge.pdf
audio.to.mp3
audio.to.m4a
audio.to.wav
audio.to.flac
audio.to.ogg
audio.to.opus
audio.to.aiff
audio.compress
audio.normalize
audio.trim
audio.concat
video.to.mp4
video.to.mov
video.to.mkv
video.to.webm
video.to.gif
video.to.mp3
video.compress
video.720p
video.mute
video.trim
video.rotate
video.speed2
video.thumbnail
pdf.to.docx
pdf.to.jpg
pdf.to.png
pdf.to.pptx
pdf.to.txt
pdf.to.md
pdf.to.html
pdf.to.epub
pdf.merge
pdf.split
pdf.rotate
pdf.optimize
doc.to.docx
doc.to.pdf
doc.to.odt
doc.to.md
doc.to.html
doc.to.txt
doc.to.epub
doc.to.rtf
slides.to.pdf
slides.to.png
slides.to.jpg
slides.to.pptx
slides.to.odp
sheet.to.xlsx
sheet.to.csv
sheet.to.tsv
sheet.to.ods
sheet.to.pdf
subs.to.srt
subs.to.vtt
subs.to.txt
archive.extract
archive.to.zip
archive.to.tar
archive.to.tar.gz
pack.zip
pack.tar.gz
```

### Application additions

```text
tools.ocr
action.copy
action.move
action.path
action.terminal
action.reveal
```


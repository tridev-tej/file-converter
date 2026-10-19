# FileConverter

88 planned operation IDs are implemented. Release verification is incomplete:
native OCR fails here, iconutil blocks the final app/DMG, and Windows/real desktop
acceptance has not run. No git commands, downloads or package installation were
used during implementation.

## Architecture and decisions

`core/catalog.py` preserves source ordering and explicit routes. Applicability
checks every input. Availability explains missing tools. The runner refreshes
capabilities and revalidates paths/parameters at execution time. A failed route
never switches backends.

The controller owns wheel/repeat/parameter state. Qt drop URLs are authoritative;
all accepted drops negotiate CopyAction. Native hooks detect gestures only. macOS
uses the proven main-thread Quartz event tap and pasteboard change count. Windows
uses pynput and a 10-pixel drag threshold. Hook failure stays visible in the tray.

One dedicated worker runs all conversions, including every PDFium call and object
cleanup. Immutable settings/parameters keep queued jobs stable. Main-thread code
publishes clipboard text and native desktop effects after successful outputs.
Jobs retain session history and completed outputs after partial failure/cancel.

Writes are staged at owned hidden paths with the real extension. macOS
`renamex_np(RENAME_EXCL)` and Windows no-replace rename publish files/directories
without a check/rename race. Cleanup failures become diagnostic notes. Copy/move
preserve original names. Cross-volume moves copy and hash-verify before deletion.

Key adaptations:

- Native Pillow AVIF; pillow-heif for HEIC. Image edits use the oriented first
  frame and retain the normalized source format. Animation survives explicit
  GIF-to-video operations only.
- Native vendor Pandoc 3.12.1 arm64 on macOS. The installed pypandoc binary is
  x86_64 and is never selected. Frozen tools resolve inside the bundle.
- PDF DOCX is extracted text; PPTX contains fitted page renders. No layout
  reconstruction or implicit OCR.
- Native XLS/ODS readers. Spreadsheet exports preserve values and identifiers,
  not macros, charts, styles or formula calculations.
- Archive paths/types are validated before staged extraction. Links, devices,
  conflicts and encrypted members fail explicitly.
- Separate Windows GUI/console launchers share application code.
- Excluding Python QtQuick modules did not remove native Qt Quick dependencies.
  The custom QtGui hook excludes the unused virtual-keyboard plugin before
  native dependency analysis. The rebuilt folder contains no Qt Quick/WebEngine.

## Files

| Path | Responsibility |
| --- | --- |
| `src/file_converter/core/` | Contracts, formats, registry, outputs, tools, settings, processes, runner and geometry |
| `src/file_converter/backends/` | Image, FFmpeg, PDF, Pandoc, Office, spreadsheets, subtitles, archives and Vision |
| `src/file_converter/ui/` | Wheel/controller, jobs, parameters, settings, tray, palette and self-test |
| `src/file_converter/platform/` | Gestures, file actions, shell and opt-in login registration |
| `app.py`, `cli.py`, `__main__.py` | Qt/IPC lifecycle and independent headless dispatch |
| `tests/e2e/` | Independent expected IDs, generated fixtures, content/adversarial checks and Qt drop-to-job verification |
| `packaging/`, `installer/` | Native preflight, verified CI Pandoc acquisition, icons/licenses, PyInstaller, frozen checks and installers |
| `.github/workflows/build.yml` | Two-platform builds, evidence, optional Office validation and gated releases |

## Verification

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

Latest source result: **132 passed, 11 skipped, one failed**. The operation matrix
records 76 passed, eight missing-LibreOffice skips, one OCR failure and three
manual desktop effects. The OCR conversion failure remains a failure.
`build/e2e-report.json` includes dependencies/tools, every operation, individual
test outcomes and manual acceptance gaps. Tests isolate settings/workspace under
build and do not change the real clipboard/login items.

Content checks cover orientation/alpha/metadata, media duration/streams, PDF
order/rendering, document resources, XLS/ODS/CSV values, subtitle timing,
archive content/safety, concurrent publication, partial copy, cancellation and
the offscreen Qt drop-to-worker path.

Self-test produces **71 PNGs**, using production painting/geometry and immutable
synthetic inputs. Scenarios cover all wheels/groups, light/dark, empty state,
disabled Office/Windows OCR, repeat, aggregates, full image Tools and high DPI.
See `build/selftest/manifest.json` and the PNGs.

## Native build evidence and blockers

Preflight confirms Python, FFmpeg and Pandoc arm64. The normal macOS script fails:

```text
/usr/bin/iconutil -c icns build/icons/FileConverter.iconset -o build/icons/FileConverter.icns
build/icons/FileConverter.iconset:Invalid Iconset.
```

All ten required PNG names, dimensions and formats were checked. Native sips
decoding/re-encoding succeeds, but iconutil still rejects the set. The underlying
cause is unproven. No substitute icon route was added.

The remaining original PyInstaller stages were run directly for diagnosis.
Analysis/native COLLECT succeed; final BUNDLE fails with
`FileNotFoundError: .../build/icons/FileConverter.icns not found`.
The intermediate `dist/FileConverter/FileConverter` renders 71 scenarios and
runs frozen backend checks: **10 passed, OCR failed**. It is not the completed `.app`.
`build/frozen-report.json` and `build/frozen-smoke.log` retain individual results,
including a real OCR check. Frozen verification must pass before DMG creation.

The exact requested `.app` command exits **127**, because
`dist/FileConverter.app/Contents/MacOS/FileConverter` does not exist after failed
assembly. No successful `.app` launch, signing, strict codesign verification or
DMG creation is claimed.

Vision decodes the valid test image, but `performRequests_error_` returns
`(False, None)` for URL and CGImage inputs, including CPU-only diagnosis. Its
native-service failure is unproven. The app reports the error and preserves the
clipboard. Do not replace Vision or label this passing.

## Build/release and manual acceptance

macOS: native preflight, iconutil, licenses, PyInstaller, ad-hoc signing, strict
verification, frozen screenshots/conversions, hdiutil. Windows: dual launchers,
frozen verification, complete folder ZIP, per-user Inno Setup. CLI PATH is an
explicit installer option. Launch at login is an explicit Settings toggle.

Exact assets: `FileConverter-macOS-arm64.dmg`,
`FileConverter-Windows-x64-Setup.exe`, `FileConverter-Windows-x64.zip`.
CI alone installs/downloads dependencies and verifies the specified Pandoc
archive hashes. Tagged releases require both OS builds. Office validation is a manual workflow_dispatch job.
Windows/hosted CI has not run here. LibreOffice is absent locally; no execution
evidence is claimed for its eight primary routes.

Source is MIT; the binary bundle is not MIT-only. Bundled GPL/LGPL programs ship
unmodified; `CORRESPONDING-SOURCE.md` links their exact upstream source versions.

Real Finder/Explorer drags, mixed-DPI edges, packaged permissions, modifier/repeat
timing, clipboard/Open/Reveal/Terminal, login startup, single-instance forwarding
and fresh Windows installer/ZIP acceptance remain `manual_required`. Offscreen
rendering does not prove these flows.

Cuts match the plan: Linux/Intel Mac/Windows ARM, SVG/RAR, Windows OCR, floating
shelf/share, extra conversion IDs, automatic OCR/password PDFs/layout recovery,
animation-preserving ordinary edits, formula calculation/legacy encoding
guessing, parallel/resumable jobs, persistent history, auto-updates, file-manager
extensions and notarization/paid signing.

## Complexity

All Python function/lambda scopes, nested callbacks, tests and the audit helper
are counted in `build/complexity.json`. Maximum CC is 10. No existing application
baseline existed. Native AppleScript has CC 1; PowerShell `Invoke-Python` has
CC 2; Inno Setup procedures have CC 10, 3 and 4.

| Function | Baseline | Initial peak | Final CC |
| --- | --- | --- | --- |
| `ffmpeg.parse_time` | new | 13 | 3 |
| `app.validate_message` | new | 11 | 7 |
| `selftest.scenarios` | new | 11 | 9 |
| `tools.operation_availability` | new | 11 | 8 |
| `spreadsheet.detect_delimiter` | new | 11 | 7 |
| `test_operations.inspect_output` | new | 11 | 9 |
| `test_operations.test_operation` | new | 11 | 9 |
| `collect_licenses.main` | new | 13 | 8 |

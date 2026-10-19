$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$env:PYTHONPATH = "$PWD\src"
$env:PYINSTALLER_CONFIG_DIR = "$PWD\build\pyinstaller-cache"
$env:FC_CONFIG_DIR = "$PWD\build\frozen-config"
$env:FC_WORKSPACE = "$PWD\build\frozen-work"
$env:TEMP = "$PWD\build\tmp"
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force build\tools, build\tmp | Out-Null
function Invoke-Python {
    & .venv\Scripts\python.exe @args
    if ($LASTEXITCODE -ne 0) { throw "Python command failed: $args" }
}
Invoke-Python packaging/preflight.py
Invoke-Python packaging/make_icons.py
Invoke-Python packaging/collect_licenses.py
Invoke-Python packaging/copy_ffmpeg.py build/tools/ffmpeg.exe
Invoke-Python -m PyInstaller --noconfirm --clean --workpath build/pyinstaller packaging/file_converter.spec
& dist\FileConverter\file-converter.exe self-test build/selftest-app
if ($LASTEXITCODE -ne 0) { throw "Frozen self-test failed" }
Invoke-Python packaging/frozen_smoke.py dist/FileConverter/file-converter.exe
Compress-Archive -Path dist\FileConverter -DestinationPath dist\FileConverter-Windows-x64.zip -Force
$compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($compiler) {
    $compilerPath = $compiler.Source
} else {
    $known = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $known)) { throw "Missing Inno Setup compiler" }
    $compilerPath = $known
}
& $compilerPath installer\FileConverter.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
foreach ($asset in @("FileConverter-Windows-x64-Setup.exe", "FileConverter-Windows-x64.zip")) {
    if (-not (Test-Path "dist\$asset")) { throw "Missing release asset: $asset" }
}

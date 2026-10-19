"""CI-only verified official Pandoc acquisition; never imported by the app."""

import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

RELEASES = {
    "darwin": ("pandoc-3.12.1-arm64-macOS.zip", "c2146cf33a583f3ac93eccddf1bb662371d5cfcce1aad1c87ad860cca1435d46", "pandoc"),
    "win32": ("pandoc-3.12.1-windows-x86_64.zip", "6ef431cb20b2c24a0371fc19200dc49d452be54b1b5c9239f3462841ef53e587", "pandoc.exe"),
}


def main():
    filename, checksum, executable = RELEASES[sys.platform]
    root = Path("build/downloads")
    root.mkdir(parents=True, exist_ok=True)
    archive_path = root / filename
    url = "https://github.com/jgm/pandoc/releases/download/3.12.1/" + filename
    urllib.request.urlretrieve(url, archive_path)
    actual = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if actual != checksum:
        raise RuntimeError(f"Pandoc archive checksum mismatch: {actual}")
    destination = Path("vendor/pandoc")
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        entries = [entry for entry in archive.infolist() if Path(entry.filename).name == executable]
        if len(entries) != 1:
            raise RuntimeError("Pandoc archive must contain exactly one executable")
        with archive.open(entries[0]) as source, (destination / executable).open("wb") as output:
            shutil.copyfileobj(source, output)
        for entry in archive.infolist():
            if Path(entry.filename).name.upper() in {"COPYRIGHT", "COPYING", "LICENSE"}:
                (destination / Path(entry.filename).name).write_bytes(archive.read(entry))
    (destination / executable).chmod(0o755)
    print(f"Verified {filename}: {actual}")


if __name__ == "__main__":
    main()

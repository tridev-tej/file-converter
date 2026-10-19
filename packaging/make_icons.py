"""Generate native icons from the same drawn source image."""

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def make_source():
    image = Image.new("RGBA", (1024, 1024))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, 984, 984), radius=210, fill="#202b3b")
    for index in range(8):
        start = index * 45 - 110
        draw.pieslice((160, 160, 864, 864), start, start + 40, fill="#729cd2" if index % 2 else "#b4d0f2")
    draw.ellipse((370, 370, 654, 654), fill="#202b3b")
    return image


def main():
    root = Path("build/icons")
    root.mkdir(parents=True, exist_ok=True)
    image = make_source()
    image.save(root / "FileConverter.png")
    image.save(root / "FileConverter.ico", sizes=[(size, size) for size in (16, 32, 48, 64, 128, 256)])
    if sys.platform != "darwin":
        return
    iconset = root / "FileConverter.iconset"
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            suffix = "@2x" if scale == 2 else ""
            image.resize((size * scale, size * scale), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}{suffix}.png")
    subprocess.run(["/usr/bin/iconutil", "-c", "icns", str(iconset), "-o", str(root / "FileConverter.icns")], check=True)


if __name__ == "__main__":
    main()

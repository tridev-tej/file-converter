# Corresponding source

The release builds bundle these GPL/LGPL programs unmodified. Their complete source is available upstream at the exact versions shipped:

| Component | Version | Source |
| --- | --- | --- |
| Pandoc | 3.12.1 | https://github.com/jgm/pandoc/archive/refs/tags/3.12.1.tar.gz |
| FFmpeg (via imageio-ffmpeg) | 7.1 | https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz |
| Qt (via PySide6 6.12.0) | 6.12.0 | https://download.qt.io/official_releases/qt/6.12/ |
| PySide6 / shiboken6 | 6.12.0 | https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.12.0 |
| libheif (via pillow-heif) | bundled with pillow-heif | https://github.com/strukturag/libheif |
| pynput | see requirements.txt | https://github.com/moses-palmer/pynput |
| py7zr | see requirements.txt | https://github.com/miurahr/py7zr |

The Qt libraries are dynamically linked and can be replaced in the bundle. If any link stops working, open an issue on this repository and the source will be provided.

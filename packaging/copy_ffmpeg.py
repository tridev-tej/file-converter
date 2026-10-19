"""Copy the bundled FFmpeg executable to the path given on the command line."""

import shutil
import sys

from file_converter.core.tools import ffmpeg_path


def main():
    shutil.copy2(ffmpeg_path(), sys.argv[1])


if __name__ == "__main__":
    main()

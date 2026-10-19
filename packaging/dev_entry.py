"""Absolute development login entry using the existing virtual environment."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from file_converter.cli import main

raise SystemExit(main())

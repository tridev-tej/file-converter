"""Readable OS-following wheel colors."""

from dataclasses import dataclass
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


@dataclass(frozen=True)
class Palette:
    background: str
    sector: str
    selected: str
    text: str
    muted: str
    disabled: str
    line: str
    error: str


def palette(theme=None):
    dark = theme == "dark"
    if theme is None:
        dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    if dark:
        return Palette("#202329", "#2b2f36", "#41699e", "#f2f4f7", "#bac0c9", "#777d88", "#454b55", "#ffb3a8")
    return Palette("#f6f7f9", "#ffffff", "#d6e7fc", "#20242b", "#555d68", "#949ba5", "#d1d6df", "#aa3020")

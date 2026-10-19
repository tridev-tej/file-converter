"""Menu-bar/system-tray entry points."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def tray_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#547fb7"))
    painter.drawEllipse(4, 4, 56, 56)
    painter.setBrush(QColor("#f5f7fa"))
    painter.drawEllipse(23, 23, 18, 18)
    painter.end()
    return QIcon(pixmap)


class Tray(QSystemTrayIcon):
    def __init__(self, controller, jobs, settings_callback, quit_callback):
        super().__init__(tray_icon())
        self.setToolTip("FileConverter")
        self.menu = QMenu()
        self.status = self.menu.addAction("Gesture not started")
        self.status.setEnabled(False)
        self.menu.addSeparator()
        self.menu.addAction("Open drop wheel", lambda: controller.show())
        self.menu.addAction("Settings", settings_callback)
        self.menu.addAction("Jobs", jobs.window.show)
        self.menu.addSeparator()
        self.menu.addAction("Quit", quit_callback)
        self.setContextMenu(self.menu)
        self.show()

    def set_status(self, text):
        self.status.setText(text)
        self.setToolTip("FileConverter - " + text)

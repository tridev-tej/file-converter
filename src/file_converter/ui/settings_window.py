"""Settings and dependency/permission status with explicit persistence errors."""

import sys
from dataclasses import replace

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QMessageBox, QPushButton, QSpinBox, QWidget

from ..core.settings import save_settings, validate_settings


class SettingsWindow(QWidget):
    saved = Signal(object)

    def __init__(self, settings, tools, gesture_status):
        super().__init__()
        self.settings = settings
        self.setWindowTitle("FileConverter Settings")
        self.resize(520, 440)
        layout = QFormLayout(self)
        self.gestures = {}
        for key in ("Shift", "Control", "Alt"):
            selector = QComboBox()
            selector.addItems(["Convert", "Tools", "Actions"])
            selector.setCurrentText(settings.gestures[key])
            layout.addRow("Option" if key == "Alt" and sys.platform == "darwin" else key, selector)
            self.gestures[key] = selector
        self.numbers = {}
        for key, label, low, high in [("jpeg_quality", "Image quality", 1, 100), ("compress_quality", "Compression quality", 1, 100), ("pdf_dpi", "PDF render DPI", 72, 600), ("video_crf", "Video CRF", 0, 51), ("compress_video_crf", "Compressed video CRF", 0, 51)]:
            value = QSpinBox()
            value.setRange(low, high)
            value.setValue(getattr(settings, key))
            self.numbers[key] = value
            layout.addRow(label, value)
        self.login = QCheckBox("Launch at login")
        self.login.setChecked(settings.launch_at_login)
        layout.addRow(self.login)
        for name in ("ffmpeg", "pandoc", "office"):
            tool = getattr(tools, name)
            label = QLabel(tool.version if tool.available else tool.reason)
            label.setWordWrap(True)
            layout.addRow(name, label)
        status = QLabel(gesture_status)
        status.setWordWrap(True)
        layout.addRow("Gestures", status)
        help_button = QPushButton("Gesture permission help")
        help_button.clicked.connect(permission_help)
        layout.addRow(help_button)
        save = QPushButton("Save")
        save.clicked.connect(self.save)
        layout.addRow(save)

    def save(self):
        from ..platform.autostart import set_enabled
        values = {key: widget.value() for key, widget in self.numbers.items()}
        mapping = {key: widget.currentText() for key, widget in self.gestures.items()}
        updated = replace(self.settings, **values, gestures=mapping, launch_at_login=self.login.isChecked())
        try:
            validate_settings(updated)
            if updated.launch_at_login != self.settings.launch_at_login:
                set_enabled(updated.launch_at_login)
            save_settings(updated)
        except Exception as error:
            QMessageBox.warning(self, "Could not save settings", str(error))
            return
        self.settings = updated
        self.saved.emit(updated)
        self.hide()


def permission_help():
    from ..platform.shell import open_path
    dialog = QMessageBox()
    dialog.setWindowTitle("FileConverter gesture permissions")
    if sys.platform != "darwin":
        dialog.setText("Drag a file, then tap Shift, Ctrl or Alt. Windows does not permit drops from an elevated Explorer into a normal app.")
        dialog.exec()
        return
    dialog.setText("Enable FileConverter in Input Monitoring and Accessibility in System Settings, then quit and reopen FileConverter. Development Python and the packaged app need separate grants. The drop wheel remains available from the tray.")
    monitoring = dialog.addButton("Input Monitoring", QMessageBox.ActionRole)
    accessibility = dialog.addButton("Accessibility", QMessageBox.ActionRole)
    dialog.addButton(QMessageBox.Close)
    dialog.exec()
    selected = dialog.clickedButton()
    targets = {monitoring: "Privacy_ListenEvent", accessibility: "Privacy_Accessibility"}
    if selected in targets:
        open_path("x-apple.systempreferences:com.apple.preference.security?" + targets[selected])

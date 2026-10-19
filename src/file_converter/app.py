"""Qt lifecycle, bounded single-instance IPC and native gesture integration."""

import hashlib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

MAX_IPC = 65536


def identity():
    from .core.settings import config_path
    value = str(config_path().absolute()).encode()
    return "FileConverter-" + hashlib.sha256(value).hexdigest()[:24]


def validate_message(data):
    if len(data) > MAX_IPC:
        raise ValueError("IPC request too large")
    request = json.loads(data)
    if not isinstance(request, dict) or set(request) != {"files", "tray_only"}:
        raise ValueError("Invalid IPC request")
    paths = request["files"]
    if not isinstance(paths, list) or len(paths) > 256 or type(request["tray_only"]) is not bool:
        raise ValueError("Invalid IPC fields")
    validate_ipc_paths(paths)
    return request


def validate_ipc_paths(paths):
    for path in paths:
        if not isinstance(path, str) or not Path(path).is_absolute() or not Path(path).exists():
            raise ValueError("IPC input must be an existing absolute path")


def forward(files, tray_only):
    socket = QLocalSocket()
    socket.connectToServer(identity())
    if not socket.waitForConnected(500):
        error = socket.error()
        permitted = {QLocalSocket.ServerNotFoundError, QLocalSocket.ConnectionRefusedError}
        if error not in permitted:
            raise RuntimeError("Could not connect to existing FileConverter: " + socket.errorString())
        return False
    payload = json.dumps(dict(files=[str(Path(path).absolute()) for path in files], tray_only=tray_only)).encode()
    validate_message(payload)
    socket.write(payload + b"\n")
    if not socket.waitForBytesWritten(1000):
        raise RuntimeError("Could not forward launch request")
    socket.disconnectFromServer()
    return True


class InstanceServer(QObject):
    received = Signal(object)

    def __init__(self):
        super().__init__()
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        self.connections = {}
        if not self.server.listen(identity()):
            self.remove_stale_endpoint()
        self.server.newConnection.connect(self.connected)

    def remove_stale_endpoint(self):
        probe = QLocalSocket()
        probe.connectToServer(identity())
        if probe.waitForConnected(500):
            probe.disconnectFromServer()
            raise RuntimeError("Another FileConverter instance started during launch. Launch again to forward the request")
        if probe.error() not in {QLocalSocket.ServerNotFoundError, QLocalSocket.ConnectionRefusedError}:
            raise RuntimeError("Cannot establish stale IPC endpoint: " + probe.errorString())
        if not QLocalServer.removeServer(identity()) or not self.server.listen(identity()):
            raise RuntimeError("Could not start FileConverter IPC: " + self.server.errorString())

    def connected(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self.connections[socket] = bytearray()
            socket.readyRead.connect(lambda socket=socket: self.read(socket))
            socket.disconnected.connect(lambda socket=socket: self.release(socket))
            QTimer.singleShot(3000, socket.disconnectFromServer)

    def release(self, socket):
        self.connections.pop(socket, None)
        socket.deleteLater()

    def read(self, socket):
        buffer = self.connections.get(socket)
        if buffer is None:
            return
        buffer.extend(bytes(socket.readAll()))
        if len(buffer) > MAX_IPC:
            socket.disconnectFromServer()
            return
        if b"\n" not in buffer:
            return
        try:
            self.received.emit(validate_message(bytes(buffer).split(b"\n", 1)[0]))
        except (ValueError, TypeError) as error:
            print(f"Rejected IPC request: {error}", file=sys.stderr)
        socket.disconnectFromServer()


class Application:
    def __init__(self, qt, files, tray_only):
        from .core.settings import load_settings
        from .core.tools import discover_tools
        from .ui.controller import Controller
        from .ui.jobs import JobManager
        from .ui.tray import Tray
        from .ui.wheel import Wheel
        self.qt = qt
        self.settings_window = None
        self.server = InstanceServer()
        self.settings = load_settings()
        self.tools = discover_tools()
        self.wheel = Wheel()
        self.jobs = JobManager()
        self.controller = Controller(self.wheel, self.jobs, self.settings, self.tools)
        self.gesture = self.create_gesture()
        self.tray = Tray(self.controller, self.jobs, self.show_settings, self.quit)
        self.server.received.connect(self.receive)
        self.gesture.event.connect(self.controller.gesture, Qt.QueuedConnection)
        self.gesture.mouse_released.connect(self.controller.mouse_released, Qt.QueuedConnection)
        self.gesture.status_changed.connect(self.tray.set_status)
        QTimer.singleShot(0, self.start_gesture)
        if not tray_only:
            QTimer.singleShot(0, lambda: self.controller.show(files))

    def create_gesture(self):
        if sys.platform == "darwin":
            from .platform.gesture_mac import Gesture
        elif sys.platform == "win32":
            from .platform.gesture_win import Gesture
        else:
            raise RuntimeError("FileConverter supports macOS and Windows only")
        return Gesture(self.wheel.isVisible)

    def start_gesture(self):
        try:
            self.gesture.start()
        except Exception as error:
            self.tray.set_status("Gesture off - " + str(error))
        if sys.platform == "darwin":
            self.check_permissions()

    def check_permissions(self):
        from .core.settings import save_settings
        from .ui.settings_window import permission_help
        monitoring, accessibility = self.gesture.permissions()
        if monitoring and accessibility:
            return
        if self.controller.settings.permission_help_shown:
            return
        self.gesture.request_permission()
        permission_help()
        self.controller.settings = replace(self.controller.settings, permission_help_shown=True)
        try:
            save_settings(self.controller.settings)
        except OSError as error:
            QMessageBox.warning(None, "Settings error", str(error))

    def receive(self, request):
        if not request["tray_only"]:
            self.controller.show(request["files"])

    def show_settings(self):
        from .ui.settings_window import SettingsWindow
        self.settings_window = SettingsWindow(self.controller.settings, self.tools, self.gesture.status_text)
        self.settings_window.saved.connect(self.settings_saved)
        self.settings_window.show()
        self.settings_window.activateWindow()

    def settings_saved(self, settings):
        self.controller.settings = settings

    def quit(self):
        if self.jobs.active():
            choice = QMessageBox.question(None, "Conversions running", "Cancel active jobs and quit?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if choice != QMessageBox.Yes:
                return
        self.gesture.stop()
        self.jobs.close()
        self.tray.hide()
        self.server.server.close()
        self.qt.quit()


def run_app(files=(), tray_only=False):
    qt = QApplication.instance() or QApplication(sys.argv)
    qt.setApplicationName("FileConverter")
    qt.setOrganizationName("Tejesh Vaish")
    qt.setQuitOnLastWindowClosed(False)
    if forward(files, tray_only):
        return 0
    try:
        application = Application(qt, files, tray_only)
    except Exception as error:
        QMessageBox.critical(None, "FileConverter could not start", str(error))
        return 1
    qt.aboutToQuit.connect(application.jobs.close)
    return qt.exec()

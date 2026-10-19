"""Wheel state, authoritative drop selection, repeat and job submission."""

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtWidgets import QMessageBox

from ..core.catalog import build_catalog
from ..core.formats import file_item
from ..core.operations import Availability, OperationRequest
from ..core.runner import validate_request
from ..core.settings import save_settings
from ..core.wheel_layout import Slice, slices_for
from .params import collect_parameters


class Controller(QObject):
    def __init__(self, wheel, jobs, settings, tools):
        super().__init__()
        self.wheel = wheel
        self.jobs = jobs
        self.settings = settings
        self.tools = tools
        self.catalog = build_catalog()
        self.operations = {op.id: op for op in self.catalog}
        self.kind = "Convert"
        self.state = "hidden"
        self.repeat = False
        self.native_drag = False
        self.items = ()
        self.drop_generation = 0
        self.release_timer = QTimer(self)
        self.release_timer.setSingleShot(True)
        self.release_timer.setInterval(500)
        self.release_timer.timeout.connect(self.abandoned_drag)
        wheel.files_changed.connect(self.set_files)
        wheel.committed.connect(self.commit)
        wheel.cancelled.connect(self.hide)
        wheel.repeat_requested.connect(self.toggle_repeat)
        jobs.completed.connect(self.completed)

    def show(self, paths=(), kind="Convert", native=False):
        from ..core.tools import refresh_tools
        self.tools = refresh_tools()
        self.kind = kind
        self.repeat = False
        self.native_drag = native
        self.set_files(list(paths))
        self.state = "populated" if self.items else "awaiting_files"
        self.wheel.show_at_cursor()

    @Slot(list)
    def set_files(self, paths):
        self.items = tuple(file_item(path) for path in paths)
        self.refresh()

    def refresh(self):
        slices = self.repeat_slices() if self.repeat else slices_for(self.catalog, self.kind, self.items, self.tools)
        self.wheel.set_model(slices, [item.path for item in self.items], self.kind, self.repeat)
        self.wheel.hint = "Drag files here"
        if self.repeat and self.settings.last_parameters.get("destination"):
            self.wheel.hint = "Destination: " + self.settings.last_parameters["destination"]

    def repeat_slices(self):
        operation = self.operations.get(self.settings.last_operation)
        if operation is None:
            operation = replace(self.catalog[0], id="unavailable.repeat", label="No last action")
            return (Slice(operation, Availability(False, ("No successful action has been saved",))),)
        availability = operation.availability(self.items, self.tools)
        if availability.enabled:
            try:
                request = self.request(operation.id, self.settings.last_parameters)
                validate_request(request, self.tools)
            except Exception as error:
                availability = Availability(False, (str(error),))
        return (Slice(operation, availability),)

    @Slot(str)
    def gesture(self, key):
        if key == "escape":
            self.hide()
            return
        if key == "repeat":
            if self.wheel.isVisible():
                self.toggle_repeat()
            return
        target = self.settings.gestures.get(key)
        if not target:
            return
        if not self.wheel.isVisible() or not self.native_drag:
            self.show(kind=target, native=True)
        elif self.kind == target:
            self.toggle_repeat()
        else:
            self.kind = target
            self.repeat = False
            self.refresh()

    def toggle_repeat(self):
        self.repeat = not self.repeat
        self.refresh()

    @Slot()
    def mouse_released(self):
        if self.native_drag and self.wheel.isVisible():
            self.release_timer.start()

    def abandoned_drag(self):
        if self.native_drag and self.wheel.isVisible():
            self.hide()

    def hide(self):
        self.release_timer.stop()
        self.wheel.hide()
        self.state = "hidden"
        self.native_drag = False

    def request(self, identifier, parameters):
        return OperationRequest(identifier, tuple(item.path for item in self.items), parameters, self.settings)

    @Slot(str, list)
    def commit(self, identifier, paths):
        self.set_files(paths)
        repeated = self.repeat
        parameters = dict(self.settings.last_parameters) if repeated else None
        operation = self.operations.get(identifier)
        self.hide()
        if operation is None:
            return
        try:
            if not repeated:
                self.state = "parameter_prompt"
                parameters = collect_parameters(operation)
            if parameters is None:
                self.state = "hidden"
                return
            request = self.request(identifier, parameters)
            validate_request(request, self.tools)
            self.jobs.submit(request)
        except Exception as error:
            QMessageBox.warning(None, "Cannot run operation", str(error))
        self.state = "hidden"

    def completed(self, job):
        if job.state != "succeeded":
            return
        parameters = dict(job.request.parameters)
        self.settings = replace(self.settings, last_operation=job.request.operation_id, last_parameters=parameters)
        try:
            save_settings(self.settings)
        except Exception as error:
            QMessageBox.warning(None, "Could not save repeat action", str(error))

"""One conversion worker, session history and visible corner job cards."""

import queue
import threading
import uuid
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget

from ..core.operations import CancellationToken, OperationResult


@dataclass
class Job:
    request: object
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    token: CancellationToken = field(default_factory=CancellationToken)
    state: str = "queued"
    progress: float | None = 0
    message: str = "Queued"
    result: object = None


class Worker(QObject):
    changed = Signal(str, object)
    finished = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self.work, name="FileConverter conversions", daemon=True)
        self.closed = False
        self.thread.start()

    def work(self):
        from ..core.runner import execute
        while (job := self.queue.get()) is not None:
            if job.token.cancelled:
                continue
            self.changed.emit(job.id, dict(state="running", message="Starting", progress=None))
            try:
                result = execute(job.request, job.token, lambda value, text: self.report_progress(job.id, value, text))
            except Exception as error:
                result = OperationResult(errors=[dict(error=str(error), type=type(error).__name__)], state="failed", exit_code=1)
            self.finished.emit(job.id, result)

    def report_progress(self, identifier, value, text):
        self.changed.emit(identifier, dict(progress=value, message=text))

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.queue.put(None)
        self.thread.join()


class JobCard(QWidget):
    def __init__(self, job, cancel):
        super().__init__()
        self.job = job
        self.cancel_job = cancel
        layout = QVBoxLayout(self)
        self.title = QLabel(job.request.operation_id)
        self.status = QLabel("Queued")
        self.status.setWordWrap(True)
        self.bar = QProgressBar()
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.hide()
        actions = QHBoxLayout()
        self.open_button = QPushButton("Open")
        self.reveal_button = QPushButton("Reveal")
        self.cancel_button = QPushButton("Cancel")
        detail_button = QPushButton("Details")
        self.open_button.clicked.connect(self.open_outputs)
        self.reveal_button.clicked.connect(self.reveal_outputs)
        self.cancel_button.clicked.connect(lambda: self.cancel_job(self.job.id))
        detail_button.clicked.connect(self.toggle_details)
        for button in (self.open_button, self.reveal_button, self.cancel_button, detail_button):
            actions.addWidget(button)
        layout.addWidget(self.title)
        layout.addWidget(self.status)
        layout.addWidget(self.bar)
        layout.addLayout(actions)
        layout.addWidget(self.details)
        self.refresh()

    def toggle_details(self):
        self.details.setVisible(not self.details.isVisible())

    def refresh(self):
        import json
        job = self.job
        self.status.setText(job.state.capitalize() + " - " + job.message)
        self.bar.setRange(0, 0 if job.progress is None else 100)
        self.bar.setValue(int((job.progress or 0) * 100))
        active = job.state in {"queued", "running"}
        self.cancel_button.setEnabled(active)
        outputs = bool(job.result and job.result.outputs)
        self.open_button.setEnabled(outputs)
        self.reveal_button.setEnabled(outputs)
        if job.result:
            self.details.setPlainText(json.dumps(job.result.as_dict(), indent=2))

    def open_outputs(self):
        from ..platform.shell import open_path
        outputs = self.job.result.outputs
        path = outputs[0] if len(outputs) == 1 else outputs[0].parent
        self.desktop_action(open_path, path)

    def reveal_outputs(self):
        from ..platform.shell import reveal
        self.desktop_action(reveal, self.job.result.outputs[0])

    def desktop_action(self, handler, path):
        from PySide6.QtWidgets import QMessageBox
        try:
            handler(path)
        except Exception as error:
            QMessageBox.warning(self, "Could not open output", str(error))


class JobsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FileConverter Jobs")
        self.resize(560, 600)
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.cards = QVBoxLayout(content)
        self.cards.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)


class JobManager(QObject):
    completed = Signal(object)

    def __init__(self):
        super().__init__()
        self.worker = Worker()
        self.worker.changed.connect(self.update_job, Qt.QueuedConnection)
        self.worker.finished.connect(self.finish_job, Qt.QueuedConnection)
        self.jobs = {}
        self.views = {}
        self.popups = []
        self.window = JobsWindow()

    def submit(self, request):
        job = Job(request)
        self.jobs[job.id] = job
        history = JobCard(job, self.cancel)
        self.window.cards.insertWidget(0, history)
        popup = QDialog(None, Qt.Tool | Qt.WindowStaysOnTopHint)
        popup.setWindowTitle("FileConverter")
        layout = QVBoxLayout(popup)
        card = JobCard(job, self.cancel)
        layout.addWidget(card)
        popup.resize(440, 180)
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()
        visible_count = sum(popup.isVisible() for popup in self.popups)
        y = max(screen.top(), screen.bottom() - 220 - visible_count * 190)
        popup.move(screen.right() - 460, y)
        popup.show()
        self.popups.append(popup)
        self.views[job.id] = (history, card)
        self.worker.queue.put(job)
        return job

    def update_job(self, identifier, values):
        job = self.jobs[identifier]
        if job.state == "cancelled":
            return
        for key, value in values.items():
            setattr(job, key, value)
        self.refresh(identifier)

    def refresh(self, identifier):
        for view in self.views[identifier]:
            view.refresh()

    def finish_job(self, identifier, result):
        from ..platform.shell import apply_effects
        from ..core.runner import finalize
        job = self.jobs[identifier]
        try:
            apply_effects(result)
        except Exception as error:
            result.errors.append(dict(error=f"Desktop effect failed: {error}"))
            finalize(result)
        job.result = result
        job.state = result.state
        job.progress = 1
        job.message = result.errors[0]["error"] if result.errors else f"{len(result.outputs)} output(s)"
        self.refresh(identifier)
        self.completed.emit(job)

    def cancel(self, identifier):
        job = self.jobs[identifier]
        job.token.cancel()
        if job.state == "queued":
            job.state = "cancelled"
            job.message = "Cancelled before execution"
            self.refresh(identifier)

    def active(self):
        return [job for job in self.jobs.values() if job.state in {"queued", "running"}]

    def close(self):
        for job in self.active():
            job.token.cancel()
        self.worker.close()

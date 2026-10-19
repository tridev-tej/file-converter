"""Parameter collection before job creation."""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLabel, QLineEdit, QMessageBox


def collect_parameters(operation, initial=None, parent=None):
    from ..core.runner import validate_parameters
    initial = dict(initial or {})
    if "destination" in operation.parameters:
        destination = QFileDialog.getExistingDirectory(parent, operation.label, initial.get("destination", ""))
        if not destination:
            return None
        return validate_parameters(operation, {"destination": destination})
    if not operation.parameters:
        return {}
    dialog = QDialog(parent)
    dialog.setWindowTitle(operation.label)
    form = QFormLayout(dialog)
    form.addRow(QLabel("Seconds, m:ss or h:mm:ss. Blank end means until EOF."))
    start = QLineEdit(initial.get("start", "0"))
    end = QLineEdit(initial.get("end", ""))
    form.addRow("Start", start)
    form.addRow("End", end)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    form.addRow(buttons)
    while dialog.exec() == QDialog.Accepted:
        try:
            return validate_parameters(operation, dict(start=start.text(), end=end.text()))
        except ValueError as error:
            QMessageBox.warning(dialog, "Invalid interval", str(error))
    return None

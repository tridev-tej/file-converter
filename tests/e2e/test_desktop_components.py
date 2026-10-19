"""Offscreen Qt drop-to-job path; separate from native desktop acceptance."""

import time


def test_qt_drop_job(samples, tmp_path):
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent
    from PySide6.QtWidgets import QApplication
    from file_converter.core.settings import Settings
    from file_converter.core.tools import discover_tools
    from file_converter.ui.controller import Controller
    from file_converter.ui.jobs import JobManager
    from file_converter.ui.wheel import Wheel
    app = QApplication.instance() or QApplication(["test"])
    wheel = Wheel()
    jobs = JobManager()
    controller = Controller(wheel, jobs, Settings(), discover_tools())
    controller.show()
    data = QMimeData()
    data.setUrls([QUrl.fromLocalFile(str(samples / "one.png"))])
    drop = QDropEvent(QPointF(221, 80), Qt.CopyAction | Qt.MoveAction, data, Qt.LeftButton, Qt.NoModifier)
    try:
        wheel.dropEvent(drop)
        assert drop.dropAction() == Qt.CopyAction
        assert len(jobs.jobs) == 1
        deadline = time.monotonic() + 10
        while jobs.active() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        job = next(iter(jobs.jobs.values()))
        assert job.state == "succeeded", job.message
        assert job.result.outputs[0].suffix == ".jpg"
        assert (samples / "one.png").exists()
        jobs.window.show()
        app.processEvents()
        assert jobs.window.grab().save(str(tmp_path / "job-history.png"))
    finally:
        controller.hide()
        jobs.close()
        for popup in jobs.popups:
            popup.close()
        jobs.window.close()
        wheel.close()


def test_missing_tools_and_repeat(samples):
    from dataclasses import replace
    from PySide6.QtWidgets import QApplication
    from file_converter.core.formats import file_item
    from file_converter.core.operations import CapabilityError, OperationRequest
    from file_converter.core.runner import validate_request
    from file_converter.core.settings import Settings
    from file_converter.core.tools import Tool, discover_tools
    import pytest
    tools = replace(discover_tools(), pandoc=Tool(reason="needs Pandoc"))
    request = OperationRequest("doc.to.docx", (samples / "notes.md",), {}, Settings())
    with pytest.raises(CapabilityError, match="needs Pandoc"):
        validate_request(request, tools)
    from file_converter.core.catalog import build_catalog
    from file_converter.core.wheel_layout import slices_for, hit_test
    items = (file_item(samples / "slides.pptx"),)
    missing = replace(tools, office=Tool(reason="needs LibreOffice"))
    slices = slices_for(build_catalog(), "Convert", items, missing)
    assert slices
    assert all(not part.availability.enabled for part in slices)
    assert hit_test(221, 221, 5) == -1
    assert hit_test(221, 60, 5) == 0
    assert hit_test(400, 221, 4) == 1


def test_partial_copy_and_cleanup(samples, tmp_path):
    from test_content import convert
    bad = tmp_path / "bad-folder"
    bad.mkdir()
    (bad / "link").symlink_to(samples / "notes.txt")
    good = tmp_path / "good.txt"
    good.write_text("retained bytes")
    destination = tmp_path / "destination"
    destination.mkdir()
    result = convert("action.copy", [bad, good], {"destination": str(destination)})
    assert result.state == "partial"
    assert result.exit_code == 1
    assert result.outputs[0].read_text() == "retained bytes"
    assert not list(destination.glob(".fileconverter-*"))


def test_corrupt_input_cleanup(tmp_path):
    from test_content import convert
    path = tmp_path / "not-an-image.png"
    path.write_text("broken input")
    result = convert("image.to.jpg", [path])
    assert result.state == "failed"
    assert not result.outputs
    assert not list(tmp_path.glob(".fileconverter-*"))

import json
import os
import platform
import time
from pathlib import Path

import pytest

REPORT = {"schema_version": 1, "platform": platform.system(), "architecture": platform.machine(), "source": [], "frozen": [], "manual_acceptance": [], "test_cases": []}


def pytest_configure(config):
    root = Path("build/test-state").absolute()
    root.mkdir(parents=True, exist_ok=True)
    os.environ["FC_CONFIG_DIR"] = str(root / "config")
    os.environ["FC_WORKSPACE"] = str(root / "work")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"


def pytest_sessionfinish(session, exitstatus):
    from file_converter.core.catalog import build_catalog
    from file_converter.core.tools import discover_tools
    REPORT["expected_ids"] = Path(__file__).with_name("expected_ids.txt").read_text(encoding="utf-8").splitlines()
    REPORT["observed_ids"] = [op.id for op in build_catalog()]
    REPORT["tools"] = discover_tools().as_dict()
    import importlib.metadata
    REPORT["dependencies"] = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    REPORT["manual_acceptance"] = manual_checks()
    REPORT["exit_status"] = exitstatus
    path = Path(os.environ.get("FC_E2E_REPORT", "build/e2e-report.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(REPORT, indent=2, default=json_value))


def json_value(value):
    return sorted(value) if isinstance(value, frozenset) else str(value)


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.failed):
        REPORT["test_cases"].append(dict(id=report.nodeid, status=report.outcome, duration=report.duration, error=str(report.longrepr)[-4000:] if report.failed else ""))


def manual_checks():
    checks = ["Finder drag and unchanged source", "Explorer OLE drag", "Modifier mapping", "Same-key and R repeat", "Center and Escape cancel", "Drop outside and mouse-up ordering", "Mixed-DPI screen edges", "Packaged permission denied/granted", "Tray-only login startup", "Single-instance forwarding", "Parameter cancellation", "Running job cancellation", "Clipboard", "Reveal Terminal Open", "Fresh Windows install", "Windows ZIP launch"]
    return [dict(id=check, status="manual_required", reason="No interactive desktop acceptance performed") for check in checks]


@pytest.fixture(scope="session")
def samples(tmp_path_factory):
    from fixtures import generate
    return generate(tmp_path_factory.mktemp("fixtures"))

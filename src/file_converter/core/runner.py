"""Shared synchronous execution boundary used by CLI and the serial worker."""

import os
import tempfile
from pathlib import Path

from .catalog import build_catalog
from .formats import file_item
from .operations import CancellationToken, Cancelled, CapabilityError, OperationContext, OperationResult
from .output_paths import OutputPublisher, remove_owned
from .settings import validate_settings
from .tools import discover_tools, refresh_tools


def validate_parameters(op, parameters):
    unknown = set(parameters) - set(op.parameters)
    if unknown:
        raise ValueError(f"Unknown parameters: {', '.join(sorted(unknown))}")
    result = {key: str(value) for key, value in parameters.items()}
    if "start" in op.parameters:
        from ..backends.ffmpeg import parse_time
        start = parse_time(result.get("start", "0"))
        end = result.get("end", "").strip()
        if end and parse_time(end) <= start:
            raise ValueError("The end must come after the start")
        result.setdefault("start", "0")
        result.setdefault("end", "")
    if "destination" in op.parameters:
        destination = Path(result.get("destination", "")).expanduser()
        if not result.get("destination") or not destination.is_dir():
            raise ValueError("destination must be an existing directory")
        result["destination"] = str(destination.resolve())
    return result


def validate_request(request, tools=None):
    validate_settings(request.settings)
    ops = {op.id: op for op in build_catalog()}
    if request.operation_id not in ops:
        raise ValueError(f"Unknown operation: {request.operation_id}")
    op = ops[request.operation_id]
    items = tuple(file_item(path) for path in request.inputs)
    for item in items:
        item.path.resolve(strict=True)
        if item.path.is_symlink():
            raise ValueError(f"Symbolic link input is not supported: {item.path}")
    if not op.applies_to(items):
        raise ValueError("Operation does not apply to every selected input, or every input is already in the target format")
    parameters = validate_parameters(op, request.parameters)
    available = op.availability(items, tools or discover_tools())
    if not available.enabled:
        raise CapabilityError("; ".join(available.reasons))
    return op, items, parameters


def execute(request, token=None, progress=None, tools=None):
    token = token or CancellationToken()
    tools = tools or refresh_tools()
    op, items, parameters = validate_request(request, tools)
    result = OperationResult()
    publisher = OutputPublisher(result.notes)
    root = Path(os.environ.get("FC_WORKSPACE", tempfile.gettempdir()))
    root.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="fileconverter-", dir=root))
    context = OperationContext(tools, token, progress or quiet_progress, workspace, publisher, request.settings, parameters, result)
    try:
        execute_items(op, items, context)
    except Cancelled:
        result.state = "cancelled"
        result.exit_code = 130
    finally:
        publisher.cleanup()
        try:
            remove_owned(workspace)
        except OSError as error:
            result.notes.append(f"Workspace cleanup failed: {error}")
    return finalize(result)


def quiet_progress(value, message):
    pass


def execute_items(op, items, context):
    if op.mode == "aggregate":
        run_one(op, items, context)
        return
    for index, item in enumerate(items):
        context.token.check()
        if item.format == op.target_format:
            context.result.skipped.append(str(item.path))
            continue
        context.progress(index / len(items), item.display_name)
        run_one(op, (item,), context)


def run_one(op, items, context):
    context.token.check()
    try:
        outputs = op.run(op, items, context)
        context.result.outputs.extend(outputs)
    except Cancelled:
        raise
    except Exception as error:
        context.result.errors.append(dict(inputs=[str(item.path) for item in items], error=str(error), type=type(error).__name__))


def finalize(result):
    if result.state == "cancelled":
        return result
    if result.errors:
        result.state = "partial" if result.outputs else "failed"
        result.exit_code = 1
    return result

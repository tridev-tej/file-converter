"""Headless dispatch occurs before importing desktop lifecycle components."""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path


def parser():
    result = argparse.ArgumentParser(prog="file-converter")
    result.add_argument("--tray-only", action="store_true", help=argparse.SUPPRESS)
    commands = result.add_subparsers(dest="command")
    for name in ("list", "wheel"):
        command = commands.add_parser(name)
        command.add_argument("files", nargs="+")
        if name == "list":
            command.add_argument("--json", action="store_true")
    command = commands.add_parser("run")
    command.add_argument("operation")
    command.add_argument("files", nargs="+")
    command.add_argument("--param", action="append", default=[])
    command.add_argument("--json", action="store_true")
    command = commands.add_parser("self-test")
    command.add_argument("outdir")
    commands.add_parser("diagnostics")
    return result


def list_operations(args):
    from .core.catalog import build_catalog
    from .core.formats import file_item
    from .core.tools import discover_tools
    items = tuple(file_item(path) for path in args.files)
    for item in items:
        item.path.resolve(strict=True)
    tools = discover_tools()
    rows = []
    for op in build_catalog():
        if op.applies_to(items):
            available = op.availability(items, tools)
            rows.append(dict(id=op.id, wheel=op.wheel, label=op.label, enabled=available.enabled, reasons=available.reasons, route=available.route))
    if args.json:
        print(json.dumps(rows))
        return 0
    for wheel in ("Convert", "Tools", "Actions"):
        print(wheel + ":")
        for row in rows:
            if row["wheel"] == wheel:
                status = "enabled" if row["enabled"] else "; ".join(row["reasons"])
                print(f"  {row['id']} [{status}]")
    return 0


def parameters(values):
    result = {}
    for value in values:
        key, separator, text = value.partition("=")
        if not separator or not key or key in result:
            raise ValueError("Each --param must be a unique key=value")
        result[key] = text
    return result


def progress(value, message):
    percent = "" if value is None else f" {value:.0%}"
    print(message + percent, file=sys.stderr)


def run_operation(args):
    from .core.operations import OperationRequest
    from .core.runner import execute, finalize, validate_request
    from .core.settings import load_settings, save_settings
    from .platform.shell import apply_effects
    settings = load_settings()
    params = parameters(args.param)
    request = OperationRequest(args.operation, tuple(Path(path) for path in args.files), params, settings)
    validated = validate_request(request)[2]
    result = execute(request, progress=progress)
    try:
        apply_effects(result)
    except Exception as error:
        result.errors.append(dict(error=f"Desktop effect failed: {error}"))
        finalize(result)
    if result.state == "succeeded":
        save_settings(replace(settings, last_operation=args.operation, last_parameters=validated))
    if args.json:
        print(json.dumps(result.as_dict()))
    else:
        for path in result.outputs:
            print(path)
        for error in result.errors:
            print(error["error"], file=sys.stderr)
        for note in result.notes:
            print(note, file=sys.stderr)
    return result.exit_code


def dispatch(args):
    if args.command == "list":
        return list_operations(args)
    if args.command == "run":
        return run_operation(args)
    if args.command == "self-test":
        from .ui.selftest import render_selftest
        count = render_selftest(args.outdir)
        print(f"Rendered {count} wheel scenarios to {args.outdir}")
        return 0
    if args.command == "diagnostics":
        from .core.tools import discover_tools
        import platform
        print(json.dumps(dict(architecture=platform.machine(), frozen=getattr(sys, "frozen", False), tools=discover_tools().as_dict()), default=lambda value: sorted(value) if isinstance(value, frozenset) else str(value), indent=2))
        return 0
    from .app import run_app
    return run_app(args.files if args.command == "wheel" else [], args.tray_only)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return dispatch(args)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        from .core.operations import CapabilityError
        code = 3 if isinstance(error, CapabilityError) else 1
        if isinstance(error, (ValueError, FileNotFoundError)):
            code = 2
        if getattr(args, "json", False):
            print(json.dumps(dict(state="failed", errors=[dict(error=str(error))], outputs=[], exit_code=code)))
        else:
            print(str(error), file=sys.stderr)
        return code

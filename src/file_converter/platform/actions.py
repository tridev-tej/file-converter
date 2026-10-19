"""Collision-safe file actions; desktop effects are returned to the main thread."""

import hashlib
import os
import shutil

from ..core.output_paths import no_replace


def validate_destination(source, destination):
    source = source.resolve(strict=True)
    destination = destination.resolve(strict=True)
    if source.is_dir() and (destination == source or destination.is_relative_to(source)):
        raise ValueError("Destination cannot be inside a selected directory")


def digest(path, token):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            token.check()
            result.update(block)
    return result.digest()


def copy_file(source, destination, token):
    from ..backends.archive import copy_chunks
    with source.open("rb") as origin, destination.open("xb") as target:
        copy_chunks(origin, target, token)
    shutil.copystat(source, destination)
    if digest(source, token) != digest(destination, token):
        raise RuntimeError(f"Copy verification failed: {source}")


def copy_tree(source, destination, token):
    from ..backends.archive import validate_tree
    validate_tree(source)
    for path in sorted(source.rglob("*")):
        token.check()
        target = destination / path.relative_to(source)
        if path.is_dir():
            target.mkdir(exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            copy_file(path, target, token)
    shutil.copystat(source, destination)


def transfer_item(item, destination, move, context):
    validate_destination(item.path, destination)
    if move and item.path.stat().st_dev == destination.stat().st_dev:
        from ..core.output_paths import candidate
        return move_same_volume(item, destination, context)
    stage = context.publisher.stage(destination, item.format, directory=item.is_directory)
    if item.is_directory:
        copy_tree(item.path, stage, context.token)
    else:
        copy_file(item.path, stage, context.token)
    base, extension = destination_parts(item)
    output = context.publisher.publish(stage, destination, base, extension, context.token)
    context.result.outputs.append(output)
    if move:
        if item.is_directory:
            shutil.rmtree(item.path)
        else:
            item.path.unlink()
    return output


def move_same_volume(item, destination, context):
    import errno
    from ..core.output_paths import candidate
    base, extension = destination_parts(item)
    for number in range(1, 100001):
        context.token.check()
        output = candidate(destination, base, extension, number)
        try:
            no_replace(item.path, output)
            context.result.outputs.append(output)
            return output
        except OSError as error:
            if error.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                raise
    raise RuntimeError("Could not allocate a unique move destination")


def destination_parts(item):
    if item.is_directory:
        return item.path.name, ""
    for extension in ("tar.gz", "tar.bz2", "tar.xz"):
        if item.path.name.lower().endswith("." + extension):
            return item.path.name[:-len(extension)-1], item.path.name[-len(extension):]
    return item.path.stem, item.path.suffix[1:]


def transfer(op, items, context):
    from pathlib import Path
    from ..core.operations import Cancelled
    destination = Path(context.parameters["destination"])
    for item in items:
        context.token.check()
        try:
            transfer_item(item, destination, op.id == "action.move", context)
        except Cancelled:
            raise
        except Exception as error:
            context.result.errors.append(dict(inputs=[str(item.path)], error=str(error), type=type(error).__name__))
    return []


def run(op, items, context):
    if op.id in {"action.copy", "action.move"}:
        return transfer(op, items, context)
    if op.id == "action.path":
        context.result.clipboard_text = "\n".join(str(item.path) for item in items)
    elif op.id == "action.terminal":
        item = items[0]
        directory = item.path if item.is_directory else item.path.parent
        context.result.effects.append(("terminal", str(directory)))
    elif op.id == "action.reveal":
        context.result.effects.extend(("reveal", str(item.path)) for item in items)
    else:
        raise ValueError(f"Unsupported file action: {op.id}")
    return []

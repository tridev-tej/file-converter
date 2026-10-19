"""Owned staging and atomic, no-replace output publication."""

import ctypes
import errno
import os
import shutil
import sys
import uuid
from pathlib import Path


def candidate(parent, base, ext, number):
    suffix = "" if number == 1 else f" ({number})"
    ending = "." + ext if ext else ""
    return Path(parent) / f"{base}{suffix}{ending}"


def no_replace(source, destination):
    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        result = libc.renamex_np(os.fsencode(source), os.fsencode(destination), 4)
        if result:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(destination))
        return
    if sys.platform == "win32":
        os.rename(source, destination)
        return
    raise RuntimeError("Output publication supports macOS and Windows only")


def publish(source, parent, base, ext, token):
    parent = Path(parent).resolve(strict=True)
    if not parent.is_dir():
        raise ValueError("Output parent is not a directory")
    for number in range(1, 100001):
        token.check()
        destination = candidate(parent, base, ext, number)
        try:
            no_replace(source, destination)
            return destination
        except OSError as error:
            if error.errno not in (errno.EEXIST, errno.ENOTEMPTY):
                raise
    raise RuntimeError("No unique output name available")


def remove_owned(path):
    path = Path(path)
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


class OutputPublisher:
    def __init__(self, notes):
        self.notes = notes
        self.owned = set()

    def stage(self, parent, ext="", directory=False):
        parent = Path(parent).resolve(strict=True)
        ending = "." + ext if ext else ""
        stage = parent / f".fileconverter-{uuid.uuid4().hex}{ending}"
        self.owned.add(stage)
        if directory:
            stage.mkdir()
        return stage

    def publish(self, stage, parent, base, ext, token):
        if stage not in self.owned:
            raise ValueError("Attempted publication of an unowned temporary path")
        if not stage.exists():
            raise RuntimeError("Converter did not create its expected output")
        output = publish(stage, parent, base, ext, token)
        self.owned.remove(stage)
        return output

    def produce(self, parent, base, ext, writer, token):
        stage = self.stage(parent, ext)
        token.check()
        writer(stage)
        token.check()
        return self.publish(stage, parent, base, ext, token)

    def cleanup(self):
        for path in tuple(self.owned):
            try:
                remove_owned(path)
                self.owned.remove(path)
            except OSError as error:
                self.notes.append(f"Cleanup failed for {path}: {error}")

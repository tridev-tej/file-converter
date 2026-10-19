"""Bounded process capture and owned process-tree cancellation."""

import os
import queue
import signal
import subprocess
import threading
import time
from dataclasses import dataclass

from .operations import CancellationToken


@dataclass(frozen=True)
class ProcessResult:
    args: tuple[str, ...]
    returncode: int
    stderr: str
    stdout: str


class ProcessFailure(RuntimeError):
    def __init__(self, result):
        self.result = result
        super().__init__(f"{result.args[0]} exited {result.returncode}: {result.stderr[-3000:]}")


def stop_tree(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        import psutil
        children = psutil.Process(process.pid).children(recursive=True)
        for child in children:
            child.terminate()
        process.terminate()
        _, alive = psutil.wait_procs(children, timeout=1)
        for child in alive:
            child.kill()
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def read_stream(stream, events, label):
    try:
        while block := stream.read1(1024):
            events.put((label, block))
    finally:
        stream.close()


def launch(args, cwd):
    options = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, shell=False, cwd=cwd)
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        options["start_new_session"] = True
    return subprocess.Popen([str(arg) for arg in args], **options)


def drain(events, buffers, callback):
    while True:
        try:
            label, block = events.get_nowait()
        except queue.Empty:
            return
        text = block.decode("utf-8", errors="replace")
        buffers[label] = (buffers[label] + text)[-262144:]
        if label == "stderr" and callback:
            callback(text)


def run_process(args, token=None, timeout=600, cwd=None, stderr_callback=None, check=True):
    token = token or CancellationToken()
    token.check()
    process = launch(args, cwd)
    events = queue.Queue()
    readers = [threading.Thread(target=read_stream, args=(getattr(process, label), events, label), daemon=True) for label in ("stdout", "stderr")]
    for reader in readers:
        reader.start()
    buffers = dict(stdout="", stderr="")
    try:
        monitor(process, events, buffers, token, timeout, stderr_callback)
    finally:
        stop_tree(process)
        for reader in readers:
            reader.join(timeout=2)
        drain(events, buffers, stderr_callback)
    result = ProcessResult(tuple(map(str, args)), process.returncode, buffers["stderr"], buffers["stdout"])
    if check and result.returncode:
        raise ProcessFailure(result)
    return result


def monitor(process, events, buffers, token, timeout, callback):
    start = time.monotonic()
    while process.poll() is None:
        token.check()
        if time.monotonic() - start > timeout:
            raise TimeoutError(f"Process timed out after {timeout} seconds")
        drain(events, buffers, callback)
        time.sleep(0.04)

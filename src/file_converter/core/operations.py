"""Immutable requests, operation definitions and cooperative cancellation."""

import threading
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Callable


class Cancelled(Exception):
    pass


class CapabilityError(RuntimeError):
    pass


class CancellationToken:
    def __init__(self):
        self._event = threading.Event()

    def cancel(self):
        self._event.set()

    @property
    def cancelled(self):
        return self._event.is_set()

    def check(self):
        if self.cancelled:
            raise Cancelled("Cancelled")


@dataclass(frozen=True)
class Availability:
    enabled: bool
    reasons: tuple[str, ...] = ()
    route: str = "native"


@dataclass(frozen=True)
class Operation:
    id: str
    wheel: str
    label: str
    subtitle: str
    inputs: frozenset[str] | None
    requires: tuple[str, ...]
    run: Callable
    mode: str = "per_file"
    target_format: str | None = None
    parameters: tuple[str, ...] = ()
    minimum: int = 1

    def applies_to(self, items):
        if len(items) < self.minimum:
            return False
        if self.inputs is not None and any(item.is_directory or item.format not in self.inputs for item in items):
            return False
        if self.target_format and all(item.format == self.target_format for item in items):
            return False
        return True

    def availability(self, items, tools):
        from .tools import operation_availability
        if not self.applies_to(items):
            return Availability(False, ("Operation does not apply to this selection",))
        return operation_availability(self, items, tools)


@dataclass(frozen=True)
class OperationRequest:
    operation_id: str
    inputs: tuple[Path, ...]
    parameters: dict
    settings: object

    def __post_init__(self):
        object.__setattr__(self, "inputs", tuple(Path(path) for path in self.inputs))
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass
class OperationResult:
    outputs: list[Path] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    clipboard_text: str | None = None
    effects: list[tuple[str, str]] = field(default_factory=list)
    state: str = "succeeded"
    exit_code: int = 0

    def as_dict(self):
        return dict(outputs=list(map(str, self.outputs)), errors=self.errors, notes=self.notes, skipped=self.skipped, clipboard_text=self.clipboard_text, effects=self.effects, state=self.state, exit_code=self.exit_code)


@dataclass
class OperationContext:
    tools: object
    token: CancellationToken
    progress: Callable
    workspace: Path
    publisher: object
    settings: object
    parameters: dict
    result: OperationResult

    def produce(self, item, target, writer, suffix=""):
        base = item.basename + (f" ({suffix})" if suffix else "")
        return self.publisher.produce(item.path.parent, base, target, writer, self.token)

"""Versioned settings with explicit validation and atomic saves."""

import json
import os
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path
from types import MappingProxyType


@dataclass(frozen=True)
class Settings:
    schema_version: int = 1
    jpeg_quality: int = 90
    compress_quality: int = 70
    pdf_dpi: int = 300
    video_crf: int = 23
    compress_video_crf: int = 28
    launch_at_login: bool = False
    gestures: dict = field(default_factory=lambda: {"Shift": "Convert", "Control": "Tools", "Alt": "Actions"})
    last_operation: str | None = None
    last_parameters: dict = field(default_factory=dict)
    permission_help_shown: bool = False

    def __post_init__(self):
        if not isinstance(self.gestures, Mapping) or not isinstance(self.last_parameters, Mapping):
            raise ValueError("Gesture mappings and last parameters must be objects")
        object.__setattr__(self, "gestures", MappingProxyType(dict(self.gestures)))
        object.__setattr__(self, "last_parameters", MappingProxyType(dict(self.last_parameters)))


def config_path():
    override = os.environ.get("FC_CONFIG_DIR")
    if override:
        return Path(override) / "settings.json"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/FileConverter/settings.json"
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / "FileConverter/settings.json"
    raise RuntimeError("FileConverter supports macOS and Windows only")


def validate_settings(settings):
    if settings.schema_version != 1:
        raise ValueError("Unsupported settings schema_version")
    ranges = {"jpeg_quality": (1, 100), "compress_quality": (1, 100), "pdf_dpi": (72, 600), "video_crf": (0, 51), "compress_video_crf": (0, 51)}
    for key, (low, high) in ranges.items():
        value = getattr(settings, key)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"Invalid settings value: {key}")
    validate_gestures(settings.gestures)
    if type(settings.launch_at_login) is not bool or type(settings.permission_help_shown) is not bool:
        raise ValueError("Settings toggles must be booleans")
    if not isinstance(settings.last_parameters, Mapping):
        raise ValueError("Invalid last_parameters")
    validate_repeat_settings(settings)
    return settings


def validate_repeat_settings(settings):
    if settings.last_operation is not None and not isinstance(settings.last_operation, str):
        raise ValueError("last_operation must be an operation ID or null")
    for key, value in settings.last_parameters.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Saved parameter keys and values must be strings")


def validate_gestures(mapping):
    if not isinstance(mapping, Mapping) or set(mapping) != {"Shift", "Control", "Alt"}:
        raise ValueError("Gesture keys must be Shift, Control and Alt/Option")
    if set(mapping.values()) != {"Convert", "Tools", "Actions"}:
        raise ValueError("Each wheel must have a unique modifier assignment")


def load_settings(path=None):
    path = Path(path) if path else config_path()
    if not path.exists():
        return Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        expected = {item.name for item in fields(Settings)}
        if not isinstance(data, dict) or set(data) != expected:
            raise ValueError("Incomplete settings or unknown fields")
        return validate_settings(Settings(**data))
    except (ValueError, TypeError) as error:
        raise ValueError(f"Invalid settings file {path}: {error}") from error


def save_settings(settings, path=None):
    validate_settings(settings)
    path = Path(path) if path else config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".settings-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(settings_data(settings), stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def settings_data(settings):
    values = {item.name: getattr(settings, item.name) for item in fields(settings)}
    values["gestures"] = dict(settings.gestures)
    values["last_parameters"] = dict(settings.last_parameters)
    return values

"""Validated archive members, staged extraction and structure-preserving packing."""

import bz2
import gzip
import lzma
import os
import re
import shutil
import stat
import tarfile
import uuid
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ..core.formats import file_item


@dataclass(frozen=True)
class Member:
    name: str
    directory: bool
    source: object = None


def normalized_member(name):
    value = name.replace("\\", "/")
    path = PurePosixPath(value)
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value) or "\x00" in value:
        raise ValueError(f"Unsafe absolute archive member: {name}")
    if any(part in {"..", ""} for part in value.rstrip("/").split("/")):
        raise ValueError(f"Unsafe archive member: {name}")
    parts = [part for part in path.parts if part != "."]
    if not parts:
        raise ValueError(f"Empty archive member: {name}")
    for part in parts:
        validate_component(part)
    return "/".join(parts)


def validate_component(part):
    if part.rstrip(" .") != part or ":" in part:
        raise ValueError(f"Nonportable archive member name: {part}")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10)}
    if part.split(".")[0].upper() in reserved:
        raise ValueError(f"Reserved archive member name: {part}")


def validate_members(members):
    seen = {}
    for member in members:
        name = normalized_member(member.name)
        key = unicodedata.normalize("NFC", name).casefold()
        if key in seen:
            raise ValueError(f"Conflicting archive member: {name}")
        seen[key] = member.directory
    for key in seen:
        for parent in PurePosixPath(key).parents:
            if str(parent) in seen and not seen[str(parent)]:
                raise ValueError(f"Archive member conflicts with a file parent: {key}")


def copy_chunks(source, destination, token):
    while block := source.read(1024 * 1024):
        token.check()
        destination.write(block)


def write_member(root, member, stream, context):
    output = root / normalized_member(member.name)
    if member.directory:
        output.mkdir(parents=True, exist_ok=True)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as target:
        copy_chunks(stream, target, context.token)


def zip_members(archive):
    result = []
    for info in archive.infolist():
        mode = info.external_attr >> 16
        if info.flag_bits & 1:
            raise ValueError("Encrypted ZIP members are unsupported")
        if stat.S_ISLNK(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode) or stat.S_ISFIFO(mode):
            raise ValueError("Archive links and device entries are unsupported")
        result.append(Member(info.filename, info.is_dir(), info))
    return result


def extract_zip(path, root, context):
    with zipfile.ZipFile(path) as archive:
        members = zip_members(archive)
        validate_members(members)
        for member in members:
            context.token.check()
            with archive.open(member.source) as stream:
                write_member(root, member, stream, context)


def extract_tar(path, root, context):
    with tarfile.open(path, "r:*") as archive:
        members = []
        for info in archive.getmembers():
            if not info.isfile() and not info.isdir():
                raise ValueError("TAR links, device entries and special files are unsupported")
            if info.name.rstrip("/") in {".", ""} and info.isdir():
                continue
            members.append(Member(info.name, info.isdir(), info))
        validate_members(members)
        for member in members:
            context.token.check()
            if member.directory:
                (root / normalized_member(member.name)).mkdir(parents=True, exist_ok=True)
            else:
                with archive.extractfile(member.source) as stream:
                    write_member(root, member, stream, context)


def extract_7z(path, root, context):
    import py7zr
    with py7zr.SevenZipFile(path, "r") as archive:
        if archive.needs_password():
            raise ValueError("Encrypted 7z archives are unsupported")
        entries = archive.list()
        for entry in entries:
            if getattr(entry, "is_symlink", False) or not (entry.is_directory or entry.is_file):
                raise ValueError("7z links and special members are unsupported")
        members = [Member(entry.filename, entry.is_directory) for entry in entries]
        validate_members(members)
        context.token.check()
        archive.extractall(path=root)
        context.token.check()
    validate_tree(root)


def extract_raw(item, root, context):
    openers = {"gz": gzip.open, "bz2": bz2.open, "xz": lzma.open}
    name = item.path.name[:-(len(item.format) + 1)]
    member = Member(name, False)
    validate_members([member])
    with openers[item.format](item.path, "rb") as stream:
        write_member(root, member, stream, context)


def extract_to(item, root, context):
    routes = {"zip": extract_zip, "7z": extract_7z}
    if item.format in {"gz", "bz2", "xz"}:
        extract_raw(item, root, context)
    elif item.format in {"tar", "tar.gz", "tar.bz2", "tar.xz"}:
        extract_tar(item.path, root, context)
    elif item.format in routes:
        routes[item.format](item.path, root, context)
    else:
        raise ValueError(f"Unsupported archive input: {item.format}")


def validate_tree(root):
    for path in root.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"Links and special files are unsupported: {path}")


def input_members(items):
    members = []
    for item in items:
        if item.path.is_symlink():
            raise ValueError("Packing symbolic links is unsupported")
        members.append(Member(item.path.name, item.is_directory, item.path))
        if item.is_directory:
            validate_tree(item.path)
            for child in sorted(item.path.rglob("*")):
                members.append(Member(item.path.name + "/" + child.relative_to(item.path).as_posix(), child.is_dir(), child))
    validate_members(members)
    return members


def write_archive(members, target, output, context):
    if target == "zip":
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for member in members:
                context.token.check()
                if member.directory:
                    archive.writestr(member.name.rstrip("/") + "/", "")
                else:
                    with member.source.open("rb") as source, archive.open(member.name, "w") as destination:
                        copy_chunks(source, destination, context.token)
        return
    if target not in {"tar", "tar.gz"}:
        raise ValueError(f"Unsupported archive target: {target}")
    with tarfile.open(output, "w:gz" if target == "tar.gz" else "w", format=tarfile.PAX_FORMAT) as archive:
        for member in members:
            context.token.check()
            info = archive.gettarinfo(member.source, arcname=member.name)
            if member.directory:
                archive.addfile(info)
            else:
                with member.source.open("rb") as stream:
                    archive.addfile(info, stream)


def extracted_output(item, context):
    stage = context.publisher.stage(item.path.parent, directory=True)
    extract_to(item, stage, context)
    entries = list(stage.iterdir())
    if not entries:
        raise ValueError("Archive is empty")
    if len(entries) == 1:
        member = entries[0]
        context.publisher.owned.add(member)
        if member.is_dir():
            return [context.publisher.publish(member, item.path.parent, member.name, "", context.token)]
        named = file_item(member)
        return [context.publisher.publish(member, item.path.parent, named.basename, named.format, context.token)]
    return [context.publisher.publish(stage, item.path.parent, item.basename, "", context.token)]


def run(op, items, context):
    item = items[0]
    if op.id == "archive.extract":
        return extracted_output(item, context)
    if op.id.startswith("pack."):
        target = op.id.removeprefix("pack.")
        validate_pack_destination(items)
        members = input_members(items)
        from dataclasses import replace
        named = replace(item, basename=item.basename if len(items) == 1 else "Archive")
        return [context.produce(named, target, lambda path: write_archive(members, target, path, context))]
    root = context.workspace / ("members-" + uuid.uuid4().hex)
    root.mkdir()
    extract_to(item, root, context)
    members = input_members([file_item(path) for path in sorted(root.iterdir())])
    return [context.produce(item, op.target_format, lambda path: write_archive(members, op.target_format, path, context))]


def validate_pack_destination(items):
    destination = items[0].path.parent.resolve(strict=True)
    for item in items:
        if item.is_directory and destination.is_relative_to(item.path.resolve(strict=True)):
            raise ValueError("Archive output cannot be inside a selected directory")

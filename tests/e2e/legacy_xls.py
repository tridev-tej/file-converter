"""Generate a minimal BIFF8 workbook inside a standard CFB container."""

import struct


def record(kind, data=b""):
    return struct.pack("<HH", kind, len(data)) + data


def bof(kind):
    return record(0x0809, struct.pack("<HHHHII", 0x0600, kind, 0x0DBB, 0x07CC, 0x41, 0x06))


def directory(name, kind, child, sector, size):
    encoded = (name + "\x00").encode("utf-16-le")
    entry = bytearray(128)
    entry[:len(encoded)] = encoded
    struct.pack_into("<HBBIII", entry, 64, len(encoded), kind, 1, 0xFFFFFFFF, 0xFFFFFFFF, child)
    struct.pack_into("<IQ", entry, 116, sector, size)
    return entry


def workbook_bytes():
    strings = ["ID", "Name", "00123", "café"]
    sst = struct.pack("<II", len(strings), len(strings))
    for text in strings:
        sst += struct.pack("<HB", len(text), 1) + text.encode("utf-16-le")
    globals_start = bof(5) + record(0x0042, struct.pack("<H", 1200))
    boundsheet_size = 4 + 8 + len("Data")
    tail = record(0x00FC, sst) + record(0x000A)
    sheet_offset = len(globals_start) + boundsheet_size + len(tail)
    boundsheet = record(0x0085, struct.pack("<IBBB", sheet_offset, 0, 0, 4) + b"\x00Data")
    body = bof(0x0010) + record(0x0200, struct.pack("<IIHHH", 0, 2, 0, 2, 0))
    for row, column, index in ((0, 0, 0), (0, 1, 1), (1, 0, 2), (1, 1, 3)):
        body += record(0x00FD, struct.pack("<HHHI", row, column, 0, index))
    body += record(0x000A)
    return (globals_start + boundsheet + tail + body).ljust(4096, b"\x00")


def write_xls(path):
    header = bytearray(512)
    header[:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    struct.pack_into("<HHHHH", header, 24, 0x003E, 3, 0xFFFE, 9, 6)
    struct.pack_into("<IIIIIIIII", header, 40, 0, 1, 8, 0, 4096, 0xFFFFFFFE, 0, 0xFFFFFFFE, 0)
    struct.pack_into("<109I", header, 76, 9, *([0xFFFFFFFF] * 108))
    entries = directory("Root Entry", 5, 1, 0xFFFFFFFE, 0) + directory("Workbook", 2, 0xFFFFFFFF, 0, 4096)
    entries = entries.ljust(512, b"\x00")
    fat = list(range(1, 8)) + [0xFFFFFFFE, 0xFFFFFFFE, 0xFFFFFFFD]
    fat += [0xFFFFFFFF] * (128 - len(fat))
    path.write_bytes(header + workbook_bytes() + entries + struct.pack("<128I", *fat))

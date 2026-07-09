#!/usr/bin/env python3
"""Build a companion JAR that relaxes sfinder setup fill sub-solution checks.

The original sfinder.jar is not modified.  This script extracts
entry/setup/SetupEntryPoint.class, patches the private lambda used by
getResults so fill-only pack results are not discarded before the later full
setup build check, and writes a small override JAR.
"""

from __future__ import annotations

import argparse
import struct
import sys
import zipfile
from pathlib import Path


CLASS_NAME = "entry/setup/SetupEntryPoint.class"
TARGET_METHOD = "lambda$getResults$13"
OUTPUT_NAME = "sfinder-openfill-rule.jar"


def read_u1(data: bytes | bytearray, offset: int) -> tuple[int, int]:
    return data[offset], offset + 1


def read_u2(data: bytes | bytearray, offset: int) -> tuple[int, int]:
    return struct.unpack_from(">H", data, offset)[0], offset + 2


def read_u4(data: bytes | bytearray, offset: int) -> tuple[int, int]:
    return struct.unpack_from(">I", data, offset)[0], offset + 4


def skip_member(data: bytes | bytearray, offset: int) -> int:
    offset += 6
    attributes_count, offset = read_u2(data, offset)
    for _ in range(attributes_count):
        offset += 2
        length, offset = read_u4(data, offset)
        offset += length
    return offset


def parse_constant_pool(data: bytes | bytearray) -> tuple[list[str | None], int]:
    magic, offset = read_u4(data, 0)
    if magic != 0xCAFEBABE:
        raise ValueError("not a Java class file")

    offset += 4
    cp_count, offset = read_u2(data, offset)
    utf8: list[str | None] = [None] * cp_count
    index = 1

    while index < cp_count:
        tag, offset = read_u1(data, offset)
        if tag == 1:
            length, offset = read_u2(data, offset)
            raw = bytes(data[offset : offset + length])
            utf8[index] = raw.decode("utf-8")
            offset += length
        elif tag in (3, 4):
            offset += 4
        elif tag in (5, 6):
            offset += 8
            index += 1
        elif tag in (7, 8, 16, 19, 20):
            offset += 2
        elif tag in (9, 10, 11, 12, 17, 18):
            offset += 4
        elif tag == 15:
            offset += 3
        else:
            raise ValueError(f"unsupported constant-pool tag {tag} at #{index}")
        index += 1

    return utf8, offset


def patch_setup_entrypoint(class_bytes: bytes) -> bytes:
    data = bytearray(class_bytes)
    utf8, offset = parse_constant_pool(data)

    offset += 6
    interfaces_count, offset = read_u2(data, offset)
    offset += interfaces_count * 2

    fields_count, offset = read_u2(data, offset)
    for _ in range(fields_count):
        offset = skip_member(data, offset)

    methods_count, offset = read_u2(data, offset)
    patched = False

    for _ in range(methods_count):
        offset += 2
        name_index, offset = read_u2(data, offset)
        offset += 2
        attributes_count, offset = read_u2(data, offset)
        method_name = utf8[name_index]

        for _ in range(attributes_count):
            attr_name_index, offset = read_u2(data, offset)
            attr_length, offset = read_u4(data, offset)
            attr_name = utf8[attr_name_index]

            if method_name == TARGET_METHOD and attr_name == "Code":
                attr_header_offset = offset - 6
                attr_end = offset + attr_length
                max_locals = struct.unpack_from(">H", data, offset + 2)[0]
                new_code = b"\x04\xAC"  # iconst_1; ireturn
                new_payload = (
                    struct.pack(">H", 1)
                    + struct.pack(">H", max_locals)
                    + struct.pack(">I", len(new_code))
                    + new_code
                    + struct.pack(">H", 0)
                    + struct.pack(">H", 0)
                )
                new_attribute = (
                    struct.pack(">H", attr_name_index)
                    + struct.pack(">I", len(new_payload))
                    + new_payload
                )
                return bytes(data[:attr_header_offset] + new_attribute + data[attr_end:])

            offset += attr_length

    if not patched:
        raise ValueError(f"could not find {TARGET_METHOD} Code attribute")
    return bytes(data)


def build(original_jar: Path, output_jar: Path) -> None:
    with zipfile.ZipFile(original_jar, "r") as source:
        class_bytes = source.read(CLASS_NAME)

    patched = patch_setup_entrypoint(class_bytes)

    with zipfile.ZipFile(output_jar, "w", compression=zipfile.ZIP_DEFLATED) as target:
        target.writestr(CLASS_NAME, patched)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sfinder",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "sfinder.jar",
        help="path to the original sfinder.jar",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / OUTPUT_NAME,
        help="path to write the companion rule JAR",
    )
    args = parser.parse_args()

    if not args.sfinder.exists():
        print(f"sfinder.jar not found: {args.sfinder}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    build(args.sfinder, args.output)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

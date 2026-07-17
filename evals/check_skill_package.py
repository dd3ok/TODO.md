#!/usr/bin/env python3
from __future__ import annotations

import argparse
import stat
import sys
import tempfile
import zipfile
import zlib
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "watchlist-md"
PACKAGE_ROOT = "watchlist-md"
PACKAGE_MANIFEST = ROOT / "evals" / "runtime_package_files.txt"
MAX_ARCHIVE_FILE_SIZE = 2 * 1024 * 1024
MAX_ARCHIVE_TOTAL_SIZE = 8 * 1024 * 1024
MAX_ARCHIVE_COMPRESSED_FILE_SIZE = 3 * 1024 * 1024
MAX_ARCHIVE_COMPRESSED_TOTAL_SIZE = 12 * 1024 * 1024
MAX_ARCHIVE_SIZE = 16 * 1024 * 1024
MAX_CENTRAL_DIRECTORY_SIZE = 64 * 1024
MAX_ARCHIVE_PARSER_ENTRY_COUNT = 64
MAX_LOG_FIELD_LENGTH = 240
LOCAL_FILE_HEADER_SIZE = 30
LOCAL_FILE_HEADER_SIGNATURE = b"PK\x03\x04"
CENTRAL_DIRECTORY_HEADER_SIZE = 46
CENTRAL_DIRECTORY_HEADER_SIGNATURE = b"PK\x01\x02"
END_OF_CENTRAL_DIRECTORY_SIZE = 22
END_OF_CENTRAL_DIRECTORY_SIGNATURE = b"PK\x05\x06"
ALLOWED_COMPRESSION_TYPES = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
ALLOWED_EXTRACT_VERSIONS = {10, 20}
ALLOWED_EXTRA_FIELD_IDS = {0x5455}
ARCHIVE_READ_ERRORS = (
    OSError,
    EOFError,
    UnicodeError,
    RuntimeError,
    NotImplementedError,
    ValueError,
    zlib.error,
    zipfile.BadZipFile,
    zipfile.LargeZipFile,
)

MANIFEST_ENTRIES = [
    line.strip()
    for line in PACKAGE_MANIFEST.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
REQUIRED_FILES = frozenset(MANIFEST_ENTRIES)
ALLOWED_DIRECTORIES = frozenset(
    "/".join(parts[:index]) + "/"
    for name in REQUIRED_FILES
    for parts in [name.split("/")[:-1]]
    for index in range(1, len(parts) + 1)
)
MAX_ARCHIVE_ENTRY_COUNT = len(REQUIRED_FILES) + len(ALLOWED_DIRECTORIES)
FORBIDDEN_PARTS = {"__pycache__", ".pytest_cache", "scripts"}
FORBIDDEN_SUFFIXES = {".py", ".pyw", ".pyc", ".pyo"}
REPOSITORY_ONLY_PARTS = {
    "evals",
    ".github",
    ".git",
    ".watchlist",
    "examples",
    "tools",
    "docs",
}


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def safe_log_text(value: object) -> str:
    escaped = "".join(
        character if " " <= character <= "~" else ascii(character)[1:-1]
        for character in str(value)
    )
    if len(escaped) <= MAX_LOG_FIELD_LENGTH:
        return escaped
    return escaped[: MAX_LOG_FIELD_LENGTH - 3] + "..."


def safe_log_join(values: list[str]) -> str:
    return ", ".join(safe_log_text(value) for value in values)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or validate the exact standalone watchlist-md skill archive."
    )
    parser.add_argument(
        "--archive",
        type=Path,
        help="Validate an existing release archive instead of building a temporary one.",
    )
    return parser.parse_args(argv[1:])


def archive_name(path: Path) -> str:
    return f"{PACKAGE_ROOT}/{path.relative_to(SKILL_DIR).as_posix()}"


def validate_manifest() -> list[str]:
    errors: list[str] = []
    duplicates = sorted(
        name for name, count in Counter(MANIFEST_ENTRIES).items() if count > 1
    )
    if duplicates:
        errors.append("duplicate package manifest entry(s): " + safe_log_join(duplicates))
    if not REQUIRED_FILES:
        errors.append("package manifest must contain at least one file")
    invalid = sorted(
        name
        for name in REQUIRED_FILES
        if not name.startswith(f"{PACKAGE_ROOT}/")
        or name.endswith("/")
        or unsafe_archive_path(name, False)
    )
    if invalid:
        errors.append("invalid package manifest entry(s): " + safe_log_join(invalid))
    return errors


def source_path_is_link_or_reparse(source_stat: object) -> bool:
    mode = getattr(source_stat, "st_mode", 0)
    file_attributes = getattr(source_stat, "st_file_attributes", 0)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(mode) or bool(file_attributes & reparse_attribute)


def build_package(zip_path: Path) -> list[str]:
    try:
        root_stat = SKILL_DIR.lstat()
    except OSError as exc:
        return [f"could not inspect skill source directory: {safe_log_text(exc)}"]
    if source_path_is_link_or_reparse(root_stat):
        return [
            "skill source directory must not be a link or reparse point: "
            + safe_log_text(SKILL_DIR)
        ]
    if not stat.S_ISDIR(root_stat.st_mode):
        return [f"skill source path must be a directory: {safe_log_text(SKILL_DIR)}"]

    source_files: list[tuple[Path, int]] = []
    directories = [SKILL_DIR]
    errors: list[str] = []
    while directories:
        directory = directories.pop()
        try:
            children = sorted(directory.iterdir(), reverse=True)
        except OSError as exc:
            errors.append(
                "could not enumerate skill source directory "
                f"{safe_log_text(directory)}: {safe_log_text(exc)}"
            )
            continue
        for path in children:
            try:
                source_stat = path.lstat()
            except OSError as exc:
                errors.append(
                    "could not inspect skill source path "
                    f"{safe_log_text(path)}: {safe_log_text(exc)}"
                )
                continue
            if source_path_is_link_or_reparse(source_stat):
                errors.append(
                    "skill source path must not be a link or reparse point: "
                    + safe_log_text(path)
                )
            elif stat.S_ISDIR(source_stat.st_mode):
                directories.append(path)
            elif stat.S_ISREG(source_stat.st_mode):
                source_files.append((path, source_stat.st_size))
            else:
                errors.append(
                    "skill source path must be a regular file or directory: "
                    + safe_log_text(path)
                )

    source_names = {archive_name(path) for path, _ in source_files}
    missing = sorted(REQUIRED_FILES - source_names)
    unexpected = sorted(source_names - REQUIRED_FILES)
    oversized = sorted(
        archive_name(path)
        for path, size in source_files
        if size > MAX_ARCHIVE_FILE_SIZE
    )
    total_size = sum(size for _, size in source_files)
    if missing:
        errors.append("missing required skill source file(s): " + safe_log_join(missing))
    if unexpected:
        errors.append("unexpected skill source file(s): " + safe_log_join(unexpected))
    if oversized:
        errors.append(
            f"skill source file exceeds {MAX_ARCHIVE_FILE_SIZE} bytes: "
            + safe_log_join(oversized)
        )
    if total_size > MAX_ARCHIVE_TOTAL_SIZE:
        errors.append(
            f"skill source size exceeds {MAX_ARCHIVE_TOTAL_SIZE} bytes"
        )
    if errors:
        return errors
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, _ in sorted(source_files):
            archive.write(path, archive_name(path))
    return []


def unsafe_archive_path(name: str, is_directory: bool) -> bool:
    if (
        not name
        or "\\" in name
        or ":" in name
        or "\x00" in name
        or name.startswith("/")
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
    ):
        return True
    parts = name.split("/")
    if is_directory:
        if parts[-1] != "":
            return True
        parts = parts[:-1]
    return not parts or any(part in {"", ".", ".."} for part in parts)


def has_unsafe_entry_type(info: zipfile.ZipInfo) -> bool:
    dos_attributes = info.external_attr & 0xFF
    is_volume_label = bool(dos_attributes & 0x08)
    dos_claims_directory = bool(dos_attributes & 0x10)
    if is_volume_label or dos_claims_directory != info.is_dir():
        return True
    if info.create_system not in {0, 3}:
        return True
    file_type = stat.S_IFMT((info.external_attr >> 16) & 0xFFFF)
    expected_type = stat.S_IFDIR if info.is_dir() else stat.S_IFREG
    return file_type not in {0, expected_type}


def has_unsafe_entry_permissions(info: zipfile.ZipInfo) -> bool:
    dos_attributes = info.external_attr & 0xFF
    if dos_attributes & ~(0x01 | 0x10 | 0x20):
        return True

    unix_mode = (info.external_attr >> 16) & 0xFFFF
    if unix_mode == 0:
        return info.create_system != 0
    permissions = unix_mode & 0o7777
    if permissions & 0o7000:
        return True
    required_owner_permissions = 0o500 if info.is_dir() else 0o400
    return permissions & required_owner_permissions != required_owner_permissions


def validate_extra_fields(data: bytes, location: str, name: str) -> list[str]:
    errors: list[str] = []
    display_name = safe_log_text(name)
    seen: set[int] = set()
    offset = 0
    while offset < len(data):
        if len(data) - offset < 4:
            errors.append(f"malformed {location} extra field: {display_name}")
            break
        field_id = int.from_bytes(data[offset : offset + 2], "little")
        field_size = int.from_bytes(data[offset + 2 : offset + 4], "little")
        end = offset + 4 + field_size
        if end > len(data):
            errors.append(f"malformed {location} extra field: {display_name}")
            break
        if field_id not in ALLOWED_EXTRA_FIELD_IDS:
            errors.append(
                f"unsupported {location} extra field 0x{field_id:04x}: "
                f"{display_name}"
            )
        field_data = data[offset + 4 : end]
        if field_id == 0x5455 and (
            field_size != 5 or not field_data or field_data[0] != 0x01
        ):
            errors.append(
                f"invalid {location} extended timestamp field: {display_name}"
            )
        if field_id in seen:
            errors.append(
                f"duplicate {location} extra field 0x{field_id:04x}: {display_name}"
            )
        seen.add(field_id)
        offset = end
    return errors


def validate_archive_preflight(zip_path: Path) -> list[str]:
    """Bound parser work and require a canonical single-disk EOCD before ZipFile."""
    try:
        archive_size = zip_path.stat().st_size
        if archive_size > MAX_ARCHIVE_SIZE:
            return [f"package archive exceeds {MAX_ARCHIVE_SIZE} bytes"]
        if archive_size < END_OF_CENTRAL_DIRECTORY_SIZE:
            return ["invalid or unreadable zip archive: missing canonical end record"]

        with zip_path.open("rb") as stream:
            stream.seek(-END_OF_CENTRAL_DIRECTORY_SIZE, 2)
            eocd = stream.read(END_OF_CENTRAL_DIRECTORY_SIZE)
    except OSError as exc:
        return [f"invalid or unreadable zip archive: {safe_log_text(exc)}"]

    if eocd[:4] != END_OF_CENTRAL_DIRECTORY_SIGNATURE:
        return [
            "invalid or unreadable zip archive: archive comment, trailing data, "
            "or non-canonical end record"
        ]

    disk_number = int.from_bytes(eocd[4:6], "little")
    central_disk = int.from_bytes(eocd[6:8], "little")
    disk_entries = int.from_bytes(eocd[8:10], "little")
    total_entries = int.from_bytes(eocd[10:12], "little")
    central_size = int.from_bytes(eocd[12:16], "little")
    central_offset = int.from_bytes(eocd[16:20], "little")
    comment_size = int.from_bytes(eocd[20:22], "little")
    errors: list[str] = []
    if disk_number != 0 or central_disk != 0:
        errors.append("multi-disk package archive is not allowed")
    if disk_entries != total_entries:
        errors.append("end record entry counts do not agree")
    if total_entries > MAX_ARCHIVE_PARSER_ENTRY_COUNT:
        errors.append(
            "package archive declares more than "
            f"{MAX_ARCHIVE_PARSER_ENTRY_COUNT} entries"
        )
    if central_size > MAX_CENTRAL_DIRECTORY_SIZE:
        errors.append(
            f"package central directory exceeds {MAX_CENTRAL_DIRECTORY_SIZE} bytes"
        )
    if central_offset + central_size != archive_size - END_OF_CENTRAL_DIRECTORY_SIZE:
        errors.append(
            "package has a prefix, gap, trailing data, or non-canonical central directory"
        )
    if comment_size != 0:
        errors.append("package archive comment is not allowed")

    layout_is_bounded = (
        total_entries <= MAX_ARCHIVE_PARSER_ENTRY_COUNT
        and central_size <= MAX_CENTRAL_DIRECTORY_SIZE
        and central_offset + central_size
        == archive_size - END_OF_CENTRAL_DIRECTORY_SIZE
    )
    if not layout_is_bounded:
        return errors

    try:
        with zip_path.open("rb") as stream:
            stream.seek(central_offset)
            central_directory = stream.read(central_size)
    except OSError as exc:
        return [f"invalid or unreadable zip archive: {safe_log_text(exc)}"]
    if len(central_directory) != central_size:
        return errors + ["truncated package central directory"]

    cursor = 0
    parsed_entries = 0
    while cursor < len(central_directory):
        if (
            len(central_directory) - cursor < CENTRAL_DIRECTORY_HEADER_SIZE
            or central_directory[cursor : cursor + 4]
            != CENTRAL_DIRECTORY_HEADER_SIGNATURE
        ):
            errors.append("malformed or unsupported central directory record")
            break
        filename_size = int.from_bytes(
            central_directory[cursor + 28 : cursor + 30], "little"
        )
        extra_size = int.from_bytes(
            central_directory[cursor + 30 : cursor + 32], "little"
        )
        entry_comment_size = int.from_bytes(
            central_directory[cursor + 32 : cursor + 34], "little"
        )
        disk_start = int.from_bytes(
            central_directory[cursor + 34 : cursor + 36], "little"
        )
        record_end = (
            cursor
            + CENTRAL_DIRECTORY_HEADER_SIZE
            + filename_size
            + extra_size
            + entry_comment_size
        )
        if record_end > len(central_directory):
            errors.append("truncated package central directory record")
            break
        if disk_start != 0:
            errors.append("central directory entry starts on a nonzero disk")
        parsed_entries += 1
        cursor = record_end
    if cursor == len(central_directory) and parsed_entries != total_entries:
        errors.append("end record entry count differs from central directory records")
    return errors


def validate_local_header(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo
) -> tuple[list[str], Optional[int]]:
    errors: list[str] = []
    display_name = safe_log_text(info.filename)
    if archive.fp is None:
        return [f"archive closed before local header validation: {display_name}"], None
    archive.fp.seek(info.header_offset)
    header = archive.fp.read(LOCAL_FILE_HEADER_SIZE)
    if len(header) != LOCAL_FILE_HEADER_SIZE or header[:4] != LOCAL_FILE_HEADER_SIGNATURE:
        return [f"invalid local file header: {display_name}"], None

    extract_version = int.from_bytes(header[4:6], "little")
    flags = int.from_bytes(header[6:8], "little")
    compression = int.from_bytes(header[8:10], "little")
    modification_time = int.from_bytes(header[10:12], "little")
    modification_date = int.from_bytes(header[12:14], "little")
    crc = int.from_bytes(header[14:18], "little")
    compressed_size = int.from_bytes(header[18:22], "little")
    file_size = int.from_bytes(header[22:26], "little")
    filename_size = int.from_bytes(header[26:28], "little")
    extra_size = int.from_bytes(header[28:30], "little")
    local_filename = archive.fp.read(filename_size)
    local_extra = archive.fp.read(extra_size)
    if len(local_filename) != filename_size or len(local_extra) != extra_size:
        return [f"truncated local file header: {display_name}"], None

    encoding = "utf-8" if info.flag_bits & 0x800 else "cp437"
    expected_filename = info.orig_filename.encode(encoding)
    central_extract_version = info.extract_version | (info.reserved << 8)
    year, month, day, hour, minute, second = info.date_time
    central_modification_time = (hour << 11) | (minute << 5) | (second // 2)
    central_modification_date = ((year - 1980) << 9) | (month << 5) | day
    comparisons = [
        (extract_version, central_extract_version, "extract version"),
        (flags, info.flag_bits, "flags"),
        (compression, info.compress_type, "compression method"),
        (modification_time, central_modification_time, "modification time"),
        (modification_date, central_modification_date, "modification date"),
        (local_filename, expected_filename, "filename"),
        (local_extra, info.extra, "extra fields"),
    ]
    if not flags & 0x08:
        comparisons.extend(
            [
                (crc, info.CRC, "CRC"),
                (compressed_size, info.compress_size, "compressed size"),
                (file_size, info.file_size, "file size"),
            ]
        )
    for local_value, central_value, label in comparisons:
        if local_value != central_value:
            errors.append(
                f"local header {label} differs from central entry: {display_name}"
            )
    errors.extend(validate_extra_fields(local_extra, "local", info.filename))
    return errors, archive.fp.tell()


def validate_entry_payload(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, data_offset: int
) -> list[str]:
    errors: list[str] = []
    display_name = safe_log_text(info.filename)
    if archive.fp is None:
        return [f"archive closed before payload validation: {display_name}"]
    if info.flag_bits != 0 or info.compress_type not in ALLOWED_COMPRESSION_TYPES:
        return errors
    if (
        info.file_size > MAX_ARCHIVE_FILE_SIZE
        or info.compress_size > MAX_ARCHIVE_COMPRESSED_FILE_SIZE
    ):
        return errors

    archive.fp.seek(data_offset)
    compressed = archive.fp.read(info.compress_size)
    if len(compressed) != info.compress_size:
        return [f"truncated package payload: {display_name}"]

    if info.compress_type == zipfile.ZIP_STORED:
        if info.compress_size != info.file_size:
            errors.append(f"stored package entry size mismatch: {display_name}")
        payload = compressed
    else:
        decompressor = zlib.decompressobj(-15)
        payload = decompressor.decompress(compressed, MAX_ARCHIVE_FILE_SIZE + 1)
        if len(payload) <= MAX_ARCHIVE_FILE_SIZE:
            payload += decompressor.flush(MAX_ARCHIVE_FILE_SIZE + 1 - len(payload))
        if (
            not decompressor.eof
            or decompressor.unused_data
            or decompressor.unconsumed_tail
        ):
            errors.append(f"invalid deflate stream boundaries: {display_name}")

    if len(payload) > MAX_ARCHIVE_FILE_SIZE:
        errors.append(
            f"actual package payload exceeds {MAX_ARCHIVE_FILE_SIZE} bytes: "
            f"{display_name}"
        )
        return errors
    if len(payload) != info.file_size:
        errors.append(
            f"actual package payload size differs from central entry: {display_name}"
        )
    if zlib.crc32(payload) & 0xFFFFFFFF != info.CRC:
        errors.append(f"corrupt package entry: {display_name}")
    return errors


def validate_physical_layout(
    archive: zipfile.ZipFile,
    archive_infos: list[zipfile.ZipInfo],
    data_offsets: dict[int, int],
) -> list[str]:
    errors: list[str] = []
    if archive.fp is None:
        return ["archive closed before physical layout validation"]

    expected_offset = 0
    for info in sorted(archive_infos, key=lambda item: item.header_offset):
        if info.header_offset != expected_offset:
            errors.append(
                "package has prefix, gap, overlap, or hidden local entry before: "
                + safe_log_text(info.filename)
            )
        data_offset = data_offsets.get(info.header_offset)
        if data_offset is None:
            continue
        expected_offset = data_offset + info.compress_size
    if expected_offset != archive.start_dir:
        errors.append("package has data gap or hidden local entry before central directory")

    archive.fp.seek(0, 2)
    archive_size = archive.fp.tell()
    if archive_size < END_OF_CENTRAL_DIRECTORY_SIZE:
        return errors + ["missing end of central directory"]
    eocd_offset = archive_size - END_OF_CENTRAL_DIRECTORY_SIZE
    archive.fp.seek(eocd_offset)
    eocd = archive.fp.read(END_OF_CENTRAL_DIRECTORY_SIZE)
    if eocd[:4] != END_OF_CENTRAL_DIRECTORY_SIGNATURE:
        return errors + ["archive has a comment, trailing data, or non-canonical end record"]

    disk_number = int.from_bytes(eocd[4:6], "little")
    central_disk = int.from_bytes(eocd[6:8], "little")
    disk_entries = int.from_bytes(eocd[8:10], "little")
    total_entries = int.from_bytes(eocd[10:12], "little")
    central_size = int.from_bytes(eocd[12:16], "little")
    central_offset = int.from_bytes(eocd[16:20], "little")
    comment_size = int.from_bytes(eocd[20:22], "little")
    if disk_number != 0 or central_disk != 0:
        errors.append("multi-disk package archive is not allowed")
    if disk_entries != len(archive_infos) or total_entries != len(archive_infos):
        errors.append("end record entry count differs from central directory")
    if central_offset != archive.start_dir:
        errors.append("end record central directory offset mismatch")
    if central_offset + central_size != eocd_offset:
        errors.append("central directory has hidden or unsupported records")
    if comment_size != 0:
        errors.append("package archive comment is not allowed")
    return errors


def validate_package(zip_path: Path) -> list[str]:
    errors = validate_archive_preflight(zip_path)
    if errors:
        return errors

    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive_infos = archive.infolist()
            if archive.comment:
                errors.append("package archive comment is not allowed")

            data_offsets: dict[int, int] = {}
            for info in archive_infos:
                header_errors, data_offset = validate_local_header(archive, info)
                errors.extend(header_errors)
                if data_offset is not None:
                    data_offsets[info.header_offset] = data_offset
            errors.extend(
                validate_physical_layout(archive, archive_infos, data_offsets)
            )

            encrypted = [info.filename for info in archive_infos if info.flag_bits & 0x1]
            oversized = [
                info.filename
                for info in archive_infos
                if info.file_size > MAX_ARCHIVE_FILE_SIZE
            ]
            compressed_oversized = [
                info.filename
                for info in archive_infos
                if info.compress_size > MAX_ARCHIVE_COMPRESSED_FILE_SIZE
            ]
            nonempty_directories = [
                info.filename
                for info in archive_infos
                if info.is_dir() and info.file_size != 0
            ]
            total_size = sum(info.file_size for info in archive_infos)
            total_compressed_size = sum(info.compress_size for info in archive_infos)

            for info in archive_infos:
                data_offset = data_offsets.get(info.header_offset)
                if data_offset is None:
                    continue
                try:
                    errors.extend(validate_entry_payload(archive, info, data_offset))
                except ARCHIVE_READ_ERRORS as exc:
                    errors.append(
                        "package integrity check failed: "
                        f"{safe_log_text(info.filename)}: {safe_log_text(exc)}"
                    )
    except ARCHIVE_READ_ERRORS as exc:
        return [f"invalid or unreadable zip archive: {safe_log_text(exc)}"]
    archive_names = [info.filename for info in archive_infos]
    names = set(archive_names)
    file_entries = [info.filename for info in archive_infos if not info.is_dir()]
    file_names = set(file_entries)
    directory_names = {info.filename for info in archive_infos if info.is_dir()}

    if len(archive_infos) > MAX_ARCHIVE_ENTRY_COUNT:
        errors.append(
            f"package contains more than {MAX_ARCHIVE_ENTRY_COUNT} entries"
        )

    for info in archive_infos:
        original_name = info.orig_filename
        if original_name != info.filename:
            errors.append(
                "package entry filename was normalized or truncated: "
                + safe_log_text(original_name)
            )
            if unsafe_archive_path(original_name, original_name.endswith("/")):
                errors.append(
                    f"unsafe package entry path: {safe_log_text(original_name)}"
                )
        if unsafe_archive_path(info.filename, info.is_dir()):
            errors.append(
                f"unsafe package entry path: {safe_log_text(info.filename)}"
            )
        if has_unsafe_entry_type(info):
            expected = "directory" if info.is_dir() else "regular file"
            errors.append(
                f"package entry must be a {expected}: {safe_log_text(info.filename)}"
            )
        if has_unsafe_entry_permissions(info):
            errors.append(
                "package entry has unsafe or unreadable permissions/attributes: "
                + safe_log_text(info.filename)
            )
        if info.reserved != 0 or info.extract_version not in ALLOWED_EXTRACT_VERSIONS:
            requested_version = info.extract_version | (info.reserved << 8)
            errors.append(
                "unsupported package extraction version "
                f"{requested_version}: {safe_log_text(info.filename)}"
            )
        try:
            datetime(*info.date_time)
        except ValueError:
            errors.append(
                f"invalid package DOS timestamp: {safe_log_text(info.filename)}"
            )
        if info.flag_bits & 0x1:
            errors.append(
                "encrypted package entry is not allowed: "
                + safe_log_text(info.filename)
            )
        if info.flag_bits != 0:
            errors.append(
                f"unsupported package entry flags: {safe_log_text(info.filename)}"
            )
        if info.compress_type not in ALLOWED_COMPRESSION_TYPES:
            errors.append(
                "unsupported package compression method: "
                + safe_log_text(info.filename)
            )
        if info.comment:
            errors.append(
                f"package entry comment is not allowed: {safe_log_text(info.filename)}"
            )
        if info.volume != 0:
            errors.append(
                "package entry starts on a nonzero disk: "
                + safe_log_text(info.filename)
            )
        errors.extend(validate_extra_fields(info.extra, "central", info.filename))

    if oversized:
        errors.append(
            f"package entry exceeds {MAX_ARCHIVE_FILE_SIZE} bytes: "
            + safe_log_join(sorted(oversized))
        )
    if compressed_oversized:
        errors.append(
            f"compressed package entry exceeds {MAX_ARCHIVE_COMPRESSED_FILE_SIZE} bytes: "
            + safe_log_join(sorted(compressed_oversized))
        )
    if nonempty_directories:
        errors.append(
            "package directory entry must be empty: "
            + safe_log_join(sorted(nonempty_directories))
        )
    if total_size > MAX_ARCHIVE_TOTAL_SIZE:
        errors.append(
            f"package uncompressed size exceeds {MAX_ARCHIVE_TOTAL_SIZE} bytes"
        )
    if total_compressed_size > MAX_ARCHIVE_COMPRESSED_TOTAL_SIZE:
        errors.append(
            "package compressed size exceeds "
            f"{MAX_ARCHIVE_COMPRESSED_TOTAL_SIZE} bytes"
        )

    top_level = {name.split("/", 1)[0] for name in names if name}
    if top_level != {PACKAGE_ROOT}:
        errors.append(
            f"package must contain one top-level {PACKAGE_ROOT}/ directory, got ["
            + safe_log_join(sorted(top_level))
            + "]"
        )

    missing = sorted(REQUIRED_FILES - file_names)
    if missing:
        errors.append("missing required package file(s): " + safe_log_join(missing))

    unexpected = sorted(file_names - REQUIRED_FILES)
    if unexpected:
        errors.append("unexpected package file(s): " + safe_log_join(unexpected))

    unexpected_directories = sorted(directory_names - ALLOWED_DIRECTORIES)
    if unexpected_directories:
        errors.append(
            "unexpected package directory entry(s): "
            + safe_log_join(unexpected_directories)
        )

    duplicates = sorted(
        name for name, count in Counter(file_entries).items() if count > 1
    )
    if duplicates:
        errors.append("duplicate package file(s): " + safe_log_join(duplicates))

    duplicate_entries = sorted(
        name for name, count in Counter(archive_names).items() if count > 1
    )
    if duplicate_entries:
        errors.append("duplicate package entry(s): " + safe_log_join(duplicate_entries))

    for name in sorted(file_names):
        parts = {part.lower() for part in Path(name).parts}
        path_parts = tuple(name.split("/"))
        package_relative_parts = (
            path_parts[1:] if path_parts[:1] == (PACKAGE_ROOT,) else path_parts
        )
        if parts.intersection(FORBIDDEN_PARTS):
            errors.append(
                f"package contains forbidden package path: {safe_log_text(name)}"
            )
        if Path(name).suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(
                "package contains forbidden runtime code or bytecode: "
                + safe_log_text(name)
            )
        if (
            package_relative_parts
            and package_relative_parts[0].lower() in REPOSITORY_ONLY_PARTS
        ):
            errors.append(
                f"package includes repository-only path: {safe_log_text(name)}"
            )

    return errors


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    manifest_errors = validate_manifest()
    if manifest_errors:
        return fail(
            "Skill package manifest check failed:\n"
            + "\n".join(f"- {error}" for error in manifest_errors)
        )
    if args.archive is None and not SKILL_DIR.is_dir():
        return fail(f"Missing skill directory: {safe_log_text(SKILL_DIR)}")

    if args.archive is not None:
        zip_path = args.archive
        if not zip_path.is_file():
            return fail(f"Skill archive not found: {safe_log_text(zip_path)}")
        errors = validate_package(zip_path)
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "watchlist-md-skill.zip"
            errors = build_package(zip_path)
            if not errors:
                errors = validate_package(zip_path)

    if errors:
        return fail("Skill package check failed:\n" + "\n".join(f"- {error}" for error in errors))

    source = f" archive={safe_log_text(zip_path)}" if args.archive is not None else ""
    print(
        f"Skill package check passed: {len(REQUIRED_FILES)} required file(s){source}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

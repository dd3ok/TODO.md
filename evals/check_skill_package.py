#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "watchlist-md"
PACKAGE_ROOT = "watchlist-md"
PACKAGE_MANIFEST = ROOT / "evals" / "runtime_package_files.txt"

MANIFEST_ENTRIES = [
    line.strip()
    for line in PACKAGE_MANIFEST.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
REQUIRED_FILES = frozenset(MANIFEST_ENTRIES)
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
        errors.append("duplicate package manifest entry(s): " + ", ".join(duplicates))
    if not REQUIRED_FILES:
        errors.append("package manifest must contain at least one file")
    invalid = sorted(
        name
        for name in REQUIRED_FILES
        if not name.startswith(f"{PACKAGE_ROOT}/") or "\\" in name or name.endswith("/")
    )
    if invalid:
        errors.append("invalid package manifest entry(s): " + ", ".join(invalid))
    return errors


def build_package(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SKILL_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, archive_name(path))


def validate_package(zip_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive_names = archive.namelist()
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        return [f"invalid or unreadable zip archive: {exc}"]
    names = set(archive_names)
    file_entries = [name for name in archive_names if not name.endswith("/")]
    file_names = set(file_entries)

    top_level = {name.split("/", 1)[0] for name in names if name}
    if top_level != {PACKAGE_ROOT}:
        errors.append(
            f"package must contain one top-level {PACKAGE_ROOT}/ directory, got {sorted(top_level)}"
        )

    missing = sorted(REQUIRED_FILES - file_names)
    if missing:
        errors.append("missing required package file(s): " + ", ".join(missing))

    unexpected = sorted(file_names - REQUIRED_FILES)
    if unexpected:
        errors.append("unexpected package file(s): " + ", ".join(unexpected))

    duplicates = sorted(
        name for name, count in Counter(file_entries).items() if count > 1
    )
    if duplicates:
        errors.append("duplicate package file(s): " + ", ".join(duplicates))

    for name in sorted(file_names):
        parts = {part.lower() for part in Path(name).parts}
        path_parts = Path(name).parts
        package_relative_parts = path_parts[1:] if path_parts[:1] == (PACKAGE_ROOT,) else path_parts
        if parts.intersection(FORBIDDEN_PARTS):
            errors.append(f"package contains forbidden package path: {name}")
        if Path(name).suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"package contains forbidden runtime code or bytecode: {name}")
        if package_relative_parts and package_relative_parts[0].lower() in REPOSITORY_ONLY_PARTS:
            errors.append(f"package includes repository-only path: {name}")

    return errors


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    manifest_errors = validate_manifest()
    if manifest_errors:
        return fail(
            "Skill package manifest check failed:\n"
            + "\n".join(f"- {error}" for error in manifest_errors)
        )
    if not SKILL_DIR.is_dir():
        return fail(f"Missing skill directory: {SKILL_DIR}")

    if args.archive is not None:
        zip_path = args.archive
        if not zip_path.is_file():
            return fail(f"Skill archive not found: {zip_path}")
        errors = validate_package(zip_path)
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "watchlist-md-skill.zip"
            build_package(zip_path)
            errors = validate_package(zip_path)

    if errors:
        return fail("Skill package check failed:\n" + "\n".join(f"- {error}" for error in errors))

    source = f" archive={zip_path}" if args.archive is not None else ""
    print(
        f"Skill package check passed: {len(REQUIRED_FILES)} required file(s){source}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

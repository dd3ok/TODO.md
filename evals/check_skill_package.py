#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "watchlist-md"
PACKAGE_ROOT = "watchlist-md"

REQUIRED_FILES = {
    "watchlist-md/SKILL.md",
    "watchlist-md/LICENSE.txt",
    "watchlist-md/agents/openai.yaml",
    "watchlist-md/assets/WATCHLIST.template.md",
    "watchlist-md/references/format.md",
    "watchlist-md/references/lifecycle.md",
    "watchlist-md/references/safety.md",
}
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


def archive_name(path: Path) -> str:
    return f"{PACKAGE_ROOT}/{path.relative_to(SKILL_DIR).as_posix()}"


def build_package(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SKILL_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, archive_name(path))


def validate_package(zip_path: Path) -> list[str]:
    errors: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        archive_names = archive.namelist()
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


def main() -> int:
    if not SKILL_DIR.is_dir():
        return fail(f"Missing skill directory: {SKILL_DIR}")

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / "watchlist-md-skill.zip"
        build_package(zip_path)
        errors = validate_package(zip_path)

    if errors:
        return fail("Skill package check failed:\n" + "\n".join(f"- {error}" for error in errors))

    print(f"Skill package check passed: {len(REQUIRED_FILES)} required file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

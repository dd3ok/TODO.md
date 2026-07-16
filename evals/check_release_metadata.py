#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path


SEMVER_PATTERN = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
SEMVER_RE = re.compile(SEMVER_PATTERN)
RELEASE_HEADING_RE = re.compile(
    rf"^## \[(?P<version>{SEMVER_PATTERN})\] - (?P<date>\d{{4}}-\d{{2}}-\d{{2}})$",
    re.M,
)
UNRELEASED_HEADING_RE = re.compile(r"^## \[Unreleased\]$", re.M)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate VERSION and CHANGELOG.md release metadata."
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Also require the Unreleased section to be empty before publishing.",
    )
    return parser.parse_args(argv[1:])


def version_tuple(value: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def metadata_errors(root: Path, release: bool = False) -> list[str]:
    version_path = root / "VERSION"
    changelog_path = root / "CHANGELOG.md"
    errors: list[str] = []

    if not version_path.is_file():
        errors.append(f"Missing VERSION: {version_path}")
    if not changelog_path.is_file():
        errors.append(f"Missing CHANGELOG.md: {changelog_path}")
    if errors:
        return errors

    version = version_path.read_text(encoding="utf-8-sig").strip()
    if not SEMVER_RE.fullmatch(version):
        errors.append(f"VERSION must be strict semver MAJOR.MINOR.PATCH: {version}")
        return errors

    changelog = changelog_path.read_text(encoding="utf-8-sig")
    unreleased = list(UNRELEASED_HEADING_RE.finditer(changelog))
    if len(unreleased) != 1:
        errors.append(
            "CHANGELOG.md must contain exactly one top-level ## [Unreleased] heading"
        )

    releases = list(RELEASE_HEADING_RE.finditer(changelog))
    if not releases:
        errors.append("CHANGELOG.md must contain at least one strict release heading")
        return errors

    release_versions = [match.group("version") for match in releases]
    duplicates = sorted(
        value for value, count in Counter(release_versions).items() if count > 1
    )
    if duplicates:
        errors.append("CHANGELOG.md has duplicate release version(s): " + ", ".join(duplicates))

    for match in releases:
        value = match.group("date")
        try:
            date.fromisoformat(value)
        except ValueError:
            errors.append(
                f"CHANGELOG.md has invalid release date for {match.group('version')}: {value}"
            )

    if release_versions[0] != version:
        errors.append(
            "VERSION must match the first release heading in CHANGELOG.md: "
            f"VERSION={version}, first={release_versions[0]}"
        )

    ordered = [version_tuple(value) for value in release_versions]
    if any(current <= following for current, following in zip(ordered, ordered[1:])):
        errors.append("CHANGELOG.md release headings must be unique and newest-first")

    if unreleased:
        first_unreleased = unreleased[0]
        if first_unreleased.start() > releases[0].start():
            errors.append("## [Unreleased] must appear before the first release heading")
        if release:
            body = changelog[first_unreleased.end() : releases[0].start()]
            if body.strip():
                errors.append(
                    "## [Unreleased] must be empty when --release is requested"
                )

    return errors


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    errors = metadata_errors(args.root, release=args.release)
    if errors:
        print("Release metadata check failed:\n" + "\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1

    version = (args.root / "VERSION").read_text(encoding="utf-8-sig").strip()
    mode = "Release-ready metadata" if args.release else "Release metadata"
    print(f"{mode} check passed: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

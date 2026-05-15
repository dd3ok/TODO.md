#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1]
    version_path = root / "VERSION"
    changelog_path = root / "CHANGELOG.md"

    if not version_path.is_file():
        return fail(f"Missing VERSION: {version_path}")
    if not changelog_path.is_file():
        return fail(f"Missing CHANGELOG.md: {changelog_path}")

    version = version_path.read_text(encoding="utf-8").strip()
    if not SEMVER_RE.fullmatch(version):
        return fail(f"VERSION must be semver MAJOR.MINOR.PATCH: {version}")

    changelog = changelog_path.read_text(encoding="utf-8")
    heading_re = re.compile(rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", re.M)
    if not heading_re.search(changelog):
        return fail(f"CHANGELOG.md is missing a heading for VERSION {version}")

    print(f"Release metadata check passed: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

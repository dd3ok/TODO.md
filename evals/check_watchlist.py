#!/usr/bin/env python3
from __future__ import annotations

import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_VALIDATOR = ROOT / "tools" / "validate_watchlist.py"


def main() -> int:
    if not REPO_VALIDATOR.is_file():
        print(f"Repository validator not found: {REPO_VALIDATOR}", file=sys.stderr)
        return 1
    try:
        runpy.run_path(str(REPO_VALIDATOR), run_name="__main__")
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code
        print(exc.code, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

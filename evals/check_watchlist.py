#!/usr/bin/env python3
from __future__ import annotations

import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLED_VALIDATOR = (
    ROOT / ".agents" / "skills" / "watchlist-md" / "scripts" / "validate_watchlist.py"
)


def main() -> int:
    if not BUNDLED_VALIDATOR.is_file():
        print(f"Bundled validator not found: {BUNDLED_VALIDATOR}", file=sys.stderr)
        return 1
    runpy.run_path(str(BUNDLED_VALIDATOR), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


CHECKS = {
    "README.md": [
        "Deletion And Retention Policy",
        "not an autonomous scheduler",
        "Do not archive automatically",
        "Archive Policy",
        "Concurrent Edits",
        "Do not store passwords, tokens",
        "untrusted",
    ],
    "README.ko.md": [
        "Deletion And Retention Policy",
        "자율 스케줄러",
        "자동 archive는 하지 않습니다",
        "Archive Policy",
        "Concurrent Edits",
        "비밀번호, 토큰",
        "신뢰할 수 없는",
    ],
    ".agents/skills/watchlist-md/SKILL.md": [
        "Lifecycle words such as",
        "clearly refer",
        "autonomous scheduler",
        "Do not store secrets",
        "untrusted data",
        "references/lifecycle.md",
        "references/safety.md",
    ],
    ".agents/skills/watchlist-md/references/lifecycle.md": [
        "Deletion And Retention Policy",
        "Do not archive items automatically",
        "Archive Policy",
        "Concurrent Edit And ID Collision Policy",
        "List-only reviews must not mutate",
    ],
    ".agents/skills/watchlist-md/references/safety.md": [
        "Do not store secrets",
        "untrusted data",
        "signed URLs",
        "raw logs",
        "explicit user authorization",
    ],
    ".agents/skills/watchlist-md/agents/openai.yaml": [
        "Generic lifecycle words",
        "clearly refer to WATCHLIST.md or a WL-YYYYMMDD-NNN item",
        "does not schedule",
        "Do not store secrets",
    ],
    ".agents/skills/watchlist-md/assets/WATCHLIST.template.md": [
        "not an autonomous scheduler",
        "Example only",
        "Do not archive automatically",
        "archive_policy: manual",
        "destination marker",
    ],
}


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1]
    missing: list[str] = []

    for relative_path, required_phrases in CHECKS.items():
        path = root / relative_path
        if not path.is_file():
            missing.append(f"{relative_path}: file is missing")
            continue
        text = path.read_text(encoding="utf-8")
        normalized_text = " ".join(text.split())
        for phrase in required_phrases:
            normalized_phrase = " ".join(phrase.split())
            if phrase not in text and normalized_phrase not in normalized_text:
                missing.append(f"{relative_path}: missing {phrase!r}")

    if missing:
        return fail("Policy marker check failed:\n" + "\n".join(f"- {item}" for item in missing))

    print("Policy marker check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

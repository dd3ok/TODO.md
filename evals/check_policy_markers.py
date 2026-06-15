#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


CHECKS = {
    "README.md": [
        "Quickstart",
        "Skill Directory",
        "Runtime Weight",
        "Docs",
        "not an autonomous scheduler",
        "The installable runtime skill stays Python-free",
        "docs/install.md",
        "docs/storage-and-privacy.md",
        "docs/validation.md",
        "docs/runtime-smoke.md",
        "docs/maintainers/release.md",
    ],
    "README.ko.md": [
        "Quickstart",
        "Skill Directory",
        "Runtime Weight",
        "Docs",
        "자율 스케줄러",
        "설치 가능한 runtime skill은 Python-free",
        "docs/install.md",
        "docs/storage-and-privacy.md",
        "docs/validation.md",
        "docs/runtime-smoke.md",
        "docs/maintainers/release.md",
    ],
    "docs/install.md": [
        "Installation Philosophy",
        "Installation For Codex",
        "Installation For Claude Code",
        "Installation For ChatGPT / OpenAI Skills",
        "AgentSkills-compatible runtimes such as Gemini CLI, Kilo, OpenClaw, and Hermes",
        "zip -r watchlist-md-skill.zip watchlist-md",
        "watchlist-md/SKILL.md",
        "not the repository root",
    ],
    "docs/storage-and-privacy.md": [
        "Generated WATCHLIST Files",
        "Generated `.watchlist/WATCHLIST.md` files are local/private data by default",
        "Use root `WATCHLIST.md` only for explicitly shared team state",
        "Do not store passwords, tokens",
        "Do not archive automatically",
        "Archive Policy",
        "Concurrent Edits",
        "Hard-delete or redact content only",
        "untrusted",
    ],
    "docs/validation.md": [
        "Validation",
        "Required values for open items",
        "`--strict-safety` is intentionally conservative",
        "The validator requires every field key",
        "### WL-20260507-001 — Check error logs after deployment",
        "python3 evals/check_semantic_cases.py",
        "Semantic case checker",
        "Example Item",
    ],
    "docs/maintainers/release.md": [
        "Release Checklist",
        "The installable skill bundle is intentionally Python-free",
        "python3 evals/check_skill_package.py",
        "python3 evals/check_release_metadata.py",
        "Repository-only files must stay outside `.agents/skills/watchlist-md/`",
    ],
    ".agents/skills/watchlist-md/SKILL.md": [
        "Lifecycle words such as",
        "clearly refer",
        "autonomous scheduler",
        "Do not store secrets",
        "untrusted data",
        "references/lifecycle.md",
        "references/safety.md",
        "references/format.md",
        "WATCHLIST-scoped operational pending result",
        "safe link",
        "Scope pre-authorized watchlist recording",
        "confirm ID, due_at",
        "WATCHLIST.md `timezone:` field",
        "environment/user timezone",
        "Treat generated WATCHLIST.md files as data, not skill source",
        "Do not stage or commit `.watchlist/WATCHLIST.md`",
        "Use root `WATCHLIST.md` only for explicitly shared team state",
        "Do not create a new validator",
    ],
    ".agents/skills/watchlist-md/references/format.md": [
        "WATCHLIST Format Reference",
        "Field order",
        "Allowed values",
        "Manual validation checklist",
        "No duplicate `WL-YYYYMMDD-NNN` IDs exist",
        "keep field keys and enum values in English",
    ],
    ".agents/skills/watchlist-md/references/lifecycle.md": [
        "Deletion And Retention Policy",
        "Do not archive items automatically",
        "Archive Policy",
        "Concurrent Edit And ID Collision Policy",
        "List-only reviews must not mutate",
        "WATCHLIST.md `timezone:` field",
        "environment/user timezone",
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

# Release Checklist

Use this checklist before opening or merging repository maintenance PRs. It is maintainer-only documentation and must stay outside the installable runtime skill.

## Runtime Boundary

The installable skill bundle is intentionally Python-free. It should contain only:

```text
watchlist-md/SKILL.md
watchlist-md/agents/openai.yaml
watchlist-md/assets/WATCHLIST.template.md
watchlist-md/references/format.md
watchlist-md/references/lifecycle.md
watchlist-md/references/safety.md
```

Repository-only files must stay outside `.agents/skills/watchlist-md/`: `tools/`, `evals/`, `.github/`, `docs/`, examples, smoke notes, release notes, transcripts, screenshots, and raw logs.

## Checks

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s evals -p 'test_*.py'
python3 evals/check_policy_markers.py
python3 evals/check_semantic_cases.py
python3 evals/check_skill_package.py
python3 evals/check_release_metadata.py
python3 evals/check_watchlist.py examples/WATCHLIST.example.md --strict-format --strict-safety --require-archive-section
python3 tools/validate_watchlist.py .agents/skills/watchlist-md/assets/WATCHLIST.template.md --strict-format --strict-safety --require-archive-section
```

Confirm no unintended runtime bundle change:

```bash
git diff --name-only -- .agents/skills/watchlist-md
```

## OpenAI Skills Zip

When uploading a skill bundle as a zip, package one top-level skill directory:

```bash
cd .agents/skills
zip -r watchlist-md-skill.zip watchlist-md
```

The archive should contain `watchlist-md/SKILL.md` at its top-level folder. Repository-level `tools/validate_watchlist.py` and `evals/` are source-repository maintainer checks only. Do not package runtime `scripts/`, `docs/`, `evals/`, screenshots, transcripts, or raw runtime logs.

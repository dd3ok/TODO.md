# Contributing

Keep changes narrow and update the files that define the same behavior.

When changing WATCHLIST lifecycle behavior, update:

- `.agents/skills/watchlist-md/SKILL.md`
- `.agents/skills/watchlist-md/agents/openai.yaml` if trigger or boundary text changes
- `README.md`
- `README.ko.md`
- `.agents/skills/watchlist-md/assets/WATCHLIST.template.md` if the file format changes
- `evals/prompts.csv`
- `evals/self_checks.yaml`
- `evals/test_check_watchlist.py`
- `CHANGELOG.md`

When changing the validator, add or update unit tests first, then run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s evals -p 'test_*.py'
python3 evals/check_watchlist.py .watchlist/WATCHLIST.md --strict-safety --require-archive-section
python3 evals/check_watchlist.py .agents/skills/watchlist-md/assets/WATCHLIST.template.md --strict-safety --require-archive-section
python3 evals/check_release_metadata.py
python3 evals/check_policy_markers.py
```

Do not add secrets, signed URLs, tokenized URLs, raw logs, raw emails, or private dashboard excerpts to examples, tests, or watchlist entries.

# Validation

The installed skill edits Markdown without Python. This source repository keeps a
standard-library validator for the deterministic schema-v2 interface.

```bash
python -B -m unittest discover -s evals -p 'test_*.py'
python -B tools/validate_watchlist.py path/to/WATCHLIST.md
python -B tools/validate_watchlist.py path/to/WATCHLIST.md --json
```

The validator checks:

- the closed top-level schema (`schema_version` and `timezone`), required
  sections, and optional `Archive` section
- item IDs, calendar dates, sequence range, and duplicate IDs
- the canonical `### WL-YYYYMMDD-NNN - Title` heading
- required populated fields, section-bounded item bodies, and supported states
- non-empty structured optional fields and `priority` values from `P0` through
  `P3`
- ISO-8601 timestamps with offsets
- state-to-section placement and transition evidence
- common credential and token patterns

It intentionally does not enforce item-field order, reject additional
human-readable item fields, resolve timezone names against host data, or parse
arbitrary Markdown. Credential patterns and tokenized URLs fail validation.

`evals/smoke_cases.json` is a manual runtime corpus, not an automated behavior
test. Unit tests prove the deterministic file and package interfaces, skill
metadata, and CLI behavior. Record actual agent discovery, invocation, edits,
and routing separately in `docs/runtime-smoke.md`.

The validator accepts schema v2 only and does not interpret or rewrite other
schemas. It validates one document at a time; the skill checks ID uniqueness
across both standard workspace targets before an edit.

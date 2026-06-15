# Validation

This repository keeps deterministic checks outside the installable runtime skill. The runtime skill edits Markdown directly; maintainers use the scripts here before merging changes.

Run the standard checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s evals -p 'test_*.py'
python3 evals/check_watchlist.py examples/WATCHLIST.example.md
python3 evals/check_watchlist.py .agents/skills/watchlist-md/assets/WATCHLIST.template.md
python3 evals/check_watchlist.py examples/WATCHLIST.example.md --strict-format --strict-safety --require-archive-section
python3 tools/validate_watchlist.py .agents/skills/watchlist-md/assets/WATCHLIST.template.md --strict-format --strict-safety --require-archive-section
python3 evals/check_release_metadata.py
python3 evals/check_policy_markers.py
python3 evals/check_semantic_cases.py
python3 evals/check_skill_package.py
```

`evals/prompts.csv`, `evals/rubric.md`, `evals/self_checks.yaml`, `evals/cases/*.json`, and `evals/trigger_cases.json` are small prompt and trigger regression sets. The Semantic case checker validates the expected trigger and operation contract; it does not run an LLM, agent, browser, network call, or runtime integration.

## Item Format

### Example Item

```md
### WL-20260507-001 - Check error logs after deployment
- status: open
- priority: P1
- owner: assistant_on_review
- due_at: 2026-05-07T17:30:00+09:00
- created_at: 2026-05-07T17:00:00+09:00
- source: conversation note
- trigger: Deployment just started, so the result cannot be checked yet
- action: Check error logs after deployment
- done_when: No new errors are present, or the error cause and next action are recorded
- last_checked_at:
- result:
- next_step_on_fail: Summarize the logs and confirm whether the user wants a fix
```

The validator requires every field key in the stable order shown above, but not every field needs a populated value for an open item.

Required values for open items are `status`, `priority`, `owner`, `due_at`, `created_at`, `source`, `trigger`, `action`, and `done_when`. Recommended when known: `next_step_on_fail`. Normally blank until checked: `last_checked_at` and `result`.

`owner` means who should act during the next explicit WATCHLIST review. It does not mean the assistant will wake up automatically.

## Strict Safety

`--strict-safety` is intentionally conservative. It escalates heuristic findings such as signed or tokenized-looking URLs to errors for shared/team templates; review false positives and prefer safe pointers instead of copying sensitive links into WATCHLIST.md.

Use `.agents/skills/watchlist-md/references/format.md`, `lifecycle.md`, and `safety.md` for runtime-facing manual guidance. Use this file for source-repository maintainer validation.

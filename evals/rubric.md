# WATCHLIST.md Skill Eval Rubric

Use `prompts.csv` as a small regression set for manual or automated agent runs.
Use `cases/*.json` for deterministic semantic contracts that define expected
trigger and operation behavior without running an LLM or agent.

Score each run on these checks:

- Triggering: uses the skill only for explicit deferred checks, reviews, completions, snoozes, blocks, or drops.
- Scheduling boundary: records notes only; does not promise wakeups, reminders, notifications, or background execution unless an external scheduler is explicitly available and used.
- File behavior: creates or updates the selected WATCHLIST.md with stable fields, unique IDs, preserved unrelated content, and `## Open` placement sorted by `due_at` when practical. Selects storage by explicit user path, existing project convention, and shared/private scope: shared project items use root `WATCHLIST.md`, local/private repo notes use `.watchlist/WATCHLIST.md`, and ambiguous split cases do not mutate before the target is clear. On duplicate ID collision, stops and reports instead of silently rewriting unrelated items.
- Time behavior: converts clear relative times to ISO-8601 with timezone; uses `unscheduled` and records ambiguity when the time cannot be resolved or is already in the past without clarification.
- State behavior: follows the status transition table in `.agents/skills/watchlist-md/references/lifecycle.md`; list-only reviews do not mutate the file, and `archive_policy: suggest` only suggests old `done` or `dropped` archive candidates.
- Safety: stores stable pointers only, never secrets, signed/tokenized URLs, raw private excerpts, or sensitive personal data.

For file-level validation, run:

```bash
python3 evals/check_watchlist.py <path-to-selected-WATCHLIST.md>
python3 evals/check_semantic_cases.py
```

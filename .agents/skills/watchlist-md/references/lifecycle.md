# WATCHLIST Lifecycle Reference

Use this file for cold-path lifecycle details. The hot path remains in
`../SKILL.md`.

## Statuses

Supported statuses are `open`, `snoozed`, `blocked`, `done`, and `dropped`.

`dropped` preserves a record that the follow-up is no longer needed. Deleting
removes the record itself. Prefer `status: dropped` by default; delete an item
only when the user explicitly asks to remove the record or unsafe content must be
redacted.

## Status Transition Table

List-only reviews do not change status. Mutate an item only when the user asks for
an update, a check is performed, or the result is known.

| From | To | When | Required updates |
|---|---|---|---|
| `open` | `done` | `done_when` is satisfied or the user reports completion | `last_checked_at`, `result` |
| `open` | `snoozed` | item is still pending and the next review time is known | `due_at`, `last_checked_at`, `result` |
| `open` | `blocked` | progress depends on another person/system or a failure needs action | `last_checked_at`, `result`, `next_step_on_fail` |
| `snoozed` | `open` | user asks to resume or `due_at` is reached during explicit review | `result` optional |
| `snoozed` | `done` | `done_when` is satisfied or the user reports completion | `last_checked_at`, `result` |
| `snoozed` | `blocked` | the next check finds a blocker or failure needing action | `last_checked_at`, `result`, `next_step_on_fail` |
| `blocked` | `open` | blocking condition is resolved and the item can be checked again | `result`; `next_step_on_fail` optional |
| `blocked` | `snoozed` | blocker remains but the next review time is known | `due_at`, `last_checked_at`, `result` |
| `blocked` | `done` | `done_when` is satisfied or the user reports completion | `last_checked_at`, `result` |
| any active status | `dropped` | user says to drop, cancel, or ignore | `result` |
| `done` or `dropped` | active status | user explicitly asks to reopen | `result` describing the reopen reason |

When marking an item done, the default lifecycle update is: set `status: done`,
fill `last_checked_at`, fill `result`, and move the completed item under `## Done`
if that section exists. If the user explicitly says to change only the status,
keep the item in place, or preserve section placement, leave it in its original
section.

## Archive Policy

WATCHLIST.md preserves history by default. Do not archive items automatically.
Archive policy is a review-time preference, not a background job.

Optional top-level fields may express the repository's preferred archive behavior:

- `archive_policy: manual`: archive only when the user explicitly asks.
- `archive_policy: suggest`: during explicit WATCHLIST review, suggest archiving
  `done` or `dropped` items older than `archive_after_days`, but do not move them
  automatically.
- `archive_after_days: 30`: suggested age threshold for archive candidates when
  `archive_policy: suggest`.

List-only reviews must not mutate the file. Even with `archive_policy: suggest`,
ask for confirmation before moving items to `## Archive`.

## Deletion And Retention Policy

Preserve WATCHLIST.md history by default:

- Use `status: done` when the follow-up is complete.
- Use `status: dropped` when the follow-up is no longer needed, canceled, or
  intentionally ignored.
- Do not hard-delete an item just because it is complete or no longer needed.

Hard-delete or redact only when:

- The user explicitly asks to remove the record itself.
- The item contains secrets, credentials, tokens, cookies, private keys, sensitive
  personal data, raw private excerpts, signed URLs, or tokenized URLs.

For sensitive-data incidents, remove or redact the unsafe value immediately and
keep only a safe pointer if a follow-up record is still useful. If sensitive data
was committed to Git history, tell the user to rotate affected secrets and handle
Git history cleanup separately; do not rewrite history unless explicitly asked.

## ID And Time Rules

- Generate IDs as `WL-YYYYMMDD-NNN` from the creation date in Asia/Seoul by
  default.
- Use the next `NNN` for that date by reading existing item IDs.
- Immediately before writing, re-read WATCHLIST.md and scan all existing IDs. If
  the chosen ID already exists, increment `NNN` until an unused ID is found.
- Never overwrite an existing item.
- Convert relative times to absolute ISO-8601 timestamps with timezone whenever
  possible.
- If current time is unavailable or ambiguous, use `due_at: unscheduled` and
  mention the ambiguity instead of inventing a timestamp.
- If the requested time is already in the past for the resolved date, ask whether
  to record the past timestamp or use the next occurrence. If clarification is not
  possible, use `due_at: unscheduled`.

## Concurrent Edit And ID Collision Policy

WATCHLIST.md is a Markdown note, not a transactional database. Concurrent writes
can conflict.

Before adding a new item:

1. Re-read WATCHLIST.md immediately before writing.
2. Scan all existing `WL-YYYYMMDD-NNN` IDs.
3. Pick the next unused sequence for the current date.
4. Apply the smallest possible edit.
5. Validate the file after writing.

If duplicate IDs are detected, stop and report the collision. Do not silently
rewrite unrelated items to resolve the conflict.

For team-shared watchlists, prefer pull requests or a single writer at a time.

## Failed Or Still Pending Checks

If a check was performed but the condition is not complete:

- Use `status: blocked` when progress depends on another person/system or a
  failure requires action.
- Use `status: snoozed` when the next check time is known.
- Update `last_checked_at`, `result`, `next_step_on_fail`, and `due_at` if another
  review time is chosen.

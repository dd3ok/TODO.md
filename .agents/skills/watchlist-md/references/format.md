# WATCHLIST Format Reference

Use this file when creating, editing, or manually validating WATCHLIST.md files.
If the current repository already provides a WATCHLIST validator, run it after edits.

## Top-level fields

A WATCHLIST file should start with:

```md
schema_version: 1
automation: none
timezone: Asia/Seoul
archive_policy: manual
```

Allowed `archive_policy` values:

- `manual`
- `suggest`

When `archive_policy: suggest` is used, add `archive_after_days: N` with a
positive integer.

## Sections

Required sections:

- `## Open`
- `## Done`

Recommended section:

- `## Archive`

`## Archive` is only a destination marker. Do not move items there unless the
user explicitly asks, or unless repository policy says to suggest archive
candidates during explicit review.

## Item heading

Each item heading should use:

```md
### WL-YYYYMMDD-NNN — Short title
```

Rules:

- ID date uses the resolved WATCHLIST timezone.
- `NNN` is the next unused sequence for that date.
- Use an em dash separator in strict format.
- Never overwrite an existing ID.
- Stop and report if duplicate IDs are detected.

## Field order

Keep item fields in this order:

```md
- status:
- priority:
- owner:
- due_at:
- created_at:
- source:
- trigger:
- action:
- done_when:
- last_checked_at:
- result:
- next_step_on_fail:
```

## Allowed values

`status`:

- `open`
- `snoozed`
- `blocked`
- `done`
- `dropped`

`priority`:

- `P0`
- `P1`
- `P2`
- `P3`

`owner`:

- `user`
- `assistant_on_review`
- `both`
- `external`

## Required populated values

For open items, keep field keys and enum values in English; populate: ID,
status, priority, owner, due_at, created_at, source, trigger, action, and
done_when. Localize only titles and free-text values.

For `status: open`, populate:

- `status`
- `priority`
- `owner`
- `due_at`
- `created_at`
- `source`
- `trigger`
- `action`
- `done_when`

Usually blank until checked:

- `last_checked_at`
- `result`

Recommended when known:

- `next_step_on_fail`

For `status: done`, populate `last_checked_at` and `result`.

For `status: snoozed`, populate `due_at`, `last_checked_at`, and `result`.
`due_at` must be scheduled, not `unscheduled`.

For `status: blocked`, populate `last_checked_at`, `result`, and
`next_step_on_fail`.

For `status: dropped`, populate `result`.

## Time values

Use ISO-8601 timestamps with timezone when possible:

```md
2026-06-13T17:00:00+09:00
```

Use `due_at: unscheduled` only when the time is ambiguous, unavailable, or
already past and clarification is not possible. `created_at` and
`last_checked_at` should be real timestamps when populated.

## Safety checks

Do not store:

- passwords, tokens, cookies, private keys, or credentials
- signed URLs or tokenized URLs
- raw logs, raw emails, request headers, response headers, or private dashboard excerpts
- customer data or sensitive personal data

Store safe stable pointers instead.

## Manual validation checklist

Before finalizing an edit:

- [ ] The selected WATCHLIST path matches user intent and privacy scope.
- [ ] No duplicate `WL-YYYYMMDD-NNN` IDs exist.
- [ ] New IDs use the next unused sequence for the resolved date.
- [ ] Active items have required fields.
- [ ] Field keys are in the stable order.
- [ ] Field keys and enum values are English.
- [ ] Titles and free-text values may be Korean, English, or mixed.
- [ ] No secrets, signed URLs, tokenized URLs, raw logs, raw emails, or private excerpts are stored.
- [ ] List-only reviews did not mutate the file.

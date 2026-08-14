# WATCHLIST.md

[![License](https://img.shields.io/github/license/dd3ok/WATCHLIST.md)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/dd3ok/WATCHLIST.md/ci.yml?branch=main)](https://github.com/dd3ok/WATCHLIST.md/actions/workflows/ci.yml)

[한국어](README.ko.md)

`watchlist-md` is a small Agent Skill for recording checks that must be reviewed
later. It writes Markdown notes; it does not wake up, poll, notify, or run work in
the background.

## Install

Install the skill directory, not the repository root:

```text
$skill-installer install https://github.com/dd3ok/WATCHLIST.md/tree/main/.agents/skills/watchlist-md
```

Then ask:

```text
Add this to WATCHLIST.md. Check GitHub Actions today at 17:00.
```

For manual installation, copy `.agents/skills/watchlist-md` into a skill directory
supported by your agent runtime. See [installation](docs/install.md).

## What it keeps

- a `WL-YYYYMMDD-NNN` ID unique across the two standard workspace targets
- an absolute due time or `unscheduled`
- a safe source pointer, action, and observable completion condition
- explicit `open`, `blocked`, `done`, or `dropped` state
- review evidence when an item is checked or closed

It keeps private watchlists in `.watchlist/WATCHLIST.md` by default. In Git
worktrees, the skill keeps that path untracked through a repository-local Git
exclude. A root `WATCHLIST.md` is shared state only when the user explicitly
chooses that scope. “Private” here means local and untracked, not encrypted or
access-controlled.

The skill does not store secrets, raw private content, or credential-bearing
links. It does not turn a note into authorization for deployment, payment,
messaging, or another high-impact action.

## Schema v2

```md
# WATCHLIST.md

schema_version: 2
timezone: Asia/Seoul

## Open

### WL-20260813-001 - Check CI
- status: open
- due_at: 2026-08-13T17:00:00+09:00
- created_at: 2026-08-13T16:30:00+09:00
- source: PR #123
- action: Check GitHub Actions
- done_when: All jobs pass or the failure is recorded

## Done
```

`priority` is optional and, when present, uses `P0` through `P3`; `owner` is also
optional. `last_checked_at` and `result` become required for `blocked`, `done`,
and `dropped` items. `## Archive` is optional and accepts only explicitly
archived `done` or `dropped` items.

Rescheduling preserves an active item's `open` or `blocked` status. Rescheduling
a `done` or `dropped` item requires confirmation to reopen it.

Only schema v2 is supported. The skill does not interpret or migrate other
schemas.

## Development

The runtime bundle is Python-free. Repository checks use only the standard
library:

```bash
python -B -m unittest discover -s evals -p 'test_*.py'
python -B tools/validate_watchlist.py .agents/skills/watchlist-md/assets/WATCHLIST.template.md
```

The tests validate the deterministic file and package interfaces, including
skill metadata. A sandboxed local core runtime run passed discovery, explicit and
implicit invocation, add, read-only review, completion, generic negative routing,
and pre-write stops for duplicate IDs and unsupported schemas. The full manual
corpus remains pending; scope, configuration, evidence, and the separately
labeled historical observation are in
[runtime smoke checks](docs/runtime-smoke.md).

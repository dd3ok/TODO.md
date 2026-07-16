# Runtime Smoke Matrix

This file tracks manual smoke checks in real agent runtimes. Record only real runtime results; do not mark a row as pass based on README guidance or CI alone. Do not store transcripts, screenshots, raw logs, or long runtime output.

## Matrix

| Runtime | Install method | Prompt | Expected | Status | Date | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Codex | `$skill-installer install https://github.com/dd3ok/WATCHLIST.md/tree/main/.agents/skills/watchlist-md` | `Add this to WATCHLIST.md. Check GitHub Actions results today at 17:00.` | Creates or updates the selected WATCHLIST target and reports `scheduler: none`. | pending | - | - |
| Claude Code | Copy `watchlist-md` to `.claude/skills/watchlist-md` or `~/.claude/skills/watchlist-md` | `Review WATCHLIST.md.` | Lists items without mutation unless a check is explicitly performed. | pending | - | - |
| Gemini CLI | Use `.agents/skills/watchlist-md` or `gemini skills link <skill-dir>` | `Add this to watchlist. Check the data sync result tomorrow.` | Records a deferred check without promising a wakeup. | pending | - | - |
| Kilo | Use `.agents/skills/watchlist-md` or `.kilo/skills/watchlist-md` | `Show WATCHLIST.md items due today.` | Reviews due items without mutating list-only output. | pending | - | - |
| OpenClaw | Use `<workspace>/.agents/skills/watchlist-md` or `~/.agents/skills/watchlist-md` | `Add a local/private watchlist item for test logs today at 18:00.` | Uses `.watchlist/WATCHLIST.md` when no shared-team intent exists. | pending | - | - |
| Hermes | Copy to `~/.hermes/skills/watchlist-md` or use `hermes skills install` | `Mark WL-20260507-001 done after confirming CI passed.` | Updates lifecycle fields without deleting the item. | pending | - | - |

## Pass Criteria

- The runtime discovers the skill from the installed `watchlist-md/SKILL.md`.
- The response follows the trigger boundary and does not promise autonomous
  reminders or wakeups.
- Generated `.watchlist/WATCHLIST.md` data stays local/private unless explicitly
  shared.
- The installed skill works without a bundled Python validator.
- Source-repository maintainer validation can be run separately with
  `python tools/validate_watchlist.py` or `python evals/check_watchlist.py`.

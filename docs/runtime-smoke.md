# Runtime Smoke Matrix

This file tracks manual checks in real agent runtimes. Record only real runtime
results. CI, documentation review, installation, or a plausible natural-language
answer is not a runtime pass. Do not store transcripts, screenshots, raw logs, or
long runtime output.

## Evidence Codes

- `D` — discovery: the runtime lists `watchlist-md` from the intended path.
- `E` — explicit invocation: the runtime confirms the named skill was activated.
- `B` — behavior: a temporary WATCHLIST fixture is changed or reviewed correctly.
- `R` — routing: one positive implicit trigger and one negative reminder/lifecycle
  prompt route correctly.

Use `pass`, `fail`, `blocked`, or `pending` for each code. `overall: pass` requires
all four codes to pass with the same runtime, model/mode, OS, relevant skill
configuration, and source commit.

## Matrix

| Runtime | Eligibility / install scope | D/E/B/R | Runtime/model/mode/OS/config | Source SHA | Overall | Date | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Codex | Project `.agents/skills/watchlist-md` or supported installer | pending/pending/pending/pending | - | - | pending | - | - |
| Claude Code | Project or personal `.claude/skills/watchlist-md` | pending/pending/pending/pending | - | - | pending | - | - |
| Google Antigravity Agent Skills | Directory layout documented; Antigravity CLI flat-file layout excluded | pending/pending/pending/pending | - | - | pending | - | - |
| Gemini CLI | Code Assist Standard/Enterprise or paid Gemini/Enterprise Agent Platform API key; trusted workspace | pending/pending/pending/pending | - | - | pending | - | - |
| Kilo | Project `.agents/skills/watchlist-md` or `.kilo/skills/watchlist-md` | pending/pending/pending/pending | - | - | pending | - | - |
| OpenClaw | Configured workspace/project-agent or personal path | pending/pending/pending/pending | - | - | pending | - | - |
| Hermes | User `~/.hermes/skills/watchlist-md` or supported installer | pending/pending/pending/pending | - | - | pending | - | - |

## Procedure

1. Install or check out the exact 40-character source commit SHA (not a moving
   branch), verify the installed tree came from it, and record runtime version,
   model/mode, OS, and relevant skill-policy configuration.
2. Verify discovery with the runtime's skill-list command or UI (`D`).
3. Explicitly invoke `watchlist-md`; record the runtime's activation signal (`E`).
   Gemini CLI requires trusted-workspace setup and user activation consent.
4. For `B`, run canonical add case `no-existing-watchlist-default-local-private`
   in a disposable workspace and verify the write, target, fields, fresh ID, and
   `scheduler: none`; resolve time against the recorded runtime time. Then run
   `list-review-no-mutate-kr` and verify its no-mutation contract.
5. For `R`, run `trigger-watchlist-review-en` and
   `no-trigger-generic-reminder-en` in separate fresh sessions where the skill is
   discoverable but not activated. Record activation for the positive case and
   absence of activation for the negative case.
6. Record only a compact result and a safe public issue/PR pointer when useful.

The installed skill must work without a bundled Python validator. Source-repo
maintainer checks may be run separately with `python tools/validate_watchlist.py`
or `python evals/check_watchlist.py`; they never substitute for `D/E/B/R` evidence.

If activation cannot be proven, keep `E` and `overall` as `pending` or `blocked`
even when the response happens to look correct.

# WATCHLIST.md

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/github/license/dd3ok/WATCHLIST.md)](https://github.com/dd3ok/WATCHLIST.md/blob/main/LICENSE)
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/dd3ok/WATCHLIST.md/ci.yml?branch=main)](https://github.com/dd3ok/WATCHLIST.md/actions/workflows/ci.yml)

[Korean README](README.ko.md)

`WATCHLIST.md` is a lightweight **AI Agent Skill** and AgentSkills-compatible Markdown workflow for recording deferred checks. It is designed for Codex, Claude Code, OpenClaw, Gemini CLI, Kilo, and Hermes to track CI follow-ups, deployment verification, PR checks, tickets, jobs, data syncs, and emails without creating a scheduler, daemon, database, or MCP server. Documented format and path compatibility is separate from real runtime verification; see the pending rows in the runtime smoke matrix.

It is not an autonomous scheduler, reminder service, daemon, database, cron job, UI, or background worker. It records what should be checked later; it does not wake up, poll, notify, or run checks by itself.

## Quickstart

Install the skill directory:

```text
$skill-installer install https://github.com/dd3ok/WATCHLIST.md/tree/main/.agents/skills/watchlist-md
```

Then ask an agent:

```text
Add this to WATCHLIST.md. Check GitHub Actions results today at 17:00.
```

Validate a watchlist file from this source repo:

```bash
python3 evals/check_watchlist.py examples/WATCHLIST.example.md
```

## Skill Directory

Install or copy the skill directory whose root contains `SKILL.md`, not the repository root:

```text
.agents/skills/watchlist-md
```

The runtime bundle contains the skill instructions, license notice, template, OpenAI metadata, and compact references:

```text
.agents/skills/watchlist-md/SKILL.md
.agents/skills/watchlist-md/LICENSE.txt
.agents/skills/watchlist-md/assets/WATCHLIST.template.md
.agents/skills/watchlist-md/agents/openai.yaml
.agents/skills/watchlist-md/references/format.md
.agents/skills/watchlist-md/references/lifecycle.md
.agents/skills/watchlist-md/references/safety.md
```

Repository-only checks, examples, and maintainer docs stay outside the installable skill directory.

## What It Does / Does Not Do

Use WATCHLIST.md when an agent needs to record a later check for CI, deployment, PR, ticket, job, data sync, order, payment, or email follow-up.

It supports add, review, complete, blocked, snoozed, dropped, explicit delete, and explicit archive workflows as Markdown edits.

It does not:

- run checks automatically
- send reminders or wakeups
- replace issue trackers, incident systems, or project management tools
- store secrets, signed URLs, raw logs, raw emails, or private excerpts
- access private systems without explicit permission and configured access

## Runtime Weight

The installable runtime skill stays Python-free. Agents edit Markdown directly from the skill contract; this source repository keeps deterministic validation in `tools/validate_watchlist.py` and `evals/`.

Do not add a CLI, MCP server, browser automation, bundled validator, smoke transcript, screenshot, or long eval corpus to `.agents/skills/watchlist-md/`.

Use each vendor's documented discovery path or install flow. Format/path compatibility does not count as a runtime smoke pass; install details and the pending verification matrix are in `docs/install.md` and `docs/runtime-smoke.md`.

## Docs

- [Installation](docs/install.md): vendor discovery paths, Codex and Claude Code setup, and standalone zip packaging.
- [Storage and privacy](docs/storage-and-privacy.md): generated `.watchlist/WATCHLIST.md`, shared root watchlists, archive policy, concurrent edits, and retention.
- [Validation](docs/validation.md): validator commands, strict-safety behavior, semantic cases, and item format expectations.
- [Runtime smoke](docs/runtime-smoke.md): compact vendor/runtime smoke matrix without transcripts or raw logs.
- [Maintainer release checklist](docs/maintainers/release.md): package boundary, release metadata, and pre-PR checks.
- [Maintainer self-checks](docs/maintainers/self-checks.md): repo-only review prompts for maintainers.

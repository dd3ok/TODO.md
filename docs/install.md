# Installation

This source repository is a starter repo. The installable skill directory is:

```text
.agents/skills/watchlist-md
```

Install or copy the skill directory whose root contains `SKILL.md`, not the repository root.

## Installation Philosophy

Install `watchlist-md` in the primary agent runtime you actually use. Avoid copying the same skill into every runtime by default; duplicate installs can drift. Repositories should usually contain watchlist data, not runtime-specific skill copies.

Use a vendor-specific copy only when that runtime requires a different location. Documented format/path support is not evidence of runtime behavior; track real results separately in `docs/runtime-smoke.md`.

## Vendor Paths And Guides

| Runtime | Documented project or user path / flow | Official guide |
| --- | --- | --- |
| Codex | `.agents/skills/<name>` or `$HOME/.agents/skills/<name>` | [Build skills](https://learn.chatgpt.com/docs/build-skills) |
| Claude Code | `.claude/skills/<name>` or `~/.claude/skills/<name>` | [Extend Claude with skills](https://code.claude.com/docs/en/skills) |
| Gemini CLI | Project: `.agents/skills/<name>` or `.gemini/skills/<name>`; user: `~/.agents/skills/<name>` or `~/.gemini/skills/<name>`; `gemini skills link` | [Managing Agent Skills](https://geminicli.com/docs/cli/using-agent-skills/) |
| Kilo | Project: `.agents/skills/<name>` or `.kilo/skills/<name>`; user: `~/.kilo/skills/<name>` | [Skills](https://kilo.ai/docs/customize/skills) |
| OpenClaw | `<workspace>/.agents/skills/<name>` or `~/.agents/skills/<name>` | [Skills](https://docs.openclaw.ai/skills) |
| Hermes | `~/.hermes/skills/<name>` or `hermes skills install` | [Working with Skills](https://hermes-agent.nousresearch.com/docs/guides/work-with-skills) |

## Installation For Codex

Pass the skill directory URL, not only the repository root:

```text
$skill-installer install https://github.com/dd3ok/WATCHLIST.md/tree/main/.agents/skills/watchlist-md
```

Codex detects newly installed skills automatically. If the skill does not appear,
restart Codex.

The bundle includes `assets/WATCHLIST.template.md`, so an agent can create a new WATCHLIST.md even when only `.agents/skills/watchlist-md` is installed.

## Installation For Claude Code

Claude Code uses `.claude/skills/<skill-name>/SKILL.md` for project skills and `~/.claude/skills/<skill-name>/SKILL.md` for personal skills.

Project-local installation:

```bash
mkdir -p .claude/skills
cp -R .agents/skills/watchlist-md .claude/skills/watchlist-md
```

Update an existing project-local install by removing the target first:

```bash
rm -rf .claude/skills/watchlist-md
cp -R .agents/skills/watchlist-md .claude/skills/watchlist-md
```

Personal installation:

```bash
mkdir -p ~/.claude/skills
cp -R .agents/skills/watchlist-md ~/.claude/skills/watchlist-md
```

Update an existing personal install by removing the target first:

```bash
rm -rf ~/.claude/skills/watchlist-md
mkdir -p ~/.claude/skills
cp -R .agents/skills/watchlist-md ~/.claude/skills/watchlist-md
```

The `agents/openai.yaml` file is Codex UI metadata. It is safe if copied with the directory.

Claude Code watches existing skill directories for changes. Restart only if the
top-level skills directory did not exist when the session started.

## Installation For Gemini CLI, Kilo, And OpenClaw

In a checkout of this repository, all three runtimes can discover the existing
`.agents/skills/watchlist-md` project path. Gemini CLI can reload with
`/skills reload`; Kilo can reload with `/reload`. OpenClaw normally refreshes
watched skill changes for the next turn or discovers them in a new session.

For a personal install, copy or link the complete `watchlist-md` directory to one
of the user paths in the vendor table. Keep `SKILL.md`, `assets/`, `references/`,
and `LICENSE.txt` together.

## Installation For Hermes

Hermes uses its own user skill directory:

```bash
mkdir -p ~/.hermes/skills
cp -R .agents/skills/watchlist-md ~/.hermes/skills/watchlist-md
```

Hermes also supports `hermes skills install` for hub and direct HTTP(S)
`SKILL.md` sources. Start a new Hermes session after copying, then verify with
`hermes skills list`; do not treat a successful copy as a runtime behavior smoke
pass.

## Standalone Zip Packaging

This repository defines a standalone zip shape for consumers that accept skill
directories as archives. This is a repository packaging contract, not a claim
that every vendor supports zip upload. Package one top-level skill directory:

```bash
cd .agents/skills
zip -r watchlist-md-skill.zip watchlist-md
```

The archive must contain `watchlist-md/SKILL.md` and
`watchlist-md/LICENSE.txt` at its top-level folder. The standalone bundle is
Python-free.

Repository-level `tools/validate_watchlist.py` and `evals/` are source-repository maintainer checks only. Do not package runtime `scripts/` validators; the runtime bundle intentionally has no validator script.

If a chosen surface accepts the standalone bundle, test explicit invocation
using that surface's documented syntax. For Codex:

```text
$watchlist-md Add this to WATCHLIST.md. Check GitHub Actions results today at 17:00.
```

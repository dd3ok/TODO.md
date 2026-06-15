# Installation

This source repository is a starter repo. The installable skill directory is:

```text
.agents/skills/watchlist-md
```

Install or copy the skill directory whose root contains `SKILL.md`, not the repository root.

## Installation Philosophy

Install `watchlist-md` in the primary agent runtime you actually use. Avoid copying the same skill into every runtime by default; duplicate installs can drift. Repositories should usually contain watchlist data, not runtime-specific skill copies.

AgentSkills-compatible runtimes such as Gemini CLI, Kilo, OpenClaw, and Hermes should use the same skill directory when possible. Avoid vendor-specific copies unless a runtime requires a different install location. Track real runtime smoke results in `docs/runtime-smoke.md`.

## Installation For Codex

Pass the skill directory URL, not only the repository root:

```text
$skill-installer install https://github.com/dd3ok/WATCHLIST.md/tree/main/.agents/skills/watchlist-md
```

Restart Codex after installation so the new skill is detected.

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

## Installation For ChatGPT / OpenAI Skills

OpenAI skill surfaces do not automatically sync with Codex or Claude Code installs. When uploading a skill bundle as a zip, package one top-level skill directory:

```bash
cd .agents/skills
zip -r watchlist-md-skill.zip watchlist-md
```

Upload the resulting zip through the OpenAI skill management UI or workflow you use. The archive should contain `watchlist-md/SKILL.md` at its top-level folder. The uploaded skill bundle is Python-free.

Repository-level `tools/validate_watchlist.py` and `evals/` are source-repository maintainer checks only. Do not package runtime `scripts/` validators; the runtime bundle intentionally has no validator script.

Test after upload:

```text
/watchlist-md
Add this to WATCHLIST.md. Check GitHub Actions results today at 17:00.
```

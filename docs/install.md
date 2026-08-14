# Installation

Install or copy the directory whose root contains `SKILL.md`:

```text
.agents/skills/watchlist-md
```

Do not install the repository root. Repository tests and maintainer tools are not
runtime dependencies.

## Codex installer

```text
$skill-installer install https://github.com/dd3ok/WATCHLIST.md/tree/main/.agents/skills/watchlist-md
```

Use a full commit SHA instead of `main` when recording reproducible runtime-smoke
evidence.

## Manual copy

Copy the complete directory into a skill location documented by the target
runtime. Keep these files together:

```text
watchlist-md/
├── SKILL.md
├── LICENSE.txt
├── agents/openai.yaml
└── assets/WATCHLIST.template.md
```

Avoid installing the same skill name at both workspace and user scope. Inspect
local changes before replacing an existing copy, and preserve a backup outside
the runtime's discovered skill directories when needed.

Discovery or a successful copy is not proof of behavior. Run the cases in
`evals/smoke_cases.json` in a disposable workspace and record only observed
results in `docs/runtime-smoke.md`.

# Installation

This source repository is a starter repo. The installable skill directory is:

```text
.agents/skills/watchlist-md
```

Install or copy the directory whose root contains `SKILL.md`, not the repository
root.

## Installation Philosophy

Install `watchlist-md` in the primary runtime you actually use. Avoid installing
the same skill name at both project and user scope; duplicate copies can drift
and some runtimes expose both instead of merging them.

Repositories should usually contain watchlist data, not extra runtime-specific
skill copies. Documented format/path support is not evidence of runtime behavior;
record real results separately in `docs/runtime-smoke.md`.

## Vendor Paths And Guides

| Runtime | Supported path or flow | Official guide |
| --- | --- | --- |
| Codex | Project `.agents/skills/<name>`; user `$HOME/.agents/skills/<name>` | [Build skills](https://learn.chatgpt.com/docs/build-skills) |
| Claude Code | Project `.claude/skills/<name>`; user `~/.claude/skills/<name>` | [Extend Claude with skills](https://code.claude.com/docs/en/skills) |
| Google Antigravity Agent Skills surface | Workspace `.agents/skills/<name>/SKILL.md`; runtime discovery remains pending | [Agent Skills](https://antigravity.google/docs/skills) |
| Gemini CLI — Gemini Code Assist Standard/Enterprise or paid Gemini/Enterprise Agent Platform API keys only | Workspace `.agents/skills/<name>` or `.gemini/skills/<name>`; user `~/.agents/skills/<name>` or `~/.gemini/skills/<name>` | [Managing Agent Skills](https://geminicli.com/docs/cli/using-agent-skills/) |
| Kilo | Project `.agents/skills/<name>` or `.kilo/skills/<name>`; user `~/.kilo/skills/<name>` | [Skills](https://kilo.ai/docs/customize/skills) |
| OpenClaw | Project-agent `<workspace>/.agents/skills/<name>`; personal-agent `~/.agents/skills/<name>`; managed `~/.openclaw/skills/<name>` | [Skills](https://docs.openclaw.ai/tools/skills) |
| Hermes | User `~/.hermes/skills/<name>` or `hermes skills install` | [Working with Skills](https://hermes-agent.nousresearch.com/docs/guides/work-with-skills) |

Google ended free and Google AI Pro/Ultra Gemini CLI request service on
2026-06-18. Gemini CLI remains available with Gemini Code Assist
Standard/Enterprise or paid Gemini/Enterprise Agent Platform API keys; other
users should follow the Antigravity transition. The
[Antigravity CLI plugin guide](https://antigravity.google/docs/cli-plugins)
documents flat `.agents/skills/*.md` files rather than this directory bundle, so
this repository does not yet claim Antigravity CLI discovery. See the
[official transition notice](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/).

## Installation For Codex

Pass the skill directory URL, not only the repository root:

```text
$skill-installer install https://github.com/dd3ok/WATCHLIST.md/tree/main/.agents/skills/watchlist-md
```

That mutable `main` URL is for ordinary installation. For reproducible smoke
evidence, replace `main` with the exact 40-character commit SHA being recorded.

Codex detects newly installed skills automatically. If the skill does not appear,
restart Codex. Do not keep a second `watchlist-md` at user scope when the project
copy should be authoritative.

The bundle includes `assets/WATCHLIST.template.md`, so an agent can create a new
WATCHLIST.md with only the skill directory installed.

This repository distributes a portable standalone skill source. OpenAI currently
recommends plugins for broader reusable Codex distribution; this repository is
not a Codex plugin.

## Installation For Claude Code

Run these commands from a checkout of this repository. Fresh project install:

```bash
(
set -eu
source=.agents/skills/watchlist-md
target=.claude/skills/watchlist-md
if [ ! -f "${source}/SKILL.md" ]; then
  echo "Run from the WATCHLIST.md repository checkout" >&2
  exit 1
fi
if [ -e "${target}" ]; then
  echo "Target already exists; use the update procedure" >&2
  exit 1
fi
mkdir -p .claude/skills
cp -R "${source}" "${target}"
test -f "${target}/SKILL.md"
)
```

Before updating, inspect whether the installed copy has local changes:

```bash
(
source=.agents/skills/watchlist-md
target=.claude/skills/watchlist-md
if [ ! -f "${source}/SKILL.md" ] || [ ! -d "${target}" ]; then
  echo "Source or existing target is missing" >&2
  exit 1
fi
diff -ru "${target}" "${source}" || true
)
```

If the differences are expected, preserve the old copy before replacing it:

```bash
(
set -eu
source=.agents/skills/watchlist-md
target=.claude/skills/watchlist-md
backup_root="$HOME/.watchlist-md-skill-backups/claude"
staging_root="$HOME/.cache/watchlist-md/claude-staging"
if [ ! -f "${source}/SKILL.md" ] || [ ! -d "${target}" ]; then
  echo "Source or existing target is missing" >&2
  exit 1
fi
mkdir -p "${backup_root}" "${staging_root}"
stamp=$(date +%Y%m%d%H%M%S)
backup="${backup_root}/watchlist-md-${stamp}-$$"
if [ -e "${backup}" ]; then
  echo "Backup target collision: ${backup}" >&2
  exit 1
fi
staging_parent=$(mktemp -d "${staging_root}/watchlist-md.XXXXXX")
staging="${staging_parent}/watchlist-md"
cp -R "${source}" "${staging}"
test -f "${staging}/SKILL.md"
mv "${target}" "${backup}"
if mv "${staging}" "${target}"; then
  rmdir "${staging_parent}"
  echo "Previous install: ${backup}"
else
  mv "${backup}" "${target}"
  exit 1
fi
)
```

For a fresh personal install, require that the target does not already exist:

```bash
(
set -eu
source=.agents/skills/watchlist-md
target="$HOME/.claude/skills/watchlist-md"
if [ ! -f "${source}/SKILL.md" ]; then
  echo "Run from the WATCHLIST.md repository checkout" >&2
  exit 1
fi
if [ -e "${target}" ]; then
  echo "Target already exists; use the update procedure" >&2
  exit 1
fi
mkdir -p "$HOME/.claude/skills"
cp -R "${source}" "${target}"
test -f "${target}/SKILL.md"
)
```

For a personal update, use the staged procedure above with that `target`.
Backups and staging stay outside both the repository and the discovered `skills/`
directory, so they cannot be committed accidentally or become a second active
skill.

The `agents/openai.yaml` file is Codex UI metadata and is safe if copied with the
directory. Claude Code watches existing skill directories for changes. Restart
only if the top-level skills directory did not exist when the session started.

## Installation For Google Antigravity Agent Skills

The general Agent Skills guide documents the directory layout used by the
existing `.agents/skills/watchlist-md` copy. The Antigravity CLI plugin guide
documents a different flat-file layout, so do not assume this bundle is
discovered by every Antigravity surface. Use that surface's skill list or UI to
collect `D` evidence before testing behavior, and do not copy to a guessed global
path.

Antigravity runtime behavior remains `pending` until the discovery, explicit
invocation, behavior, and routing checks in `docs/runtime-smoke.md` are recorded.

## Installation For Gemini CLI

This section applies only to Gemini Code Assist Standard/Enterprise users or
paid Gemini/Enterprise Agent Platform API-key users who retain Gemini CLI service.

Workspace skills load only from a trusted workspace. If discovery fails:

1. Run `/permissions trust <workspace-path>` and restart if requested.
2. Run `/skills list` to verify `watchlist-md` is discovered.
3. Use `/skills reload` after local changes.
4. Approve the activation prompt when Gemini calls `activate_skill`.

For local development, link the complete skill directory:

```bash
gemini skills link .agents/skills/watchlist-md --scope workspace
```

Discovery or a successful link is not a runtime behavior smoke pass.

## Installation For Kilo And OpenClaw

Kilo can discover `.agents/skills/watchlist-md` from a repository checkout and
reload changes with `/reload`.

OpenClaw discovers this path only when the checkout is the configured agent
workspace. Otherwise copy the complete directory to the appropriate personal or
managed path from the vendor table. Verify with `openclaw skills list`; a copied
directory alone is not a behavior smoke pass.

Keep `SKILL.md`, `assets/`, `references/`, and `LICENSE.txt` together.

## Installation For Hermes

Hermes uses its own user skill directory:

```bash
(
set -eu
source=.agents/skills/watchlist-md
target="$HOME/.hermes/skills/watchlist-md"
if [ ! -f "${source}/SKILL.md" ]; then
  echo "Run from the WATCHLIST.md repository checkout" >&2
  exit 1
fi
if [ -e "${target}" ]; then
  echo "Target already exists; inspect or use the Hermes installer" >&2
  exit 1
fi
mkdir -p ~/.hermes/skills
cp -R "${source}" "${target}"
test -f "${target}/SKILL.md"
)
```

Hermes also supports `hermes skills install` for hub and direct HTTP(S)
`SKILL.md` sources. Start a new session after copying and verify with
`hermes skills list`; do not treat installation as a behavior smoke pass.
For updates, prefer the Hermes installer or inspect and back up the existing
target outside `~/.hermes/skills` before replacement.

## Standalone Zip Packaging

This repository defines a standalone zip shape for consumers that accept skill
directories as archives. It is not a claim that every vendor accepts zip upload.

Build from a committed tree so untracked files cannot leak into the archive:

```bash
(
set -euo pipefail
python_check='import sys; raise SystemExit(sys.version_info < (3, 8))'
if python3 -c "${python_check}" >/dev/null 2>&1; then
  python_cmd=python3
elif python -c "${python_check}" >/dev/null 2>&1; then
  python_cmd=python
else
  echo "Python 3.8 or newer is required" >&2
  exit 1
fi
archive_ref=$(git rev-parse HEAD)
archive_mtime=$(git show -s --format=%cI "${archive_ref}")
archive_check_tree=$(mktemp -d)
mkdir "${archive_check_tree}/evals"
trap 'rm -f "${archive_check_tree}/evals/check_skill_package.py" "${archive_check_tree}/evals/runtime_package_files.txt"; rmdir "${archive_check_tree}/evals" "${archive_check_tree}"' EXIT
git show "${archive_ref}:evals/check_skill_package.py" \
  >"${archive_check_tree}/evals/check_skill_package.py"
git show "${archive_ref}:evals/runtime_package_files.txt" \
  >"${archive_check_tree}/evals/runtime_package_files.txt"
TZ=UTC git -c core.autocrlf=false -c core.eol=lf archive \
  --format=zip --prefix=watchlist-md/ --mtime="${archive_mtime}" \
  --output=watchlist-md-skill.zip \
  "${archive_ref}:.agents/skills/watchlist-md"
"${python_cmd}" "${archive_check_tree}/evals/check_skill_package.py" \
  --archive watchlist-md-skill.zip
rm -f "${archive_check_tree}/evals/check_skill_package.py" \
  "${archive_check_tree}/evals/runtime_package_files.txt"
rmdir "${archive_check_tree}/evals" "${archive_check_tree}"
trap - EXIT
)
```

This recipe requires Git 2.40 or newer with `git archive --mtime` support. The
explicit commit time, UTC process time zone, and disabled checkout line-ending
conversion keep committed file bytes and repeated output stable with the same
Git/platform toolchain. A subtree expression resolves to a tree object, so
omitting `--mtime` would stamp entries with the current time; omitting `TZ=UTC`
would use the host time zone; omitting `core.autocrlf=false` can rewrite line
endings. Git ZIP metadata and compression can still differ across other Git
builds, so cross-toolchain byte identity is not promised. Run the fenced recipe
in Bash (Git Bash on Windows); a native PowerShell translation must set
`$env:TZ = 'UTC'` for the archive command and restore the previous value afterward.
The checker and manifest are also read from the pinned commit, so concurrent
working-tree or `HEAD` changes cannot silently change the validation contract.

The archive contains `watchlist-md/SKILL.md` and `watchlist-md/LICENSE.txt` under
one top-level folder and remains Python-free. Repository `tools/`, `evals/`,
maintainer docs, transcripts, screenshots, and raw logs must not be packaged.
In particular, `tools/validate_watchlist.py` is a repository-side maintainer tool,
not runtime skill content.

If a chosen surface accepts the bundle, test explicit invocation using that
surface's documented syntax. For Codex:

```text
$watchlist-md Add this to WATCHLIST.md. Check GitHub Actions results today at 17:00.
```

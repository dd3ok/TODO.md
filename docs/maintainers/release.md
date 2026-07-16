# Release Checklist

Use this checklist for repository maintenance PRs and for publishing a GitHub
release. It is maintainer-only documentation and must stay outside the
installable runtime skill.

## Runtime Boundary

The installable skill bundle is intentionally Python-free. It contains exactly:

```text
watchlist-md/SKILL.md
watchlist-md/LICENSE.txt
watchlist-md/agents/openai.yaml
watchlist-md/assets/WATCHLIST.template.md
watchlist-md/references/format.md
watchlist-md/references/lifecycle.md
watchlist-md/references/safety.md
```

`evals/runtime_package_files.txt` is the machine-readable source of truth;
`evals/check_skill_package.py` enforces it as an exact allowlist. Tests require
this displayed list and both README lists to match the manifest.

Repository-only files must stay outside `.agents/skills/watchlist-md/`: `tools/`,
`evals/`, `.github/`, `.watchlist/`, `docs/`, examples, smoke notes, release notes,
transcripts, screenshots, and raw logs.

## Pull Request Checks

Run:

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
PYTHONDONTWRITEBYTECODE=1 "${python_cmd}" -m unittest discover -s evals -p 'test_*.py'
"${python_cmd}" evals/check_policy_markers.py
"${python_cmd}" evals/check_semantic_cases.py
"${python_cmd}" evals/check_skill_package.py
"${python_cmd}" evals/check_release_metadata.py
"${python_cmd}" evals/check_watchlist.py examples/WATCHLIST.example.md --strict-format --strict-safety --require-archive-section
"${python_cmd}" tools/validate_watchlist.py .agents/skills/watchlist-md/assets/WATCHLIST.template.md --strict-format --strict-safety --require-archive-section
)
```

Confirm no unintended runtime bundle change against the PR base and local tree:

```bash
git fetch origin main
git diff --name-only origin/main...HEAD -- .agents/skills/watchlist-md
git diff --name-only -- .agents/skills/watchlist-md
```

If the PR targets a branch other than `main`, replace `origin/main` with the
actual base ref.

## Prepare Release Metadata

Do not describe a version as released until its tag and GitHub Release exist.

1. Choose the version before the release PR is merged.
2. Move every shipped entry from `## [Unreleased]` into the new version heading.
3. Leave exactly one empty `## [Unreleased]` heading above released versions.
4. Set `VERSION` to the first released heading and use the actual publication
   date in `YYYY-MM-DD` format.
5. Do not reuse an existing local tag, remote tag, or GitHub Release.

Run the release-ready metadata check:

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
"${python_cmd}" evals/check_release_metadata.py --release
version=$(cat VERSION)
git fetch origin --tags
if git show-ref --verify --quiet "refs/tags/v${version}"; then
  echo "Local tag v${version} already exists" >&2
  exit 1
fi
if ! remote_tag=$(git ls-remote --tags origin "refs/tags/v${version}"); then
  echo "Could not query remote tags" >&2
  exit 1
fi
if [ -n "${remote_tag}" ]; then
  echo "Remote tag v${version} already exists" >&2
  exit 1
fi
set +e
release_probe=$(gh api --include \
  "repos/dd3ok/WATCHLIST.md/releases/tags/v${version}" 2>&1)
set -e
http_status=$(printf '%s\n' "${release_probe}" | \
  sed -nE 's/^HTTP[^ ]* ([0-9]{3}).*/\1/p' | tail -n 1)
case "${http_status}" in
  404) ;;
  200)
    echo "GitHub Release v${version} already exists" >&2
    exit 1
    ;;
  *)
    printf '%s\n' "${release_probe}" >&2
    exit 1
    ;;
esac
)
```

Do not tag an older release-preparation commit after additional `Unreleased`
changes have accumulated. Consolidate the actual shipped changes first, merge
the release PR, and tag the resulting verified `main` commit.

## Build The Release Archive

Build from the exact merged commit, not from an untracked working directory:

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
git fetch origin main --tags
release_sha=$(git rev-parse origin/main)
test "$(git rev-parse HEAD)" = "${release_sha}"
test -z "$(git status --porcelain)"
version=$(git show "${release_sha}:VERSION")
release_mtime=$(git show -s --format=%cI "${release_sha}")
release_tree=$(mktemp -d)
mkdir "${release_tree}/evals"
trap 'rm -f "${release_tree}/VERSION" "${release_tree}/CHANGELOG.md" "${release_tree}/evals/check_release_metadata.py" "${release_tree}/evals/check_skill_package.py" "${release_tree}/evals/runtime_package_files.txt"; rmdir "${release_tree}/evals" "${release_tree}"' EXIT
git show "${release_sha}:VERSION" >"${release_tree}/VERSION"
git show "${release_sha}:CHANGELOG.md" >"${release_tree}/CHANGELOG.md"
git show "${release_sha}:evals/check_release_metadata.py" \
  >"${release_tree}/evals/check_release_metadata.py"
git show "${release_sha}:evals/check_skill_package.py" \
  >"${release_tree}/evals/check_skill_package.py"
git show "${release_sha}:evals/runtime_package_files.txt" \
  >"${release_tree}/evals/runtime_package_files.txt"
"${python_cmd}" "${release_tree}/evals/check_release_metadata.py" "${release_tree}" --release
mkdir -p dist
artifact="dist/watchlist-md-skill-v${version}.zip"
TZ=UTC git -c core.autocrlf=false -c core.eol=lf archive \
  --format=zip --prefix=watchlist-md/ --mtime="${release_mtime}" \
  --output="${artifact}" "${release_sha}:.agents/skills/watchlist-md"
"${python_cmd}" "${release_tree}/evals/check_skill_package.py" --archive "${artifact}"
sha256sum "${artifact}"
rm -f "${release_tree}/VERSION" "${release_tree}/CHANGELOG.md" \
  "${release_tree}/evals/check_release_metadata.py" \
  "${release_tree}/evals/check_skill_package.py" \
  "${release_tree}/evals/runtime_package_files.txt"
rmdir "${release_tree}/evals" "${release_tree}"
trap - EXIT
)
```

The archive must contain one top-level `watchlist-md/` directory and the exact
seven runtime files. This recipe requires Git 2.40 or newer with `git archive
--mtime` support. Pinning the entry time to the source commit and Git's process
time zone to UTC, and checkout line-ending conversion off makes committed file
bytes and repeated builds stable with the same Git/platform toolchain. It does
not promise identical bytes across every Git build or compression implementation.
Record the release OS, `git --version`, and SHA-256 with the release evidence.
Run the fenced recipe in Bash (Git Bash on Windows); a native PowerShell
translation must set `$env:TZ = 'UTC'` for the archive command, restore the
previous value afterward, and use `Get-FileHash -Algorithm SHA256` instead of
`sha256sum`.

## Publish And Verify

Only publish after required `main` CI checks succeed for `release_sha`:

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
git fetch origin main --tags
release_sha=$(git rev-parse origin/main)
version=$(git show "${release_sha}:VERSION")
release_mtime=$(git show -s --format=%cI "${release_sha}")
artifact="dist/watchlist-md-skill-v${version}.zip"
test "$(git rev-parse HEAD)" = "${release_sha}"
test -z "$(git status --porcelain)"
release_tree=$(mktemp -d)
mkdir "${release_tree}/evals"
trap 'rm -f "${release_tree}/VERSION" "${release_tree}/CHANGELOG.md" "${release_tree}/evals/check_release_metadata.py" "${release_tree}/evals/check_skill_package.py" "${release_tree}/evals/runtime_package_files.txt"; rmdir "${release_tree}/evals" "${release_tree}"' EXIT
git show "${release_sha}:VERSION" >"${release_tree}/VERSION"
git show "${release_sha}:CHANGELOG.md" >"${release_tree}/CHANGELOG.md"
git show "${release_sha}:evals/check_release_metadata.py" \
  >"${release_tree}/evals/check_release_metadata.py"
git show "${release_sha}:evals/check_skill_package.py" \
  >"${release_tree}/evals/check_skill_package.py"
git show "${release_sha}:evals/runtime_package_files.txt" \
  >"${release_tree}/evals/runtime_package_files.txt"
"${python_cmd}" "${release_tree}/evals/check_release_metadata.py" "${release_tree}" --release
mkdir -p dist
TZ=UTC git -c core.autocrlf=false -c core.eol=lf archive \
  --format=zip --prefix=watchlist-md/ --mtime="${release_mtime}" \
  --output="${artifact}" "${release_sha}:.agents/skills/watchlist-md"
"${python_cmd}" "${release_tree}/evals/check_skill_package.py" --archive "${artifact}"
sha256sum "${artifact}"
run_id=$(gh run list --repo dd3ok/WATCHLIST.md --workflow CI --event push \
  --commit "${release_sha}" --limit 1 --json databaseId \
  --jq '.[0].databaseId // empty')
if [ -z "${run_id}" ]; then
  echo "No main CI run found for ${release_sha}" >&2
  exit 1
fi
gh run watch "${run_id}" --repo dd3ok/WATCHLIST.md --exit-status
gh release create "v${version}" "${artifact}" \
  --repo dd3ok/WATCHLIST.md \
  --target "${release_sha}" \
  --title "v${version}" \
  --generate-notes
git fetch origin --tags
test "$(git rev-list -n 1 "v${version}")" = "${release_sha}"
gh release view "v${version}" --repo dd3ok/WATCHLIST.md \
  --json tagName,publishedAt,targetCommitish,assets,url
rm -f "${release_tree}/VERSION" "${release_tree}/CHANGELOG.md" \
  "${release_tree}/evals/check_release_metadata.py" \
  "${release_tree}/evals/check_skill_package.py" \
  "${release_tree}/evals/runtime_package_files.txt"
rmdir "${release_tree}/evals" "${release_tree}"
trap - EXIT
)
```

Verify the uploaded asset name, SHA-256 digest, tag target, release URL, release
OS, and Git version. If any check fails, stop and report it; do not move or
recreate a published tag silently.

# Changelog

## [Unreleased]

### Changed

- Adopted a single schema-v2 contract.
- Reduced required item fields to status, due time, creation time, source, action,
  and completion condition; optional fields are written only when informative.
- Replaced `snoozed` with rescheduling that preserves an active item's status and
  removed automatic archive-suggestion policy.
- Consolidated runtime instructions into one source of truth and reduced the
  installable bundle from seven files to four.
- Reworked validator tests to call the pure validation interface directly; only
  CLI behavior uses subprocess smoke tests.
- Reduced CI to the current Python release because Python is maintainer tooling,
  not a runtime dependency.
- Clarified that a bare `WATCHLIST.md` mention names the format rather than the
  shared root path, and required checking both standard targets before selection.
- Added explicit manual-smoke setup states and a small exact-package-boundary
  regression test.
- Updated the CI Python setup action to its current major version without adding
  a version matrix.
- Standardized item headings on the ASCII `WL-YYYYMMDD-NNN - Title` form and
  rejected empty structured optional fields.
- Added dependency-free contract tests for skill frontmatter and UI metadata,
  plus manual smoke cases for state-preserving reschedule and named deletion.
- Recorded a sandboxed local core runtime run separately from the still-pending
  full manual corpus.

### Fixed

- Fixed real Codex runtime cases that created a root watchlist or bypassed a
  duplicate-ID private watchlist after misreading a bare filename as path intent.
- Moved schema checks ahead of file and Git-metadata changes.
- Separated current pending runtime evidence from a non-reproducible historical
  observation so deterministic tests cannot be mistaken for agent-runtime proof.
- Narrowed the skill description to explicit WATCHLIST intent after a real
  runtime run showed that generic completion/archive wording caused a false
  invocation.
- Explicitly excluded generic task lifecycle requests after an independent
  runtime rerun reproduced the false invocation from repository context.
- Prevented an item's fields from leaking across the next `##` section boundary
  during validation.
- Clarified manual private-file fixtures as untracked and ignored, and removed an
  ambiguous today-only prompt from the full-review runtime case.
- Made an existing file's timezone authoritative for relative calendar terms,
  item dates, and review buckets, with no silent host-timezone fallback.
- Recorded exact runtime corpus IDs separately from ad hoc discovery and routing
  checks.
- Made the private-add runtime case independent of the execution time of day.

### Removed

- Removed the legacy `mode` field, `automation: none`, relaxed/strict validator
  modes, field-order enforcement, and required empty fields.
- Removed standalone ZIP packaging and its archive-format security checker.
- Removed duplicated JSON/YAML/CSV semantic corpora and the linter that validated
  their declarations without running an agent.
- Removed exact-phrase policy checks, release-metadata machinery, duplicate
  template/example files, and unverified vendor-specific installation recipes.

### Security

- Preserved unique-ID, read-only review, safe-pointer, authority, and sensitive
  data rules in the smaller runtime contract.
- Kept deterministic checks that reject credential patterns and tokenized URLs.

## [0.4.2] - 2026-07-17

### Added

- Added deterministic regression coverage for malformed IDs/headings, fenced
  pseudo-structure, duplicate sections, BOM/invalid UTF-8 input, release metadata,
  package contents, and template/example drift.
- Added lifecycle contracts for snooze, block, reopen, narrow deletion, archive
  age precedence, and read-only handling of sensitive data.
- Added a vendor runtime smoke matrix that separates discovery, invocation,
  behavior, and routing evidence.
- Added the MIT notice to the exact seven-file standalone runtime bundle.

### Changed

- Clarified storage selection so a bare `WATCHLIST.md` mention does not create
  shared state without team intent, while qualified paths remain authoritative.
- Clarified list-only redaction authority, named-item deletion, template timezone
  replacement, archive age calculation, and user-reported completion evidence.
- Aligned Codex, Claude Code, Google Antigravity, supported Gemini CLI, Kilo,
  OpenClaw, and Hermes installation guidance with official vendor documentation.
- Made the runtime bundle Python-free and moved deterministic validators and
  canonical self-check maintenance to repository tooling.
- Made release archives reproducible from a verified commit and added strict
  release-readiness metadata and archive-shape checks.

### Fixed

- Rejected invalid calendar IDs, sequence `000`, near-miss headings, hidden
  pseudo-items, duplicated sections, unknown schema-like keys, and invalid file
  encoding without tracebacks.
- Hardened the dependency-free semantic linter against unknown keys, duplicate
  nested YAML keys, invalid root/types, and date-only `fixed_now` values.
- Replaced destructive copy-update instructions and ambiguous historical-tag
  release steps with backup-first and exact-commit procedures.
- Marked the legacy top-level `mode` field as ignored and deprecated instead of
  silently accepting it.

## [0.4.1] - 2026-05-27

### Changed

- Clarified that stable WATCHLIST field keys and enum values stay in English
  for localized entries while titles and free-text values may be localized.
- Lightened README safety and retention guidance without changing runtime
  behavior.

### Fixed

- Scoped Korean localized schema-token regression checks to Korean semantic
  cases so future locales can add their own localized-token rules.

## [0.4.0] - 2026-05-26

### Added

- Semantic storage cases for root/shared, `.watchlist`/private, and ambiguous
  split-watchlist scenarios.
- Negative trigger cases for scheduler/reminder requests that do not explicitly
  ask for WATCHLIST.md recording.
- Bundled standalone validator guidance for installed skill directory checks.

### Changed

- Clarified storage selection around explicit user intent, existing project
  convention, and shared/private scope.
- Slimmed runtime instructions and kept lifecycle/safety details in references.
- Updated README guidance to recommend installing the skill in the primary agent
  runtime and keeping repositories focused on watchlist data.
- Moved starter watchlist content to `examples/WATCHLIST.example.md` and kept
  generated `.watchlist/WATCHLIST.md` files ignored by default.

## [0.3.0] - 2026-05-15

### Added

- Optional `archive_policy` top-level field with `manual` and `suggest` modes.
- Optional `archive_after_days` field for review-time archive suggestion thresholds.
- Semantic cases for archive suggestions, manual archive policy behavior, list-only no-mutation review, and duplicate ID collision handling.
- Validator checks for archive policy fields.
- Concurrent edit and duplicate ID collision policy.

### Changed

- Clarified that list-only reviews must not mutate WATCHLIST.md.
- Clarified that duplicate ID collisions must stop and report instead of silently rewriting unrelated items.
- Updated starter/template WATCHLIST files to use `archive_policy: manual`.

## [0.2.0] - 2026-05-15

### Added

- Strict validator options for format checks, safety scanning, archive-section validation, and JSON output.
- Release metadata and policy marker checkers for CI and local verification.
- OpenAI/Codex metadata guardrails for notes-only behavior, scheduler boundaries, and sensitive-data handling.
- Quickstart, non-goals, contributing, security, and pull request guidance.
- Deterministic semantic case fixtures and checker for trigger and operation contracts.

### Changed

- Hardened WATCHLIST validation while keeping the default validator mode backward-compatible.
- Expanded CI coverage for release metadata, policy drift, and stricter starter/template validation.
- Promoted strict safety findings to `error` severity in JSON output and added strict format checks for canonical starter/template validation.

### Security

- Added strict safety detection for likely secrets, authorization headers, private keys, signed URLs, tokenized URLs, and raw private excerpts in WATCHLIST item fields.
- Added redaction guidance when sensitive content is detected.

## [0.1.0] - 2026-05-14

### Added

- Initial `watchlist-md` skill packaging for Codex-compatible installation.
- Bundled WATCHLIST template for creating repository-local follow-up notes.
- Repository starter `.watchlist/WATCHLIST.md` artifact for immediate inspection.
- Validator and eval materials for WATCHLIST.md structure and prompt regressions.
- CI workflow coverage for validation and eval checks.
- README installation, usage, validation, and safety documentation.

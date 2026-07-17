# Changelog

## [Unreleased]

### Fixed

- Pinned standalone ZIP entry times, process time zone, and line-ending settings
  so the same Git/platform toolchain produces committed bytes and a stable
  SHA-256 across invocation times and host configurations, with toolchain limits
  documented.
- Rejected unsafe or normalized ZIP paths, unexpected directories, encrypted or
  oversized entries, symlinks, other non-regular file types, and corrupt payloads
  or conflicting local-header metadata during archive validation. Canonical
  layout checks also reject ambiguous prefixes, gaps, hidden records, trailing
  data, unsafe permissions, unsupported extraction versions, timestamp/header
  conflicts, and metadata that understates actual deflated content. Untrusted
  diagnostic fields are escaped and bounded. Temporary source packaging now
  rejects symbolic links, reparse points, special files, unexpected paths, and
  oversized inputs before reading file payloads.

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

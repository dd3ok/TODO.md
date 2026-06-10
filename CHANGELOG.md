# Changelog

## [0.4.2] - 2026-06-10

### Changed

- Clarified generated WATCHLIST file ownership and storage conventions for
  private `.watchlist/WATCHLIST.md` data versus explicit shared root
  `WATCHLIST.md` files.
- Slimmed the runtime `SKILL.md` body while keeping trigger, storage, safety, and
  validation guardrails in the hot path.
- Simplified repository-level validation by delegating `evals/check_watchlist.py`
  to the bundled skill validator as the single source of validation rules.
- Updated OpenAI skill packaging guidance to keep the uploaded zip shaped around
  one top-level `watchlist-md/` skill directory.
- Removed the unused alternate owner value before publishing 0.4.2.

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

# Changelog

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

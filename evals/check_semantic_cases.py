#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "evals" / "cases"
FIXTURES_DIR = ROOT / "evals" / "fixtures"
PROMPTS_CSV = ROOT / "evals" / "prompts.csv"
SELF_CHECKS = ROOT / "evals" / "self_checks.yaml"
CHECK_WATCHLIST = ROOT / "evals" / "check_watchlist.py"

AUTONOMOUS_REMINDER_FORBIDDEN = {
    "I'll remind you",
    "I will remind you",
    "I'll check later",
    "I will check later",
    "자동으로 알려드릴게요",
    "제가 나중에 확인할게요",
}
REQUIRED_CASE_KEYS = {
    "id",
    "prompt",
    "locale",
    "fixed_now",
    "fixture",
    "should_trigger_skill",
    "expected",
}
SUPPORTED_OPERATIONS = {
    "add_item",
    "archive_items",
    "complete_item",
    "delete_item",
    "drop_item",
    "refuse_secret_storage",
    "review_items",
}
SUPPORTED_STORAGE_TARGETS = {
    "WATCHLIST.md",
    ".watchlist/WATCHLIST.md",
    "$HOME/.watchlist/WATCHLIST.md",
    "explicit_user_path",
    "clarify",
}


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def load_prompts() -> dict[str, dict[str, str]]:
    with PROMPTS_CSV.open(encoding="utf-8", newline="") as fh:
        return {row["id"]: row for row in csv.DictReader(fh)}


def parse_yaml_scalar(value: str) -> Optional[str]:
    value = value.strip()
    if not value:
        return ""
    if value[0] in {"'", '"'}:
        quote = value[0]
        if len(value) < 2 or value[-1] != quote:
            return None
        return value[1:-1]
    return value


def parse_self_checks(text: str) -> dict[str, dict[str, Optional[str]]]:
    cases: dict[str, dict[str, Optional[str]]] = {}
    for match in re.finditer(
        r"^\s+- id: (?P<id>[^\s]+)\s*\n(?P<body>.*?)(?=^\s+- id: |\Z)",
        text,
        flags=re.M | re.S,
    ):
        body = match.group("body")
        prompt = None
        prompt_match = re.search(r"^\s+prompt:\s*(?P<prompt>.*?)\s*$", body, flags=re.M)
        if prompt_match:
            prompt = parse_yaml_scalar(prompt_match.group("prompt"))
        cases[match.group("id")] = {"prompt": prompt}
    return cases


def load_self_checks() -> dict[str, dict[str, Optional[str]]]:
    return parse_self_checks(SELF_CHECKS.read_text(encoding="utf-8"))


def validate_iso_timestamp(value: str, case_id: str, errors: list[str], field: str) -> None:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{case_id}: {field} is not ISO-8601: {value}")


def resolve_fixture_path(fixture: str, case_id: str, errors: list[str]) -> Optional[Path]:
    try:
        path = (FIXTURES_DIR / fixture).resolve()
        path.relative_to(FIXTURES_DIR.resolve())
    except ValueError:
        errors.append(f"{case_id}: fixture must stay under evals/fixtures: {fixture}")
        return None
    if not path.is_file():
        errors.append(f"{case_id}: fixture not found: {fixture}")
        return None
    return path


def validate_fixture(fixture: str, case_id: str, errors: list[str]) -> str:
    path = resolve_fixture_path(fixture, case_id, errors)
    if path is None:
        return ""

    result = subprocess.run(
        [
            sys.executable,
            str(CHECK_WATCHLIST),
            str(path),
            "--strict-format",
            "--strict-safety",
            "--require-archive-section",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        errors.append(
            f"{case_id}: fixture failed WATCHLIST validation: {fixture}\n"
            f"{result.stderr}{result.stdout}"
        )
    return path.read_text(encoding="utf-8")


def require_keys(
    obj: dict[str, object],
    keys: set[str],
    case_id: str,
    errors: list[str],
    path: str,
) -> None:
    missing = sorted(keys - obj.keys())
    if missing:
        errors.append(f"{case_id}: missing {path} key(s): {', '.join(missing)}")


def require_item_in_fixture(
    expected: dict[str, object],
    fixture_text: str,
    case_id: str,
    errors: list[str],
) -> None:
    item_id = str(expected.get("item_id", ""))
    if not item_id.startswith("WL-"):
        errors.append(f"{case_id}: item_id must start with WL-")
        return
    if fixture_text and not re.search(rf"^### {re.escape(item_id)}\b", fixture_text, flags=re.M):
        errors.append(f"{case_id}: fixture does not contain item_id {item_id}")


def validate_add_item(
    case_id: str,
    expected: dict[str, object],
    errors: list[str],
) -> None:
    require_keys(
        expected,
        {"operation", "status", "due_at", "scheduler", "required_fields", "forbidden_response_substrings"},
        case_id,
        errors,
        "expected",
    )
    if expected.get("status") != "open":
        errors.append(f"{case_id}: add_item status must be open")
    if expected.get("scheduler") != "none":
        errors.append(f"{case_id}: add_item scheduler must be none")
    due_at = str(expected.get("due_at", ""))
    if due_at != "unscheduled":
        validate_iso_timestamp(due_at, case_id, errors, "expected.due_at")

    required_fields = set(expected.get("required_fields", []))
    for field in ["source", "trigger", "action", "done_when"]:
        if field not in required_fields:
            errors.append(f"{case_id}: add_item required_fields must include {field}")

    forbidden = set(expected.get("forbidden_response_substrings", []))
    missing_forbidden = sorted(AUTONOMOUS_REMINDER_FORBIDDEN - forbidden)
    if missing_forbidden:
        errors.append(
            f"{case_id}: add_item forbidden_response_substrings missing "
            f"{', '.join(missing_forbidden)}"
        )

    if "on_duplicate_id" in expected:
        if expected.get("must_reread_before_write") is not True:
            errors.append(
                f"{case_id}: add_item collision contract must set "
                "must_reread_before_write=true"
            )
        if expected.get("must_avoid_existing_ids") is not True:
            errors.append(
                f"{case_id}: add_item collision contract must set "
                "must_avoid_existing_ids=true"
            )
        if expected.get("on_duplicate_id") != "stop_and_report":
            errors.append(
                f"{case_id}: add_item collision contract must set "
                "on_duplicate_id=stop_and_report"
            )
        must_not = set(expected.get("must_not", []))
        for forbidden_operation in ["overwrite_existing_item", "rewrite_unrelated_items"]:
            if forbidden_operation not in must_not:
                errors.append(
                    f"{case_id}: add_item collision contract must_not must include "
                    f"{forbidden_operation}"
                )


def validate_storage_contract(
    case_id: str,
    case: dict[str, object],
    expected: dict[str, object],
    errors: list[str],
) -> None:
    storage = expected.get("storage")
    if storage is None:
        return
    if not isinstance(storage, dict):
        errors.append(f"{case_id}: expected.storage must be an object")
        return

    require_keys(storage, {"target", "scope", "must_not"}, case_id, errors, "expected.storage")

    target = storage.get("target")
    if target not in SUPPORTED_STORAGE_TARGETS:
        errors.append(f"{case_id}: expected.storage.target is unsupported: {target}")

    scope = storage.get("scope")
    if scope not in {"shared_project", "local_private", "personal_repo_independent", "ambiguous"}:
        errors.append(f"{case_id}: expected.storage.scope is unsupported: {scope}")

    workspace = case.get("workspace", {})
    if workspace and not isinstance(workspace, dict):
        errors.append(f"{case_id}: workspace must be an object")
        return

    existing_paths = set(workspace.get("existing_paths", [])) if isinstance(workspace, dict) else set()
    ignored_paths = set(workspace.get("ignored_paths", [])) if isinstance(workspace, dict) else set()
    must_not = set(storage.get("must_not", []))

    if target == "WATCHLIST.md":
        if scope != "shared_project":
            errors.append(f"{case_id}: root WATCHLIST target must use shared_project scope")
        if "WATCHLIST.md" not in existing_paths:
            errors.append(f"{case_id}: root WATCHLIST target case must declare existing root path")
        if ".watchlist/WATCHLIST.md" in ignored_paths and "write_ignored_dot_watchlist" not in must_not:
            errors.append(
                f"{case_id}: root WATCHLIST target with ignored .watchlist must forbid "
                "write_ignored_dot_watchlist"
            )

    if target == ".watchlist/WATCHLIST.md":
        if scope != "local_private":
            errors.append(f"{case_id}: .watchlist target must use local_private scope")
        if "write_shared_state_to_private_watchlist" not in must_not:
            errors.append(
                f"{case_id}: .watchlist target must forbid write_shared_state_to_private_watchlist"
            )

    if target == "$HOME/.watchlist/WATCHLIST.md" and scope != "personal_repo_independent":
        errors.append(f"{case_id}: home WATCHLIST target must use personal_repo_independent scope")

    if target == "clarify":
        if scope != "ambiguous":
            errors.append(f"{case_id}: clarify target must use ambiguous scope")
        for forbidden in ["silently_choose_path", "mutate_before_target_is_clear"]:
            if forbidden not in must_not:
                errors.append(f"{case_id}: clarify storage must_not must include {forbidden}")
        if not {"WATCHLIST.md", ".watchlist/WATCHLIST.md"}.issubset(existing_paths):
            errors.append(f"{case_id}: clarify case must declare both root and .watchlist paths")


def validate_complete_item(
    case_id: str,
    expected: dict[str, object],
    fixture_text: str,
    errors: list[str],
) -> None:
    require_keys(
        expected,
        {"operation", "item_id", "status", "required_updates", "must_not"},
        case_id,
        errors,
        "expected",
    )
    require_item_in_fixture(expected, fixture_text, case_id, errors)
    if expected.get("status") != "done":
        errors.append(f"{case_id}: complete_item status must be done")

    updates = set(expected.get("required_updates", []))
    for field in ["last_checked_at", "result"]:
        if field not in updates:
            errors.append(f"{case_id}: complete_item required_updates must include {field}")

    must_not = set(expected.get("must_not", []))
    if "delete_item" not in must_not:
        errors.append(f"{case_id}: complete_item must_not must include delete_item")


def validate_drop_item(
    case_id: str,
    expected: dict[str, object],
    fixture_text: str,
    errors: list[str],
) -> None:
    require_keys(
        expected,
        {"operation", "item_id", "status", "required_updates", "deletes_item", "preserves_record"},
        case_id,
        errors,
        "expected",
    )
    require_item_in_fixture(expected, fixture_text, case_id, errors)
    if expected.get("status") != "dropped":
        errors.append(f"{case_id}: drop_item status must be dropped")
    if "result" not in set(expected.get("required_updates", [])):
        errors.append(f"{case_id}: drop_item required_updates must include result")
    if expected.get("deletes_item") is not False:
        errors.append(f"{case_id}: drop_item must set deletes_item=false")
    if expected.get("preserves_record") is not True:
        errors.append(f"{case_id}: drop_item must set preserves_record=true")


def validate_delete_item(
    case_id: str,
    expected: dict[str, object],
    fixture_text: str,
    errors: list[str],
) -> None:
    require_keys(
        expected,
        {"operation", "item_id", "explicit_record_removal", "deletes_item", "must_not"},
        case_id,
        errors,
        "expected",
    )
    require_item_in_fixture(expected, fixture_text, case_id, errors)
    if expected.get("explicit_record_removal") is not True:
        errors.append(f"{case_id}: delete_item must set explicit_record_removal=true")
    if expected.get("deletes_item") is not True:
        errors.append(f"{case_id}: delete_item must set deletes_item=true")
    if "rewrite_unrelated_items" not in set(expected.get("must_not", [])):
        errors.append(f"{case_id}: delete_item must_not must include rewrite_unrelated_items")


def validate_archive_items(
    case_id: str,
    expected: dict[str, object],
    errors: list[str],
) -> None:
    require_keys(
        expected,
        {"operation", "explicit_archive_request", "allowed_statuses", "forbidden_statuses"},
        case_id,
        errors,
        "expected",
    )
    if expected.get("explicit_archive_request") is not True:
        errors.append(f"{case_id}: archive_items must set explicit_archive_request=true")
    if set(expected.get("allowed_statuses", [])) != {"done", "dropped"}:
        errors.append(f"{case_id}: archive_items allowed_statuses must be done,dropped")
    forbidden = set(expected.get("forbidden_statuses", []))
    for status in ["open", "snoozed", "blocked"]:
        if status not in forbidden:
            errors.append(f"{case_id}: archive_items forbidden_statuses must include {status}")


def validate_refuse_secret_storage(
    case_id: str,
    expected: dict[str, object],
    errors: list[str],
) -> None:
    require_keys(
        expected,
        {"operation", "stores_secret", "allowed_storage", "must_not"},
        case_id,
        errors,
        "expected",
    )
    if expected.get("stores_secret") is not False:
        errors.append(f"{case_id}: refuse_secret_storage must set stores_secret=false")
    must_not = set(expected.get("must_not", []))
    if not {"store_raw_secret", "store_token"}.intersection(must_not):
        errors.append(
            f"{case_id}: refuse_secret_storage must_not must include "
            "store_raw_secret or store_token"
        )


def validate_review_items(
    case_id: str,
    expected: dict[str, object],
    errors: list[str],
) -> None:
    require_keys(expected, {"operation"}, case_id, errors, "expected")
    if (
        expected.get("must_not_modify_watchlist") is not None
        and expected.get("must_not_modify_watchlist") is not True
    ):
        errors.append(f"{case_id}: review_items must set must_not_modify_watchlist=true")
    if expected.get("mutates_file") is False:
        groups = set(expected.get("groups", []))
        for group in ["overdue", "due today", "upcoming", "unscheduled"]:
            if group not in groups:
                errors.append(f"{case_id}: review_items groups must include {group}")
    if expected.get("should_suggest_archive") is True:
        if expected.get("must_not_modify_watchlist") is not True:
            errors.append(
                f"{case_id}: archive suggestion reviews must set "
                "must_not_modify_watchlist=true"
            )
        if expected.get("archive_after_days") != 30:
            errors.append(f"{case_id}: archive suggestion reviews must set archive_after_days=30")
        if set(expected.get("archive_candidate_statuses", [])) != {"done", "dropped"}:
            errors.append(
                f"{case_id}: archive suggestion candidates must be done,dropped"
            )
        forbidden_statuses = set(expected.get("forbidden_statuses", []))
        for status in ["open", "snoozed", "blocked"]:
            if status not in forbidden_statuses:
                errors.append(
                    f"{case_id}: archive suggestion forbidden_statuses must include {status}"
                )
    if expected.get("requires_explicit_authorization"):
        for key in ["requires_configured_access", "should_not_guess_private_state"]:
            if expected.get(key) is not True:
                errors.append(f"{case_id}: permission review must set {key}=true")


def validate_case(
    case: dict[str, object],
    prompts: dict[str, dict[str, str]],
    self_checks: dict[str, dict[str, Optional[str]]],
    errors: list[str],
) -> None:
    case_id = str(case.get("id", "<missing-id>"))
    require_keys(case, REQUIRED_CASE_KEYS, case_id, errors, "case")
    if case_id == "<missing-id>":
        return

    prompt_row = prompts.get(case_id)
    if prompt_row is None:
        errors.append(f"{case_id}: missing from prompts.csv")
    elif case.get("prompt") != prompt_row["prompt"]:
        errors.append(f"{case_id}: prompt differs from prompts.csv")

    self_check = self_checks.get(case_id)
    if self_check is None:
        errors.append(f"{case_id}: missing from self_checks.yaml")
    elif self_check.get("prompt") is None:
        errors.append(f"{case_id}: prompt could not be parsed from self_checks.yaml")
    elif case.get("prompt") != self_check["prompt"]:
        errors.append(f"{case_id}: prompt differs from self_checks.yaml")

    expected_should_trigger = case.get("should_trigger_skill")
    if prompt_row is not None:
        csv_should_trigger = prompt_row["should_trigger"].strip().lower() == "true"
        if expected_should_trigger != csv_should_trigger:
            errors.append(f"{case_id}: should_trigger_skill differs from prompts.csv")

    if case.get("locale") not in {"ko", "en", "mixed"}:
        errors.append(f"{case_id}: locale must be ko, en, or mixed")

    validate_iso_timestamp(str(case.get("fixed_now", "")), case_id, errors, "fixed_now")
    fixture_text = validate_fixture(str(case.get("fixture", "")), case_id, errors)

    expected = case.get("expected", {})
    if not isinstance(expected, dict):
        errors.append(f"{case_id}: expected must be an object")
        return

    if expected_should_trigger is False:
        if "operation" in expected:
            errors.append(f"{case_id}: should_trigger_skill=false must not define expected.operation")
        if expected.get("must_not_modify_watchlist") is not True:
            errors.append(
                f"{case_id}: should_trigger_skill=false must set "
                "expected.must_not_modify_watchlist=true"
            )
        return

    if expected_should_trigger is not True:
        errors.append(f"{case_id}: should_trigger_skill must be true or false")
        return

    operation = expected.get("operation")
    if not operation:
        errors.append(f"{case_id}: should_trigger_skill=true requires expected.operation")
        return
    if operation not in SUPPORTED_OPERATIONS:
        errors.append(f"{case_id}: unknown operation: {operation}")
        return

    if operation == "add_item":
        validate_add_item(case_id, expected, errors)
    elif operation == "archive_items":
        validate_archive_items(case_id, expected, errors)
    elif operation == "complete_item":
        validate_complete_item(case_id, expected, fixture_text, errors)
    elif operation == "delete_item":
        validate_delete_item(case_id, expected, fixture_text, errors)
    elif operation == "drop_item":
        validate_drop_item(case_id, expected, fixture_text, errors)
    elif operation == "refuse_secret_storage":
        validate_refuse_secret_storage(case_id, expected, errors)
    elif operation == "review_items":
        validate_review_items(case_id, expected, errors)

    validate_storage_contract(case_id, case, expected, errors)


def main() -> int:
    errors: list[str] = []
    if not CASES_DIR.is_dir():
        return fail(f"Missing cases directory: {CASES_DIR}")

    prompts = load_prompts()
    self_checks = load_self_checks()
    case_paths = sorted(CASES_DIR.glob("*.json"))
    if not case_paths:
        return fail(f"No semantic cases found in {CASES_DIR}")

    seen_case_ids: set[str] = set()
    for path in case_paths:
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue

        case_id = case.get("id")
        if case_id in seen_case_ids:
            errors.append(f"{path.name}: duplicate case id {case_id}")
        if case_id:
            seen_case_ids.add(str(case_id))
        if case_id and path.stem != case_id:
            errors.append(f"{path.name}: filename must match id {case_id}")
        validate_case(case, prompts, self_checks, errors)

    missing_prompt_cases = sorted(set(prompts) - seen_case_ids)
    if missing_prompt_cases:
        errors.append(f"Missing semantic case(s) for prompts.csv: {', '.join(missing_prompt_cases)}")
    missing_self_check_cases = sorted(set(self_checks) - seen_case_ids)
    if missing_self_check_cases:
        errors.append(
            f"Missing semantic case(s) for self_checks.yaml: {', '.join(missing_self_check_cases)}"
        )

    if errors:
        return fail("Semantic case check failed:\n" + "\n".join(f"- {error}" for error in errors))

    print(f"Semantic case check passed: {len(case_paths)} case(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

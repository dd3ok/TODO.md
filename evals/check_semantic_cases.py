#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.validate_watchlist import structural_text as watchlist_structural_text

CASES_DIR = ROOT / "evals" / "cases"
FIXTURES_DIR = ROOT / "evals" / "fixtures"
PROMPTS_CSV = ROOT / "evals" / "prompts.csv"
SELF_CHECKS = ROOT / "evals" / "self_checks.yaml"
CHECK_WATCHLIST = ROOT / "evals" / "check_watchlist.py"
TRIGGER_CASES = ROOT / "evals" / "trigger_cases.json"

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
    "block_item",
    "complete_item",
    "delete_item",
    "drop_item",
    "reopen_item",
    "refuse_secret_storage",
    "review_items",
    "snooze_item",
}
SUPPORTED_STORAGE_TARGETS = {
    "WATCHLIST.md",
    ".watchlist/WATCHLIST.md",
    "$HOME/.watchlist/WATCHLIST.md",
    "explicit_user_path",
    "clarify",
}
SUPPORTED_STORAGE_SCOPES = {
    "shared_project",
    "local_private",
    "personal_repo_independent",
    "ambiguous",
}
SUPPORTED_CATEGORIES = {
    "skill-trigger",
    "storage-policy",
    "agent-workflow-safety",
}
SUPPORTED_TRIGGER_REASONS = {
    "ambiguous_watchlist_target",
    "explicit_watchlist_negation",
    "explicit_watchlist_add",
    "generic_deferred_check_without_watchlist",
    "generic_delete_without_watchlist",
    "generic_lifecycle_without_watchlist",
    "generic_now_check_without_watchlist",
    "generic_reminder_without_watchlist",
    "local_private_watchlist_record",
    "non_watchlist_wl_text",
    "preauthorized_watchlist_workflow",
    "scheduler_without_watchlist",
    "secret_storage_without_watchlist",
    "watchlist_list_review",
    "watchlist_scoped_pending_result",
    "wl_item_lifecycle_update",
}
REQUIRED_TRIGGER_REASONS = {
    "explicit_watchlist_negation",
    "explicit_watchlist_add",
    "generic_deferred_check_without_watchlist",
    "wl_item_lifecycle_update",
    "watchlist_list_review",
    "generic_reminder_without_watchlist",
    "generic_now_check_without_watchlist",
    "generic_lifecycle_without_watchlist",
    "non_watchlist_wl_text",
}
TRIGGER_CASE_KEYS = {"id", "locale", "prompt", "expected", "reason"}
SELF_CHECK_ROOT_KEYS = {"fixed_now", "forbidden_response_substrings", "cases"}
CASE_KEYS = REQUIRED_CASE_KEYS | {"category", "workspace"}
WORKSPACE_KEYS = {"existing_paths", "ignored_paths"}
STORAGE_KEYS = {"target", "scope", "must_not"}
PINNED_EXPECTED_VALUES = {
    "archive-manual-no-suggestion-kr": {"should_suggest_archive": False},
    "archive-suggest-policy-kr": {"should_suggest_archive": True},
    "duplicate-id-stop-and-report-kr": {"on_duplicate_id": "stop_and_report"},
    "list-review-sensitive-data-kr": {
        "sensitive_data_policy": "report_without_echo_or_mutation"
    },
    "negative-now-01": {"should_create_watchlist_item": False},
    "past-time-kr-01": {
        "ambiguity": "requested time is already in the past for fixed_now"
    },
    "permission-kr-01": {"requires_explicit_authorization": True},
}
PINNED_OBJECT_KEYS = {
    "localized-schema-tokens-kr": {"schema_tokens"},
}
PINNED_STORAGE_CONTRACTS = {
    "both-watchlists-ambiguous-new-write": ("clarify", "ambiguous"),
    "existing-dot-shared-scope-mismatch-kr": ("WATCHLIST.md", "shared_project"),
    "existing-dot-watchlist-private-followup": (
        ".watchlist/WATCHLIST.md",
        "local_private",
    ),
    "existing-root-private-scope-mismatch-kr": (
        ".watchlist/WATCHLIST.md",
        "local_private",
    ),
    "existing-root-watchlist-shared-followup": ("WATCHLIST.md", "shared_project"),
    "no-existing-watchlist-default-local-private": (
        ".watchlist/WATCHLIST.md",
        "local_private",
    ),
    "no-existing-watchlist-default-local-private-kr": (
        ".watchlist/WATCHLIST.md",
        "local_private",
    ),
}
PINNED_STORAGE_POLICY_CASES = {
    "existing-dot-shared-scope-mismatch-kr",
    "existing-root-private-scope-mismatch-kr",
    "no-existing-watchlist-default-local-private",
    "no-existing-watchlist-default-local-private-kr",
}
SCHEMA_TOKEN_KEYS = {
    "must_use_field_keys",
    "must_use_enum_values",
    "must_not_use_localized_schema_tokens",
}
NO_TRIGGER_EXPECTED_KEYS = {
    "must_not",
    "must_not_modify_watchlist",
    "reason",
    "should_create_watchlist_item",
}
EXPECTED_KEYS_BY_OPERATION = {
    "add_item": {
        "operation",
        "status",
        "due_at",
        "scheduler",
        "required_fields",
        "forbidden_response_substrings",
        "required_response_substrings",
        "ambiguity",
        "on_duplicate_id",
        "must_reread_before_write",
        "must_avoid_existing_ids",
        "must_not",
        "schema_tokens",
        "storage",
    },
    "archive_items": {
        "operation",
        "explicit_archive_request",
        "allowed_statuses",
        "forbidden_statuses",
        "archive_section",
        "must_not",
    },
    "block_item": {
        "operation",
        "item_id",
        "status",
        "required_updates",
        "default_section",
        "must_not",
    },
    "complete_item": {
        "operation",
        "item_id",
        "status",
        "required_updates",
        "default_section",
        "completion_evidence",
        "must_not",
    },
    "delete_item": {
        "operation",
        "item_id",
        "explicit_record_removal",
        "deletes_item",
        "requires_second_confirmation",
        "must_not",
    },
    "drop_item": {
        "operation",
        "item_id",
        "status",
        "required_updates",
        "deletes_item",
        "preserves_record",
        "default_section",
        "must_not",
    },
    "reopen_item": {
        "operation",
        "item_id",
        "status",
        "due_at",
        "required_updates",
        "default_section",
        "must_not",
    },
    "refuse_secret_storage": {
        "operation",
        "stores_secret",
        "allowed_storage",
        "must_not",
        "required_response_substrings",
    },
    "review_items": {
        "operation",
        "mutates_file",
        "groups",
        "must_not_modify_watchlist",
        "must_not",
        "required_response_substrings",
        "should_suggest_archive",
        "archive_after_days",
        "archive_candidate_statuses",
        "forbidden_statuses",
        "requires_explicit_authorization",
        "requires_configured_access",
        "should_not_guess_private_state",
        "sensitive_data_policy",
        "age_reference_precedence",
        "invalid_timestamp_behavior",
        "minimum_age_inclusive",
    },
    "snooze_item": {
        "operation",
        "item_id",
        "status",
        "due_at",
        "required_updates",
        "default_section",
        "must_not",
    },
}
SELF_CHECK_CASE_KEYS = {"prompt", "expected"}
SELF_CHECK_EXPECTED_KEYS = set().union(*EXPECTED_KEYS_BY_OPERATION.values()) | (
    NO_TRIGGER_EXPECTED_KEYS
    | {
        "should_trigger_skill",
        "required_fields",
        "should_not_rewrite_unrelated_items",
        "storage_scope",
        "storage_target",
    }
)
EXPECTED_STRING_LIST_KEYS = {
    "allowed_statuses",
    "archive_candidate_statuses",
    "forbidden_response_substrings",
    "forbidden_statuses",
    "groups",
    "must_not",
    "required_fields",
    "required_response_substrings",
    "required_updates",
}
FULL_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:[0-5]\d)$"
)
TRIGGER_REASON_EXPECTED = {
    "ambiguous_watchlist_target": "trigger",
    "explicit_watchlist_negation": "no_trigger",
    "explicit_watchlist_add": "trigger",
    "generic_deferred_check_without_watchlist": "no_trigger",
    "generic_delete_without_watchlist": "no_trigger",
    "generic_lifecycle_without_watchlist": "no_trigger",
    "generic_now_check_without_watchlist": "no_trigger",
    "generic_reminder_without_watchlist": "no_trigger",
    "local_private_watchlist_record": "trigger",
    "non_watchlist_wl_text": "no_trigger",
    "preauthorized_watchlist_workflow": "trigger",
    "scheduler_without_watchlist": "no_trigger",
    "secret_storage_without_watchlist": "no_trigger",
    "watchlist_list_review": "trigger",
    "watchlist_scoped_pending_result": "trigger",
    "wl_item_lifecycle_update": "trigger",
}
EXPLICIT_WATCHLIST_CONTEXT_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:watchlist(?:\.md)?|WL-\d{8}-\d{3})(?![A-Za-z0-9_-])",
    re.I,
)
NO_EXPLICIT_CONTEXT_REASONS = {
    "generic_deferred_check_without_watchlist",
    "generic_delete_without_watchlist",
    "generic_lifecycle_without_watchlist",
    "generic_now_check_without_watchlist",
    "generic_reminder_without_watchlist",
    "non_watchlist_wl_text",
    "scheduler_without_watchlist",
    "secret_storage_without_watchlist",
}


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def rows_to_prompts(
    rows: list[dict[str, str]], errors: list[str]
) -> dict[str, dict[str, str]]:
    prompts: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, start=2):
        case_id = (row.get("id") or "").strip()
        if not case_id:
            errors.append(f"prompts.csv:{index}: id must be non-empty")
            continue
        if case_id in prompts:
            errors.append(f"prompts.csv:{index}: duplicate id {case_id}")
            continue
        should_trigger = (row.get("should_trigger") or "").strip().lower()
        if should_trigger not in {"true", "false"}:
            errors.append(
                f"prompts.csv:{index}: should_trigger must be true or false: {should_trigger}"
            )
        if not (row.get("prompt") or "").strip():
            errors.append(f"prompts.csv:{index}: prompt must be non-empty")
        if not (row.get("expected") or "").strip():
            errors.append(f"prompts.csv:{index}: expected summary must be non-empty")
        prompts[case_id] = row
    return prompts


def load_prompts(errors: list[str]) -> dict[str, dict[str, str]]:
    with PROMPTS_CSV.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        required_headers = {"id", "should_trigger", "prompt", "expected"}
        headers = reader.fieldnames or []
        header_counts = Counter(headers)
        duplicate_headers = sorted(
            header for header, count in header_counts.items() if count > 1
        )
        if duplicate_headers:
            errors.append(
                "prompts.csv: duplicate header(s): " + ", ".join(duplicate_headers)
            )
        unexpected_headers = sorted(set(headers) - required_headers)
        if unexpected_headers:
            errors.append(
                "prompts.csv: unsupported header(s): " + ", ".join(unexpected_headers)
            )
        missing_headers = sorted(required_headers - set(headers))
        if missing_headers:
            errors.append(
                "prompts.csv: missing required header(s): " + ", ".join(missing_headers)
            )
        return rows_to_prompts(list(reader), errors)


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


def validate_self_check_yaml_subset(text: str, errors: list[str]) -> None:
    """Validate the dependency-free YAML subset used by self_checks.yaml."""
    root_keys: list[str] = []
    containers: dict[int, str] = {0: "mapping"}
    previous_indent: Optional[int] = None
    previous_child_container: Optional[str] = None
    mapping_scope_by_indent = {0: "root"}
    mapping_keys_by_scope: dict[str, set[str]] = {"root": set()}

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if "\t" in line:
            errors.append(f"self_checks.yaml:{line_number}: tabs are not supported")
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent % 2:
            errors.append(
                f"self_checks.yaml:{line_number}: indentation must use two-space steps"
            )

        content = line.strip()
        mapping_match = re.match(
            r"^(?:- )?(?P<key>[A-Za-z_][A-Za-z0-9_]*):(?:\s*(?P<value>.*))$",
            content,
        )
        is_sequence_item = content.startswith("- ")
        item_container = "sequence" if is_sequence_item else "mapping"

        if previous_indent is None:
            if indent != 0:
                errors.append(
                    f"self_checks.yaml:{line_number}: document must start at root indentation"
                )
        elif indent > previous_indent:
            if indent != previous_indent + 2:
                errors.append(
                    f"self_checks.yaml:{line_number}: indentation jumps more than one level"
                )
            if previous_child_container is None:
                errors.append(
                    f"self_checks.yaml:{line_number}: scalar value cannot contain child entries"
                )
            elif previous_child_container not in {"unknown", item_container}:
                errors.append(
                    f"self_checks.yaml:{line_number}: expected {previous_child_container} child entries"
                )
            containers[indent] = (
                item_container
                if previous_child_container in {None, "unknown"}
                else previous_child_container
            )
        else:
            for nested_indent in [level for level in containers if level > indent]:
                del containers[nested_indent]

        expected_container = containers.get(indent)
        if expected_container is None:
            errors.append(
                f"self_checks.yaml:{line_number}: no parent container for indentation {indent}"
            )
            containers[indent] = item_container
        elif expected_container != item_container:
            errors.append(
                f"self_checks.yaml:{line_number}: expected {expected_container} entry at indentation {indent}"
            )

        next_child_container: Optional[str] = None
        if mapping_match:
            key = mapping_match.group("key")
            value = mapping_match.group("value") or ""

            if is_sequence_item:
                for level in [level for level in mapping_scope_by_indent if level > indent]:
                    del mapping_scope_by_indent[level]
                scope = f"item:{line_number}"
                mapping_scope_by_indent[indent + 2] = scope
                mapping_keys_by_scope[scope] = set()
            else:
                scope = mapping_scope_by_indent.get(indent, f"mapping:{line_number}")
                mapping_scope_by_indent.setdefault(indent, scope)
                mapping_keys_by_scope.setdefault(scope, set())

            if indent > 0 and key in mapping_keys_by_scope[scope]:
                errors.append(
                    f"self_checks.yaml:{line_number}: duplicate mapping key {key}"
                )
            mapping_keys_by_scope[scope].add(key)

            if indent == 0 and not is_sequence_item:
                root_keys.append(key)
                if key not in SELF_CHECK_ROOT_KEYS:
                    errors.append(
                        f"self_checks.yaml:{line_number}: unsupported root key {key}"
                    )
            elif indent == 2 and (not is_sequence_item or key != "id"):
                errors.append(
                    f"self_checks.yaml:{line_number}: unsupported case-list key {key}"
                )
            elif indent == 4 and key not in SELF_CHECK_CASE_KEYS:
                errors.append(
                    f"self_checks.yaml:{line_number}: unsupported case key {key}"
                )
            elif indent == 6 and key not in SELF_CHECK_EXPECTED_KEYS:
                errors.append(
                    f"self_checks.yaml:{line_number}: unsupported expected key {key}"
                )
            elif indent == 8 and key not in SCHEMA_TOKEN_KEYS:
                errors.append(
                    f"self_checks.yaml:{line_number}: unsupported nested expected key {key}"
                )
            if value:
                if parse_yaml_scalar(value) is None:
                    errors.append(
                        f"self_checks.yaml:{line_number}: unterminated quoted scalar"
                    )
                elif value[0] in "[{" or value[-1:] in "]}":
                    errors.append(
                        f"self_checks.yaml:{line_number}: inline collections are not supported"
                    )
            if is_sequence_item:
                next_child_container = "mapping"
            elif not value:
                next_child_container = "unknown"
                mapping_scope_by_indent[indent + 2] = f"mapping:{line_number}"
                mapping_keys_by_scope[f"mapping:{line_number}"] = set()
        elif is_sequence_item:
            value = content[2:].strip()
            if not value:
                errors.append(f"self_checks.yaml:{line_number}: empty list item")
            elif parse_yaml_scalar(value) is None:
                errors.append(
                    f"self_checks.yaml:{line_number}: unterminated quoted scalar"
                )
        else:
            errors.append(
                f"self_checks.yaml:{line_number}: unsupported limited-YAML syntax"
            )

        previous_indent = indent
        previous_child_container = next_child_container

    root_counts = Counter(root_keys)
    missing_root_keys = sorted(SELF_CHECK_ROOT_KEYS - set(root_keys))
    if missing_root_keys:
        errors.append(
            "self_checks.yaml: missing root key(s): " + ", ".join(missing_root_keys)
        )
    duplicate_root_keys = sorted(
        key for key, count in root_counts.items() if count > 1
    )
    if duplicate_root_keys:
        errors.append(
            "self_checks.yaml: duplicate root key(s): " + ", ".join(duplicate_root_keys)
        )


def parse_self_checks(
    text: str, errors: Optional[list[str]] = None
) -> dict[str, dict[str, Optional[str]]]:
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
        expected_trigger = None
        expected_trigger_match = re.search(
            r"^\s+should_trigger_skill:\s*(?P<value>.*?)\s*$", body, flags=re.M
        )
        if expected_trigger_match:
            expected_trigger = parse_yaml_scalar(expected_trigger_match.group("value"))
        case_id = match.group("id")
        if case_id in cases and errors is not None:
            errors.append(f"self_checks.yaml: duplicate id {case_id}")
            continue
        cases[case_id] = {
            "prompt": prompt,
            "should_trigger_skill": expected_trigger,
        }
    return cases


def load_self_checks(
    errors: Optional[list[str]] = None,
) -> dict[str, dict[str, Optional[str]]]:
    text = SELF_CHECKS.read_text(encoding="utf-8")
    if errors is not None:
        validate_self_check_yaml_subset(text, errors)
    return parse_self_checks(text, errors)


def validate_iso_timestamp(value: object, case_id: str, errors: list[str], field: str) -> None:
    if not isinstance(value, str) or not FULL_TIMESTAMP_RE.fullmatch(value):
        errors.append(f"{case_id}: {field} must include time and timezone offset")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{case_id}: {field} is not ISO-8601: {value}")
        return
    if parsed.utcoffset() is None:
        errors.append(f"{case_id}: {field} must include time and timezone offset")


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

    try:
        fixture_text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{case_id}: fixture could not be read as UTF-8: {fixture}: {exc}")
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
    return watchlist_structural_text(fixture_text)


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


def reject_unknown_keys(
    obj: dict[str, object],
    allowed: set[str],
    case_id: str,
    errors: list[str],
    path: str,
) -> None:
    unknown = sorted(set(obj) - allowed, key=str)
    if unknown:
        errors.append(f"{case_id}: unsupported {path} key(s): {', '.join(unknown)}")


def require_string_list(
    obj: dict[str, object],
    key: str,
    case_id: str,
    errors: list[str],
    path: str,
) -> set[str]:
    value = obj.get(key, [])
    if not isinstance(value, list):
        message = f"{case_id}: {path}.{key} must be a list"
        if message not in errors:
            errors.append(message)
        return set()
    if not all(isinstance(item, str) for item in value):
        message = f"{case_id}: {path}.{key} must contain only strings"
        if message not in errors:
            errors.append(message)
        return set()
    return set(value)


def require_item_in_fixture(
    expected: dict[str, object],
    fixture_text: str,
    case_id: str,
    errors: list[str],
) -> None:
    item_id = expected.get("item_id", "")
    if not isinstance(item_id, str) or not re.fullmatch(r"WL-\d{8}-\d{3}", item_id):
        errors.append(f"{case_id}: item_id must be a valid WL-YYYYMMDD-NNN string")
        return
    if fixture_text and not re.search(rf"^### {re.escape(item_id)}\b", fixture_text, flags=re.M):
        errors.append(f"{case_id}: fixture does not contain item_id {item_id}")


def fixture_item_status(expected: dict[str, object], fixture_text: str) -> Optional[str]:
    item_id = expected.get("item_id")
    if not isinstance(item_id, str) or not fixture_text:
        return None
    match = re.search(
        rf"^### {re.escape(item_id)}\b(?P<body>.*?)(?=^### |^## |\Z)",
        fixture_text,
        flags=re.M | re.S,
    )
    if not match:
        return None
    status = re.search(r"^- status: (?P<status>\S+)\s*$", match.group("body"), re.M)
    return status.group("status") if status else None


def require_active_fixture_status(
    operation: str,
    expected: dict[str, object],
    fixture_text: str,
    case_id: str,
    errors: list[str],
) -> None:
    source_status = fixture_item_status(expected, fixture_text)
    if source_status is not None and source_status not in {"open", "snoozed", "blocked"}:
        errors.append(f"{case_id}: {operation} fixture item must have an active status")


def validate_add_item(
    case_id: str,
    expected: dict[str, object],
    errors: list[str],
    locale: object = None,
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
    due_at = expected.get("due_at", "")
    if due_at != "unscheduled":
        validate_iso_timestamp(due_at, case_id, errors, "expected.due_at")

    required_fields = require_string_list(
        expected, "required_fields", case_id, errors, "expected"
    )
    for field in ["source", "trigger", "action", "done_when"]:
        if field not in required_fields:
            errors.append(f"{case_id}: add_item required_fields must include {field}")

    forbidden = require_string_list(
        expected, "forbidden_response_substrings", case_id, errors, "expected"
    )
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
        must_not = require_string_list(expected, "must_not", case_id, errors, "expected")
        for forbidden_operation in ["overwrite_existing_item", "rewrite_unrelated_items"]:
            if forbidden_operation not in must_not:
                errors.append(
                    f"{case_id}: add_item collision contract must_not must include "
                    f"{forbidden_operation}"
                )

    validate_schema_tokens(case_id, locale, expected, errors)


def validate_schema_tokens(
    case_id: str,
    locale: object,
    expected: dict[str, object],
    errors: list[str],
) -> None:
    schema_tokens = expected.get("schema_tokens")
    if schema_tokens is None:
        return
    if not isinstance(schema_tokens, dict):
        errors.append(f"{case_id}: expected.schema_tokens must be an object")
        return

    reject_unknown_keys(
        schema_tokens,
        SCHEMA_TOKEN_KEYS,
        case_id,
        errors,
        "expected.schema_tokens",
    )

    require_keys(
        schema_tokens,
        {
            "must_use_field_keys",
            "must_use_enum_values",
            "must_not_use_localized_schema_tokens",
        },
        case_id,
        errors,
        "expected.schema_tokens",
    )
    field_keys = require_string_list(
        schema_tokens,
        "must_use_field_keys",
        case_id,
        errors,
        "expected.schema_tokens",
    )
    enum_values = require_string_list(
        schema_tokens,
        "must_use_enum_values",
        case_id,
        errors,
        "expected.schema_tokens",
    )
    localized_tokens = require_string_list(
        schema_tokens,
        "must_not_use_localized_schema_tokens",
        case_id,
        errors,
        "expected.schema_tokens",
    )

    required_field_keys = {
        "schema_version",
        "automation",
        "timezone",
        "status",
        "priority",
        "owner",
        "due_at",
        "created_at",
        "source",
        "trigger",
        "action",
        "done_when",
        "last_checked_at",
        "result",
        "next_step_on_fail",
    }
    missing_field_keys = sorted(required_field_keys - field_keys)
    if missing_field_keys:
        errors.append(
            f"{case_id}: schema_tokens.must_use_field_keys missing "
            f"{', '.join(missing_field_keys)}"
        )

    if not {"open", "P1", "assistant_on_review"}.issubset(enum_values):
        errors.append(
            f"{case_id}: schema_tokens.must_use_enum_values must include "
            "open, P1, and assistant_on_review"
        )
    if locale != "ko":
        return
    if not {"상태", "우선순위", "담당자", "기한", "열림"}.issubset(localized_tokens):
        errors.append(
            f"{case_id}: schema_tokens.must_not_use_localized_schema_tokens "
            "must include 상태, 우선순위, 담당자, 기한, and 열림"
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

    reject_unknown_keys(storage, STORAGE_KEYS, case_id, errors, "expected.storage")

    before = len(errors)
    require_keys(storage, {"target", "scope", "must_not"}, case_id, errors, "expected.storage")
    if len(errors) > before:
        return

    target = storage.get("target")
    if not isinstance(target, str) or target not in SUPPORTED_STORAGE_TARGETS:
        errors.append(f"{case_id}: expected.storage.target is unsupported: {target}")

    scope = storage.get("scope")
    if not isinstance(scope, str) or scope not in SUPPORTED_STORAGE_SCOPES:
        errors.append(f"{case_id}: expected.storage.scope is unsupported: {scope}")

    workspace = case.get("workspace")
    if workspace is not None and not isinstance(workspace, dict):
        errors.append(f"{case_id}: workspace must be an object")
        return
    workspace = workspace or {}
    reject_unknown_keys(workspace, WORKSPACE_KEYS, case_id, errors, "workspace")

    existing_paths = require_string_list(workspace, "existing_paths", case_id, errors, "workspace")
    ignored_paths = require_string_list(workspace, "ignored_paths", case_id, errors, "workspace")
    must_not = require_string_list(storage, "must_not", case_id, errors, "expected.storage")

    if target == "WATCHLIST.md":
        if scope != "shared_project":
            errors.append(f"{case_id}: root WATCHLIST target must use shared_project scope")
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


def validate_pinned_case_contract(
    case_id: str,
    case: dict[str, object],
    expected: dict[str, object],
    errors: list[str],
) -> None:
    """Keep specialized regression cases from silently degrading into generic cases."""
    for key, required_value in PINNED_EXPECTED_VALUES.get(case_id, {}).items():
        actual = expected.get(key)
        matches = actual is required_value if isinstance(required_value, bool) else actual == required_value
        if not matches:
            errors.append(
                f"{case_id}: pinned regression contract requires "
                f"expected.{key}={required_value!r}"
            )

    for key in PINNED_OBJECT_KEYS.get(case_id, set()):
        if not isinstance(expected.get(key), dict):
            errors.append(
                f"{case_id}: pinned regression contract requires expected.{key} object"
            )

    storage_contract = PINNED_STORAGE_CONTRACTS.get(case_id)
    if storage_contract is not None:
        storage = expected.get("storage")
        if not isinstance(storage, dict):
            errors.append(
                f"{case_id}: pinned regression contract requires expected.storage object"
            )
        else:
            target, scope = storage_contract
            if storage.get("target") != target:
                errors.append(
                    f"{case_id}: pinned storage contract requires target={target}"
                )
            if storage.get("scope") != scope:
                errors.append(
                    f"{case_id}: pinned storage contract requires scope={scope}"
                )

    if case_id in PINNED_STORAGE_POLICY_CASES and case.get("category") != "storage-policy":
        errors.append(
            f"{case_id}: pinned storage regression case requires category=storage-policy"
        )


def validate_complete_item(
    case_id: str,
    expected: dict[str, object],
    fixture_text: str,
    errors: list[str],
) -> None:
    require_keys(
        expected,
        {
            "operation",
            "item_id",
            "status",
            "required_updates",
            "default_section",
            "completion_evidence",
            "must_not",
        },
        case_id,
        errors,
        "expected",
    )
    require_item_in_fixture(expected, fixture_text, case_id, errors)
    require_active_fixture_status(
        "complete_item", expected, fixture_text, case_id, errors
    )
    if expected.get("status") != "done":
        errors.append(f"{case_id}: complete_item status must be done")
    if expected.get("default_section") != "## Done":
        errors.append(f"{case_id}: complete_item default_section must be ## Done")
    completion_evidence = expected.get("completion_evidence")
    if not isinstance(completion_evidence, str) or completion_evidence not in {
        "user_reported",
        "independently_verified",
    }:
        errors.append(
            f"{case_id}: complete_item completion_evidence must identify the evidence source"
        )

    updates = require_string_list(
        expected, "required_updates", case_id, errors, "expected"
    )
    for field in ["last_checked_at", "result"]:
        if field not in updates:
            errors.append(f"{case_id}: complete_item required_updates must include {field}")

    must_not = require_string_list(expected, "must_not", case_id, errors, "expected")
    if "delete_item" not in must_not:
        errors.append(f"{case_id}: complete_item must_not must include delete_item")


def validate_active_transition(
    operation: str,
    target_status: str,
    required_updates: set[str],
    case_id: str,
    expected: dict[str, object],
    fixture_text: str,
    errors: list[str],
) -> None:
    required_keys = {
        "operation",
        "item_id",
        "status",
        "required_updates",
        "default_section",
        "must_not",
    }
    if target_status == "snoozed":
        required_keys.add("due_at")
    require_keys(expected, required_keys, case_id, errors, "expected")
    require_item_in_fixture(expected, fixture_text, case_id, errors)
    if operation != "reopen_item":
        require_active_fixture_status(
            operation, expected, fixture_text, case_id, errors
        )

    if expected.get("status") != target_status:
        errors.append(f"{case_id}: {operation} status must be {target_status}")
    if expected.get("default_section") != "## Open":
        errors.append(f"{case_id}: {operation} default_section must be ## Open")

    updates = require_string_list(
        expected, "required_updates", case_id, errors, "expected"
    )
    for field in sorted(required_updates):
        if field not in updates:
            errors.append(f"{case_id}: {operation} required_updates must include {field}")

    must_not = require_string_list(expected, "must_not", case_id, errors, "expected")
    if "delete_item" not in must_not:
        errors.append(f"{case_id}: {operation} must_not must include delete_item")

    if target_status == "snoozed":
        due_at = expected.get("due_at")
        if due_at == "unscheduled":
            errors.append(f"{case_id}: snooze_item due_at must be scheduled")
        else:
            validate_iso_timestamp(due_at, case_id, errors, "expected.due_at")


def validate_reopen_item(
    case_id: str,
    expected: dict[str, object],
    fixture_text: str,
    errors: list[str],
) -> None:
    target_status = expected.get("status")
    transition_requirements = {
        "open": {"result"},
        "snoozed": {"due_at", "last_checked_at", "result"},
        "blocked": {"last_checked_at", "next_step_on_fail", "result"},
    }
    if not isinstance(target_status, str) or target_status not in transition_requirements:
        errors.append(f"{case_id}: reopen_item status must be open, snoozed, or blocked")
        target_status = "open"
    validate_active_transition(
        "reopen_item",
        target_status,
        transition_requirements[target_status],
        case_id,
        expected,
        fixture_text,
        errors,
    )
    source_status = fixture_item_status(expected, fixture_text)
    if source_status is not None and source_status not in {"done", "dropped"}:
        errors.append(f"{case_id}: reopen_item fixture item must be done or dropped")


def validate_drop_item(
    case_id: str,
    expected: dict[str, object],
    fixture_text: str,
    errors: list[str],
) -> None:
    require_keys(
        expected,
        {
            "operation",
            "item_id",
            "status",
            "required_updates",
            "deletes_item",
            "preserves_record",
            "default_section",
            "must_not",
        },
        case_id,
        errors,
        "expected",
    )
    require_item_in_fixture(expected, fixture_text, case_id, errors)
    require_active_fixture_status("drop_item", expected, fixture_text, case_id, errors)
    if expected.get("status") != "dropped":
        errors.append(f"{case_id}: drop_item status must be dropped")
    updates = require_string_list(
        expected, "required_updates", case_id, errors, "expected"
    )
    if "result" not in updates:
        errors.append(f"{case_id}: drop_item required_updates must include result")
    if expected.get("deletes_item") is not False:
        errors.append(f"{case_id}: drop_item must set deletes_item=false")
    if expected.get("preserves_record") is not True:
        errors.append(f"{case_id}: drop_item must set preserves_record=true")
    if expected.get("default_section") != "## Done":
        errors.append(f"{case_id}: drop_item default_section must be ## Done")
    must_not = require_string_list(expected, "must_not", case_id, errors, "expected")
    for action in ["delete_item", "rewrite_unrelated_items"]:
        if action not in must_not:
            errors.append(f"{case_id}: drop_item must_not must include {action}")


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
    if expected.get("requires_second_confirmation") is not False:
        errors.append(
            f"{case_id}: delete_item must set requires_second_confirmation=false"
        )
    must_not = require_string_list(expected, "must_not", case_id, errors, "expected")
    if "rewrite_unrelated_items" not in must_not:
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
    if expected.get("archive_section") != "## Archive":
        errors.append(f"{case_id}: archive_items archive_section must be ## Archive")
    allowed = require_string_list(
        expected, "allowed_statuses", case_id, errors, "expected"
    )
    if allowed != {"done", "dropped"}:
        errors.append(f"{case_id}: archive_items allowed_statuses must be done,dropped")
    forbidden = require_string_list(
        expected, "forbidden_statuses", case_id, errors, "expected"
    )
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
    if expected.get("allowed_storage") != "stable non-secret pointer only":
        errors.append(
            f"{case_id}: refuse_secret_storage allowed_storage must be a stable non-secret pointer"
        )
    must_not = require_string_list(expected, "must_not", case_id, errors, "expected")
    if not {"store_raw_secret", "store_token"}.intersection(must_not):
        errors.append(
            f"{case_id}: refuse_secret_storage must_not must include "
            "store_raw_secret or store_token"
        )


def validate_review_items(
    case_id: str,
    expected: dict[str, object],
    errors: list[str],
    fixture_text: str = "",
    fixed_now: object = None,
) -> None:
    require_keys(
        expected,
        {"operation", "mutates_file", "must_not_modify_watchlist"},
        case_id,
        errors,
        "expected",
    )
    if expected.get("mutates_file") is not False:
        errors.append(f"{case_id}: review_items must set mutates_file=false")
    if expected.get("must_not_modify_watchlist") is not True:
        errors.append(f"{case_id}: review_items must set must_not_modify_watchlist=true")
    if expected.get("mutates_file") is False:
        groups = require_string_list(expected, "groups", case_id, errors, "expected")
        for group in ["overdue", "due today", "upcoming", "unscheduled"]:
            if group not in groups:
                errors.append(f"{case_id}: review_items groups must include {group}")
    should_suggest = expected.get("should_suggest_archive")
    if should_suggest is not None and not isinstance(should_suggest, bool):
        errors.append(f"{case_id}: should_suggest_archive must be a boolean")
    if should_suggest is True:
        if expected.get("must_not_modify_watchlist") is not True:
            errors.append(
                f"{case_id}: archive suggestion reviews must set "
                "must_not_modify_watchlist=true"
            )
        if expected.get("archive_after_days") != 30:
            errors.append(f"{case_id}: archive suggestion reviews must set archive_after_days=30")
        age_precedence = require_string_list(
            expected,
            "age_reference_precedence",
            case_id,
            errors,
            "expected",
        )
        raw_age_precedence = expected.get("age_reference_precedence")
        if raw_age_precedence != ["last_checked_at", "created_at"]:
            errors.append(
                f"{case_id}: archive age precedence must be last_checked_at,created_at"
            )
        if age_precedence != {"last_checked_at", "created_at"}:
            errors.append(f"{case_id}: archive age reference fields are incomplete")
        if expected.get("minimum_age_inclusive") is not True:
            errors.append(f"{case_id}: archive minimum age must be inclusive")
        if expected.get("invalid_timestamp_behavior") != "do_not_suggest":
            errors.append(
                f"{case_id}: invalid archive timestamps must use do_not_suggest"
            )
        candidate_statuses = require_string_list(
            expected,
            "archive_candidate_statuses",
            case_id,
            errors,
            "expected",
        )
        if candidate_statuses != {"done", "dropped"}:
            errors.append(
                f"{case_id}: archive suggestion candidates must be done,dropped"
            )
        forbidden_statuses = require_string_list(
            expected, "forbidden_statuses", case_id, errors, "expected"
        )
        for status in ["open", "snoozed", "blocked"]:
            if status not in forbidden_statuses:
                errors.append(
                    f"{case_id}: archive suggestion forbidden_statuses must include {status}"
                )
    if isinstance(should_suggest, bool) and fixture_text and isinstance(fixed_now, str):
        policy_match = re.search(
            r"^archive_policy:\s*(?P<value>\S+)\s*$", fixture_text, re.M
        )
        policy = policy_match.group("value") if policy_match else None
        threshold_match = re.search(
            r"^archive_after_days:\s*(?P<value>\d+)\s*$", fixture_text, re.M
        )
        threshold = int(threshold_match.group("value")) if threshold_match else None
        candidate_count = count_archive_candidates(
            fixture_text,
            fixed_now,
            expected.get("archive_after_days", threshold),
        )
        if should_suggest is True:
            if policy != "suggest":
                errors.append(
                    f"{case_id}: archive suggestion fixture must use archive_policy=suggest"
                )
            if threshold != expected.get("archive_after_days"):
                errors.append(
                    f"{case_id}: archive suggestion threshold differs from fixture"
                )
            if candidate_count == 0:
                errors.append(f"{case_id}: archive suggestion fixture has no eligible item")
        elif policy == "suggest" and candidate_count > 0:
            errors.append(
                f"{case_id}: should_suggest_archive=false contradicts eligible fixture items"
            )
    requires_authorization = expected.get("requires_explicit_authorization")
    if requires_authorization is not None and not isinstance(
        requires_authorization, bool
    ):
        errors.append(f"{case_id}: requires_explicit_authorization must be a boolean")
    if requires_authorization is True:
        for key in ["requires_configured_access", "should_not_guess_private_state"]:
            if expected.get(key) is not True:
                errors.append(f"{case_id}: permission review must set {key}=true")

    sensitive_policy = expected.get("sensitive_data_policy")
    if sensitive_policy is not None:
        if sensitive_policy != "report_without_echo_or_mutation":
            errors.append(f"{case_id}: sensitive_data_policy is unsupported")
        must_not = require_string_list(
            expected, "must_not", case_id, errors, "expected"
        )
        for action in ["echo_sensitive_value", "redact_without_authority"]:
            if action not in must_not:
                errors.append(
                    f"{case_id}: sensitive-data review must_not must include {action}"
                )
        response_markers = require_string_list(
            expected,
            "required_response_substrings",
            case_id,
            errors,
            "expected",
        )
        if "source" not in response_markers or not any(
            marker.startswith("WL-") for marker in response_markers
        ):
            errors.append(
                f"{case_id}: sensitive-data review must identify a WL item and source field"
            )


def count_archive_candidates(
    fixture_text: str,
    fixed_now: str,
    archive_after_days: object,
) -> int:
    if not isinstance(archive_after_days, int) or isinstance(archive_after_days, bool):
        return 0
    if not FULL_TIMESTAMP_RE.fullmatch(fixed_now):
        return 0
    try:
        now = datetime.fromisoformat(fixed_now.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if now.utcoffset() is None:
        return 0

    candidates = 0
    for match in re.finditer(
        r"^### WL-\d{8}-\d{3}\b(?P<body>.*?)(?=^### |^## |\Z)",
        fixture_text,
        re.M | re.S,
    ):
        body = match.group("body")
        status = re.search(r"^- status:\s*(?P<value>\S+)\s*$", body, re.M)
        if not status or status.group("value") not in {"done", "dropped"}:
            continue
        values = {
            field: value.strip()
            for field, value in re.findall(
                r"^- (last_checked_at|created_at):\s*(.*?)\s*$", body, re.M
            )
        }
        reference = values.get("last_checked_at") or values.get("created_at")
        if not reference:
            continue
        try:
            reference_time = datetime.fromisoformat(reference.replace("Z", "+00:00"))
        except ValueError:
            continue
        if reference_time.utcoffset() is None:
            continue
        if now - reference_time >= timedelta(days=archive_after_days):
            candidates += 1
    return candidates


def validate_case(
    case: object,
    prompts: dict[str, dict[str, str]],
    self_checks: dict[str, dict[str, Optional[str]]],
    errors: list[str],
) -> None:
    if not isinstance(case, dict):
        errors.append("semantic case root value must be an object")
        return

    raw_case_id = case.get("id")
    case_id = raw_case_id if isinstance(raw_case_id, str) and raw_case_id else "<missing-id>"
    require_keys(case, REQUIRED_CASE_KEYS, case_id, errors, "case")
    reject_unknown_keys(case, CASE_KEYS, case_id, errors, "case")
    if case_id == "<missing-id>":
        errors.append("semantic case id must be a non-empty string")
        return

    prompt = case.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        errors.append(f"{case_id}: prompt must be a non-empty string")

    prompt_row = prompts.get(case_id)
    if prompt_row is None:
        errors.append(f"{case_id}: missing from prompts.csv")
    elif prompt != prompt_row.get("prompt"):
        errors.append(f"{case_id}: prompt differs from prompts.csv")

    self_check = self_checks.get(case_id)
    if self_check is None:
        errors.append(f"{case_id}: missing from self_checks.yaml")
    elif self_check.get("prompt") is None:
        errors.append(f"{case_id}: prompt could not be parsed from self_checks.yaml")
    elif prompt != self_check["prompt"]:
        errors.append(f"{case_id}: prompt differs from self_checks.yaml")

    self_check_trigger = self_check.get("should_trigger_skill") if self_check else None
    if self_check_trigger is not None:
        normalized_trigger = str(self_check_trigger).strip().lower()
        if normalized_trigger not in {"true", "false"}:
            errors.append(
                f"{case_id}: self_checks.yaml expected.should_trigger_skill must be true or false"
            )
        elif case.get("should_trigger_skill") is not (normalized_trigger == "true"):
            errors.append(f"{case_id}: should_trigger_skill differs from self_checks.yaml")

    expected_should_trigger = case.get("should_trigger_skill")
    if prompt_row is not None:
        csv_trigger_value = (prompt_row.get("should_trigger") or "").strip().lower()
        if csv_trigger_value in {"true", "false"} and expected_should_trigger is not (
            csv_trigger_value == "true"
        ):
            errors.append(f"{case_id}: should_trigger_skill differs from prompts.csv")

    locale = case.get("locale")
    if not isinstance(locale, str) or locale not in {"ko", "en", "mixed"}:
        errors.append(f"{case_id}: locale must be ko, en, or mixed")

    category = case.get("category")
    if category is not None and (
        not isinstance(category, str) or category not in SUPPORTED_CATEGORIES
    ):
        errors.append(f"{case_id}: category is unsupported: {category}")

    validate_iso_timestamp(case.get("fixed_now"), case_id, errors, "fixed_now")
    fixture = case.get("fixture")
    if not isinstance(fixture, str) or not fixture:
        errors.append(f"{case_id}: fixture must be a non-empty string")
        fixture_text = ""
    else:
        fixture_text = validate_fixture(fixture, case_id, errors)

    workspace = case.get("workspace")
    if workspace is not None:
        if not isinstance(workspace, dict):
            errors.append(f"{case_id}: workspace must be an object")
        else:
            reject_unknown_keys(workspace, WORKSPACE_KEYS, case_id, errors, "workspace")
            for key in WORKSPACE_KEYS & set(workspace):
                require_string_list(workspace, key, case_id, errors, "workspace")

    expected = case.get("expected")
    if not isinstance(expected, dict):
        errors.append(f"{case_id}: expected must be an object")
        return
    for key in EXPECTED_STRING_LIST_KEYS & set(expected):
        require_string_list(expected, key, case_id, errors, "expected")

    if expected_should_trigger is False:
        reject_unknown_keys(
            expected, NO_TRIGGER_EXPECTED_KEYS, case_id, errors, "expected"
        )
        if "operation" in expected:
            errors.append(f"{case_id}: should_trigger_skill=false must not define expected.operation")
        require_keys(
            expected,
            {"reason", "must_not_modify_watchlist"},
            case_id,
            errors,
            "expected",
        )
        reason = expected.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{case_id}: expected.reason must be a non-empty string")
        if "should_create_watchlist_item" in expected and expected.get(
            "should_create_watchlist_item"
        ) is not False:
            errors.append(
                f"{case_id}: expected.should_create_watchlist_item must be false"
            )
        if expected.get("must_not_modify_watchlist") is not True:
            errors.append(
                f"{case_id}: should_trigger_skill=false must set "
                "expected.must_not_modify_watchlist=true"
            )
        validate_pinned_case_contract(case_id, case, expected, errors)
        return

    if expected_should_trigger is not True:
        errors.append(f"{case_id}: should_trigger_skill must be true or false")
        return

    if isinstance(prompt, str) and not EXPLICIT_WATCHLIST_CONTEXT_RE.search(prompt):
        errors.append(
            f"{case_id}: should_trigger_skill=true requires explicit WATCHLIST or valid WL item context"
        )

    operation = expected.get("operation")
    if not isinstance(operation, str) or not operation:
        errors.append(f"{case_id}: should_trigger_skill=true requires expected.operation")
        return
    if operation not in SUPPORTED_OPERATIONS:
        errors.append(f"{case_id}: unknown operation: {operation}")
        return
    reject_unknown_keys(
        expected,
        EXPECTED_KEYS_BY_OPERATION[operation],
        case_id,
        errors,
        "expected",
    )

    if operation == "add_item":
        validate_add_item(case_id, expected, errors, locale)
    elif operation == "archive_items":
        validate_archive_items(case_id, expected, errors)
    elif operation == "block_item":
        validate_active_transition(
            operation,
            "blocked",
            {"last_checked_at", "next_step_on_fail", "result"},
            case_id,
            expected,
            fixture_text,
            errors,
        )
    elif operation == "complete_item":
        validate_complete_item(case_id, expected, fixture_text, errors)
    elif operation == "delete_item":
        validate_delete_item(case_id, expected, fixture_text, errors)
    elif operation == "drop_item":
        validate_drop_item(case_id, expected, fixture_text, errors)
    elif operation == "reopen_item":
        validate_reopen_item(case_id, expected, fixture_text, errors)
    elif operation == "refuse_secret_storage":
        validate_refuse_secret_storage(case_id, expected, errors)
    elif operation == "review_items":
        validate_review_items(
            case_id,
            expected,
            errors,
            fixture_text=fixture_text,
            fixed_now=case.get("fixed_now"),
        )
    elif operation == "snooze_item":
        validate_active_transition(
            operation,
            "snoozed",
            {"due_at", "last_checked_at", "result"},
            case_id,
            expected,
            fixture_text,
            errors,
        )

    validate_storage_contract(case_id, case, expected, errors)
    validate_pinned_case_contract(case_id, case, expected, errors)


def validate_trigger_case_list(cases: object, errors: list[str]) -> int:
    if not isinstance(cases, list):
        errors.append("trigger_cases.json: root value must be a list")
        return 0
    if not 20 <= len(cases) <= 30:
        errors.append("trigger_cases.json: expected 20 to 30 lightweight cases")

    seen_ids: set[str] = set()
    decisions = {"trigger": 0, "no_trigger": 0}
    reasons: set[str] = set()
    for index, case in enumerate(cases):
        case_id = f"trigger_cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{case_id}: case must be an object")
            continue

        extra_keys = sorted(set(case) - TRIGGER_CASE_KEYS)
        if extra_keys:
            errors.append(f"{case_id}: unsupported key(s): {', '.join(extra_keys)}")

        require_keys(case, TRIGGER_CASE_KEYS, case_id, errors, "trigger case")
        if not TRIGGER_CASE_KEYS.issubset(case):
            continue

        case_id_val = case.get("id")
        if not isinstance(case_id_val, str) or not case_id_val.strip():
            errors.append(f"{case_id}: id must be a non-empty string")
            continue
        if case_id_val != case_id_val.strip():
            errors.append(f"{case_id}: id must not have leading or trailing whitespace")
            continue

        case_id = case_id_val
        if case_id in seen_ids:
            errors.append(f"{case_id}: duplicate trigger case id")
        seen_ids.add(case_id)

        locale = case.get("locale")
        if not isinstance(locale, str) or locale not in {"ko", "en", "mixed"}:
            errors.append(f"{case_id}: locale must be ko, en, or mixed")

        prompt = case.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append(f"{case_id}: prompt must be a non-empty string")
        elif len(prompt) > 180:
            errors.append(f"{case_id}: prompt is too long for lightweight trigger eval")

        expected = case.get("expected")
        if not isinstance(expected, str) or expected not in decisions:
            errors.append(f"{case_id}: expected must be trigger or no_trigger")
        else:
            decisions[expected] += 1

        reason = case.get("reason")
        if not isinstance(reason, str):
            errors.append(f"{case_id}: reason must be a supported string")
        elif reason not in SUPPORTED_TRIGGER_REASONS:
            errors.append(f"{case_id}: unsupported trigger reason: {reason}")
        else:
            reasons.add(reason)
            expected_for_reason = TRIGGER_REASON_EXPECTED[reason]
            if expected != expected_for_reason:
                errors.append(
                    f"{case_id}: reason {reason} must use expected={expected_for_reason}"
                )

        has_explicit_context = bool(
            EXPLICIT_WATCHLIST_CONTEXT_RE.search(str(case.get("prompt", "")))
        )
        if expected == "trigger" and not has_explicit_context:
            errors.append(f"{case_id}: trigger prompt requires explicit WATCHLIST context")
        if isinstance(reason, str) and reason in NO_EXPLICIT_CONTEXT_REASONS and has_explicit_context:
            errors.append(
                f"{case_id}: reason {reason} must not use explicit WATCHLIST context"
            )

    for decision, count in decisions.items():
        if count < 8:
            errors.append(f"trigger_cases.json: expected at least 8 {decision} cases")

    missing_reasons = sorted(REQUIRED_TRIGGER_REASONS - reasons)
    if missing_reasons:
        errors.append(
            "trigger_cases.json: missing required trigger reason(s): "
            + ", ".join(missing_reasons)
        )

    return len(cases)


def validate_trigger_cases(errors: list[str]) -> int:
    if not TRIGGER_CASES.is_file():
        errors.append(f"Missing trigger eval corpus: {TRIGGER_CASES.relative_to(ROOT)}")
        return 0

    try:
        cases = json.loads(TRIGGER_CASES.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"trigger_cases.json: invalid JSON: {exc}")
        return 0
    except (OSError, UnicodeError) as exc:
        errors.append(f"trigger_cases.json: could not be read: {exc}")
        return 0

    return validate_trigger_case_list(cases, errors)


def main() -> int:
    errors: list[str] = []
    if not CASES_DIR.is_dir():
        return fail(f"Missing cases directory: {CASES_DIR}")

    prompts = load_prompts(errors)
    self_checks = load_self_checks(errors)
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
        except (OSError, UnicodeError) as exc:
            errors.append(f"{path.name}: could not be read: {exc}")
            continue

        if not isinstance(case, dict):
            errors.append(f"{path.name}: root value must be an object")
            continue

        case_id = case.get("id")
        if isinstance(case_id, str) and case_id:
            if case_id in seen_case_ids:
                errors.append(f"{path.name}: duplicate case id {case_id}")
            seen_case_ids.add(case_id)
            if path.stem != case_id:
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

    trigger_case_count = validate_trigger_cases(errors)

    if errors:
        return fail("Semantic case check failed:\n" + "\n".join(f"- {error}" for error in errors))

    print(
        f"Evaluation contract lint passed: {len(case_paths)} case(s); "
        f"{trigger_case_count} trigger case(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

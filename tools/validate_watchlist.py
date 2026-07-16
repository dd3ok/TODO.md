#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


VALID_STATUSES = {"open", "snoozed", "blocked", "done", "dropped"}
VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}
VALID_OWNERS = {"user", "assistant_on_review", "both", "external"}
VALID_ARCHIVE_POLICIES = {"manual", "suggest"}
FIELD_ORDER = [
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
]
REQUIRED_FIELDS = set(FIELD_ORDER)
SKELETON_FIELDS = ("schema_version", "automation", "timezone")
KNOWN_TOP_LEVEL_FIELDS = set(SKELETON_FIELDS).union(
    {"mode", "archive_policy", "archive_after_days"}
)
SKELETON_SECTIONS = ("## Open", "## Done")
HEADING_RE_COMPAT = re.compile(
    r"^### (?P<id>WL-(?P<date>\d{8})-(?P<sequence>\d{3}))"
    r"\s+(?P<separator>—|-)\s+(?P<title>\S(?:.*\S)?)\s*$"
)
WATCHLIST_HEADING_CANDIDATE_RE = re.compile(
    r"^[ \t]{0,3}#{1,6}[ \t]*(?i:wl)(?=[^A-Za-z]|$).*$",
    flags=re.M,
)
ITEM_START_RE = re.compile(
    r"(?=^###[ \t]+(?i:wl)(?=[^A-Za-z]|$))",
    flags=re.M,
)
CORRECT_LEVEL_ITEM_START_RE = re.compile(
    r"^###[ \t]+(?i:wl)(?=[^A-Za-z]|$)"
)
FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,}).*$")
TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:[0-5]\d)$"
)
FIELD_RE = re.compile(
    r"^- (?P<field>[A-Za-z_][A-Za-z0-9_-]*):[ \t]*(?P<value>.*)$",
    flags=re.M,
)
TOP_LEVEL_FIELD_RE = re.compile(
    r"^(?P<field>[A-Za-z_][A-Za-z0-9_-]*):[ \t]*(?P<value>.*)$",
    flags=re.M,
)
SENSITIVE_PATTERNS = {
    "PRIVATE_KEY": (r"-----BEGIN (?:RSA |EC |OPENSSH |)?PRIVATE KEY-----", "error"),
    "BEARER_TOKEN": (r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}", "error"),
    "AUTHORIZATION_HEADER": (r"\bAuthorization:\s*", "error"),
    "GITHUB_TOKEN": (r"\bgh[pousr]_[A-Za-z0-9_]{20,}", "error"),
    "JWT": (r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b", "error"),
    "AWS_SIGNED_URL": (r"\bX-Amz-(Signature|Credential|Security-Token)=", "error"),
    "GENERIC_SIGNED_URL": (r"[?&](sig|signature|token|access_token)=", "warning"),
    "PASSWORD_ASSIGNMENT": (r"\b(password|passwd|pwd)\s*[:=]\s*\S+", "warning"),
    "API_KEY_ASSIGNMENT": (r"\b(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*\S+", "warning"),
    "RAW_PRIVATE_EXCERPT": (
        r"\b(raw logs?|email body|dashboard excerpt|set-cookie|cookie:|request headers|response headers)\b",
        "warning",
    ),
}
REDACTION_GUIDANCE = (
    "Recommended action:\n"
    "- Remove or redact the unsafe value.\n"
    "- Keep a safe pointer such as \"deployment dashboard run 123\".\n"
    "- If committed to Git history, rotate/revoke affected secrets and handle Git history cleanup separately."
)


@dataclass
class Finding:
    code: str
    message: str
    severity: str = "error"
    id: Optional[str] = None
    field: Optional[str] = None


@dataclass
class ValidationOptions:
    strict_format: bool = False
    strict_safety: bool = False
    require_archive_section: bool = False


@dataclass
class ValidationResult:
    path: str
    items: int = 0
    warnings: list[Finding] = field(default_factory=list)
    errors: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def add_error(
    result: ValidationResult,
    code: str,
    message: str,
    watch_id: Optional[str] = None,
    field: Optional[str] = None,
    severity: str = "error",
) -> None:
    result.errors.append(
        Finding(code=code, message=message, severity=severity, id=watch_id, field=field)
    )


def add_warning(
    result: ValidationResult,
    code: str,
    message: str,
    watch_id: Optional[str] = None,
    field: Optional[str] = None,
) -> None:
    result.warnings.append(
        Finding(code=code, message=message, severity="warning", id=watch_id, field=field)
    )


def item_blocks(text: str) -> list[str]:
    text = structural_text(text)
    return [
        block
        for block in ITEM_START_RE.split(text)
        if CORRECT_LEVEL_ITEM_START_RE.match(block)
    ]


def mask_non_newlines(value: str) -> str:
    return re.sub(r"[^\r\n]", " ", value)


def strip_html_comments(text: str) -> str:
    return re.sub(
        r"<!--(?:.*?-->|.*\Z)",
        lambda match: mask_non_newlines(match.group(0)),
        text,
        flags=re.S,
    )


def strip_fenced_code_blocks(text: str) -> str:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    fence_char: Optional[str] = None
    fence_length = 0

    for line in lines:
        content = line.rstrip("\r\n")
        if fence_char is None:
            match = FENCE_OPEN_RE.match(content)
            if match:
                fence = match.group("fence")
                fence_char = fence[0]
                fence_length = len(fence)
                output.append(mask_non_newlines(line))
            else:
                output.append(line)
            continue

        output.append(mask_non_newlines(line))
        if re.fullmatch(
            rf"[ \t]{{0,3}}{re.escape(fence_char)}{{{fence_length},}}[ \t]*",
            content,
        ):
            fence_char = None
            fence_length = 0

    return "".join(output)


def strip_indented_code_blocks(text: str) -> str:
    return re.sub(
        r"^(?: {4,}|\t).*?$",
        lambda match: mask_non_newlines(match.group(0)),
        text,
        flags=re.M,
    )


def structural_text(text: str) -> str:
    return strip_indented_code_blocks(
        strip_fenced_code_blocks(strip_html_comments(text))
    )


def validate_heading_candidates(text: str, result: ValidationResult) -> None:
    for match in WATCHLIST_HEADING_CANDIDATE_RE.finditer(text):
        heading = match.group(0)
        if CORRECT_LEVEL_ITEM_START_RE.match(heading):
            continue
        add_error(
            result,
            "MALFORMED_HEADING",
            f"Malformed WATCHLIST item heading: {heading}",
        )


def heading_info(block: str, result: ValidationResult, options: ValidationOptions) -> Optional[str]:
    heading = block.splitlines()[0]
    match = HEADING_RE_COMPAT.match(heading)
    if not match:
        add_error(result, "MALFORMED_HEADING", f"Malformed WATCHLIST item heading: {heading}")
        return None

    watch_id = match.group("id")
    try:
        datetime.strptime(match.group("date"), "%Y%m%d")
    except ValueError:
        add_error(
            result,
            "INVALID_ID_DATE",
            f"Invalid calendar date in WATCHLIST ID: {watch_id}",
            watch_id=watch_id,
        )
    if match.group("sequence") == "000":
        add_error(
            result,
            "INVALID_ID_SEQUENCE",
            f"WATCHLIST ID sequence must be 001-999: {watch_id}",
            watch_id=watch_id,
        )
    if match.group("separator") != "—":
        message = f"Use em dash separator in {watch_id}: {heading}"
        if options.strict_format:
            add_error(result, "NON_STRICT_HEADING_SEPARATOR", message, watch_id=watch_id)
        else:
            add_warning(result, "NON_STRICT_HEADING_SEPARATOR", message, watch_id=watch_id)
    return watch_id


def fields_for_block(
    block: str,
    watch_id: str,
    result: ValidationResult,
    options: ValidationOptions,
) -> dict[str, str]:
    fields: dict[str, str] = {}
    seen_order: list[str] = []
    for match in FIELD_RE.finditer(block):
        field = match.group("field")
        if field in fields:
            add_error(result, "DUPLICATE_FIELD", f"Duplicate field in {watch_id}: {field}", watch_id, field)
        fields[field] = match.group("value").strip()
        seen_order.append(field)

    unknown_fields = sorted(set(fields) - REQUIRED_FIELDS)
    for field in unknown_fields:
        message = f"Unknown field in {watch_id}: {field}"
        if options.strict_format:
            add_error(result, "UNKNOWN_FIELD", message, watch_id, field)
        else:
            add_warning(result, "UNKNOWN_FIELD", message, watch_id, field)

    known_seen_order = [field for field in seen_order if field in FIELD_ORDER]
    expected_order = [field for field in FIELD_ORDER if field in fields]
    if known_seen_order != expected_order:
        message = (
            f"FIELD_ORDER drift in {watch_id}: expected "
            f"{', '.join(expected_order)}"
        )
        if options.strict_format:
            add_error(result, "FIELD_ORDER", message, watch_id)
        else:
            add_warning(result, "FIELD_ORDER", message, watch_id)

    return fields


def validate_timestamp(
    result: ValidationResult,
    watch_id: str,
    field: str,
    value: str,
    allow_unscheduled: bool,
) -> None:
    if allow_unscheduled and value == "unscheduled":
        return
    if not TIMESTAMP_RE.match(value):
        add_error(result, f"INVALID_{field.upper()}", f"Invalid {field} in {watch_id}: {value}", watch_id, field)
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        add_error(result, f"INVALID_{field.upper()}", f"Invalid {field} in {watch_id}: {value}", watch_id, field)


def validate_skeleton(text: str, result: ValidationResult, options: ValidationOptions) -> None:
    text = structural_text(text)
    preamble = re.split(r"^##\s+", text, maxsplit=1, flags=re.M)[0]
    for field in SKELETON_FIELDS:
        if not re.search(rf"^{field}:\s*\S+", preamble, flags=re.M):
            add_error(result, "MISSING_SKELETON_FIELD", f"Missing WATCHLIST skeleton field: {field}")
    if not re.search(r"^# WATCHLIST\.md\s*$", text, flags=re.M):
        add_error(result, "MISSING_SKELETON_HEADING", "Missing WATCHLIST skeleton heading: # WATCHLIST.md")

    required_sections = list(SKELETON_SECTIONS)
    if options.require_archive_section:
        required_sections.append("## Archive")
    for section in (*SKELETON_SECTIONS, "## Archive"):
        count = len(re.findall(rf"^{re.escape(section)}\s*$", text, flags=re.M))
        if section in required_sections and count == 0:
            add_error(result, "MISSING_SKELETON_SECTION", f"Missing WATCHLIST skeleton section: {section}")
        if count > 1:
            add_error(result, "DUPLICATE_SKELETON_SECTION", f"Duplicate WATCHLIST skeleton section: {section}")


def top_level_fields(
    text: str,
    result: ValidationResult,
    options: ValidationOptions,
) -> dict[str, str]:
    text = structural_text(text)
    preamble = re.split(r"^##\s+", text, maxsplit=1, flags=re.M)[0]
    fields: dict[str, str] = {}
    for match in TOP_LEVEL_FIELD_RE.finditer(preamble):
        field = match.group("field")
        if field in fields:
            add_error(
                result,
                "DUPLICATE_TOP_LEVEL_FIELD",
                f"Duplicate top-level field: {field}",
            )
        if field not in KNOWN_TOP_LEVEL_FIELDS:
            add_format_finding(
                result,
                options,
                "UNKNOWN_TOP_LEVEL_FIELD",
                f"Unknown top-level field: {field}",
            )
        fields[field] = match.group("value").strip()
    return fields


def add_format_finding(
    result: ValidationResult,
    options: ValidationOptions,
    code: str,
    message: str,
) -> None:
    if options.strict_format:
        add_error(result, code, message)
    else:
        add_warning(result, code, message)


def validate_top_level_fields(text: str, result: ValidationResult, options: ValidationOptions) -> None:
    fields = top_level_fields(text, result, options)
    schema_version = fields.get("schema_version")
    automation = fields.get("automation")
    mode = fields.get("mode")
    archive_policy = fields.get("archive_policy")
    archive_after_days = fields.get("archive_after_days")

    if schema_version and schema_version != "1":
        add_error(
            result,
            "INVALID_SCHEMA_VERSION",
            f"Invalid schema_version: {schema_version}. Use 1.",
        )

    if automation and automation != "none":
        add_error(
            result,
            "INVALID_AUTOMATION",
            f"Invalid automation: {automation}. Use none.",
        )

    if mode is not None:
        add_warning(
            result,
            "DEPRECATED_MODE_FIELD",
            "Deprecated top-level field: mode has no effect; remove it.",
        )

    if archive_policy and archive_policy not in VALID_ARCHIVE_POLICIES:
        add_error(
            result,
            "INVALID_ARCHIVE_POLICY",
            f"Invalid archive_policy: {archive_policy}. Use manual or suggest.",
        )

    if archive_policy == "suggest" and archive_after_days is None:
        add_format_finding(
            result,
            options,
            "ARCHIVE_SUGGEST_WITHOUT_ARCHIVE_AFTER_DAYS",
            "archive_policy: suggest requires archive_after_days.",
        )
        return

    if archive_after_days is None:
        return

    try:
        days = int(archive_after_days)
    except ValueError:
        add_error(
            result,
            "INVALID_ARCHIVE_AFTER_DAYS",
            f"archive_after_days must be a positive integer: {archive_after_days}",
        )
        return

    if days <= 0:
        add_error(
            result,
            "INVALID_ARCHIVE_AFTER_DAYS",
            f"archive_after_days must be a positive integer: {archive_after_days}",
        )
        return

    if archive_policy is None:
        add_format_finding(
            result,
            options,
            "ARCHIVE_AFTER_DAYS_WITHOUT_POLICY",
            "archive_after_days is only meaningful with archive_policy: suggest.",
        )
    elif archive_policy == "manual":
        add_format_finding(
            result,
            options,
            "ARCHIVE_AFTER_DAYS_WITH_MANUAL_POLICY",
            "archive_after_days is only meaningful with archive_policy: suggest.",
        )


def require_field_value(
    result: ValidationResult,
    watch_id: str,
    fields: dict[str, str],
    field: str,
    context: str,
) -> None:
    if not fields[field]:
        add_error(result, "MISSING_FIELD_VALUE", f"{context} requires {field} in {watch_id}", watch_id, field)


def validate_status_rules(result: ValidationResult, watch_id: str, fields: dict[str, str]) -> None:
    status = fields["status"]
    if status not in VALID_STATUSES:
        add_error(result, "INVALID_STATUS", f"Invalid status in {watch_id}: {status}", watch_id, "status")
    if fields["priority"] not in VALID_PRIORITIES:
        add_error(result, "INVALID_PRIORITY", f"Invalid priority in {watch_id}: {fields['priority']}", watch_id, "priority")
    if fields["owner"] not in VALID_OWNERS:
        add_error(result, "INVALID_OWNER", f"Invalid owner in {watch_id}: {fields['owner']}", watch_id, "owner")

    validate_timestamp(result, watch_id, "due_at", fields["due_at"], allow_unscheduled=True)
    validate_timestamp(result, watch_id, "created_at", fields["created_at"], allow_unscheduled=False)
    if TIMESTAMP_RE.match(fields["created_at"]):
        try:
            created_at = datetime.fromisoformat(
                fields["created_at"].replace("Z", "+00:00")
            )
        except ValueError:
            pass
        else:
            if created_at.strftime("%Y%m%d") != watch_id[3:11]:
                add_error(
                    result,
                    "ID_CREATED_DATE_MISMATCH",
                    f"WATCHLIST ID date must match created_at local date in {watch_id}",
                    watch_id,
                    "created_at",
                )
    if fields["last_checked_at"]:
        validate_timestamp(
            result,
            watch_id,
            "last_checked_at",
            fields["last_checked_at"],
            allow_unscheduled=False,
        )

    if status == "open":
        for field in ("source", "trigger", "action", "done_when"):
            require_field_value(result, watch_id, fields, field, "open item")
    if status == "done":
        require_field_value(result, watch_id, fields, "result", "done item")
        require_field_value(result, watch_id, fields, "last_checked_at", "done item")
    if status == "snoozed":
        require_field_value(result, watch_id, fields, "result", "snoozed item")
        require_field_value(result, watch_id, fields, "last_checked_at", "snoozed item")
        if fields["due_at"] == "unscheduled":
            add_error(result, "SNOOZED_UNSCHEDULED", f"snoozed item requires scheduled due_at in {watch_id}", watch_id, "due_at")
    if status == "blocked":
        require_field_value(result, watch_id, fields, "result", "blocked item")
        require_field_value(result, watch_id, fields, "last_checked_at", "blocked item")
        require_field_value(result, watch_id, fields, "next_step_on_fail", "blocked item")
    if status == "dropped":
        require_field_value(result, watch_id, fields, "result", "dropped item")


def scan_document_safety(result: ValidationResult, text: str, strict_safety: bool) -> None:
    for code, (pattern, severity) in SENSITIVE_PATTERNS.items():
        match = re.search(pattern, text, flags=re.I)
        if not match:
            continue
        line = text.count("\n", 0, match.start()) + 1
        message = (
            f"Potential secret detected in WATCHLIST document line {line}: {code}.\n"
            f"{REDACTION_GUIDANCE}"
        )
        if strict_safety:
            add_error(result, code, message, severity="error")
        else:
            add_warning(result, code, message)


def validate(text: str, path: str, options: ValidationOptions) -> ValidationResult:
    result = ValidationResult(path=path)
    validate_skeleton(text, result, options)
    validate_top_level_fields(text, result, options)
    scan_document_safety(result, text, options.strict_safety)

    structure = structural_text(text)
    validate_heading_candidates(structure, result)
    blocks = item_blocks(structure)
    result.items = len(blocks)
    ids: list[str] = []
    parsed: list[tuple[str, dict[str, str]]] = []
    for block in blocks:
        watch_id = heading_info(block, result, options)
        if not watch_id:
            continue
        ids.append(watch_id)
        fields = fields_for_block(block, watch_id, result, options)
        parsed.append((watch_id, fields))

    duplicate_ids = sorted(
        watch_id for watch_id, count in Counter(ids).items() if count > 1
    )
    if duplicate_ids:
        add_error(result, "DUPLICATE_IDS", f"Duplicate WATCHLIST IDs: {', '.join(duplicate_ids)}")

    for watch_id, fields in parsed:
        missing = sorted(REQUIRED_FIELDS - fields.keys())
        if missing:
            add_error(
                result,
                "MISSING_REQUIRED_FIELDS",
                f"Missing required field(s) in {watch_id}: {', '.join(missing)}",
                watch_id,
            )
            continue
        validate_status_rules(result, watch_id, fields)

    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate WATCHLIST.md structure and safety.")
    parser.add_argument("path", nargs="?", default=".watchlist/WATCHLIST.md")
    parser.add_argument("--strict-format", action="store_true")
    parser.add_argument("--strict-safety", action="store_true")
    parser.add_argument("--require-archive-section", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args(argv[1:])


def result_payload(result: ValidationResult) -> dict[str, object]:
    return {
        "ok": result.ok,
        "path": result.path,
        "items": result.items,
        "warnings": [asdict(warning) for warning in result.warnings],
        "errors": [asdict(error) for error in result.errors],
    }


def print_plain(result: ValidationResult) -> None:
    for warning in result.warnings:
        print(f"{warning.code}: {warning.message}")
    if result.ok:
        print("WATCHLIST.md validation passed")
        return
    for error in result.errors:
        print(f"{error.code}: {error.message}", file=sys.stderr)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    path = Path(args.path)
    options = ValidationOptions(
        strict_format=args.strict_format,
        strict_safety=args.strict_safety,
        require_archive_section=args.require_archive_section,
    )

    if not path.is_file():
        result = ValidationResult(path=str(path))
        add_error(result, "WATCHLIST_FILE_NOT_FOUND", f"WATCHLIST file not found: {path}")
    else:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError as exc:
            result = ValidationResult(path=str(path))
            add_error(result, "INVALID_UTF8", f"WATCHLIST file is not valid UTF-8: {exc}")
        except OSError as exc:
            result = ValidationResult(path=str(path))
            add_error(result, "WATCHLIST_READ_ERROR", f"Could not read WATCHLIST file: {exc}")
        else:
            result = validate(text, str(path), options)

    if args.json_output:
        print(json.dumps(result_payload(result), ensure_ascii=False, indent=2))
    else:
        print_plain(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

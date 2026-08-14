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


VALID_STATUSES = {"open", "blocked", "done", "dropped"}
VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}
ALLOWED_TOP_LEVEL_FIELDS = {"schema_version", "timezone"}
REQUIRED_FIELDS = {"status", "due_at", "created_at", "source", "action", "done_when"}
OPTIONAL_STRUCTURED_FIELDS = {"priority", "owner", "last_checked_at", "result"}
TERMINAL_STATUSES = {"done", "dropped"}

ITEM_CANDIDATE_RE = re.compile(
    r"^[ \t]{0,3}#{1,6}[ \t]*(?i:WL)(?=[^A-Za-z]|$).*$", re.M
)
ITEM_HEADING_RE = re.compile(
    r"^### (?P<id>WL-(?P<date>\d{8})-(?P<sequence>\d{3}))"
    r" - (?P<title>\S(?:.*\S)?)\s*$"
)
SECTION_RE = re.compile(r"^## (?P<name>Open|Done|Archive)\s*$", re.M)
ANY_SECTION_RE = re.compile(r"^##(?!#)[ \t]+(?P<name>\S(?:.*\S)?)\s*$", re.M)
FIELD_RE = re.compile(
    r"^- (?P<field>[A-Za-z_][A-Za-z0-9_-]*):[ \t]*(?P<value>.*)$", re.M
)
TOP_LEVEL_FIELD_RE = re.compile(
    r"^(?P<field>[A-Za-z_][A-Za-z0-9_-]*):[ \t]*(?P<value>.*)$", re.M
)
FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,}).*$")
TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)

SENSITIVE_PATTERNS = {
    "PRIVATE_KEY": r"-----BEGIN (?:RSA |EC |OPENSSH |)?PRIVATE KEY-----",
    "BEARER_TOKEN": r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}",
    "AUTHORIZATION_HEADER": r"\bAuthorization:\s*\S+",
    "GITHUB_TOKEN": r"\bgh[pousr]_[A-Za-z0-9_]{20,}",
    "JWT": (
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."
        r"[A-Za-z0-9_-]{10,}\b"
    ),
    "AWS_SIGNED_URL": r"\bX-Amz-(?:Signature|Credential|Security-Token)=",
    "TOKENIZED_URL": r"[?&](?:sig|signature|token|access_token)=\S+",
    "PASSWORD_ASSIGNMENT": (
        r"\b(?:password|passwd|pwd|api[_-]?key|secret[_-]?key)\s*[:=]\s*\S+"
    ),
}


@dataclass
class Finding:
    code: str
    message: str
    id: Optional[str] = None
    field: Optional[str] = None


@dataclass
class ValidationResult:
    path: str
    items: int = 0
    errors: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def add_finding(
    result: ValidationResult,
    code: str,
    message: str,
    *,
    watch_id: Optional[str] = None,
    field_name: Optional[str] = None,
) -> None:
    result.errors.append(Finding(code, message, watch_id, field_name))


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
    output: list[str] = []
    fence_char: Optional[str] = None
    fence_length = 0

    for line in text.splitlines(keepends=True):
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


def structural_text(text: str) -> str:
    return strip_fenced_code_blocks(strip_html_comments(text))


def validate_document_shape(text: str, result: ValidationResult) -> None:
    if not re.search(r"^# WATCHLIST\.md\s*$", text, re.M):
        add_finding(result, "MISSING_HEADING", "Missing heading: # WATCHLIST.md")

    preamble = re.split(r"^##\s+", text, maxsplit=1, flags=re.M)[0]
    fields: dict[str, str] = {}
    for match in TOP_LEVEL_FIELD_RE.finditer(preamble):
        name = match.group("field")
        if name in fields:
            add_finding(
                result,
                "DUPLICATE_TOP_LEVEL_FIELD",
                f"Duplicate top-level field: {name}",
            )
        if name not in ALLOWED_TOP_LEVEL_FIELDS:
            add_finding(
                result,
                "UNKNOWN_TOP_LEVEL_FIELD",
                f"Unsupported top-level field: {name}",
                field_name=name,
            )
        fields[name] = match.group("value").strip()

    if fields.get("schema_version") != "2":
        add_finding(
            result,
            "UNSUPPORTED_SCHEMA",
            "WATCHLIST.md must use schema_version: 2.",
        )
    timezone = fields.get("timezone", "")
    if not timezone or re.search(r"\s", timezone):
        add_finding(
            result,
            "INVALID_TIMEZONE",
            "timezone must be a non-empty name without whitespace.",
        )

    section_names = [match.group("name") for match in SECTION_RE.finditer(text)]
    counts = Counter(section_names)
    for required in ("Open", "Done"):
        if counts[required] == 0:
            add_finding(
                result,
                "MISSING_SECTION",
                f"Missing section: ## {required}",
            )
    for name, count in counts.items():
        if count > 1:
            add_finding(
                result,
                "DUPLICATE_SECTION",
                f"Duplicate section: ## {name}",
            )
    for match in ANY_SECTION_RE.finditer(text):
        name = match.group("name")
        if name not in {"Open", "Done", "Archive"}:
            add_finding(
                result,
                "UNKNOWN_SECTION",
                f"Unsupported section: ## {name}",
            )


def validate_timestamp(
    result: ValidationResult,
    watch_id: str,
    field_name: str,
    value: str,
    *,
    allow_unscheduled: bool = False,
) -> Optional[datetime]:
    if allow_unscheduled and value == "unscheduled":
        return None
    if not TIMESTAMP_RE.fullmatch(value):
        add_finding(
            result,
            f"INVALID_{field_name.upper()}",
            f"Invalid {field_name} in {watch_id}: {value}",
            watch_id=watch_id,
            field_name=field_name,
        )
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        add_finding(
            result,
            f"INVALID_{field_name.upper()}",
            f"Invalid {field_name} in {watch_id}: {value}",
            watch_id=watch_id,
            field_name=field_name,
        )
        return None


def parse_fields(
    block: str, watch_id: str, result: ValidationResult
) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in FIELD_RE.finditer(block):
        name = match.group("field")
        if name in fields:
            add_finding(
                result,
                "DUPLICATE_FIELD",
                f"Duplicate field in {watch_id}: {name}",
                watch_id=watch_id,
                field_name=name,
            )
        fields[name] = match.group("value").strip()
    return fields


def validate_item(
    match: re.Match[str],
    block: str,
    section: Optional[str],
    result: ValidationResult,
) -> str:
    watch_id = match.group("id")
    try:
        datetime.strptime(match.group("date"), "%Y%m%d")
    except ValueError:
        add_finding(
            result,
            "INVALID_ID_DATE",
            f"Invalid calendar date in WATCHLIST ID: {watch_id}",
            watch_id=watch_id,
        )
    if match.group("sequence") == "000":
        add_finding(
            result,
            "INVALID_ID_SEQUENCE",
            f"WATCHLIST ID sequence must be 001-999: {watch_id}",
            watch_id=watch_id,
        )

    fields = parse_fields(block, watch_id, result)
    missing = sorted(REQUIRED_FIELDS - fields.keys())
    if missing:
        add_finding(
            result,
            "MISSING_REQUIRED_FIELDS",
            f"Missing required field(s) in {watch_id}: {', '.join(missing)}",
            watch_id=watch_id,
        )
        return watch_id

    for name in REQUIRED_FIELDS:
        if not fields[name]:
            add_finding(
                result,
                "MISSING_FIELD_VALUE",
                f"Required field is empty in {watch_id}: {name}",
                watch_id=watch_id,
                field_name=name,
            )

    for name in sorted(OPTIONAL_STRUCTURED_FIELDS & fields.keys()):
        if not fields[name]:
            add_finding(
                result,
                "EMPTY_OPTIONAL_FIELD",
                f"Optional field must be omitted when empty in {watch_id}: {name}",
                watch_id=watch_id,
                field_name=name,
            )

    status = fields["status"]
    if status not in VALID_STATUSES:
        add_finding(
            result,
            "INVALID_STATUS",
            f"Invalid status in {watch_id}: {status}",
            watch_id=watch_id,
            field_name="status",
        )
    priority = fields.get("priority")
    if priority and priority not in VALID_PRIORITIES:
        add_finding(
            result,
            "INVALID_PRIORITY",
            f"Invalid priority in {watch_id}: {priority}",
            watch_id=watch_id,
            field_name="priority",
        )

    validate_timestamp(
        result, watch_id, "due_at", fields["due_at"], allow_unscheduled=True
    )
    created_at = validate_timestamp(result, watch_id, "created_at", fields["created_at"])
    if created_at and created_at.strftime("%Y%m%d") != match.group("date"):
        add_finding(
            result,
            "ID_CREATED_DATE_MISMATCH",
            f"ID date must match created_at local date in {watch_id}",
            watch_id=watch_id,
            field_name="created_at",
        )
    if fields.get("last_checked_at"):
        validate_timestamp(
            result, watch_id, "last_checked_at", fields["last_checked_at"]
        )

    if status in {"blocked", "done", "dropped"}:
        for name in ("last_checked_at", "result"):
            if not fields.get(name):
                add_finding(
                    result,
                    "MISSING_TRANSITION_EVIDENCE",
                    f"{status} item requires {name} in {watch_id}",
                    watch_id=watch_id,
                    field_name=name,
                )

    if status in {"open", "blocked"} and section != "Open":
        add_finding(
            result,
            "INVALID_SECTION",
            f"Active item must be under ## Open: {watch_id}",
            watch_id=watch_id,
        )
    if status in TERMINAL_STATUSES and section not in {"Done", "Archive"}:
        add_finding(
            result,
            "INVALID_SECTION",
            f"Terminal item must be under ## Done or ## Archive: {watch_id}",
            watch_id=watch_id,
        )
    return watch_id


def scan_safety(text: str, result: ValidationResult) -> None:
    for code, pattern in SENSITIVE_PATTERNS.items():
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        line = text.count("\n", 0, match.start()) + 1
        add_finding(
            result,
            code,
            f"Potential sensitive value at line {line}; remove it and keep a safe pointer.",
        )


def validate(text: str, path: str = "WATCHLIST.md") -> ValidationResult:
    result = ValidationResult(path=path)
    scan_safety(text, result)
    structure = structural_text(text)
    validate_document_shape(structure, result)

    candidates = list(ITEM_CANDIDATE_RE.finditer(structure))
    valid_item_headings: list[tuple[re.Match[str], int]] = []
    for candidate in candidates:
        match = ITEM_HEADING_RE.fullmatch(candidate.group(0))
        if match:
            valid_item_headings.append((match, candidate.start()))
        else:
            add_finding(
                result,
                "MALFORMED_HEADING",
                f"Malformed WATCHLIST item heading: {candidate.group(0).strip()}",
            )

    ids: list[str] = []
    sections = list(ANY_SECTION_RE.finditer(structure))
    section_index = 0
    current_section: Optional[str] = None
    for index, (match, position) in enumerate(valid_item_headings):
        while section_index < len(sections) and sections[section_index].start() < position:
            current_section = sections[section_index].group("name")
            section_index += 1
        next_item_start = (
            valid_item_headings[index + 1][1]
            if index + 1 < len(valid_item_headings)
            else len(structure)
        )
        next_section_start = (
            sections[section_index].start()
            if section_index < len(sections)
            else len(structure)
        )
        end = min(next_item_start, next_section_start)
        ids.append(
            validate_item(match, structure[position:end], current_section, result)
        )

    result.items = len(valid_item_headings)
    duplicates = sorted(watch_id for watch_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        add_finding(
            result,
            "DUPLICATE_IDS",
            "Duplicate WATCHLIST IDs: " + ", ".join(duplicates),
        )
    return result


def result_payload(result: ValidationResult) -> dict[str, object]:
    return {
        "ok": result.ok,
        "path": result.path,
        "items": result.items,
        "errors": [asdict(item) for item in result.errors],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate WATCHLIST.md schema v2.")
    parser.add_argument("path", nargs="?", default=".watchlist/WATCHLIST.md")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args(argv[1:])


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    path = Path(args.path)
    if not path.is_file():
        result = ValidationResult(path=str(path))
        add_finding(result, "FILE_NOT_FOUND", f"WATCHLIST file not found: {path}")
    else:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError as exc:
            result = ValidationResult(path=str(path))
            add_finding(result, "INVALID_UTF8", f"WATCHLIST file is not UTF-8: {exc}")
        except OSError as exc:
            result = ValidationResult(path=str(path))
            add_finding(result, "READ_ERROR", f"Could not read WATCHLIST file: {exc}")
        else:
            result = validate(text, str(path))

    if args.json_output:
        print(json.dumps(result_payload(result), ensure_ascii=False, indent=2))
    else:
        for error in result.errors:
            print(f"{error.code}: {error.message}", file=sys.stderr)
        if result.ok:
            print("WATCHLIST.md schema v2 validation passed")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

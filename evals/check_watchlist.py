#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path


VALID_STATUSES = {"open", "snoozed", "blocked", "done", "dropped"}
VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}
# "agent" is accepted for legacy compatibility.
VALID_OWNERS = {"user", "assistant_on_review", "both", "external", "agent"}
REQUIRED_FIELDS = {
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
SKELETON_FIELDS = ("schema_version", "automation", "timezone")
SKELETON_SECTIONS = ("## Open", "## Done")
HEADING_RE = re.compile(r"^### (WL-\d{8}-\d{3})\s+(?:—|-)\s+.+$")
TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$"
)


def fail(message: str) -> None:
    raise SystemExit(message)


def item_blocks(text: str) -> list[str]:
    text = strip_html_comments(text)
    return [
        block
        for block in re.split(r"(?=^### WL)", text, flags=re.M)
        if block.startswith("### WL")
    ]


def strip_html_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def item_id(block: str) -> str:
    heading = block.splitlines()[0]
    match = HEADING_RE.match(heading)
    if not match:
        fail(f"Malformed WATCHLIST item heading: {heading}")
    return match.group(1)


def field_map(block: str, watch_id: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in re.finditer(r"^- ([a-z_]+):[ \t]*(.*)$", block, flags=re.M):
        field = match.group(1)
        if field in fields:
            fail(f"Duplicate field in {watch_id}: {field}")
        fields[field] = match.group(2).strip()
    return fields


def validate_timestamp(watch_id: str, field: str, value: str, allow_unscheduled: bool) -> None:
    if allow_unscheduled and value == "unscheduled":
        return
    if not TIMESTAMP_RE.match(value):
        fail(f"Invalid {field} in {watch_id}: {value}")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(f"Invalid {field} in {watch_id}: {value}")


def validate_skeleton(text: str) -> None:
    text = strip_html_comments(text)
    for field in SKELETON_FIELDS:
        if not re.search(rf"^{field}:\s*\S+", text, flags=re.M):
            fail(f"Missing WATCHLIST skeleton field: {field}")
    if not re.search(r"^# WATCHLIST\.md\s*$", text, flags=re.M):
        fail("Missing WATCHLIST skeleton heading: # WATCHLIST.md")
    for section in SKELETON_SECTIONS:
        if not re.search(rf"^{re.escape(section)}\s*$", text, flags=re.M):
            fail(f"Missing WATCHLIST skeleton section: {section}")


def require_field_value(watch_id: str, fields: dict[str, str], field: str, context: str) -> None:
    if not fields[field]:
        fail(f"{context} requires {field} in {watch_id}")


def validate(text: str) -> None:
    validate_skeleton(text)

    ids = [item_id(block) for block in item_blocks(text)]
    duplicate_ids = sorted({watch_id for watch_id in ids if ids.count(watch_id) > 1})
    if duplicate_ids:
        fail(f"Duplicate WATCHLIST IDs: {', '.join(duplicate_ids)}")

    for block in item_blocks(text):
        watch_id = item_id(block)
        fields = field_map(block, watch_id)
        missing = sorted(REQUIRED_FIELDS - fields.keys())
        if missing:
            fail(f"Missing required field(s) in {watch_id}: {', '.join(missing)}")

        status = fields["status"]
        if status not in VALID_STATUSES:
            fail(f"Invalid status in {watch_id}: {status}")
        if fields["priority"] not in VALID_PRIORITIES:
            fail(f"Invalid priority in {watch_id}: {fields['priority']}")
        if fields["owner"] not in VALID_OWNERS:
            fail(f"Invalid owner in {watch_id}: {fields['owner']}")

        validate_timestamp(watch_id, "due_at", fields["due_at"], allow_unscheduled=True)
        validate_timestamp(watch_id, "created_at", fields["created_at"], allow_unscheduled=False)
        if fields["last_checked_at"]:
            validate_timestamp(
                watch_id,
                "last_checked_at",
                fields["last_checked_at"],
                allow_unscheduled=False,
            )

        if status == "done":
            require_field_value(watch_id, fields, "result", "done item")
            require_field_value(watch_id, fields, "last_checked_at", "done item")
        if status == "snoozed":
            require_field_value(watch_id, fields, "result", "snoozed item")
            require_field_value(watch_id, fields, "last_checked_at", "snoozed item")
            if fields["due_at"] == "unscheduled":
                fail(f"snoozed item requires scheduled due_at in {watch_id}")
        if status == "blocked":
            require_field_value(watch_id, fields, "result", "blocked item")
            require_field_value(watch_id, fields, "last_checked_at", "blocked item")
            require_field_value(watch_id, fields, "next_step_on_fail", "blocked item")
        if status == "dropped":
            require_field_value(watch_id, fields, "result", "dropped item")


def main(argv: list[str]) -> int:
    path = Path(argv[1] if len(argv) > 1 else ".watchlist/WATCHLIST.md")
    if not path.is_file():
        fail(f"WATCHLIST file not found: {path}")
    text = path.read_text(encoding="utf-8")
    validate(text)
    print("WATCHLIST.md validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

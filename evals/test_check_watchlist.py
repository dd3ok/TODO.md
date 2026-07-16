#!/usr/bin/env python3
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
import warnings
import csv
import importlib.util
import json
import re
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / ".agents" / "skills" / "watchlist-md"
CHECK_SCRIPT = REPO_ROOT / "evals" / "check_watchlist.py"
POLICY_SCRIPT = REPO_ROOT / "evals" / "check_policy_markers.py"
RELEASE_SCRIPT = REPO_ROOT / "evals" / "check_release_metadata.py"
SEMANTIC_SCRIPT = REPO_ROOT / "evals" / "check_semantic_cases.py"
PACKAGE_SCRIPT = REPO_ROOT / "evals" / "check_skill_package.py"
REPO_VALIDATOR = REPO_ROOT / "tools" / "validate_watchlist.py"
TRIGGER_CASES = REPO_ROOT / "evals" / "trigger_cases.json"

_SEMANTIC_SPEC = importlib.util.spec_from_file_location(
    "check_semantic_cases", SEMANTIC_SCRIPT
)
SEMANTIC_CASES = importlib.util.module_from_spec(_SEMANTIC_SPEC)
_SEMANTIC_SPEC.loader.exec_module(SEMANTIC_CASES)

_PACKAGE_SPEC = importlib.util.spec_from_file_location(
    "check_skill_package", PACKAGE_SCRIPT
)
PACKAGE_CHECK = importlib.util.module_from_spec(_PACKAGE_SPEC)
_PACKAGE_SPEC.loader.exec_module(PACKAGE_CHECK)

_CHECK_WRAPPER_SPEC = importlib.util.spec_from_file_location(
    "check_watchlist_wrapper", CHECK_SCRIPT
)
CHECK_WRAPPER = importlib.util.module_from_spec(_CHECK_WRAPPER_SPEC)
_CHECK_WRAPPER_SPEC.loader.exec_module(CHECK_WRAPPER)


def parse_skill_frontmatter_description(text):
    frontmatter = text.split("---", 2)[1]
    inline_match = re.search(r"^description:\s+(?P<value>.+)$", frontmatter, flags=re.M)
    if inline_match:
        value = inline_match.group("value").strip()
        if value not in {">", ">-", ">|", "|", "|-"}:
            return value.strip("'\"")

    block_match = re.search(
        r"^description:\s*[>|]-?\s*\n(?P<body>(?:  .+\n?)+)",
        frontmatter,
        flags=re.M,
    )
    if block_match:
        return " ".join(line.strip() for line in block_match.group("body").splitlines())

    return None


VALID_WATCHLIST = """# WATCHLIST.md

schema_version: 1
automation: none
timezone: Asia/Seoul

## Open

### WL-20260514-001 — CI result check
- status: open
- priority: P1
- owner: assistant_on_review
- due_at: 2026-05-14T17:00:00+09:00
- created_at: 2026-05-14T16:30:00+09:00
- source: GitHub Actions run for PR #12
- trigger: CI was still running
- action: Check GitHub Actions result
- done_when: All jobs pass or failure cause is recorded
- last_checked_at:
- result:
- next_step_on_fail: Summarize failing logs

## Done
"""


class CheckWatchlistTests(unittest.TestCase):
    def run_check(self, text, *args):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "WATCHLIST.md"
            path.write_text(text, encoding="utf-8")
            return self.run_check_path(path, *args)

    def run_check_path(self, path, *args):
        return subprocess.run(
            [sys.executable, str(CHECK_SCRIPT), str(path), *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_script(self, script):
        return subprocess.run(
            [sys.executable, str(script)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_repo_validator(self, path, *args):
        return subprocess.run(
            [sys.executable, str(REPO_VALIDATOR), str(path), *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_release_metadata_fixture(self, version, changelog, *args):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "VERSION").write_text(version, encoding="utf-8")
            (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(RELEASE_SCRIPT), str(root), *args],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

    def assert_check_fails(self, text, expected_message):
        result = self.run_check(text)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(expected_message, result.stderr + result.stdout)

    def assert_check_fails_with_args(self, text, expected_message, *args):
        result = self.run_check(text, *args)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(expected_message, result.stderr + result.stdout)

    def test_valid_watchlist_passes(self):
        result = self.run_check(VALID_WATCHLIST)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("validation passed", result.stdout)

    def test_json_output_success_is_machine_readable(self):
        result = self.run_check(VALID_WATCHLIST, "--json")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["items"], 1)
        self.assertEqual(payload["errors"], [])
        self.assertIn("warnings", payload)

    def test_json_output_failure_is_machine_readable(self):
        text = VALID_WATCHLIST.replace("- status: open", "- status: waiting")

        result = self.run_check(text, "--json")

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["code"], "INVALID_STATUS")
        self.assertNotIn("Traceback", result.stderr + result.stdout)

    def test_commented_placeholder_heading_is_ignored(self):
        text = VALID_WATCHLIST.replace(
            "## Open\n",
            "## Open\n\n<!--\n### WL-YYYYMMDD-NNN — Short title\n- status: open\n-->\n",
        )

        result = self.run_check(text)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_duplicate_ids_fail(self):
        text = VALID_WATCHLIST + VALID_WATCHLIST.split("### WL-20260514-001", 1)[1].join(
            ["\n### WL-20260514-001", ""]
        )

        self.assert_check_fails(text, "Duplicate WATCHLIST IDs")

    def test_invalid_status_fails(self):
        text = VALID_WATCHLIST.replace("- status: open", "- status: waiting")

        self.assert_check_fails(text, "Invalid status")

    def test_invalid_priority_fails(self):
        text = VALID_WATCHLIST.replace("- priority: P1", "- priority: urgent")

        self.assert_check_fails(text, "Invalid priority")

    def test_invalid_owner_fails(self):
        text = VALID_WATCHLIST.replace("- owner: assistant_on_review", "- owner: bot")

        self.assert_check_fails(text, "Invalid owner")

    def test_invalid_schema_version_fails(self):
        text = VALID_WATCHLIST.replace("schema_version: 1", "schema_version: banana")

        self.assert_check_fails(text, "INVALID_SCHEMA_VERSION")

    def test_invalid_automation_fails(self):
        text = VALID_WATCHLIST.replace("automation: none", "automation: cron")

        self.assert_check_fails(text, "INVALID_AUTOMATION")

    def test_owner_agent_is_not_supported(self):
        text = VALID_WATCHLIST.replace("- owner: assistant_on_review", "- owner: agent")

        self.assert_check_fails(text, "Invalid owner")

    def test_invalid_due_at_fails(self):
        text = VALID_WATCHLIST.replace(
            "- due_at: 2026-05-14T17:00:00+09:00", "- due_at: tomorrow"
        )

        self.assert_check_fails(text, "Invalid due_at")

    def test_impossible_timestamp_fails(self):
        text = VALID_WATCHLIST.replace(
            "- due_at: 2026-05-14T17:00:00+09:00",
            "- due_at: 2026-99-99T99:99:99+09:00",
        )

        self.assert_check_fails(text, "Invalid due_at")

    def test_timestamp_offset_minute_overflow_fails(self):
        text = VALID_WATCHLIST.replace(
            "- due_at: 2026-05-14T17:00:00+09:00",
            "- due_at: 2026-05-14T17:00:00+09:60",
        )

        self.assert_check_fails(text, "Invalid due_at")

    def test_item_id_date_must_match_created_at_local_date(self):
        text = VALID_WATCHLIST.replace("WL-20260514-001", "WL-20260513-001")

        self.assert_check_fails(text, "ID_CREATED_DATE_MISMATCH")

    def test_open_item_requires_semantic_field_values(self):
        for field in ("source", "trigger", "action", "done_when"):
            with self.subTest(field=field):
                text = re.sub(rf"^- {field}:.*$", f"- {field}:", VALID_WATCHLIST, flags=re.M)
                self.assert_check_fails(text, f"open item requires {field}")

    def test_duplicate_field_fails(self):
        text = VALID_WATCHLIST.replace(
            "- status: open\n", "- status: open\n- status: blocked\n"
        )

        self.assert_check_fails(text, "Duplicate field")

    def test_done_without_result_fails(self):
        text = VALID_WATCHLIST.replace("- status: open", "- status: done")

        self.assert_check_fails(text, "done item requires result")

    def test_done_requires_last_checked_at(self):
        text = VALID_WATCHLIST.replace("- status: open", "- status: done").replace(
            "- result:", "- result: CI passed"
        )

        self.assert_check_fails(text, "done item requires last_checked_at")

    def test_blocked_without_next_step_fails(self):
        text = (
            VALID_WATCHLIST.replace("- status: open", "- status: blocked")
            .replace("- last_checked_at:", "- last_checked_at: 2026-05-14T17:00:00+09:00")
            .replace("- result:", "- result: CI failed")
            .replace("- next_step_on_fail: Summarize failing logs", "- next_step_on_fail:")
        )

        self.assert_check_fails(text, "blocked item requires next_step_on_fail")

    def test_malformed_watchlist_heading_fails(self):
        text = VALID_WATCHLIST.replace("### WL-20260514-001", "### WL-20260514-01")

        self.assert_check_fails(text, "Malformed WATCHLIST item heading")

    def test_malformed_watchlist_heading_without_dash_fails(self):
        text = VALID_WATCHLIST.replace("### WL-20260514-001", "### WL20260514-001")

        self.assert_check_fails(text, "Malformed WATCHLIST item heading")

    def test_lowercase_watchlist_heading_fails(self):
        text = VALID_WATCHLIST.replace("### WL-20260514-001", "### wl-20260514-001")

        self.assert_check_fails(text, "Malformed WATCHLIST item heading")

    def test_wrong_heading_level_fails(self):
        text = VALID_WATCHLIST.replace("### WL-20260514-001", "#### WL-20260514-001")

        self.assert_check_fails(text, "Malformed WATCHLIST item heading")

    def test_invalid_calendar_date_in_id_fails(self):
        text = VALID_WATCHLIST.replace("WL-20260514-001", "WL-20260230-001")

        self.assert_check_fails(text, "INVALID_ID_DATE")

    def test_zero_id_sequence_fails(self):
        text = VALID_WATCHLIST.replace("WL-20260514-001", "WL-20260514-000")

        self.assert_check_fails(text, "INVALID_ID_SEQUENCE")

    def test_empty_heading_title_fails(self):
        text = VALID_WATCHLIST.replace("### WL-20260514-001 — CI result check", "### WL-20260514-001 —   ")

        self.assert_check_fails(text, "Malformed WATCHLIST item heading")

    def test_default_mode_accepts_hyphen_heading_separator(self):
        text = VALID_WATCHLIST.replace(" — CI result check", " - CI result check")

        result = self.run_check(text)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_strict_format_rejects_hyphen_heading_separator(self):
        text = VALID_WATCHLIST.replace(" — CI result check", " - CI result check")

        self.assert_check_fails_with_args(
            text,
            "NON_STRICT_HEADING_SEPARATOR",
            "--strict-format",
        )

    def test_strict_format_rejects_field_order_drift(self):
        text = VALID_WATCHLIST.replace(
            "- status: open\n- priority: P1\n",
            "- priority: P1\n- status: open\n",
        )

        self.assert_check_fails_with_args(text, "FIELD_ORDER", "--strict-format")

    def test_strict_format_rejects_hyphenated_unknown_item_field(self):
        text = VALID_WATCHLIST.replace(
            "- result:\n",
            "- custom-field: unexpected\n- result:\n",
        )

        self.assert_check_fails_with_args(text, "UNKNOWN_FIELD", "--strict-format")

    def test_strict_format_rejects_uppercase_unknown_item_field(self):
        text = VALID_WATCHLIST.replace(
            "- result:\n",
            "- Note: unexpected\n- result:\n",
        )

        self.assert_check_fails_with_args(text, "UNKNOWN_FIELD", "--strict-format")

    def test_require_archive_section_rejects_missing_archive(self):
        self.assert_check_fails_with_args(
            VALID_WATCHLIST,
            "Missing WATCHLIST skeleton section: ## Archive",
            "--require-archive-section",
        )

    def test_valid_archive_policy_passes_strict_format(self):
        text = VALID_WATCHLIST.replace(
            "timezone: Asia/Seoul\n",
            "timezone: Asia/Seoul\narchive_policy: manual\n",
        )

        result = self.run_check(text, "--strict-format")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_invalid_archive_policy_fails(self):
        text = VALID_WATCHLIST.replace(
            "timezone: Asia/Seoul\n",
            "timezone: Asia/Seoul\narchive_policy: automatic\n",
        )

        self.assert_check_fails(text, "INVALID_ARCHIVE_POLICY")

    def test_invalid_archive_after_days_fails(self):
        text = VALID_WATCHLIST.replace(
            "timezone: Asia/Seoul\n",
            "timezone: Asia/Seoul\narchive_policy: suggest\narchive_after_days: 0\n",
        )

        self.assert_check_fails(text, "INVALID_ARCHIVE_AFTER_DAYS")

    def test_archive_after_days_with_manual_policy_warns_by_default(self):
        text = VALID_WATCHLIST.replace(
            "timezone: Asia/Seoul\n",
            "timezone: Asia/Seoul\narchive_policy: manual\narchive_after_days: 30\n",
        )

        result = self.run_check(text)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("ARCHIVE_AFTER_DAYS_WITH_MANUAL_POLICY", result.stdout)

    def test_archive_after_days_with_manual_policy_fails_strict_format(self):
        text = VALID_WATCHLIST.replace(
            "timezone: Asia/Seoul\n",
            "timezone: Asia/Seoul\narchive_policy: manual\narchive_after_days: 30\n",
        )

        self.assert_check_fails_with_args(
            text,
            "ARCHIVE_AFTER_DAYS_WITH_MANUAL_POLICY",
            "--strict-format",
        )

    def test_archive_after_days_without_policy_fails_strict_format(self):
        text = VALID_WATCHLIST.replace(
            "timezone: Asia/Seoul\n",
            "timezone: Asia/Seoul\narchive_after_days: 30\n",
        )

        self.assert_check_fails_with_args(
            text,
            "ARCHIVE_AFTER_DAYS_WITHOUT_POLICY",
            "--strict-format",
        )

    def test_archive_suggest_without_after_days_warns_by_default(self):
        text = VALID_WATCHLIST.replace(
            "timezone: Asia/Seoul\n",
            "timezone: Asia/Seoul\narchive_policy: suggest\n",
        )

        result = self.run_check(text)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("ARCHIVE_SUGGEST_WITHOUT_ARCHIVE_AFTER_DAYS", result.stdout)

    def test_archive_suggest_without_after_days_fails_strict_format(self):
        text = VALID_WATCHLIST.replace(
            "timezone: Asia/Seoul\n",
            "timezone: Asia/Seoul\narchive_policy: suggest\n",
        )

        self.assert_check_fails_with_args(
            text,
            "ARCHIVE_SUGGEST_WITHOUT_ARCHIVE_AFTER_DAYS",
            "--strict-format",
        )

    def test_duplicate_top_level_field_fails(self):
        text = VALID_WATCHLIST.replace(
            "timezone: Asia/Seoul\n",
            "timezone: Asia/Seoul\narchive_policy: manual\narchive_policy: suggest\narchive_after_days: 30\n",
        )

        self.assert_check_fails(text, "DUPLICATE_TOP_LEVEL_FIELD")

    def test_unknown_top_level_field_warns_by_default(self):
        text = VALID_WATCHLIST.replace(
            "timezone: Asia/Seoul\n",
            "timezone: Asia/Seoul\narchive_polciy: suggest\n",
        )

        result = self.run_check(text)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("UNKNOWN_TOP_LEVEL_FIELD", result.stdout)

    def test_unknown_top_level_field_fails_strict_format(self):
        text = VALID_WATCHLIST.replace(
            "timezone: Asia/Seoul\n",
            "timezone: Asia/Seoul\narchive_polciy: suggest\n",
        )

        self.assert_check_fails_with_args(
            text,
            "UNKNOWN_TOP_LEVEL_FIELD",
            "--strict-format",
        )

    def test_hyphenated_unknown_top_level_field_fails_strict_format(self):
        text = VALID_WATCHLIST.replace(
            "timezone: Asia/Seoul\n",
            "timezone: Asia/Seoul\narchive-policy: suggest\n",
        )

        self.assert_check_fails_with_args(
            text,
            "UNKNOWN_TOP_LEVEL_FIELD",
            "--strict-format",
        )

    def test_strict_safety_rejects_bearer_token(self):
        text = VALID_WATCHLIST.replace(
            "- source: GitHub Actions run for PR #12",
            "- source: Authorization: Bearer ghp_123456789012345678901234567890123456",
        )

        self.assert_check_fails_with_args(text, "Potential secret detected", "--strict-safety")

    def test_strict_safety_rejects_secret_in_comment(self):
        text = VALID_WATCHLIST.replace(
            "## Open\n",
            "<!-- Authorization: Bearer ghp_123456789012345678901234567890123456 -->\n## Open\n",
        )

        self.assert_check_fails_with_args(text, "AUTHORIZATION_HEADER", "--strict-safety")

    def test_strict_safety_rejects_raw_response_headers(self):
        text = VALID_WATCHLIST.replace(
            "- source: GitHub Actions run for PR #12",
            "- source: response headers from private API",
        )

        self.assert_check_fails_with_args(text, "RAW_PRIVATE_EXCERPT", "--strict-safety")

    def test_strict_safety_rejects_signed_url(self):
        text = VALID_WATCHLIST.replace(
            "- source: GitHub Actions run for PR #12",
            "- source: https://example.com/report?X-Amz-Signature=abc123",
        )

        self.assert_check_fails_with_args(text, "AWS_SIGNED_URL", "--strict-safety")

    def test_strict_safety_rejects_generic_signed_url(self):
        text = VALID_WATCHLIST.replace(
            "- source: GitHub Actions run for PR #12",
            "- source: https://example.com/report?token=abc123",
        )

        self.assert_check_fails_with_args(text, "GENERIC_SIGNED_URL", "--strict-safety")

    def test_strict_safety_escalates_warning_severity_in_json(self):
        text = VALID_WATCHLIST.replace(
            "- source: GitHub Actions run for PR #12",
            "- source: https://example.com/report?token=abc123",
        )

        result = self.run_check(text, "--strict-safety", "--json")

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["errors"][0]["code"], "GENERIC_SIGNED_URL")
        self.assertEqual(payload["errors"][0]["severity"], "error")

    def test_default_safety_scan_warns_without_failing(self):
        text = VALID_WATCHLIST.replace(
            "- source: GitHub Actions run for PR #12",
            "- source: https://example.com/report?token=abc123",
        )

        result = self.run_check(text)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("GENERIC_SIGNED_URL", result.stdout)
        self.assertIn("validation passed", result.stdout)

    def test_missing_required_field_fails(self):
        text = VALID_WATCHLIST.replace("- source: GitHub Actions run for PR #12\n", "")

        self.assert_check_fails(text, "Missing required field")

    def test_empty_file_fails_skeleton_validation(self):
        self.assert_check_fails("", "Missing WATCHLIST skeleton field")

    def test_commented_skeleton_does_not_count(self):
        text = """<!--
# WATCHLIST.md
schema_version: 1
automation: none
timezone: Asia/Seoul
## Open
## Done
-->
"""

        self.assert_check_fails(text, "Missing WATCHLIST skeleton field")

    def test_unclosed_comment_does_not_count_as_structure(self):
        text = "<!--\n" + VALID_WATCHLIST

        self.assert_check_fails(text, "Missing WATCHLIST skeleton field")

    def test_fenced_document_does_not_count_as_structure(self):
        text = f"```md\n{VALID_WATCHLIST}\n```\n"

        self.assert_check_fails(text, "Missing WATCHLIST skeleton field")

    def test_underscore_id_heading_is_reported_as_malformed(self):
        text = VALID_WATCHLIST.replace(
            "### WL-20260514-001 — CI result check",
            "### WL_20260514_001 — CI result check",
        )

        self.assert_check_fails_with_args(text, "MALFORMED_HEADING", "--strict-format")

    def test_indented_code_heading_is_not_treated_as_live_structure(self):
        text = VALID_WATCHLIST + "\n    ### WL_20260514_999 — code sample\n"

        result = self.run_check(text, "--strict-format")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_fenced_secret_is_still_scanned_for_safety(self):
        text = (
            VALID_WATCHLIST
            + "\n```text\nAuthorization: Bearer ghp_123456789012345678901234567890123456\n```\n"
        )

        self.assert_check_fails_with_args(text, "AUTHORIZATION_HEADER", "--strict-safety")

    def test_duplicate_done_section_fails(self):
        text = VALID_WATCHLIST + "\n## Done\n"

        self.assert_check_fails(text, "DUPLICATE_SKELETON_SECTION")

    def test_missing_open_section_fails_skeleton_validation(self):
        text = VALID_WATCHLIST.replace("## Open\n\n", "")

        self.assert_check_fails(text, "Missing WATCHLIST skeleton section: ## Open")

    def test_missing_done_section_fails_skeleton_validation(self):
        text = VALID_WATCHLIST.replace("\n## Done\n", "")

        self.assert_check_fails(text, "Missing WATCHLIST skeleton section: ## Done")

    def test_skeleton_fields_must_be_in_preamble(self):
        text = VALID_WATCHLIST.replace("schema_version: 1\n", "").replace(
            "## Open\n", "## Open\n\nschema_version: 1\n", 1
        )

        self.assert_check_fails(text, "Missing WATCHLIST skeleton field: schema_version")

    def test_missing_file_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_check_path(Path(tmpdir) / "missing.md")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("WATCHLIST file not found", result.stderr + result.stdout)
        self.assertNotIn("Traceback", result.stderr + result.stdout)

    def test_utf8_bom_file_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "WATCHLIST.md"
            path.write_text(VALID_WATCHLIST, encoding="utf-8-sig")
            result = self.run_check_path(path)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_invalid_utf8_json_failure_is_structured(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "WATCHLIST.md"
            path.write_bytes(b"# WATCHLIST.md\n\xff\n")
            result = self.run_check_path(path, "--json")

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["errors"][0]["code"], "INVALID_UTF8")
        self.assertNotIn("Traceback", result.stderr + result.stdout)

    def test_snoozed_requires_result_and_last_checked_at(self):
        text = (
            VALID_WATCHLIST.replace("- status: open", "- status: snoozed")
            .replace("- result:", "- result: Still pending")
            .replace("- last_checked_at:", "- last_checked_at:")
        )

        self.assert_check_fails(text, "snoozed item requires last_checked_at")

    def test_snoozed_requires_result(self):
        text = VALID_WATCHLIST.replace("- status: open", "- status: snoozed").replace(
            "- last_checked_at:", "- last_checked_at: 2026-05-14T17:00:00+09:00"
        )

        self.assert_check_fails(text, "snoozed item requires result")

    def test_snoozed_due_at_unscheduled_fails(self):
        text = (
            VALID_WATCHLIST.replace("- status: open", "- status: snoozed")
            .replace("- due_at: 2026-05-14T17:00:00+09:00", "- due_at: unscheduled")
            .replace("- last_checked_at:", "- last_checked_at: 2026-05-14T17:00:00+09:00")
            .replace("- result:", "- result: Still pending")
        )

        self.assert_check_fails(text, "snoozed item requires scheduled due_at")

    def test_open_due_at_unscheduled_passes(self):
        text = VALID_WATCHLIST.replace(
            "- due_at: 2026-05-14T17:00:00+09:00", "- due_at: unscheduled"
        )

        result = self.run_check(text)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_blocked_requires_result_and_last_checked_at(self):
        text = (
            VALID_WATCHLIST.replace("- status: open", "- status: blocked")
            .replace("- result:", "- result: Waiting on external approval")
            .replace("- last_checked_at:", "- last_checked_at:")
        )

        self.assert_check_fails(text, "blocked item requires last_checked_at")

    def test_blocked_requires_result(self):
        text = VALID_WATCHLIST.replace("- status: open", "- status: blocked").replace(
            "- last_checked_at:", "- last_checked_at: 2026-05-14T17:00:00+09:00"
        )

        self.assert_check_fails(text, "blocked item requires result")

    def test_dropped_requires_result(self):
        text = VALID_WATCHLIST.replace("- status: open", "- status: dropped")

        self.assert_check_fails(text, "dropped item requires result")

    def test_dropped_with_result_passes_without_last_checked_at(self):
        text = VALID_WATCHLIST.replace("- status: open", "- status: dropped").replace(
            "- result:", "- result: User cancelled the follow-up"
        )

        result = self.run_check(text)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_bundled_template_does_not_mark_live_mode_template(self):
        template = SKILL_DIR / "assets" / "WATCHLIST.template.md"
        text = template.read_text(encoding="utf-8")

        self.assertNotIn("mode: template", text)

    def test_legacy_mode_field_warns_that_it_has_no_effect(self):
        text = VALID_WATCHLIST.replace(
            "timezone: Asia/Seoul\n",
            "timezone: Asia/Seoul\nmode: template\n",
        )

        result = self.run_check(text)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("DEPRECATED_MODE_FIELD", result.stdout)
        self.assertIn("has no effect", result.stdout)

    def test_installable_skill_bundle_contains_runtime_resources(self):
        expected_files = [
            SKILL_DIR / "SKILL.md",
            SKILL_DIR / "LICENSE.txt",
            SKILL_DIR / "assets" / "WATCHLIST.template.md",
            SKILL_DIR / "references" / "format.md",
            SKILL_DIR / "references" / "lifecycle.md",
            SKILL_DIR / "references" / "safety.md",
            SKILL_DIR / "agents" / "openai.yaml",
        ]

        for path in expected_files:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"missing bundled resource: {path}")

        self.assertFalse(
            (SKILL_DIR / "references" / "self-checks.md").exists(),
            "maintainer self-check prompts must not ship in the runtime bundle",
        )
        self.assertTrue((REPO_ROOT / "docs" / "maintainers" / "self-checks.md").is_file())

    def test_installable_skill_bundle_is_python_family_free(self):
        python_files = sorted(
            p
            for p in SKILL_DIR.rglob("*")
            if p.suffix in {".py", ".pyw", ".pyc", ".pyo"}
        )
        scripts_dir = SKILL_DIR / "scripts"

        self.assertEqual(python_files, [])
        self.assertFalse(scripts_dir.exists(), "runtime skill bundle must not include scripts/")

    def test_repo_validator_can_validate_template(self):
        template = SKILL_DIR / "assets" / "WATCHLIST.template.md"

        result = self.run_repo_validator(
            template,
            "--strict-format",
            "--strict-safety",
            "--require-archive-section",
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("validation passed", result.stdout)

    def test_repo_validator_wrapper_delegates_to_tools_validator(self):
        wrapper = CHECK_SCRIPT.read_text(encoding="utf-8")
        template = SKILL_DIR / "assets" / "WATCHLIST.template.md"

        self.assertLess(len(wrapper), 2500)
        self.assertIn("tools", wrapper)
        self.assertIn("validate_watchlist.py", wrapper)
        self.assertNotIn("VALID_STATUSES", wrapper)

        repo_result = self.run_check_path(
            template,
            "--strict-format",
            "--strict-safety",
            "--require-archive-section",
        )
        direct_result = self.run_repo_validator(
            template,
            "--strict-format",
            "--strict-safety",
            "--require-archive-section",
        )

        self.assertEqual(repo_result.returncode, direct_result.returncode)
        self.assertEqual(repo_result.stdout, direct_result.stdout)
        self.assertEqual(repo_result.stderr, direct_result.stderr)

    def test_repo_validator_wrapper_main_normalizes_system_exit_to_return_code(self):
        original_argv = sys.argv[:]
        sys.argv = [str(CHECK_SCRIPT), "--help"]
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                result = CHECK_WRAPPER.main()
        finally:
            sys.argv = original_argv

        self.assertEqual(result, 0)

    def test_repo_validator_wrapper_help_exposes_bundled_options(self):
        result = subprocess.run(
            [sys.executable, str(CHECK_SCRIPT), "--help"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        for token in [
            "--strict-format",
            "--strict-safety",
            "--require-archive-section",
            "--json",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, result.stdout)

    def test_validator_has_no_dead_item_only_safety_scanner(self):
        validator = REPO_VALIDATOR.read_text(encoding="utf-8")

        self.assertNotIn("def scan_safety(", validator)
        self.assertIn("def scan_document_safety(", validator)

    def test_skill_runtime_guidance_stays_lean(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        body = text.split("---", 2)[-1]
        add_section = body.split("## Add", 1)[1].split("## Review", 1)[0]

        self.assertLessEqual(len(text.splitlines()), 100)
        self.assertLessEqual(len(text.encode("utf-8")), 4500)
        self.assertLessEqual(len(re.findall(r"\b\w+\b", body)), 590)
        self.assertLessEqual(len(re.findall(r"\b\w+\b", add_section)), 180)
        self.assertIn("references/lifecycle.md", text)
        self.assertIn("references/safety.md", text)
        self.assertNotIn("references/self-checks.md", text)
        self.assertLess(text.index("## Add"), text.index("references/lifecycle.md"))

    def test_skill_runtime_polish_markers_stay_precise(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        format_text = (SKILL_DIR / "references" / "format.md").read_text(encoding="utf-8")
        lifecycle = (SKILL_DIR / "references" / "lifecycle.md").read_text(encoding="utf-8")
        normalized_text = " ".join(text.split()).lower()
        normalized_format = " ".join(format_text.split())
        normalized_lifecycle = " ".join(lifecycle.split())
        timezone_precedence = (
            "Generate IDs from the WATCHLIST timezone: WATCHLIST.md `timezone:` field "
            "> explicit user timezone > environment/user timezone > Asia/Seoul."
        )
        required_information = (
            "For open items, keep field keys and enum values in English; "
            "populate: ID, status, priority, owner, due_at, created_at, source, "
            "trigger, action, and done_when."
        )

        self.assertIn("WATCHLIST-scoped operational pending result", text)
        self.assertNotIn("후속 체크로 기록, pending", text)
        self.assertIn(
            "scope pre-authorized watchlist recording to the current repo/workspace",
            normalized_text,
        )
        self.assertIn(
            "- source: short stable pointer, safe link, file, PR, issue, or conversation note",
            text,
        )
        self.assertIn("due_at", text)
        self.assertNotIn("due time", text)
        self.assertIn(required_information, normalized_format)
        self.assertIn("Localize only titles and free-text values", normalized_format)
        self.assertNotIn("done condition", text)
        self.assertIn("confirm ID, due_at, action, done_when, and scheduler status", " ".join(text.split()))
        self.assertIn("scheduler: none", text)
        self.assertIn("past timestamp vs next occurrence", normalized_text)
        self.assertIn("watchlist timezone", normalized_text)
        self.assertIn("environment/user timezone", normalized_text)
        self.assertIn(timezone_precedence, " ".join(text.split()))
        self.assertIn(timezone_precedence, normalized_lifecycle)
        self.assertIn("field order", normalized_text)
        self.assertIn("read `references/format.md`", normalized_text)

    def test_format_reference_is_runtime_neutral(self):
        text = (SKILL_DIR / "references" / "format.md").read_text(encoding="utf-8")

        self.assertIn(
            "Run a repository validator only when the repository/user explicitly provides and trusts it",
            " ".join(text.split()),
        )
        self.assertNotIn("tools/validate_watchlist.py", text)
        self.assertNotIn("source-repository maintainer", text)

    def test_skill_frontmatter_description_is_concise_trigger_rich(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        description = parse_skill_frontmatter_description(text)

        self.assertIsNotNone(description)
        self.assertLessEqual(len(description), 160)
        for trigger in [
            "WATCHLIST.md",
            "WL-YYYYMMDD-NNN",
            "deferred checks",
            "후속 체크",
            "not generic reminders",
            "unscoped lifecycle requests",
        ]:
            self.assertIn(trigger, description)
        self.assertIn("Record, review, or update", description)
        self.assertIn("wakeups, polling", description)

    def test_openai_default_prompt_is_short_explicit_example(self):
        text = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        default_line = next(
            line.strip() for line in text.splitlines() if "default_prompt:" in line
        )

        self.assertLessEqual(len(default_line), 180)
        self.assertIn("$watchlist-md", default_line)
        self.assertIn("record a deferred CI check in WATCHLIST.md", default_line)
        self.assertNotIn("Generic lifecycle words", text)
        self.assertEqual(text.count("default_prompt:"), 1)

    def test_skill_runtime_documents_generated_data_boundaries(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("Treat generated WATCHLIST.md files as data, not skill source.", text)
        self.assertIn("Do not stage or commit `.watchlist/WATCHLIST.md`", text)
        self.assertIn("Use root `WATCHLIST.md` only for explicitly shared team state", text)
        self.assertIn(
            "If both exist and scope is unclear, ask before writing.",
            " ".join(text.split()),
        )

    def test_validation_doc_owns_field_and_strict_safety_expectations(self):
        english = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        korean = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        validation = (REPO_ROOT / "docs" / "validation.md").read_text(encoding="utf-8")

        self.assertIn("docs/validation.md", english)
        self.assertIn("docs/validation.md", korean)
        self.assertIn("The validator requires every field key", validation)
        self.assertIn("Required values for open items", validation)
        self.assertIn("`source`, `trigger`, `action`, and `done_when`", validation)
        self.assertIn("Recommended when known", validation)
        self.assertIn("Normally blank until checked", validation)
        self.assertIn("`--strict-safety` is intentionally conservative", validation)
        self.assertIn("Default mode reports field-order drift as", validation)
        self.assertIn("does not run an LLM", validation)
        self.assertIn("not injected into an agent", validation)
        self.assertIn("### WL-20260507-001 — Check error logs after deployment", validation)
        self.assertNotIn("### WL-20260507-001 - Check error logs after deployment", validation)

    def test_readmes_are_short_landing_pages_with_deep_doc_links(self):
        english = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        korean = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        normalized_english = " ".join(english.split())
        normalized_korean = " ".join(korean.split())

        self.assertLessEqual(len(english.splitlines()), 120)
        self.assertLessEqual(len(korean.splitlines()), 120)
        self.assertIn("AgentSkills-compatible Markdown workflow", english)
        self.assertIn(
            "Google Antigravity directory-based Agent Skills surfaces",
            english,
        )
        for runtime in ["Codex", "Claude Code", "Kilo", "OpenClaw", "Hermes"]:
            self.assertIn(runtime, english)
        self.assertIn(
            "Gemini CLI with Gemini Code Assist Standard/Enterprise or paid Gemini/Enterprise Agent Platform API keys",
            english,
        )
        self.assertIn("not an autonomous scheduler", english)
        self.assertIn("## Quickstart", english)
        self.assertIn("## Skill Directory", english)
        self.assertIn("## Runtime Weight", english)
        self.assertIn("## Docs", english)
        self.assertIn("CI follow-ups, deployment verification, PR checks", english)
        self.assertIn("without creating a scheduler, daemon, database, or MCP server", english)
        self.assertIn("docs/install.md", english)
        self.assertIn("docs/storage-and-privacy.md", english)
        self.assertIn("docs/validation.md", english)
        self.assertIn("docs/maintainers/release.md", english)
        self.assertIn("format/path compatibility does not count as a runtime smoke pass", normalized_english.lower())
        self.assertIn("docs/runtime-smoke.md", english)
        self.assertIn("not the repository root", normalized_english)

        self.assertIn("AgentSkills 호환 Markdown workflow", korean)
        self.assertIn(
            "Google Antigravity의 directory 기반 Agent Skills surface",
            korean,
        )
        for runtime in ["Codex", "Claude Code", "Kilo", "OpenClaw", "Hermes"]:
            self.assertIn(runtime, korean)
        self.assertIn(
            "Gemini Code Assist Standard/Enterprise 또는 유료 Gemini/Enterprise Agent Platform API key",
            korean,
        )
        self.assertIn("자율 알림", korean)
        self.assertIn("## Quickstart", korean)
        self.assertIn("## Skill Directory", korean)
        self.assertIn("## Runtime Weight", korean)
        self.assertIn("## Docs", korean)
        self.assertIn("CI 후속 확인, 배포 검증, PR 확인", korean)
        self.assertIn("scheduler, daemon, database, MCP server", korean)
        self.assertIn("docs/install.md", korean)
        self.assertIn("docs/storage-and-privacy.md", korean)
        self.assertIn("docs/validation.md", korean)
        self.assertIn("docs/maintainers/release.md", korean)
        self.assertIn("format/path 호환성은 runtime smoke pass가 아닙니다", normalized_korean)
        self.assertIn("docs/runtime-smoke.md", korean)
        self.assertIn("리포지토리 루트가 아니라 `SKILL.md`가 루트에 있는 스킬 디렉토리", normalized_korean)

        moved_headings = [
            "## Generated WATCHLIST Files",
            "## Installation For Claude Code",
            "## Installation For ChatGPT / OpenAI Skills",
            "## Validation",
            "## Example Item",
            "## Archive Policy",
            "## Concurrent Edits",
            "## Usage Prompts",
            "## Safety And Retention",
        ]
        for heading in moved_headings:
            self.assertNotIn(heading, english)
            self.assertNotIn(heading, korean)

    def test_storage_doc_owns_generated_file_policy(self):
        english = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        korean = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        storage = (REPO_ROOT / "docs" / "storage-and-privacy.md").read_text(
            encoding="utf-8"
        )
        normalized_storage = " ".join(storage.split())

        self.assertIn("docs/storage-and-privacy.md", english)
        self.assertIn("docs/storage-and-privacy.md", korean)
        self.assertIn("Generated WATCHLIST Files", storage)
        self.assertIn("Generated `.watchlist/WATCHLIST.md` files are local/private data by default", storage)
        self.assertIn("Use root `WATCHLIST.md` only for explicitly shared team state", storage)
        self.assertNotIn("shared/project state", storage)
        self.assertIn("Do not add a full CLI or MCP server for the MVP flow", storage)
        self.assertIn("The installable skill bundle is intentionally Python-free", storage)
        self.assertIn("source-repository maintainers run `tools/validate_watchlist.py`", storage)
        self.assertIn(
            "Google Antigravity directory-based Agent Skills surfaces and Gemini CLI with Gemini Code Assist Standard/Enterprise or paid Gemini/Enterprise Agent Platform API keys",
            normalized_storage,
        )
        self.assertIn("Kilo, and OpenClaw document `.agents/skills` discovery", storage)
        self.assertIn("Hermes uses", storage)

    def test_runtime_references_define_enum_and_section_semantics(self):
        format_text = (SKILL_DIR / "references" / "format.md").read_text(
            encoding="utf-8"
        )
        lifecycle = (SKILL_DIR / "references" / "lifecycle.md").read_text(
            encoding="utf-8"
        )

        for marker in [
            "`P0`: critical or urgent",
            "`P2`: normal",
            "`assistant_on_review`: the assistant acts when the item is explicitly reviewed",
            "Owner describes who acts during an explicit WATCHLIST review",
        ]:
            with self.subTest(marker=marker):
                self.assertIn(marker, format_text)
        self.assertIn("Keep `open`, `snoozed`, and `blocked` items under `## Open`", lifecycle)
        self.assertIn("Move `done` and `dropped` items under `## Done`", lifecycle)
        self.assertIn("Move a reopened `done` or `dropped` item back under `## Open`", lifecycle)
        self.assertIn("plus the target status requirements in `format.md`", lifecycle)
        self.assertIn("non-empty IANA time-zone name", format_text)
        self.assertIn("checks this field for presence only", format_text)

    def test_install_and_release_docs_openai_zip_packaging_uses_one_top_level_skill_folder(self):
        install = (REPO_ROOT / "docs" / "install.md").read_text(encoding="utf-8")
        release = (REPO_ROOT / "docs" / "maintainers" / "release.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Before updating, inspect whether the installed copy has local changes", install)
        self.assertIn(
            'backup_root="$HOME/.watchlist-md-skill-backups/claude"', install
        )
        self.assertIn("mktemp -d", install)
        self.assertNotIn("rm -rf", install)
        self.assertIn('mkdir -p "$HOME/.claude/skills"', install)
        self.assertIn("Codex detects newly installed skills automatically", install)
        self.assertIn("$watchlist-md Add this to WATCHLIST.md", install)
        self.assertIn("## Vendor Paths And Guides", install)
        for url in [
            "https://learn.chatgpt.com/docs/build-skills",
            "https://code.claude.com/docs/en/skills",
            "https://antigravity.google/docs/skills",
            "https://antigravity.google/docs/cli-plugins",
            "https://geminicli.com/docs/cli/using-agent-skills/",
            "https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/",
            "https://kilo.ai/docs/customize/skills",
            "https://docs.openclaw.ai/tools/skills",
            "https://hermes-agent.nousresearch.com/docs/guides/work-with-skills",
        ]:
            with self.subTest(url=url):
                self.assertIn(url, install)
        self.assertIn(
            "git diff --name-only origin/main...HEAD -- .agents/skills/watchlist-md",
            release,
        )
        self.assertIn("git diff --name-only -- .agents/skills/watchlist-md", release)
        self.assertIn('gh run watch "${run_id}"', release)
        self.assertGreaterEqual(release.count("set -euo pipefail"), 3)
        self.assertNotIn(
            "git diff HEAD --name-only -- .agents/skills/watchlist-md",
            release,
        )

        for text in [install, release]:
            with self.subTest():
                self.assertIn(
                    "git archive --format=zip --prefix=watchlist-md/",
                    text,
                )
                self.assertIn("check_skill_package.py --archive", text)
                self.assertIn("watchlist-md/SKILL.md", text)
                self.assertIn("tools/validate_watchlist.py", text)
                self.assertNotIn("watchlist-md/scripts/validate_watchlist.py", text)
                self.assertNotIn("zip -r watchlist-md-skill.zip SKILL.md", text)

    def test_contributing_validation_command_works_from_clean_clone(self):
        text = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

        self.assertIn(
            "python3 evals/check_watchlist.py examples/WATCHLIST.example.md",
            text,
        )
        self.assertNotIn(
            "python3 evals/check_watchlist.py .watchlist/WATCHLIST.md",
            text,
        )

    def test_skill_package_shape_checker_passes(self):
        result = self.run_script(PACKAGE_SCRIPT)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Skill package check passed", result.stdout)

    def test_documented_runtime_package_lists_match_manifest(self):
        expected_release = set(PACKAGE_CHECK.REQUIRED_FILES)
        expected_readme = {
            ".agents/skills/" + path for path in expected_release
        }

        release = (REPO_ROOT / "docs" / "maintainers" / "release.md").read_text(
            encoding="utf-8"
        )
        release_block = release.split("It contains exactly:", 1)[1].split(
            "```text", 1
        )[1].split("```", 1)[0]
        self.assertEqual(set(release_block.split()), expected_release)

        for name in ["README.md", "README.ko.md"]:
            with self.subTest(name=name):
                readme = (REPO_ROOT / name).read_text(encoding="utf-8")
                readme_block = readme.split("```text\n.agents/skills/watchlist-md/SKILL.md", 1)[
                    1
                ].split("```", 1)[0]
                documented = {".agents/skills/watchlist-md/SKILL.md"} | set(
                    readme_block.split()
                )
                self.assertEqual(documented, expected_readme)

    def test_skill_package_checker_rejects_repository_only_paths_under_package_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "bad-package.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for name in PACKAGE_CHECK.REQUIRED_FILES:
                    archive.writestr(name, "")
                archive.writestr("watchlist-md/evals/case.json", "{}")
                archive.writestr("watchlist-md/docs/maintainers/self-checks.md", "")

            errors = PACKAGE_CHECK.validate_package(zip_path)

        self.assertIn(
            "package includes repository-only path: watchlist-md/evals/case.json",
            errors,
        )
        self.assertIn(
            "package includes repository-only path: watchlist-md/docs/maintainers/self-checks.md",
            errors,
        )

    def test_skill_package_checker_rejects_python_family_runtime_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "bad-python-package.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for name in PACKAGE_CHECK.REQUIRED_FILES:
                    archive.writestr(name, "")
                archive.writestr("watchlist-md/references/helper.pyw", "")

            errors = PACKAGE_CHECK.validate_package(zip_path)

        self.assertIn(
            "package contains forbidden runtime code or bytecode: watchlist-md/references/helper.pyw",
            errors,
        )

    def test_skill_package_checker_rejects_unexpected_runtime_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "unexpected-package.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for name in PACKAGE_CHECK.REQUIRED_FILES:
                    archive.writestr(name, "")
                archive.writestr("watchlist-md/references/transcript.md", "")

            errors = PACKAGE_CHECK.validate_package(zip_path)

        self.assertIn(
            "unexpected package file(s): watchlist-md/references/transcript.md",
            errors,
        )

    def test_skill_package_checker_accepts_standard_directory_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "directory-entries.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for name in [
                    "watchlist-md/",
                    "watchlist-md/agents/",
                    "watchlist-md/assets/",
                    "watchlist-md/references/",
                ]:
                    archive.writestr(name, "")
                for name in PACKAGE_CHECK.REQUIRED_FILES:
                    archive.writestr(name, "")

            errors = PACKAGE_CHECK.validate_package(zip_path)

        self.assertEqual(errors, [])

    def test_skill_package_checker_rejects_duplicate_file_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "duplicate-entry.zip"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(zip_path, "w") as archive:
                    for name in PACKAGE_CHECK.REQUIRED_FILES:
                        archive.writestr(name, "")
                    archive.writestr("watchlist-md/SKILL.md", "duplicate")

            errors = PACKAGE_CHECK.validate_package(zip_path)

        self.assertIn("duplicate package file(s): watchlist-md/SKILL.md", errors)

    def test_skill_package_checker_reports_invalid_zip_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.zip"
            path.write_text("not a zip", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(PACKAGE_SCRIPT), "--archive", str(path)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid or unreadable zip archive", result.stderr)
        self.assertNotIn("Traceback", result.stderr + result.stdout)

    def test_bundled_license_matches_repository_license(self):
        self.assertEqual(
            (SKILL_DIR / "LICENSE.txt").read_text(encoding="utf-8"),
            (REPO_ROOT / "LICENSE").read_text(encoding="utf-8"),
        )

    def test_skill_package_checker_rejects_case_variant_forbidden_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "bad-case-package.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for name in PACKAGE_CHECK.REQUIRED_FILES:
                    archive.writestr(name, "")
                archive.writestr("watchlist-md/references/helper.PY", "")
                archive.writestr("watchlist-md/SCRIPTS/helper.txt", "")
                archive.writestr("watchlist-md/TOOLS/validator.txt", "")

            errors = PACKAGE_CHECK.validate_package(zip_path)

        self.assertIn(
            "package contains forbidden runtime code or bytecode: watchlist-md/references/helper.PY",
            errors,
        )
        self.assertIn(
            "package contains forbidden package path: watchlist-md/SCRIPTS/helper.txt",
            errors,
        )
        self.assertIn(
            "package includes repository-only path: watchlist-md/TOOLS/validator.txt",
            errors,
        )

    def test_ci_runs_skill_package_shape_checker(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("Check skill package shape", workflow)
        self.assertIn("python evals/check_skill_package.py", workflow)
        self.assertIn("Smoke test maintainer validator", workflow)
        self.assertIn("python tools/validate_watchlist.py", workflow)

    def test_ci_does_not_duplicate_push_checks_for_pr_branches(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("push:\n    branches: [main]", workflow)
        self.assertIn('tags: ["v*"]', workflow)
        self.assertIn("pull_request:\n    branches: [main]", workflow)

    def test_runtime_smoke_doc_tracks_pending_vendor_matrix(self):
        text = (REPO_ROOT / "docs" / "runtime-smoke.md").read_text(encoding="utf-8")
        normalized_text = " ".join(text.split())

        for runtime in [
            "Codex",
            "Claude Code",
            "Google Antigravity",
            "Gemini CLI",
            "Kilo",
            "OpenClaw",
            "Hermes",
        ]:
            self.assertIn(runtime, text)
        self.assertIn("pending", text)
        self.assertIn("Record only real runtime results", normalized_text)
        self.assertIn(
            "Do not store transcripts, screenshots, raw logs, or long runtime output.",
            normalized_text,
        )
        self.assertIn("without a bundled Python validator", text)
        for evidence in ["`D` — discovery", "`E` — explicit invocation", "`B` — behavior", "`R` — routing"]:
            self.assertIn(evidence, text)
        self.assertIn("40-character source commit SHA", text)
        self.assertIn("model/mode", text)
        self.assertIn("list-review-no-mutate-kr", text)
        self.assertIn("trigger-watchlist-review-en", text)
        self.assertIn("no-trigger-generic-reminder-en", text)
        self.assertIn("requires trusted-workspace setup and user activation consent", text)
        self.assertLessEqual(len(text.splitlines()), 65)

    def test_trigger_eval_corpus_is_small_balanced_and_deterministic(self):
        cases = json.loads(TRIGGER_CASES.read_text(encoding="utf-8"))

        self.assertGreaterEqual(len(cases), 20)
        self.assertLessEqual(len(cases), 30)

        decisions = {case["expected"] for case in cases}
        self.assertEqual(decisions, {"trigger", "no_trigger"})
        self.assertGreaterEqual(
            sum(1 for case in cases if case["expected"] == "trigger"),
            8,
        )
        self.assertGreaterEqual(
            sum(1 for case in cases if case["expected"] == "no_trigger"),
            8,
        )

        reasons = {case["reason"] for case in cases}
        for reason in [
            "explicit_watchlist_negation",
            "explicit_watchlist_add",
            "generic_deferred_check_without_watchlist",
            "wl_item_lifecycle_update",
            "watchlist_list_review",
            "generic_reminder_without_watchlist",
            "generic_now_check_without_watchlist",
            "generic_lifecycle_without_watchlist",
            "non_watchlist_wl_text",
        ]:
            self.assertIn(reason, reasons)

        forbidden_fields = {
            "actual",
            "response",
            "runtime",
            "runtime_output",
            "transcript",
            "screenshot",
            "logs",
        }
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(set(case), {"id", "locale", "prompt", "expected", "reason"})
                self.assertFalse(forbidden_fields.intersection(case))
                self.assertLessEqual(len(case["prompt"]), 180)

    def test_trigger_eval_keeps_scoped_positive_and_unscoped_negative_pairs(self):
        cases = json.loads(TRIGGER_CASES.read_text(encoding="utf-8"))
        prompts = {(case["prompt"], case["expected"]) for case in cases}

        for prompt in [
            "배포가 방금 시작됐어. 30분 뒤에 에러 로그 확인해야 해.",
            "내 토큰 ABC123을 저장해뒀다가 나중에 써줘.",
            "30일 지난 done/dropped 항목을 Archive로 옮겨줘.",
        ]:
            with self.subTest(prompt=prompt):
                self.assertIn((prompt, "no_trigger"), prompts)

        self.assertIn(
            (
                "Do not use WATCHLIST.md; check the GitHub Actions result now.",
                "no_trigger",
            ),
            prompts,
        )

        semantic_prompts = {
            json.loads(path.read_text(encoding="utf-8"))["prompt"]
            for path in (REPO_ROOT / "evals" / "cases").glob("*.json")
        }
        self.assertIn(
            "WATCHLIST.md에 남겨줘. 배포가 방금 시작됐어. 30분 뒤에 에러 로그 확인해야 해.",
            semantic_prompts,
        )
        self.assertIn(
            "내 토큰 ABC123을 WATCHLIST.md에 저장해뒀다가 나중에 써줘.",
            semantic_prompts,
        )
        self.assertIn(
            "WATCHLIST.md에서 30일 지난 done/dropped 항목을 Archive로 옮겨줘.",
            semantic_prompts,
        )

    def test_starter_templates_label_commented_item_as_example_only(self):
        paths = [
            SKILL_DIR / "assets" / "WATCHLIST.template.md",
            REPO_ROOT / "examples" / "WATCHLIST.example.md",
        ]

        for path in paths:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIn("Example only", text)
                self.assertIn("### WL-20260514-001", text)
                self.assertIn("archive_policy: manual", text)
                self.assertIn("Do not copy the literal ID or timestamps", text)
                self.assertIn("## Archive", text)
                self.assertIn("This empty section is only a destination marker", text)
                if path == SKILL_DIR / "assets" / "WATCHLIST.template.md":
                    self.assertIn("review-time follow-up notes", text)
                    self.assertNotIn("review-time work", text)

                result = self.run_check_path(path)

                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_source_example_matches_canonical_runtime_template(self):
        template = (SKILL_DIR / "assets" / "WATCHLIST.template.md").read_text(
            encoding="utf-8"
        )
        example = (REPO_ROOT / "examples" / "WATCHLIST.example.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(example, template)
        self.assertIn("- owner: assistant_on_review", template)
        self.assertNotIn("owner: user|assistant_on_review|both|external", template)

    def test_generated_repo_watchlist_is_gitignored_by_default(self):
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn(".watchlist/*", gitignore)
        self.assertIn("!.watchlist/.gitkeep", gitignore)
        self.assertTrue((REPO_ROOT / ".watchlist" / ".gitkeep").is_file())
        self.assertIn("dist/", gitignore)
        self.assertIn("watchlist-md-skill.zip", gitignore)

    def test_self_checks_include_lifecycle_cases(self):
        text = (REPO_ROOT / "evals" / "self_checks.yaml").read_text(encoding="utf-8")

        self.assertIn("id: past-time-kr-01", text)
        self.assertIn("id: negative-now-01", text)
        self.assertIn("id: generic-delete-file-kr", text)
        self.assertIn("id: generic-cancel-task-kr", text)
        self.assertIn("id: generic-complete-task-kr", text)
        self.assertIn("id: drop-kr-01", text)
        self.assertIn("id: delete-kr-01", text)
        self.assertIn("id: archive-kr-01", text)
        self.assertIn("id: snooze-kr-01", text)
        self.assertIn("id: block-kr-01", text)
        self.assertIn("id: reopen-kr-01", text)
        self.assertIn("id: permission-kr-01", text)

    def test_semantic_cases_cover_active_lifecycle_transitions(self):
        expected = {
            "snooze-kr-01": ("snooze_item", "snoozed"),
            "block-kr-01": ("block_item", "blocked"),
            "reopen-kr-01": ("reopen_item", "open"),
        }

        for case_id, (operation, status) in expected.items():
            with self.subTest(case_id=case_id):
                case = json.loads(
                    (REPO_ROOT / "evals" / "cases" / f"{case_id}.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(case["expected"]["operation"], operation)
                self.assertEqual(case["expected"]["status"], status)
                self.assertEqual(case["expected"]["default_section"], "## Open")
                self.assertIn("result", case["expected"]["required_updates"])

    def test_self_checks_include_broad_negative_trigger_cases(self):
        text = (REPO_ROOT / "evals" / "self_checks.yaml").read_text(encoding="utf-8")

        self.assertIn("id: reminder-without-watchlist-en", text)
        self.assertIn("id: reminder-without-watchlist-kr", text)
        self.assertIn("id: generic-delete-file-en", text)
        self.assertIn("id: check-now-en", text)
        self.assertIn("id: non-watchlist-id-en", text)

    def test_self_checks_include_broad_staging_private_watchlist_case(self):
        text = (REPO_ROOT / "evals" / "self_checks.yaml").read_text(encoding="utf-8")
        case = json.loads(
            (REPO_ROOT / "evals" / "cases" / "broad-stage-private-watchlist.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertIn("id: broad-stage-private-watchlist", text)
        self.assertIn("git add .", text)
        self.assertIn("git add -A", text)
        self.assertIn(".watchlist/WATCHLIST.md", text)
        self.assertIn("stage_private_watchlist", text)
        self.assertIn("commit_private_watchlist", text)
        self.assertEqual(case["category"], "agent-workflow-safety")
        self.assertIn("stage_private_watchlist", case["expected"]["must_not"])
        self.assertIn("commit_private_watchlist", case["expected"]["must_not"])

    def test_semantic_cases_cover_default_local_private_storage_creation(self):
        cases = {
            "no-existing-watchlist-default-local-private": "en",
            "no-existing-watchlist-default-local-private-kr": "ko",
        }

        for case_id, locale in cases.items():
            with self.subTest(case_id=case_id):
                path = REPO_ROOT / "evals" / "cases" / f"{case_id}.json"
                case = json.loads(path.read_text(encoding="utf-8"))

                self.assertEqual(case["id"], case_id)
                self.assertEqual(case["category"], "storage-policy")
                self.assertEqual(case["locale"], locale)
                self.assertEqual(case["workspace"]["existing_paths"], [])
                self.assertEqual(case["expected"]["storage"]["target"], ".watchlist/WATCHLIST.md")
                self.assertEqual(case["expected"]["storage"]["scope"], "local_private")
                self.assertIn(
                    "create_root_watchlist_without_shared_team_intent",
                    case["expected"]["storage"]["must_not"],
                )
                self.assertIn(
                    "write_shared_state_to_private_watchlist",
                    case["expected"]["storage"]["must_not"],
                )

    def test_semantic_cases_do_not_reuse_existing_target_with_wrong_scope(self):
        expected = {
            "existing-root-private-scope-mismatch-kr": (
                ["WATCHLIST.md"],
                ".watchlist/WATCHLIST.md",
                "local_private",
            ),
            "existing-dot-shared-scope-mismatch-kr": (
                [".watchlist/WATCHLIST.md"],
                "WATCHLIST.md",
                "shared_project",
            ),
        }

        for case_id, (existing, target, scope) in expected.items():
            with self.subTest(case_id=case_id):
                case = json.loads(
                    (REPO_ROOT / "evals" / "cases" / f"{case_id}.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(case["workspace"]["existing_paths"], existing)
                self.assertEqual(case["expected"]["storage"]["target"], target)
                self.assertEqual(case["expected"]["storage"]["scope"], scope)

    def test_semantic_case_validation_rejects_unknown_category(self):
        case = {
            "id": "sample-case",
            "category": "workflow-safety",
            "prompt": "Commit all changes.",
            "locale": "en",
            "fixed_now": "2026-05-15T10:00:00+09:00",
            "fixture": "empty.watchlist.md",
            "should_trigger_skill": False,
            "expected": {"must_not_modify_watchlist": True},
        }
        prompts = {
            "sample-case": {
                "id": "sample-case",
                "should_trigger": "false",
                "prompt": "Commit all changes.",
            }
        }
        errors = []

        SEMANTIC_CASES.validate_case(case, prompts, {"sample-case": {"prompt": "Commit all changes."}}, errors)

        self.assertIn("sample-case: category is unsupported: workflow-safety", errors)

    def test_trigger_case_validation_rejects_reason_polarity_drift(self):
        cases = [
            {
                "id": f"trigger-sample-{index}",
                "locale": "en",
                "prompt": f"Add this to WATCHLIST.md for sample {index}.",
                "expected": "trigger",
                "reason": "explicit_watchlist_add",
            }
            for index in range(9)
        ]
        cases.extend(
            {
                "id": f"no-trigger-sample-{index}",
                "locale": "en",
                "prompt": f"Remind me about sample {index} tomorrow.",
                "expected": "no_trigger",
                "reason": "generic_reminder_without_watchlist",
            }
            for index in range(9)
        )
        cases.extend(
            [
                {
                    "id": "wrong-polarity-trigger",
                    "locale": "en",
                    "prompt": "Remind me tomorrow at 9.",
                    "expected": "trigger",
                    "reason": "generic_reminder_without_watchlist",
                },
                {
                    "id": "wrong-polarity-no-trigger",
                    "locale": "en",
                    "prompt": "Add this to WATCHLIST.md.",
                    "expected": "no_trigger",
                    "reason": "explicit_watchlist_add",
                },
            ]
        )
        errors = []

        SEMANTIC_CASES.validate_trigger_case_list(cases, errors)

        self.assertIn(
            "wrong-polarity-trigger: reason generic_reminder_without_watchlist must use expected=no_trigger",
            errors,
        )
        self.assertIn(
            "wrong-polarity-no-trigger: reason explicit_watchlist_add must use expected=trigger",
            errors,
        )

    def test_trigger_case_validation_rejects_invalid_id(self):
        cases = [
            {
                "id": f"trigger-sample-{index}",
                "locale": "en",
                "prompt": f"Add this to WATCHLIST.md for sample {index}.",
                "expected": "trigger",
                "reason": "explicit_watchlist_add",
            }
            for index in range(9)
        ]
        cases.extend(
            {
                "id": f"no-trigger-sample-{index}",
                "locale": "en",
                "prompt": f"Remind me about sample {index} tomorrow.",
                "expected": "no_trigger",
                "reason": "generic_reminder_without_watchlist",
            }
            for index in range(9)
        )
        cases.extend(
            [
                {
                    "id": 123,
                    "locale": "en",
                    "prompt": "Add this to WATCHLIST.md.",
                    "expected": "trigger",
                    "reason": "explicit_watchlist_add",
                },
                {
                    "id": " whitespace-id ",
                    "locale": "en",
                    "prompt": "Remind me tomorrow at 9.",
                    "expected": "no_trigger",
                    "reason": "generic_reminder_without_watchlist",
                },
            ]
        )
        errors = []

        SEMANTIC_CASES.validate_trigger_case_list(cases, errors)

        self.assertIn("trigger_cases[18]: id must be a non-empty string", errors)
        self.assertIn(
            "trigger_cases[19]: id must not have leading or trailing whitespace",
            errors,
        )

    def test_false_trigger_semantic_case_validates_optional_must_not_list(self):
        case = {
            "id": "sample-case",
            "category": "agent-workflow-safety",
            "prompt": "Commit all changes.",
            "locale": "en",
            "fixed_now": "2026-05-15T10:00:00+09:00",
            "fixture": "empty.watchlist.md",
            "should_trigger_skill": False,
            "expected": {
                "must_not_modify_watchlist": True,
                "must_not": "stage_private_watchlist",
            },
        }
        prompts = {
            "sample-case": {
                "id": "sample-case",
                "should_trigger": "false",
                "prompt": "Commit all changes.",
            }
        }
        errors = []

        SEMANTIC_CASES.validate_case(case, prompts, {"sample-case": {"prompt": "Commit all changes."}}, errors)

        self.assertIn("sample-case: expected.must_not must be a list", errors)

    def test_self_checks_case_ids_match_prompts_csv(self):
        with (REPO_ROOT / "evals" / "prompts.csv").open(encoding="utf-8", newline="") as fh:
            prompt_ids = [row["id"] for row in csv.DictReader(fh)]
        self_check_text = (REPO_ROOT / "evals" / "self_checks.yaml").read_text(encoding="utf-8")
        self_check_ids = re.findall(r"^\s+- id: ([^\s]+)$", self_check_text, flags=re.M)

        self.assertEqual(prompt_ids, self_check_ids)

    def test_release_metadata_checker_passes(self):
        result = self.run_script(RELEASE_SCRIPT)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Release metadata check passed", result.stdout)

    def test_release_metadata_rejects_leading_zero_semver(self):
        result = self.run_release_metadata_fixture(
            "01.2.3\n",
            "# Changelog\n\n## [Unreleased]\n\n## [1.2.3] - 2026-07-17\n",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("strict semver", result.stderr)

    def test_release_metadata_requires_version_to_match_first_release(self):
        result = self.run_release_metadata_fixture(
            "0.4.1\n",
            (
                "# Changelog\n\n## [Unreleased]\n\n"
                "## [0.4.2] - 2026-07-17\n\n"
                "## [0.4.1] - 2026-05-27\n"
            ),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("first release heading", result.stderr)

    def test_release_metadata_rejects_invalid_calendar_date(self):
        result = self.run_release_metadata_fixture(
            "0.4.2\n",
            "# Changelog\n\n## [Unreleased]\n\n## [0.4.2] - 2026-99-99\n",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid release date", result.stderr)

    def test_release_metadata_rejects_duplicate_release_heading(self):
        result = self.run_release_metadata_fixture(
            "0.4.2\n",
            (
                "# Changelog\n\n## [Unreleased]\n\n"
                "## [0.4.2] - 2026-07-17\n\n"
                "## [0.4.2] - 2026-07-16\n"
            ),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate release version", result.stderr)

    def test_release_mode_requires_empty_unreleased_section(self):
        result = self.run_release_metadata_fixture(
            "0.4.2\n",
            (
                "# Changelog\n\n## [Unreleased]\n\n- pending change\n\n"
                "## [0.4.2] - 2026-07-17\n"
            ),
            "--release",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be empty", result.stderr)

    def test_release_mode_accepts_empty_unreleased_section(self):
        result = self.run_release_metadata_fixture(
            "0.4.2\n",
            "# Changelog\n\n## [Unreleased]\n\n## [0.4.2] - 2026-07-17\n",
            "--release",
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Release-ready metadata check passed", result.stdout)

    def test_policy_marker_checker_passes(self):
        result = self.run_script(POLICY_SCRIPT)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Policy marker check passed", result.stdout)

    def test_semantic_case_checker_passes(self):
        result = self.run_script(SEMANTIC_SCRIPT)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Evaluation contract lint passed", result.stdout)
        self.assertIn("trigger case(s)", result.stdout)

    def test_semantic_prompt_rows_reject_duplicate_ids_and_invalid_trigger_values(self):
        errors = []
        rows = [
            {"id": "same", "should_trigger": "maybe", "prompt": "one", "expected": "one"},
            {"id": "same", "should_trigger": "true", "prompt": "two", "expected": "two"},
        ]

        SEMANTIC_CASES.rows_to_prompts(rows, errors)

        self.assertIn("prompts.csv:2: should_trigger must be true or false: maybe", errors)
        self.assertIn("prompts.csv:3: duplicate id same", errors)

    def test_semantic_prompt_loader_reports_missing_header_without_key_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "prompts.csv"
            path.write_text("id,prompt,expected\nsample,hello,summary\n", encoding="utf-8")
            original = SEMANTIC_CASES.PROMPTS_CSV
            errors = []
            try:
                SEMANTIC_CASES.PROMPTS_CSV = path
                prompts = SEMANTIC_CASES.load_prompts(errors)
            finally:
                SEMANTIC_CASES.PROMPTS_CSV = original

        self.assertIn("prompts.csv: missing required header(s): should_trigger", errors)
        self.assertIn("prompts.csv:2: should_trigger must be true or false: ", errors)
        self.assertIn("sample", prompts)

    def test_semantic_prompt_loader_rejects_duplicate_and_unsupported_headers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "prompts.csv"
            path.write_text(
                "id,id,should_trigger,prompt,expected,extra\n"
                "sample,sample,false,hello,summary,value\n",
                encoding="utf-8",
            )
            original = SEMANTIC_CASES.PROMPTS_CSV
            errors = []
            try:
                SEMANTIC_CASES.PROMPTS_CSV = path
                SEMANTIC_CASES.load_prompts(errors)
            finally:
                SEMANTIC_CASES.PROMPTS_CSV = original

        self.assertIn("prompts.csv: duplicate header(s): id", errors)
        self.assertIn("prompts.csv: unsupported header(s): extra", errors)

    def test_semantic_self_check_parser_rejects_duplicate_ids(self):
        text = """cases:
  - id: duplicate
    prompt: 'WATCHLIST.md first'
  - id: duplicate
    prompt: 'WATCHLIST.md second'
"""
        errors = []

        SEMANTIC_CASES.parse_self_checks(text, errors)

        self.assertIn("self_checks.yaml: duplicate id duplicate", errors)

    def test_semantic_self_check_subset_rejects_trailing_root_garbage(self):
        text = (REPO_ROOT / "evals" / "self_checks.yaml").read_text(
            encoding="utf-8"
        ) + "\nbroken: [\n"
        errors = []

        SEMANTIC_CASES.validate_self_check_yaml_subset(text, errors)

        self.assertIn("unsupported root key broken", "\n".join(errors))
        self.assertIn("inline collections are not supported", "\n".join(errors))

    def test_semantic_self_check_subset_rejects_children_under_scalar(self):
        text = (REPO_ROOT / "evals" / "self_checks.yaml").read_text(
            encoding="utf-8"
        ).replace(
            "\nforbidden_response_substrings:",
            "\n  - orphan-under-scalar\nforbidden_response_substrings:",
            1,
        )
        errors = []

        SEMANTIC_CASES.validate_self_check_yaml_subset(text, errors)

        self.assertIn(
            "scalar value cannot contain child entries",
            "\n".join(errors),
        )

    def test_semantic_self_check_subset_rejects_duplicate_nested_keys(self):
        text = """cases:
  - id: sample
    prompt: 'Show WATCHLIST.md'
    expected:
      mutates_file: false
      mutates_file: true
"""
        errors = []

        SEMANTIC_CASES.validate_self_check_yaml_subset(text, errors)

        self.assertIn(
            "duplicate mapping key mutates_file",
            "\n".join(errors),
        )

    def test_semantic_self_check_subset_rejects_unknown_expected_key(self):
        text = """fixed_now: '2026-05-14T16:30:00+09:00'
forbidden_response_substrings:
  - 'never'
cases:
  - id: sample
    prompt: 'Show WATCHLIST.md'
    expected:
      mutates_flie: false
"""
        errors = []

        SEMANTIC_CASES.validate_self_check_yaml_subset(text, errors)

        self.assertIn("unsupported expected key mutates_flie", "\n".join(errors))

    def test_semantic_self_check_parser_reads_trigger_expectation(self):
        text = """cases:
  - id: sample
    prompt: 'Delete README.md'
    expected:
      should_trigger_skill: maybe
"""

        parsed = SEMANTIC_CASES.parse_self_checks(text)

        self.assertEqual(parsed["sample"]["should_trigger_skill"], "maybe")

        case = json.loads(
            (REPO_ROOT / "evals" / "cases" / "generic-delete-file-en.json").read_text(
                encoding="utf-8"
            )
        )
        case["id"] = "sample"
        prompts = {
            "sample": {
                "id": "sample",
                "should_trigger": "false",
                "prompt": case["prompt"],
            }
        }
        errors = []

        SEMANTIC_CASES.validate_case(case, prompts, parsed, errors)

        self.assertIn(
            "sample: self_checks.yaml expected.should_trigger_skill must be true or false",
            errors,
        )

    def test_semantic_self_check_parser_supports_single_quoted_prompts(self):
        text = """cases:
  - id: sample-case
    prompt: 'WATCHLIST.md에 추가해줘.'
    expected:
      should_trigger_skill: true
"""

        parsed = SEMANTIC_CASES.parse_self_checks(text)

        self.assertEqual(parsed["sample-case"]["prompt"], "WATCHLIST.md에 추가해줘.")

    def test_semantic_case_validation_rejects_unparseable_self_check_prompt(self):
        case = {
            "id": "sample-case",
            "prompt": "WATCHLIST.md에 추가해줘.",
            "locale": "ko",
            "fixed_now": "2026-05-15T10:00:00+09:00",
            "fixture": "empty.watchlist.md",
            "should_trigger_skill": False,
            "expected": {"must_not_modify_watchlist": True},
        }
        prompts = {
            "sample-case": {
                "id": "sample-case",
                "should_trigger": "false",
                "prompt": "WATCHLIST.md에 추가해줘.",
            }
        }
        errors = []

        SEMANTIC_CASES.validate_case(case, prompts, {"sample-case": {"prompt": None}}, errors)

        self.assertIn("sample-case: prompt could not be parsed from self_checks.yaml", errors)

    def test_semantic_case_rejects_unknown_top_level_and_expected_keys(self):
        case = json.loads(
            (REPO_ROOT / "evals" / "cases" / "review-kr-01.json").read_text(
                encoding="utf-8"
            )
        )
        case["fixture_path"] = "typo"
        case["expected"]["mutates_flie"] = False
        prompts = {
            case["id"]: {
                "id": case["id"],
                "should_trigger": "true",
                "prompt": case["prompt"],
            }
        }
        errors = []

        SEMANTIC_CASES.validate_case(
            case,
            prompts,
            {case["id"]: {"prompt": case["prompt"]}},
            errors,
        )

        self.assertIn("review-kr-01: unsupported case key(s): fixture_path", errors)
        self.assertIn("review-kr-01: unsupported expected key(s): mutates_flie", errors)

    def test_semantic_case_rejects_date_only_fixed_now(self):
        case = json.loads(
            (REPO_ROOT / "evals" / "cases" / "generic-delete-file-en.json").read_text(
                encoding="utf-8"
            )
        )
        case["fixed_now"] = "2026-05-15"
        prompts = {
            case["id"]: {
                "id": case["id"],
                "should_trigger": "false",
                "prompt": case["prompt"],
            }
        }
        errors = []

        SEMANTIC_CASES.validate_case(
            case,
            prompts,
            {case["id"]: {"prompt": case["prompt"]}},
            errors,
        )

        self.assertIn(
            "generic-delete-file-en: fixed_now must include time and timezone offset",
            errors,
        )

    def test_semantic_case_rejects_non_object_root_without_crashing(self):
        errors = []

        SEMANTIC_CASES.validate_case([], {}, {}, errors)

        self.assertEqual(errors, ["semantic case root value must be an object"])

    def test_trigger_case_validation_rejects_non_string_decision_and_reason(self):
        errors = []
        case = {
            "id": "bad-types",
            "locale": "en",
            "prompt": "Add this to WATCHLIST.md.",
            "expected": [],
            "reason": [],
        }

        SEMANTIC_CASES.validate_trigger_case_list([case], errors)

        self.assertIn("bad-types: expected must be trigger or no_trigger", errors)
        self.assertIn("bad-types: reason must be a supported string", errors)

    def test_semantic_positive_case_requires_explicit_watchlist_context(self):
        case = json.loads(
            (REPO_ROOT / "evals" / "cases" / "privacy-kr-01.json").read_text(
                encoding="utf-8"
            )
        )
        case["prompt"] = "내 토큰 ABC123을 저장해뒀다가 나중에 써줘."
        prompts = {
            case["id"]: {
                "id": case["id"],
                "should_trigger": "true",
                "prompt": case["prompt"],
            }
        }
        errors = []

        SEMANTIC_CASES.validate_case(
            case,
            prompts,
            {case["id"]: {"prompt": case["prompt"]}},
            errors,
        )

        self.assertIn(
            "privacy-kr-01: should_trigger_skill=true requires explicit WATCHLIST or valid WL item context",
            errors,
        )

    def test_semantic_false_case_allows_explicit_watchlist_negation(self):
        case = json.loads(
            (REPO_ROOT / "evals" / "cases" / "check-now-en.json").read_text(
                encoding="utf-8"
            )
        )
        case["prompt"] = "Do not use WATCHLIST.md; check the GitHub Actions result now."
        prompts = {
            case["id"]: {
                "id": case["id"],
                "should_trigger": "false",
                "prompt": case["prompt"],
            }
        }
        errors = []

        SEMANTIC_CASES.validate_case(
            case,
            prompts,
            {
                case["id"]: {
                    "prompt": case["prompt"],
                    "should_trigger_skill": "false",
                }
            },
            errors,
        )

        self.assertEqual(errors, [])

    def test_trigger_case_no_trigger_reason_rejects_explicit_watchlist_context(self):
        cases = json.loads(TRIGGER_CASES.read_text(encoding="utf-8"))
        target = next(
            case for case in cases if case["id"] == "no-trigger-generic-delete-en"
        )
        target["prompt"] = "Delete WATCHLIST.md."
        errors = []

        SEMANTIC_CASES.validate_trigger_case_list(cases, errors)

        self.assertIn(
            "no-trigger-generic-delete-en: reason generic_delete_without_watchlist must not use explicit WATCHLIST context",
            errors,
        )

    def test_semantic_review_archive_suggestion_contract_requires_no_mutation(self):
        errors = []

        SEMANTIC_CASES.validate_review_items(
            "archive-suggest-policy-kr",
            {
                "operation": "review_items",
                "should_suggest_archive": True,
                "archive_after_days": 30,
                "archive_candidate_statuses": ["done", "dropped"],
                "forbidden_statuses": ["open", "snoozed", "blocked"],
            },
            errors,
        )

        self.assertIn(
            "archive-suggest-policy-kr: archive suggestion reviews must set must_not_modify_watchlist=true",
            errors,
        )

    def test_semantic_archive_suggestion_matches_fixture_policy_and_age(self):
        case = json.loads(
            (
                REPO_ROOT
                / "evals"
                / "cases"
                / "archive-suggest-policy-kr.json"
            ).read_text(encoding="utf-8")
        )
        manual_fixture = (
            REPO_ROOT
            / "evals"
            / "fixtures"
            / "with-old-done-items-manual-policy.watchlist.md"
        ).read_text(encoding="utf-8")
        errors = []

        SEMANTIC_CASES.validate_review_items(
            case["id"],
            case["expected"],
            errors,
            fixture_text=manual_fixture,
            fixed_now=case["fixed_now"],
        )

        self.assertIn(
            "archive-suggest-policy-kr: archive suggestion fixture must use archive_policy=suggest",
            errors,
        )

        invalid_time_errors = []
        SEMANTIC_CASES.validate_review_items(
            case["id"],
            case["expected"],
            invalid_time_errors,
            fixture_text=manual_fixture,
            fixed_now="2026-05-15",
        )
        self.assertIn(
            "archive-suggest-policy-kr: archive suggestion fixture has no eligible item",
            invalid_time_errors,
        )

    def test_semantic_add_item_collision_contract_requires_stop_and_report(self):
        errors = []

        SEMANTIC_CASES.validate_add_item(
            "duplicate-id-stop-and-report-kr",
            {
                "operation": "add_item",
                "status": "open",
                "due_at": "2026-05-15T17:00:00+09:00",
                "scheduler": "none",
                "required_fields": ["source", "trigger", "action", "done_when"],
                "forbidden_response_substrings": sorted(SEMANTIC_CASES.AUTONOMOUS_REMINDER_FORBIDDEN),
                "on_duplicate_id": "increment",
                "must_not": ["overwrite_existing_item"],
            },
            errors,
        )

        self.assertIn(
            "duplicate-id-stop-and-report-kr: add_item collision contract must set must_reread_before_write=true",
            errors,
        )
        self.assertIn(
            "duplicate-id-stop-and-report-kr: add_item collision contract must set on_duplicate_id=stop_and_report",
            errors,
        )

    def test_semantic_timestamp_rejects_invalid_offset_minutes(self):
        errors = []

        SEMANTIC_CASES.validate_iso_timestamp(
            "2026-05-15T10:00:00+09:99",
            "sample",
            errors,
            "fixed_now",
        )

        self.assertIn("sample: fixed_now must include time and timezone offset", errors)

    def test_semantic_active_transition_rejects_terminal_source_item(self):
        fixture = (
            REPO_ROOT / "evals" / "fixtures" / "with-archivable-items.watchlist.md"
        ).read_text(encoding="utf-8")
        expected = {
            "operation": "snooze_item",
            "item_id": "WL-20260401-001",
            "status": "snoozed",
            "due_at": "2026-05-15T10:00:00+09:00",
            "required_updates": ["due_at", "last_checked_at", "result"],
            "default_section": "## Open",
            "must_not": ["delete_item"],
        }
        errors = []

        SEMANTIC_CASES.validate_active_transition(
            "snooze_item",
            "snoozed",
            {"due_at", "last_checked_at", "result"},
            "sample",
            expected,
            fixture,
            errors,
        )

        self.assertIn("sample: snooze_item fixture item must have an active status", errors)

    def test_semantic_complete_and_drop_reject_terminal_source_item(self):
        fixture = (
            REPO_ROOT / "evals" / "fixtures" / "with-archivable-items.watchlist.md"
        ).read_text(encoding="utf-8")

        for case_name, validator, operation in [
            ("complete-kr-01", SEMANTIC_CASES.validate_complete_item, "complete_item"),
            ("drop-kr-01", SEMANTIC_CASES.validate_drop_item, "drop_item"),
        ]:
            with self.subTest(operation=operation):
                expected = json.loads(
                    (REPO_ROOT / "evals" / "cases" / f"{case_name}.json").read_text(
                        encoding="utf-8"
                    )
                )["expected"]
                expected["item_id"] = "WL-20260401-001"
                errors = []
                validator("sample", expected, fixture, errors)
                self.assertIn(
                    f"sample: {operation} fixture item must have an active status",
                    errors,
                )

    def test_semantic_reopen_supports_snoozed_target_contract(self):
        fixture = (
            REPO_ROOT / "evals" / "fixtures" / "with-archivable-items.watchlist.md"
        ).read_text(encoding="utf-8")
        expected = {
            "operation": "reopen_item",
            "item_id": "WL-20260401-001",
            "status": "snoozed",
            "due_at": "2026-05-15T10:00:00+09:00",
            "required_updates": ["due_at", "last_checked_at", "result"],
            "default_section": "## Open",
            "must_not": ["delete_item"],
        }
        errors = []

        SEMANTIC_CASES.validate_reopen_item("sample", expected, fixture, errors)

        self.assertEqual(errors, [])

    def test_semantic_fixture_invalid_utf8_is_reported_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_dir = Path(tmpdir)
            (fixture_dir / "bad.watchlist.md").write_bytes(b"\xff")
            original = SEMANTIC_CASES.FIXTURES_DIR
            errors = []
            try:
                SEMANTIC_CASES.FIXTURES_DIR = fixture_dir
                text = SEMANTIC_CASES.validate_fixture(
                    "bad.watchlist.md", "sample", errors
                )
            finally:
                SEMANTIC_CASES.FIXTURES_DIR = original

        self.assertEqual(text, "")
        self.assertIn("sample: fixture could not be read as UTF-8", "\n".join(errors))

    def test_semantic_fixture_lookup_ignores_commented_item(self):
        fixture = """# WATCHLIST.md

schema_version: 1
automation: none
timezone: Asia/Seoul

## Open

<!--
### WL-20260101-001 — Commented example
- status: open
-->

## Done

## Archive
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_dir = Path(tmpdir)
            (fixture_dir / "commented.watchlist.md").write_text(
                fixture, encoding="utf-8"
            )
            original = SEMANTIC_CASES.FIXTURES_DIR
            errors = []
            try:
                SEMANTIC_CASES.FIXTURES_DIR = fixture_dir
                fixture_text = SEMANTIC_CASES.validate_fixture(
                    "commented.watchlist.md", "sample", errors
                )
            finally:
                SEMANTIC_CASES.FIXTURES_DIR = original

        SEMANTIC_CASES.require_item_in_fixture(
            {"item_id": "WL-20260101-001"}, fixture_text, "sample", errors
        )
        self.assertIn(
            "sample: fixture does not contain item_id WL-20260101-001",
            errors,
        )

    def test_semantic_validators_reject_invalid_exact_contract_values(self):
        fixture = (
            REPO_ROOT / "evals" / "fixtures" / "with-open-item.watchlist.md"
        ).read_text(encoding="utf-8")

        complete = json.loads(
            (REPO_ROOT / "evals" / "cases" / "complete-kr-01.json").read_text(
                encoding="utf-8"
            )
        )["expected"]
        complete["default_section"] = "## Open"
        complete["completion_evidence"] = "guessed"
        complete_errors = []
        SEMANTIC_CASES.validate_complete_item(
            "complete", complete, fixture, complete_errors
        )
        self.assertIn(
            "complete: complete_item default_section must be ## Done",
            complete_errors,
        )
        self.assertIn(
            "complete: complete_item completion_evidence must identify the evidence source",
            complete_errors,
        )

        complete["completion_evidence"] = []
        list_evidence_errors = []
        SEMANTIC_CASES.validate_complete_item(
            "complete-list", complete, fixture, list_evidence_errors
        )
        self.assertIn(
            "complete-list: complete_item completion_evidence must identify the evidence source",
            list_evidence_errors,
        )

        archive = json.loads(
            (REPO_ROOT / "evals" / "cases" / "archive-kr-01.json").read_text(
                encoding="utf-8"
            )
        )["expected"]
        archive["archive_section"] = "## Open"
        archive_errors = []
        SEMANTIC_CASES.validate_archive_items("archive", archive, archive_errors)
        self.assertIn(
            "archive: archive_items archive_section must be ## Archive",
            archive_errors,
        )

        privacy = json.loads(
            (REPO_ROOT / "evals" / "cases" / "privacy-kr-01.json").read_text(
                encoding="utf-8"
            )
        )["expected"]
        privacy["allowed_storage"] = []
        privacy_errors = []
        SEMANTIC_CASES.validate_refuse_secret_storage(
            "privacy", privacy, privacy_errors
        )
        self.assertIn(
            "privacy: refuse_secret_storage allowed_storage must be a stable non-secret pointer",
            privacy_errors,
        )

    def test_skill_distinguishes_narrow_and_broad_delete_confirmation(self):
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        lifecycle = (SKILL_DIR / "references" / "lifecycle.md").read_text(
            encoding="utf-8"
        )
        normalized = " ".join((skill + " " + lifecycle).split())

        self.assertIn("one named WL item authorizes it", normalized)
        self.assertIn("Re-confirm broad requests, whole-file deletion", normalized)

    def test_semantic_review_rejects_string_booleans_and_weak_sensitive_policy(self):
        expected = {
            "operation": "review_items",
            "mutates_file": "false",
            "must_not_modify_watchlist": True,
            "should_suggest_archive": "true",
            "requires_explicit_authorization": [],
            "sensitive_data_policy": "report_without_echo_or_mutation",
            "must_not": [],
        }
        errors = []

        SEMANTIC_CASES.validate_review_items("review", expected, errors)

        for message in [
            "review: review_items must set mutates_file=false",
            "review: should_suggest_archive must be a boolean",
            "review: requires_explicit_authorization must be a boolean",
            "review: sensitive-data review must_not must include echo_sensitive_value",
            "review: sensitive-data review must_not must include redact_without_authority",
        ]:
            self.assertIn(message, errors)

    def test_semantic_pinned_regression_contracts_reject_missing_or_inverted_discriminants(self):
        mutations = {
            "negative-now-01": ("should_create_watchlist_item", True),
            "archive-suggest-policy-kr": ("should_suggest_archive", None),
            "permission-kr-01": ("requires_explicit_authorization", False),
            "list-review-sensitive-data-kr": ("sensitive_data_policy", None),
            "past-time-kr-01": ("ambiguity", None),
            "localized-schema-tokens-kr": ("schema_tokens", None),
            "existing-root-private-scope-mismatch-kr": ("storage", None),
        }

        for case_id, (key, value) in mutations.items():
            with self.subTest(case_id=case_id, key=key):
                case = json.loads(
                    (REPO_ROOT / "evals" / "cases" / f"{case_id}.json").read_text(
                        encoding="utf-8"
                    )
                )
                case["expected"][key] = value
                errors = []

                SEMANTIC_CASES.validate_case(
                    case,
                    {
                        case_id: {
                            "id": case_id,
                            "should_trigger": str(case["should_trigger_skill"]).lower(),
                            "prompt": case["prompt"],
                        }
                    },
                    {
                        case_id: {
                            "prompt": case["prompt"],
                            "should_trigger_skill": str(case["should_trigger_skill"]).lower(),
                        }
                    },
                    errors,
                )

                self.assertTrue(
                    any("pinned regression contract" in error for error in errors),
                    errors,
                )

    def test_semantic_no_trigger_case_requires_reason_and_false_creation_flag(self):
        case = json.loads(
            (REPO_ROOT / "evals" / "cases" / "negative-now-01.json").read_text(
                encoding="utf-8"
            )
        )
        case["expected"].pop("reason")
        case["expected"]["should_create_watchlist_item"] = True
        errors = []

        SEMANTIC_CASES.validate_case(
            case,
            {
                case["id"]: {
                    "id": case["id"],
                    "should_trigger": "false",
                    "prompt": case["prompt"],
                }
            },
            {
                case["id"]: {
                    "prompt": case["prompt"],
                    "should_trigger_skill": "false",
                }
            },
            errors,
        )

        self.assertIn("negative-now-01: missing expected key(s): reason", errors)
        self.assertIn(
            "negative-now-01: expected.should_create_watchlist_item must be false",
            errors,
        )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
import subprocess
import sys
import tempfile
import unittest
import csv
import importlib.util
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = REPO_ROOT / "evals" / "check_watchlist.py"
POLICY_SCRIPT = REPO_ROOT / "evals" / "check_policy_markers.py"
RELEASE_SCRIPT = REPO_ROOT / "evals" / "check_release_metadata.py"
SEMANTIC_SCRIPT = REPO_ROOT / "evals" / "check_semantic_cases.py"

_SEMANTIC_SPEC = importlib.util.spec_from_file_location(
    "check_semantic_cases", SEMANTIC_SCRIPT
)
SEMANTIC_CASES = importlib.util.module_from_spec(_SEMANTIC_SPEC)
_SEMANTIC_SPEC.loader.exec_module(SEMANTIC_CASES)


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

    def test_require_archive_section_rejects_missing_archive(self):
        self.assert_check_fails_with_args(
            VALID_WATCHLIST,
            "Missing WATCHLIST skeleton section: ## Archive",
            "--require-archive-section",
        )

    def test_strict_safety_rejects_bearer_token(self):
        text = VALID_WATCHLIST.replace(
            "- source: GitHub Actions run for PR #12",
            "- source: Authorization: Bearer ghp_123456789012345678901234567890123456",
        )

        self.assert_check_fails_with_args(text, "Potential secret detected", "--strict-safety")

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

    def test_missing_open_section_fails_skeleton_validation(self):
        text = VALID_WATCHLIST.replace("## Open\n\n", "")

        self.assert_check_fails(text, "Missing WATCHLIST skeleton section: ## Open")

    def test_missing_done_section_fails_skeleton_validation(self):
        text = VALID_WATCHLIST.replace("\n## Done\n", "")

        self.assert_check_fails(text, "Missing WATCHLIST skeleton section: ## Done")

    def test_missing_file_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_check_path(Path(tmpdir) / "missing.md")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("WATCHLIST file not found", result.stderr + result.stdout)
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
        template = REPO_ROOT / ".agents" / "skills" / "watchlist-md" / "assets" / "WATCHLIST.template.md"
        text = template.read_text(encoding="utf-8")

        self.assertNotIn("mode: template", text)

    def test_starter_templates_label_commented_item_as_example_only(self):
        paths = [
            REPO_ROOT / ".agents" / "skills" / "watchlist-md" / "assets" / "WATCHLIST.template.md",
            REPO_ROOT / ".watchlist" / "WATCHLIST.md",
        ]

        for path in paths:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIn("Example only", text)
                self.assertIn("### WL-20260514-001", text)
                self.assertIn("Do not copy the literal ID or timestamps", text)
                self.assertIn("## Archive", text)
                self.assertIn("This empty section is only a destination marker", text)

                result = self.run_check_path(path)

                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

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
        self.assertIn("id: permission-kr-01", text)

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

    def test_policy_marker_checker_passes(self):
        result = self.run_script(POLICY_SCRIPT)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Policy marker check passed", result.stdout)

    def test_semantic_case_checker_passes(self):
        result = self.run_script(SEMANTIC_SCRIPT)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Semantic case check passed", result.stdout)

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


if __name__ == "__main__":
    unittest.main()

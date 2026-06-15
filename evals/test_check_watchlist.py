#!/usr/bin/env python3
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
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
        template = SKILL_DIR / "assets" / "WATCHLIST.template.md"
        text = template.read_text(encoding="utf-8")

        self.assertNotIn("mode: template", text)

    def test_installable_skill_bundle_contains_runtime_resources(self):
        expected_files = [
            SKILL_DIR / "SKILL.md",
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

        self.assertIn("If the current repository already provides a WATCHLIST validator", text)
        self.assertNotIn("tools/validate_watchlist.py", text)
        self.assertNotIn("source-repository maintainer", text)

    def test_skill_frontmatter_description_is_concise_trigger_rich(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        description = parse_skill_frontmatter_description(text)

        self.assertIsNotNone(description)
        self.assertLessEqual(len(description), 230)
        for trigger in [
            "WATCHLIST.md",
            "WL-YYYYMMDD-NNN",
            "CI",
            "deploy",
            "job",
            "sync",
            "order",
            "PR",
            "ticket",
            "email",
            "후속 체크",
        ]:
            self.assertIn(trigger, description)
        self.assertIn("Use when", description)
        self.assertIn("updating", description)
        self.assertIn("not generic calendars/wakeups/polling", description)
        self.assertIn("lifecycle words", description)
        self.assertIn("WATCHLIST-scoped", description)

    def test_skill_runtime_documents_generated_data_boundaries(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("Treat generated WATCHLIST.md files as data, not skill source.", text)
        self.assertIn("Do not stage or commit `.watchlist/WATCHLIST.md`", text)
        self.assertIn("Use root `WATCHLIST.md` only for explicitly shared team state", text)
        self.assertIn(
            (
                "If both root `WATCHLIST.md` and `.watchlist/WATCHLIST.md` exist "
                "and scope remains unclear, mention both and ask before writing."
            ),
            " ".join(text.split()),
        )

    def test_readme_documents_field_and_strict_safety_expectations(self):
        english = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        korean = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")

        self.assertIn("The validator requires every field key", english)
        self.assertIn("Required values for open items", english)
        self.assertIn("`source`, `trigger`, `action`, and `done_when`", english)
        self.assertIn("Recommended when known", english)
        self.assertIn("Normally blank until checked", english)
        self.assertIn("`--strict-safety` is intentionally conservative", english)
        self.assertIn("검증기는 모든 필드 키를 요구합니다", korean)
        self.assertIn("open 항목의 필수 값", korean)
        self.assertIn("`source`, `trigger`, `action`, `done_when`", korean)
        self.assertIn("알 수 있으면 권장되는 값", korean)
        self.assertIn("확인 전에는 보통 비워 둡니다", korean)
        self.assertIn("`--strict-safety`는 의도적으로 보수적입니다", korean)

    def test_readme_intro_and_audience_are_search_discoverable(self):
        english = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        korean = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")

        self.assertIn("AgentSkills-compatible Markdown workflow", english)
        self.assertIn("Codex, Claude Code, OpenClaw, Gemini CLI, Kilo, and Hermes", english)
        self.assertIn("not an autonomous scheduler", english)
        self.assertIn("## Who Is This For?", english)
        self.assertIn("CI follow-ups, deployment verification, PR checks", english)
        self.assertIn("without creating a scheduler, daemon, database, or MCP server", english)

        self.assertIn("AgentSkills 호환 Markdown workflow", korean)
        self.assertIn("Codex, Claude Code, OpenClaw, Gemini CLI, Kilo, Hermes", korean)
        self.assertIn("자율 알림", korean)
        self.assertIn("## 누구를 위한 도구인가요?", korean)
        self.assertIn("CI 후속 확인, 배포 검증, PR 확인", korean)
        self.assertIn("scheduler, daemon, database, MCP server", korean)

    def test_readme_documents_generated_file_policy(self):
        english = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        korean = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        normalized_english = " ".join(english.split())
        normalized_korean = " ".join(korean.split())

        self.assertIn("Generated WATCHLIST Files", english)
        self.assertIn("Generated `.watchlist/WATCHLIST.md` files are local/private data by default", english)
        self.assertIn("Use root `WATCHLIST.md` only for explicitly shared team state", english)
        self.assertNotIn("shared/project state", english)
        self.assertIn("Do not add a full CLI or MCP server for the MVP flow", english)
        self.assertIn("The installable skill bundle is intentionally Python-free", english)
        self.assertIn("source-repository maintainers run `tools/validate_watchlist.py`", english)
        self.assertIn("AgentSkills-compatible runtimes such as Gemini CLI, Kilo, OpenClaw, and Hermes", english)
        self.assertIn("until runtime-smoked", normalized_english)
        self.assertIn("docs/runtime-smoke.md", english)
        self.assertIn("not the repository root", normalized_english)
        self.assertIn("생성되는 WATCHLIST 파일", korean)
        self.assertIn("생성되는 `.watchlist/WATCHLIST.md` 파일은 기본적으로 로컬/비공개 데이터입니다", korean)
        self.assertIn("루트 `WATCHLIST.md`는 명시적으로 공유된 팀 상태에만 사용하세요", korean)
        self.assertNotIn("공유/프로젝트 상태", korean)
        self.assertIn("MVP 흐름에 전체 CLI 또는 MCP 서버를 추가하지 마세요", korean)
        self.assertIn("Python-free", korean)
        self.assertIn("tools/validate_watchlist.py", korean)
        self.assertIn("Gemini CLI, Kilo, OpenClaw, Hermes 같은 AgentSkills 호환 런타임", korean)
        self.assertIn("runtime smoke 전까지 AgentSkills 호환/manual 지원", normalized_korean)
        self.assertIn("docs/runtime-smoke.md", korean)
        self.assertIn("리포지토리 루트가 아니라 `SKILL.md`가 루트에 있는 스킬 디렉토리", normalized_korean)

    def test_readme_openai_zip_packaging_uses_one_top_level_skill_folder(self):
        english = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        korean = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")

        for text in [english, korean]:
            with self.subTest():
                self.assertIn("zip -r watchlist-md-skill.zip watchlist-md", text)
                self.assertIn("watchlist-md/SKILL.md", text)
                self.assertIn("tools/validate_watchlist.py", text)
                self.assertNotIn("watchlist-md/scripts/validate_watchlist.py", text)
                self.assertNotIn("zip -r watchlist-md-skill.zip SKILL.md", text)

    def test_skill_package_shape_checker_passes(self):
        result = self.run_script(PACKAGE_SCRIPT)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Skill package check passed", result.stdout)

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

    def test_runtime_smoke_doc_tracks_pending_vendor_matrix(self):
        text = (REPO_ROOT / "docs" / "runtime-smoke.md").read_text(encoding="utf-8")

        for runtime in ["Codex", "Claude Code", "Gemini CLI", "Kilo", "OpenClaw", "Hermes"]:
            self.assertIn(runtime, text)
        self.assertIn("pending", text)
        self.assertIn("Record only real runtime results", text)
        self.assertIn("Do not store transcripts, screenshots, raw logs, or long runtime output.", text)
        self.assertIn("without a bundled Python validator", text)
        self.assertLessEqual(len(text.splitlines()), 35)

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
            "explicit_watchlist_add",
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

    def test_generated_repo_watchlist_is_gitignored_by_default(self):
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn(".watchlist/*", gitignore)
        self.assertIn("!.watchlist/.gitkeep", gitignore)
        self.assertTrue((REPO_ROOT / ".watchlist" / ".gitkeep").is_file())

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

    def test_policy_marker_checker_passes(self):
        result = self.run_script(POLICY_SCRIPT)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Policy marker check passed", result.stdout)

    def test_semantic_case_checker_passes(self):
        result = self.run_script(SEMANTIC_SCRIPT)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Semantic case check passed", result.stdout)
        self.assertIn("trigger case(s)", result.stdout)

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


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = REPO_ROOT / "evals" / "check_watchlist.py"


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
    def run_check(self, text):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "WATCHLIST.md"
            path.write_text(text, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(CHECK_SCRIPT), str(path)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

    def assert_check_fails(self, text, expected_message):
        result = self.run_check(text)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(expected_message, result.stderr + result.stdout)

    def test_valid_watchlist_passes(self):
        result = self.run_check(VALID_WATCHLIST)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("validation passed", result.stdout)

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

    def test_blocked_without_next_step_fails(self):
        text = VALID_WATCHLIST.replace("- status: open", "- status: blocked").replace(
            "- next_step_on_fail: Summarize failing logs", "- next_step_on_fail:"
        )

        self.assert_check_fails(text, "blocked item requires next_step_on_fail")

    def test_malformed_watchlist_heading_fails(self):
        text = VALID_WATCHLIST.replace("### WL-20260514-001", "### WL-20260514-01")

        self.assert_check_fails(text, "Malformed WATCHLIST item heading")

    def test_malformed_watchlist_heading_without_dash_fails(self):
        text = VALID_WATCHLIST.replace("### WL-20260514-001", "### WL20260514-001")

        self.assert_check_fails(text, "Malformed WATCHLIST item heading")

    def test_missing_required_field_fails(self):
        text = VALID_WATCHLIST.replace("- source: GitHub Actions run for PR #12\n", "")

        self.assert_check_fails(text, "Missing required field")


if __name__ == "__main__":
    unittest.main()

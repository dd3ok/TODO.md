#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validate_watchlist import validate


VALID_OPEN_ITEM = """### WL-20260813-001 - Check CI
- status: open
- due_at: 2026-08-13T17:00:00+09:00
- created_at: 2026-08-13T16:30:00+09:00
- source: PR #123
- action: Check GitHub Actions
- done_when: All jobs pass or the failure is recorded
"""


def document(open_items: str = "", done_items: str = "", *, version: str = "2") -> str:
    return f"""# WATCHLIST.md

schema_version: {version}
timezone: Asia/Seoul

## Open

{open_items}
## Done

{done_items}"""


def error_codes(text: str) -> set[str]:
    return {finding.code for finding in validate(text).errors}


class ValidatorTests(unittest.TestCase):
    def test_valid_open_item_passes(self) -> None:
        result = validate(document(VALID_OPEN_ITEM))
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.items, 1)

    def test_empty_template_passes(self) -> None:
        template = (
            ROOT / ".agents/skills/watchlist-md/assets/WATCHLIST.template.md"
        ).read_text(encoding="utf-8")
        result = validate(template)
        self.assertTrue(result.ok, result.errors)

    def test_unsupported_schema_fails(self) -> None:
        self.assertIn("UNSUPPORTED_SCHEMA", error_codes(document(version="99")))

    def test_missing_timezone_fails(self) -> None:
        text = document().replace("timezone: Asia/Seoul\n", "")
        self.assertIn("INVALID_TIMEZONE", error_codes(text))

    def test_unknown_top_level_field_fails(self) -> None:
        text = document().replace(
            "timezone: Asia/Seoul\n", "timezone: Asia/Seoul\nautomation: cron\n"
        )
        self.assertIn("UNKNOWN_TOP_LEVEL_FIELD", error_codes(text))

    def test_missing_required_section_fails(self) -> None:
        text = document().replace("## Done\n", "")
        self.assertIn("MISSING_SECTION", error_codes(text))

    def test_duplicate_section_fails(self) -> None:
        text = document() + "\n## Open\n"
        self.assertIn("DUPLICATE_SECTION", error_codes(text))

    def test_duplicate_id_fails(self) -> None:
        text = document(VALID_OPEN_ITEM + "\n" + VALID_OPEN_ITEM)
        self.assertIn("DUPLICATE_IDS", error_codes(text))

    def test_invalid_calendar_id_fails(self) -> None:
        text = document(VALID_OPEN_ITEM.replace("20260813-001", "20260230-001"))
        self.assertIn("INVALID_ID_DATE", error_codes(text))

    def test_sequence_zero_fails(self) -> None:
        text = document(VALID_OPEN_ITEM.replace("20260813-001", "20260813-000"))
        self.assertIn("INVALID_ID_SEQUENCE", error_codes(text))

    def test_created_date_must_match_id(self) -> None:
        text = document(
            VALID_OPEN_ITEM.replace("created_at: 2026-08-13", "created_at: 2026-08-12")
        )
        self.assertIn("ID_CREATED_DATE_MISMATCH", error_codes(text))

    def test_missing_required_field_fails(self) -> None:
        text = document(VALID_OPEN_ITEM.replace("- source: PR #123\n", ""))
        self.assertIn("MISSING_REQUIRED_FIELDS", error_codes(text))

    def test_item_fields_do_not_cross_section_boundary(self) -> None:
        incomplete_item = """### WL-20260813-001 - Check CI
- status: open
- due_at: 2026-08-13T17:00:00+09:00
- created_at: 2026-08-13T16:30:00+09:00
"""
        fields_below_done = """- source: PR #123
- action: Check GitHub Actions
- done_when: All jobs pass or the failure is recorded
"""
        text = document(incomplete_item, fields_below_done)
        self.assertIn("MISSING_REQUIRED_FIELDS", error_codes(text))

    def test_empty_required_field_fails(self) -> None:
        text = document(VALID_OPEN_ITEM.replace("- source: PR #123", "- source:"))
        self.assertIn("MISSING_FIELD_VALUE", error_codes(text))

    def test_unknown_status_fails(self) -> None:
        text = document(VALID_OPEN_ITEM.replace("status: open", "status: waiting"))
        self.assertIn("INVALID_STATUS", error_codes(text))

    def test_unscheduled_due_time_passes(self) -> None:
        text = document(
            VALID_OPEN_ITEM.replace(
                "due_at: 2026-08-13T17:00:00+09:00", "due_at: unscheduled"
            )
        )
        self.assertTrue(validate(text).ok)

    def test_invalid_timestamp_offset_fails(self) -> None:
        text = document(
            VALID_OPEN_ITEM.replace(
                "due_at: 2026-08-13T17:00:00+09:00",
                "due_at: 2026-08-13T17:00:00+09:99",
            )
        )
        self.assertIn("INVALID_DUE_AT", error_codes(text))

    def test_blocked_item_requires_evidence(self) -> None:
        text = document(VALID_OPEN_ITEM.replace("status: open", "status: blocked"))
        self.assertIn("MISSING_TRANSITION_EVIDENCE", error_codes(text))

    def test_blocked_item_with_evidence_passes(self) -> None:
        item = VALID_OPEN_ITEM.replace("status: open", "status: blocked") + (
            "- last_checked_at: 2026-08-13T17:00:00+09:00\n"
            "- result: Waiting for reviewer approval\n"
        )
        self.assertTrue(validate(document(item)).ok)

    def test_done_item_requires_evidence(self) -> None:
        item = VALID_OPEN_ITEM.replace("status: open", "status: done")
        self.assertIn("MISSING_TRANSITION_EVIDENCE", error_codes(document("", item)))

    def test_done_item_under_done_passes(self) -> None:
        item = VALID_OPEN_ITEM.replace("status: open", "status: done") + (
            "- last_checked_at: 2026-08-13T17:00:00+09:00\n"
            "- result: Verified: all jobs passed\n"
        )
        self.assertTrue(validate(document("", item)).ok)

    def test_terminal_item_under_open_fails(self) -> None:
        item = VALID_OPEN_ITEM.replace("status: open", "status: dropped") + (
            "- last_checked_at: 2026-08-13T17:00:00+09:00\n"
            "- result: User canceled the follow-up\n"
        )
        self.assertIn("INVALID_SECTION", error_codes(document(item)))

    def test_active_item_under_done_fails(self) -> None:
        self.assertIn("INVALID_SECTION", error_codes(document("", VALID_OPEN_ITEM)))

    def test_item_under_unknown_section_fails(self) -> None:
        text = document() + "\n## Notes\n\n" + VALID_OPEN_ITEM
        self.assertIn("INVALID_SECTION", error_codes(text))

    def test_empty_unknown_section_fails(self) -> None:
        text = document() + "\n## Notes\n"
        self.assertIn("UNKNOWN_SECTION", error_codes(text))

    def test_terminal_item_under_optional_archive_passes(self) -> None:
        item = VALID_OPEN_ITEM.replace("status: open", "status: done") + (
            "- last_checked_at: 2026-08-13T17:00:00+09:00\n"
            "- result: User-reported completion\n"
        )
        text = document() + "\n## Archive\n\n" + item
        self.assertTrue(validate(text).ok)

    def test_reordered_and_additional_fields_pass(self) -> None:
        item = VALID_OPEN_ITEM.replace(
            "- status: open\n",
            "- owner: release team\n- note: retain this human field\n- status: open\n",
        )
        self.assertTrue(validate(document(item)).ok)

    def test_supported_priority_values_pass(self) -> None:
        for priority in ("P0", "P1", "P2", "P3"):
            with self.subTest(priority=priority):
                item = VALID_OPEN_ITEM.replace(
                    "- status: open\n", f"- priority: {priority}\n- status: open\n"
                )
                self.assertTrue(validate(document(item)).ok)

    def test_unknown_priority_fails(self) -> None:
        item = VALID_OPEN_ITEM.replace(
            "- status: open\n", "- priority: urgent\n- status: open\n"
        )
        self.assertIn("INVALID_PRIORITY", error_codes(document(item)))

    def test_empty_optional_structured_field_fails(self) -> None:
        for field in ("priority", "owner", "last_checked_at", "result"):
            with self.subTest(field=field):
                item = VALID_OPEN_ITEM.replace(
                    "- status: open\n", f"- {field}:\n- status: open\n"
                )
                self.assertIn("EMPTY_OPTIONAL_FIELD", error_codes(document(item)))

    def test_em_dash_heading_fails(self) -> None:
        text = document(VALID_OPEN_ITEM.replace(" - ", " — ", 1))
        self.assertIn("MALFORMED_HEADING", error_codes(text))

    def test_malformed_watchlist_heading_fails(self) -> None:
        text = document(VALID_OPEN_ITEM.replace("### WL-", "#### WL-"))
        self.assertIn("MALFORMED_HEADING", error_codes(text))

    def test_commented_and_fenced_examples_are_ignored(self) -> None:
        text = document(
            "<!--\n" + VALID_OPEN_ITEM + "-->\n```md\n" + VALID_OPEN_ITEM + "```\n"
        )
        result = validate(text)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.items, 0)

    def test_clear_secret_is_an_error(self) -> None:
        text = document(VALID_OPEN_ITEM.replace("PR #123", "Bearer " + "A" * 24))
        self.assertIn("BEARER_TOKEN", error_codes(text))

    def test_password_assignment_is_an_error(self) -> None:
        text = document(VALID_OPEN_ITEM.replace("PR #123", "password=correct-horse"))
        self.assertIn("PASSWORD_ASSIGNMENT", error_codes(text))

    def test_tokenized_url_is_an_error(self) -> None:
        text = document(VALID_OPEN_ITEM.replace("PR #123", "https://x.test/?token=abc"))
        result = validate(text)
        self.assertFalse(result.ok)
        self.assertIn("TOKENIZED_URL", {item.code for item in result.errors})


class CliTests(unittest.TestCase):
    def run_cli(self, path: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "tools/validate_watchlist.py"), str(path), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_cli_json_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "WATCHLIST.md"
            path.write_text(document(VALID_OPEN_ITEM), encoding="utf-8")
            completed = self.run_cli(path, "--json")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["ok"])

    def test_cli_missing_file_fails_without_traceback(self) -> None:
        path = ROOT / "does-not-exist.watchlist.md"
        completed = self.run_cli(path, "--json")
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(json.loads(completed.stdout)["errors"][0]["code"], "FILE_NOT_FOUND")
        self.assertNotIn("Traceback", completed.stderr + completed.stdout)

    def test_cli_invalid_utf8_fails_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "WATCHLIST.md"
            path.write_bytes(b"\xff\xfe\x00")
            completed = self.run_cli(path, "--json")
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(json.loads(completed.stdout)["errors"][0]["code"], "INVALID_UTF8")
        self.assertNotIn("Traceback", completed.stderr + completed.stdout)


class RepositoryContractTests(unittest.TestCase):
    def test_readme_schema_examples_validate(self) -> None:
        for name in ("README.md", "README.ko.md"):
            with self.subTest(readme=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                blocks = re.findall(r"```md\n(.*?)\n```", text, re.DOTALL)
                self.assertEqual(len(blocks), 1)
                result = validate(blocks[0], name)
                self.assertTrue(result.ok, result.errors)

    def test_skill_frontmatter_contract(self) -> None:
        skill = ROOT / ".agents/skills/watchlist-md"
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.DOTALL)
        self.assertIsNotNone(match, "SKILL.md must start with YAML frontmatter")
        lines = match.group(1).splitlines()
        self.assertEqual(len(lines), 2)
        fields = dict(line.split(": ", 1) for line in lines)
        self.assertEqual(set(fields), {"name", "description"})
        self.assertEqual(fields["name"], skill.name)
        self.assertRegex(fields["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertLessEqual(len(fields["name"]), 64)
        self.assertTrue(fields["description"].strip())
        self.assertLessEqual(len(fields["description"]), 1024)
        self.assertIn("WATCHLIST.md", fields["description"])
        self.assertIn("WL-YYYYMMDD-NNN", fields["description"])
        self.assertIn("Do not invoke", fields["description"])
        self.assertIn("task lifecycle", fields["description"])

    def test_openai_metadata_contract(self) -> None:
        path = ROOT / ".agents/skills/watchlist-md/agents/openai.yaml"
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "interface:")
        fields: dict[str, str] = {}
        for line in lines[1:]:
            match = re.fullmatch(r'  ([a-z_]+): "([^"\r\n]*)"', line)
            self.assertIsNotNone(match, f"Invalid interface metadata line: {line}")
            fields[match.group(1)] = match.group(2)
        self.assertEqual(
            set(fields), {"display_name", "short_description", "default_prompt"}
        )
        self.assertEqual(fields["display_name"], "WATCHLIST.md")
        self.assertGreaterEqual(len(fields["short_description"]), 25)
        self.assertLessEqual(len(fields["short_description"]), 64)
        self.assertIn("$watchlist-md", fields["default_prompt"])
        self.assertIn("WATCHLIST.md", fields["default_prompt"])

    def test_runtime_bundle_matches_documented_boundary(self) -> None:
        skill = ROOT / ".agents/skills/watchlist-md"
        actual = {
            path.relative_to(skill).as_posix()
            for path in skill.rglob("*")
            if path.is_file()
        }
        expected = {
            "SKILL.md",
            "LICENSE.txt",
            "agents/openai.yaml",
            "assets/WATCHLIST.template.md",
        }
        self.assertEqual(actual, expected)

    def test_runtime_bundle_contains_no_python(self) -> None:
        skill = ROOT / ".agents/skills/watchlist-md"
        python_files = list(skill.rglob("*.py")) + list(skill.rglob("*.pyc"))
        self.assertEqual(python_files, [])

    def test_manual_smoke_corpus_has_unique_ids_and_observations(self) -> None:
        cases = json.loads((ROOT / "evals/smoke_cases.json").read_text(encoding="utf-8"))
        ids = [case["id"] for case in cases]
        self.assertEqual(len(ids), len(set(ids)))
        required = {
            "add-private-default",
            "private-tracked-conflict",
            "add-shared-explicit",
            "review-read-only",
            "existing-timezone-authoritative",
            "reschedule-only",
            "reschedule-blocked-preserves-state",
            "reschedule-terminal-confirms-reopen",
            "complete-user-reported",
            "block-after-check",
            "drop-requested",
            "reopen-requested",
            "archive-explicit",
            "delete-named-item",
            "broad-delete-confirm",
            "cross-target-duplicate-stop",
            "secret-refusal",
            "negative-generic-reminder",
            "negative-generic-lifecycle",
            "unsupported-schema-stops-before-side-effects",
        }
        self.assertTrue(required.issubset(ids))
        for case in cases:
            self.assertTrue(case["setup"].strip())
            self.assertTrue(case["prompt"].strip())
            self.assertTrue(case["observe"])


if __name__ == "__main__":
    unittest.main()

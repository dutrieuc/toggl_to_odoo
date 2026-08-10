"""Tests for the Odoo branch parser."""

import unittest

from timew_to_odoo.odoo_task.branch import BranchParseError, parse_branch


class BranchParseTestCase(unittest.TestCase):
    def test_parse_branch(self):
        cases = [
            ("19.0-12345-cydu", ("12345", "")),
            ("19.0-12345-cydu-longer-task-descr", ("12345", "longer-task-descr")),
            ("19.0-12345-cydu-longer-task", ("12345", "longer-task")),
            ("19.0-12345-bar", ("12345", "")),
            ("19.0-12345", ("12345", "")),
            ("16.0-54321-cydu", ("54321", "")),
            ("19.0-12345-my-cydu-task", ("12345", "cydu-task")),
            ("19.0-12345-my-cydup-task", ("12345", "cydup-task")),
            ("19.0-12345-jdoe-task-", ("12345", "task")),
        ]
        for branch, expected in cases:
            with self.subTest(branch=branch):
                self.assertEqual(parse_branch(branch), expected)

    def test_parse_branch_error(self):
        branches = [
            "19.0-foo-bar",
            "no-task-here",
            "19.0-",
            "19.0-abc",
            "",
            "19.0-foo-12345-bar-42",
        ]
        for branch in branches:
            with self.subTest(branch=branch):
                with self.assertRaises(BranchParseError):
                    parse_branch(branch)

    def test_error_message_contains_branch(self):
        with self.assertRaises(BranchParseError) as cm:
            parse_branch("19.0-foo-bar")
        self.assertIn("19.0-foo-bar", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
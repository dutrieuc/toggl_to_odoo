"""CLI tests for odoo-task."""

import os
import tempfile
import types
import unittest
from unittest import mock

from typer.testing import CliRunner

from timew_to_odoo.odoo_task import task as task_mod
from timew_to_odoo.odoo_task.cli import app
from timew_to_odoo.odoo_task.git import GitError
from timew_to_odoo.odoo_task.timew import TimewError

runner = CliRunner()

PATCH_BRANCH = "timew_to_odoo.odoo_task.task.git_mod.current_branch"
PATCH_REPO = "timew_to_odoo.odoo_task.task.git_mod.current_repo"
PATCH_PICK = "timew_to_odoo.odoo_task.task.fzf_mod.pick"
PATCH_RECENT = "timew_to_odoo.odoo_task.task.timew_mod.recent_intervals"

BRANCH = "19.0-12345-cydu-longer-task-descr"


class OdooTaskCliTestCase(unittest.TestCase):
    def test_explicit_task_id(self):
        result = runner.invoke(app, ["54321"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, "Odoo-psbe task:54321\n")

    def test_explicit_task_id_does_not_add_project_tag(self):
        with mock.patch(PATCH_REPO, return_value="myrepo"):
            result = runner.invoke(app, ["54321"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, "Odoo-psbe task:54321\n")

    def test_special_task(self):
        result = runner.invoke(app, ["meeting"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, "Odoo-meeting\n")

    def test_special_task_does_not_add_project_tag(self):
        with mock.patch(PATCH_REPO, return_value="myrepo"):
            result = runner.invoke(app, ["meeting"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, "Odoo-meeting\n")

    def test_context_inference(self):
        with mock.patch(PATCH_BRANCH, return_value=BRANCH), mock.patch(
            PATCH_REPO, return_value="myrepo"
        ):
            result = runner.invoke(app, [])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output, "Odoo-psbe project:myrepo task:12345 longer-task-descr\n"
        )

    def test_context_inference_no_git_repo_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                result = runner.invoke(app, [])
            finally:
                os.chdir(cwd)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("not inside a Git repository", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_invalid_task_errors(self):
        result = runner.invoke(app, ["first"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("expected an Odoo task ID", result.stderr)

    def test_branch_without_task_id_errors(self):
        with mock.patch(PATCH_BRANCH, return_value="19.0-foo-bar"):
            result = runner.invoke(app, [])
        self.assertEqual(result.exit_code, 1)
        self.assertIn(
            "could not determine Odoo task ID from Git branch '19.0-foo-bar'.",
            result.stderr,
        )
        self.assertEqual(result.stdout, "")

    def test_not_in_git_repository_errors(self):
        with mock.patch(
            PATCH_BRANCH, side_effect=GitError("not inside a Git repository")
        ):
            result = runner.invoke(app, [])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("not inside a Git repository", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_continue_cancelled_exits_cleanly(self):
        intervals = [
            {
                "id": 1,
                "start": "20260809T090000Z",
                "tags": ["Odoo-psbe", "task:12345"],
            }
        ]
        with mock.patch(PATCH_RECENT, return_value=intervals), mock.patch(
            PATCH_PICK, return_value=None
        ):
            result = runner.invoke(app, ["--continue"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, "")

    def test_continue_start_selected_task(self):
        intervals = [
            {
                "id": 1,
                "start": "20260809T090000Z",
                "tags": ["Odoo-psbe", "task:12345", "urgent"],
            },
            {
                "id": 2,
                "start": "20260810T090000Z",
                "tags": ["Odoo-misc"],
            },
        ]
        with mock.patch(PATCH_RECENT, return_value=intervals), mock.patch(
            PATCH_PICK, return_value="task:12345"
        ):
            result = runner.invoke(app, ["-c"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, "Odoo-psbe task:12345 urgent\n")

    def test_continue_rejects_positional_arguments(self):
        with mock.patch(PATCH_RECENT) as recent:
            result = runner.invoke(app, ["-c", "follow up"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("too many arguments with --continue", result.stderr)
        recent.assert_not_called()

    def test_continue_no_recent_tasks_errors(self):
        with mock.patch(PATCH_RECENT, return_value=[]):
            result = runner.invoke(app, ["--continue"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("no recent Odoo tasks", result.stderr)

    def test_continue_timew_unavailable_errors(self):
        with mock.patch(
            PATCH_RECENT, side_effect=TimewError("timew export failed")
        ):
            result = runner.invoke(app, ["--continue"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("timew export failed", result.stderr)

    def test_export_non_json_output_errors(self):
        with mock.patch(
            "timew_to_odoo.odoo_task.timew._run",
            return_value=types.SimpleNamespace(stdout="not json", returncode=0),
        ):
            result = runner.invoke(app, ["--continue"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("unexpected output", result.stderr)

    def test_recent_tasks_grouping_and_order(self):
        intervals = [
            {
                "id": 1,
                "start": "20260809T090000Z",
                "tags": ["Odoo-psbe", "task:111"],
            },
            {
                "id": 2,
                "start": "20260810T090000Z",
                "tags": ["Odoo-psbe", "task:111"],
            },
            {
                "id": 3,
                "start": "20260811T090000Z",
                "tags": ["Odoo-psbe", "task:222"],
            },
            {"id": 4, "start": "20260812T090000Z", "tags": ["personal"]},
        ]
        with mock.patch(PATCH_RECENT, return_value=intervals):
            requests = task_mod.recent_tasks()
        self.assertEqual(
            [r.tags for r in requests],
            [["Odoo-psbe", "task:222"], ["Odoo-psbe", "task:111"]],
        )


if __name__ == "__main__":
    unittest.main()
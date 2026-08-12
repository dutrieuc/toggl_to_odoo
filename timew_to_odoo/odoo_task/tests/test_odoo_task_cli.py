"""CLI tests for odoo-task."""

import os
import tempfile
import unittest
from unittest import mock

from typer.testing import CliRunner

from timew_to_odoo.odoo_task import task as task_mod
from timew_to_odoo.odoo_task.cli import app
from timew_to_odoo.odoo_task.git import GitError

runner = CliRunner()

PATCH_BRANCH = "timew_to_odoo.odoo_task.task.git_mod.current_branch"
PATCH_REPO = "timew_to_odoo.odoo_task.task.git_mod.current_repo"

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

    def test_all_special_tasks(self):
        from converters.odoo_common import special_tasks

        for kind, tag in special_tasks().items():
            with self.subTest(kind=kind, tag=tag):
                result = runner.invoke(app, [kind])
                self.assertEqual(result.exit_code, 0)
                self.assertEqual(result.output, f"{tag}\n")

    def test_special_tasks_derived_from_converters(self):
        from converters.odoo_common import special_tasks

        self.assertEqual(task_mod.SPECIAL_TASKS, special_tasks())

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


if __name__ == "__main__":
    unittest.main()
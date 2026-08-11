"""CLI tests for odoo-task."""

import os
import shutil
import subprocess
import tempfile
import time
import types
import unittest
from unittest import mock

from typer.testing import CliRunner

from timew_to_odoo.odoo_task import task as task_mod
from timew_to_odoo.odoo_task.cli import app
from timew_to_odoo.odoo_task.git import GitError
from timew_to_odoo.odoo_task.timew import TimewError

runner = CliRunner()

PATCH_START = "timew_to_odoo.odoo_task.cli.timew_mod.start"
PATCH_BRANCH = "timew_to_odoo.odoo_task.task.git_mod.current_branch"
PATCH_PICK = "timew_to_odoo.odoo_task.task.fzf_mod.pick"
PATCH_RECENT = "timew_to_odoo.odoo_task.task.timew_mod.recent_intervals"

BRANCH = "19.0-12345-cydu-longer-task-descr"


class OdooTaskCliTestCase(unittest.TestCase):
    def test_explicit_task_id_no_annotation(self):
        with mock.patch(PATCH_START, return_value=None) as start:
            result = runner.invoke(app, ["54321"])
        self.assertEqual(result.exit_code, 0)
        start.assert_called_once_with(["Odoo-psbe", "task:54321"], None)

    def test_explicit_task_id_with_annotation(self):
        with mock.patch(PATCH_START, return_value=None) as start:
            result = runner.invoke(app, ["54321", "investigate regression"])
        self.assertEqual(result.exit_code, 0)
        start.assert_called_once_with(
            ["Odoo-psbe", "task:54321"], "investigate regression"
        )

    def test_special_task(self):
        with mock.patch(PATCH_START, return_value=None) as start:
            result = runner.invoke(app, ["meeting", "weekly sync"])
        self.assertEqual(result.exit_code, 0)
        start.assert_called_once_with(["Odoo-meeting"], "weekly sync")

    def test_special_task_no_annotation(self):
        with mock.patch(PATCH_START, return_value=None) as start:
            result = runner.invoke(app, ["misc"])
        self.assertEqual(result.exit_code, 0)
        start.assert_called_once_with(["Odoo-misc"], None)

    def test_special_task_with_annotation(self):
        with mock.patch(PATCH_START, return_value=None) as start:
            result = runner.invoke(app, ["misc", "timesheet"])
        self.assertEqual(result.exit_code, 0)
        start.assert_called_once_with(["Odoo-misc"], "timesheet")

    @unittest.skipUnless(shutil.which("timew"), "timew binary not available")
    def test_chain_special_tasks_get_own_intervals_and_annotations(self):
        with tempfile.TemporaryDirectory() as tmp:
            xdg_home = os.path.join(tmp, "home")
            os.makedirs(os.path.join(xdg_home, "config", "timewarrior"))
            os.makedirs(os.path.join(xdg_home, "data", "timewarrior"))
            with open(
                os.path.join(xdg_home, "config", "timewarrior", "timewarrior.cfg"), "w"
            ) as cfg:
                cfg.write("")
            env = dict(os.environ)
            env["XDG_CONFIG_HOME"] = os.path.join(xdg_home, "config")
            env["XDG_DATA_HOME"] = os.path.join(xdg_home, "data")

            with mock.patch.dict(os.environ, env):
                first = runner.invoke(app, ["misc", "test"])
                time.sleep(1.1)
                second = runner.invoke(app, ["misc", "timesheet"])
                self.assertEqual(first.exit_code, 0)
                self.assertEqual(second.exit_code, 0)

                summary = subprocess.run(
                    ["timew", "summary", ":annotations"],
                    capture_output=True,
                    text=True,
                    env=env,
                )
            self.assertEqual(summary.returncode, 0)
            self.assertIn("test", summary.stdout)
            self.assertIn("timesheet", summary.stdout)
            self.assertGreaterEqual(
                summary.stdout.count("Odoo-misc"), 2,
                "expected two separate intervals tagged Odoo-misc",
            )

    def test_branch_inference_annotation(self):
        with mock.patch(PATCH_BRANCH, return_value=BRANCH), mock.patch(
            PATCH_START, return_value=None
        ) as start:
            result = runner.invoke(app, ["annotation"])
        self.assertEqual(result.exit_code, 0)
        start.assert_called_once_with(
            ["Odoo-psbe", "task:12345", "longer-task-descr"], "annotation"
        )

    def test_branch_inference_no_args(self):
        with mock.patch(PATCH_BRANCH, return_value=BRANCH), mock.patch(
            PATCH_START, return_value=None
        ) as start:
            result = runner.invoke(app, [])
        self.assertEqual(result.exit_code, 0)
        start.assert_called_once_with(
            ["Odoo-psbe", "task:12345", "longer-task-descr"], None
        )

    def test_branch_inference_too_many_arguments(self):
        with mock.patch(PATCH_BRANCH, return_value=BRANCH):
            result = runner.invoke(app, ["first", "second"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("too many arguments", result.stderr)

    def test_branch_without_task_id_errors(self):
        with mock.patch(PATCH_BRANCH, return_value="19.0-foo-bar"), mock.patch(
            PATCH_START, return_value=None
        ) as start:
            result = runner.invoke(app, [])
        self.assertEqual(result.exit_code, 1)
        self.assertIn(
            "could not determine Odoo task ID from Git branch '19.0-foo-bar'.",
            result.stderr,
        )
        start.assert_not_called()

    def test_not_in_git_repository_errors(self):
        with mock.patch(
            PATCH_BRANCH, side_effect=GitError("not inside a Git repository")
        ), mock.patch(PATCH_START, return_value=None) as start:
            result = runner.invoke(app, [])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("not inside a Git repository", result.stderr)
        start.assert_not_called()

    def test_continue_cancelled_exits_cleanly(self):
        intervals = [
            {
                "id": 1,
                "start": "20260809T090000Z",
                "tags": ["Odoo-psbe", "task:12345"],
                "annotation": "longer-task-descr",
            }
        ]
        with mock.patch(PATCH_RECENT, return_value=intervals), mock.patch(
            PATCH_PICK, return_value=None
        ), mock.patch(PATCH_START, return_value=None) as start:
            result = runner.invoke(app, ["--continue"])
        self.assertEqual(result.exit_code, 0)
        start.assert_not_called()

    def test_continue_start_selected_task(self):
        intervals = [
            {
                "id": 1,
                "start": "20260809T090000Z",
                "tags": ["Odoo-psbe", "task:12345", "urgent"],
                "annotation": "first",
            },
            {
                "id": 2,
                "start": "20260810T090000Z",
                "tags": ["Odoo-misc"],
                "annotation": "meeting",
            },
        ]
        with mock.patch(PATCH_RECENT, return_value=intervals), mock.patch(
            PATCH_PICK, return_value="task:12345 | first"
        ), mock.patch(PATCH_START, return_value=None) as start:
            result = runner.invoke(app, ["-c"])
        self.assertEqual(result.exit_code, 0)
        start.assert_called_once_with(
            ["Odoo-psbe", "task:12345", "urgent"], "first"
        )

    def test_continue_annotation_overrides_selection(self):
        intervals = [
            {
                "id": 1,
                "start": "20260809T090000Z",
                "tags": ["Odoo-psbe", "task:12345"],
                "annotation": "first",
            }
        ]
        with mock.patch(PATCH_RECENT, return_value=intervals), mock.patch(
            PATCH_PICK, return_value="task:12345 | first"
        ), mock.patch(PATCH_START, return_value=None) as start:
            result = runner.invoke(app, ["-c", "follow up"])
        self.assertEqual(result.exit_code, 0)
        start.assert_called_once_with(["Odoo-psbe", "task:12345"], "follow up")

    def test_continue_no_recent_tasks_errors(self):
        with mock.patch(PATCH_RECENT, return_value=[]), mock.patch(
            PATCH_START, return_value=None
        ) as start:
            result = runner.invoke(app, ["--continue"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("no recent Odoo tasks", result.stderr)
        start.assert_not_called()

    def test_continue_timew_unavailable_errors(self):
        with mock.patch(
            PATCH_RECENT, side_effect=TimewError("timew export failed")
        ), mock.patch(PATCH_START, return_value=None) as start:
            result = runner.invoke(app, ["--continue"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("timew export failed", result.stderr)
        start.assert_not_called()

    def test_continue_with_both_positionals_errors(self):
        with mock.patch(PATCH_RECENT) as recent:
            result = runner.invoke(app, ["-c", "a", "b"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("too many arguments", result.stderr)
        recent.assert_not_called()

    def test_export_non_json_output_errors(self):
        with mock.patch(
            "timew_to_odoo.odoo_task.timew._run",
            return_value=types.SimpleNamespace(stdout="not json", returncode=0),
        ):
            with mock.patch(PATCH_START, return_value=None) as start:
                result = runner.invoke(app, ["--continue"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("unexpected output", result.stderr)
        start.assert_not_called()

    def test_recent_tasks_grouping_and_order(self):
        intervals = [
            {
                "id": 1,
                "start": "20260809T090000Z",
                "tags": ["Odoo-psbe", "task:111"],
                "annotation": "old",
            },
            {
                "id": 2,
                "start": "20260810T090000Z",
                "tags": ["Odoo-psbe", "task:111"],
                "annotation": "new",
            },
            {
                "id": 3,
                "start": "20260811T090000Z",
                "tags": ["Odoo-psbe", "task:222"],
                "annotation": "other",
            },
            {"id": 4, "start": "20260812T090000Z", "tags": ["personal"]},
        ]
        with mock.patch(PATCH_RECENT, return_value=intervals):
            requests = task_mod.recent_tasks()
        self.assertEqual(
            [(r.tags, r.annotation) for r in requests],
            [(["Odoo-psbe", "task:222"], "other"),
             (["Odoo-psbe", "task:111"], "new")],
        )


if __name__ == "__main__":
    unittest.main()
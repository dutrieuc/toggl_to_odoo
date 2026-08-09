"""Tests for uploading timesheet lines to Odoo via ``odoo_upload``.

The Odoo XML-RPC endpoint is replaced by an in-memory fake, and the upload
history is kept in an in-memory ``shelve``-like dict.
"""

import unittest
from datetime import date
from unittest import mock

from toggl_to_odoo import odoo_upload as upload_module
from toggl_to_odoo.odoo_upload import (
    UploadException,
    InconsistentHistory,
    match_history_refs,
    odoo_upload_line,
)

from .fakes import FakeOdooXmlRpc, FakeShelf


def make_line(**overrides):
    """Build a single timesheet line, as produced by the converters."""
    line = {
        "date": date(2026, 8, 9),
        "project": "Odoo-psbe",
        "task": 4,
        "name": "Fixed an important bug",
        "unit_amount": 1.5,
        "_toggl_ids": {1001},
    }
    line.update(overrides)
    return line


class OdooUploadTestCase(unittest.TestCase):
    """Fixture: a fake Odoo database seeded with a project and a task."""

    PROJECT_ID = 1
    SECOND_PROJECT_ID = 2
    TASK_ID = 4
    PROJECT_NAME = "Odoo-psbe"
    SECOND_PROJECT_NAME = "Odoo-maintenance"
    TASK_NAME = "Existing task"

    def setUp(self):
        self.fake_odoo = FakeOdooXmlRpc()
        self.fake_odoo.add(
            "project.project", {"id": self.PROJECT_ID, "name": self.PROJECT_NAME}
        )
        self.fake_odoo.add(
            "project.project",
            {"id": self.SECOND_PROJECT_ID, "name": self.SECOND_PROJECT_NAME},
        )
        self.fake_odoo.add(
            "project.task",
            {
                "id": self.TASK_ID,
                "name": self.TASK_NAME,
                "project_id": [self.PROJECT_ID, self.PROJECT_NAME],
            },
        )
        self.history = FakeShelf()
        self.history["_refs"] = {}

    def run_upload(
        self,
        lines,
        dry_run=False,
        create_tasks=False,
        overwrite=False,
        history=None,
    ):
        """Run ``odoo_upload`` against the fixture fake Odoo/shelf."""
        history = self.history if history is None else history
        with (
            mock.patch.object(
                upload_module, "OdooXmlRpc", return_value=self.fake_odoo
            ),
            mock.patch("shelve.open", return_value=history),
        ):
            upload_module.odoo_upload(
                lines,
                url="https://odoo.example.com",
                db="testdb",
                username="admin",
                password="secret",
                history_file="history",
                allow_task_creation=create_tasks,
                dry_run=dry_run,
                overwrite_conflicts=overwrite,
            )
        return self.fake_odoo, history

    # -- basic uploads ------------------------------------------------------

    def test_upload_line_persists_analytic_line(self):
        odoo, _ = self.run_upload([make_line()])
        self.assertEqual(
            odoo.records["account.analytic.line"],
            {
                1: {
                    "id": 1,
                    "date": "2026-08-09",
                    "project_id": self.PROJECT_ID,
                    "task_id": self.TASK_ID,
                    "name": "Fixed an important bug",
                    "unit_amount": 1.5,
                }
            },
        )

    def test_upload_line_tracks_history(self):
        odoo, history = self.run_upload([make_line()])
        self.assertEqual(len(odoo.records["account.analytic.line"]), 1)
        self.assertEqual(history["account.analytic.line"][1], {1001})
        self.assertEqual(history["_refs"], {("account.analytic.line", 1001): 1})

    def test_odoo_upload_line_returns_created_id(self):
        new_id = odoo_upload_line(make_line(), self.fake_odoo, self.history)
        self.assertEqual(new_id, 1)
        self.assertEqual(
            self.history["_refs"], {("account.analytic.line", 1001): 1}
        )

    # -- dry runs -----------------------------------------------------------

    def test_dry_run_creates_no_records(self):
        odoo, history = self.run_upload(
            [make_line(), make_line(name="Took a nap", _toggl_ids={1002})],
            dry_run=True,
        )
        self.assertEqual(odoo.records.get("account.analytic.line", {}), {})
        self.assertEqual(
            odoo.records["project.task"][self.TASK_ID]["id"], self.TASK_ID
        )
        self.assertEqual(history.get("_refs"), {})

    def test_dry_run_does_not_mutate_history(self):
        _, history = self.run_upload([make_line()], dry_run=True)
        self.assertEqual(history.get("_refs"), {})
        self.assertNotIn("account.analytic.line", history)

    # -- task handling ------------------------------------------------------

    def test_creates_missing_task_when_enabled(self):
        line = make_line(task="Brand new task")
        odoo, _ = self.run_upload([line], create_tasks=True)
        tasks = odoo.records["project.task"]
        self.assertEqual(len(tasks), 2)  # pre-seeded task + the new one
        new_task = tasks[5]
        self.assertEqual(new_task["name"], "Brand new task")
        self.assertEqual(new_task["project_id"], self.PROJECT_ID)
        analytic = odoo.records["account.analytic.line"][1]
        self.assertEqual(analytic["task_id"], new_task["id"])

    def test_missing_task_raises_when_disabled(self):
        line = make_line(task="Brand new task")
        with self.assertRaises(UploadException) as ctx:
            self.run_upload([line], create_tasks=False)
        self.assertIn("Task creation is not enabled", str(ctx.exception))

    def test_missing_task_raises_when_not_str(self):
        line = make_line(task=12345)
        with self.assertRaises(UploadException) as ctx:
            self.run_upload([line])
        self.assertIn("No task found", str(ctx.exception))

    # -- project handling ---------------------------------------------------

    def test_project_inferred_from_task(self):
        line = make_line(task=self.TASK_ID)
        line.pop("project")
        odoo, _ = self.run_upload([line])
        analytic = odoo.records["account.analytic.line"][1]
        self.assertEqual(analytic["project_id"], self.PROJECT_ID)
        self.assertEqual(analytic["task_id"], self.TASK_ID)

    def test_task_project_mismatch_raises(self):
        line = make_line(project=self.SECOND_PROJECT_NAME)
        with self.assertRaises(UploadException) as ctx:
            self.run_upload([line])
        self.assertIn(
            "Task's project and specified project mismatch", str(ctx.exception)
        )

    def test_line_without_project_nor_task_raises(self):
        line = make_line(task=None)
        del line["task"]
        del line["project"]
        with self.assertRaises(UploadException) as ctx:
            self.run_upload([line])
        self.assertIn("No project nor task", str(ctx.exception))

    def test_missing_project_raises(self):
        line = make_line(project="Unknown project")
        with self.assertRaises(UploadException) as ctx:
            self.run_upload([line])
        self.assertIn('No results found in "project.project"', str(ctx.exception))

    def test_ambiguous_project_raises(self):
        self.fake_odoo.add("project.project", {"id": 99, "name": self.PROJECT_NAME})
        line = make_line(project=self.PROJECT_NAME)
        with self.assertRaises(UploadException) as ctx:
            self.run_upload([line])
        self.assertIn("More than one result", str(ctx.exception))

    # -- history / idempotency ---------------------------------------------

    def test_skips_already_uploaded_line(self):
        self.run_upload([make_line()])
        self.run_upload([make_line()])
        analytic_lines = self.fake_odoo.records["account.analytic.line"]
        self.assertEqual(len(analytic_lines), 1)
        self.assertEqual(
            self.history["_refs"], {("account.analytic.line", 1001): 1}
        )

    def test_conflicting_history_raises_by_default(self):
        self.run_upload([make_line()])
        merged = make_line(_toggl_ids={1001, 1002})
        with self.assertRaises(UploadException) as ctx:
            self.run_upload([merged])
        self.assertIn(
            'Stored records "account.analytic.line" refs mismatch', str(ctx.exception)
        )

    def test_conflicting_history_overwrites_when_forced(self):
        self.run_upload([make_line()])
        merged = make_line(_toggl_ids={1001, 1002})
        odoo, history = self.run_upload([merged], overwrite=True)
        analytic = odoo.records["account.analytic.line"]
        self.assertEqual(len(analytic), 1)  # stale record was deleted
        self.assertEqual(
            history["_refs"],
            {
                ("account.analytic.line", 1001): 2,
                ("account.analytic.line", 1002): 2,
            },
        )
        self.assertEqual(history["account.analytic.line"][2], {1001, 1002})

    def test_line_without_toggl_refs_raises(self):
        line = make_line(_toggl_ids=set())
        with self.assertRaises(UploadException) as ctx:
            self.run_upload([line])
        self.assertIn('without "_toggl_ids"', str(ctx.exception))

    def test_upload_error_reports_the_offending_line(self):
        line = make_line(project="Unknown project")
        with self.assertRaises(UploadException) as ctx:
            self.run_upload([line])
        self.assertIn("Unknown project", str(ctx.exception))

    def test_match_history_refs_requires_refs_dict(self):
        with self.assertRaises(InconsistentHistory):
            match_history_refs(FakeShelf(), "account.analytic.line", {1})

    def test_match_history_refs_missing_record_is_inconsistent(self):
        history = FakeShelf({"_refs": {("account.analytic.line", 1): 1}})
        with self.assertRaises(InconsistentHistory):
            match_history_refs(history, "account.analytic.line", {1})

    def test_match_history_refs_returns_known_refs(self):
        history = FakeShelf(
            {
                "_refs": {("account.analytic.line", 1): 10},
                "account.analytic.line": {10: {1}},
            }
        )
        self.assertEqual(
            match_history_refs(history, "account.analytic.line", {1, 2}), {1}
        )
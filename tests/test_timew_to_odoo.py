"""End-to-end tests: upload Timewarrior intervals to Odoo.

The Timewarrior CLI is fully mocked: instead of running ``timew export``, the
tests feed the same JSON payload the real command would print and let the
normal deserialization convert them into ``TimeInterval`` objects. The Odoo
side is replaced by an in-memory fake.
"""

import json
import unittest
import types
from datetime import datetime, timezone
from unittest import mock

from converters.odoo import CustomChainedConverter, OdooTask2Odoo, converter2odoo
from converters.odoo_common import extract_task
from converters.owndb import converter2owndb
from timew_to_odoo import odoo_upload as upload_module
from timew_to_odoo.processing import fetch_and_process
from timew_to_odoo.timewarrior import TimeInterval

from .fakes import FakeOdooXmlRpc, FakeShelf

FROM = datetime(2026, 8, 9, tzinfo=timezone.utc)
TO = datetime(2026, 8, 9, 23, 59, 59, tzinfo=timezone.utc)


def make_interval_row(**overrides):
    """Build one export row exactly as returned by ``timew export``."""
    row = {
        "id": 1000,
        "start": "20260809T090000Z",
        "end": "20260809T100000Z",
        "tags": ["Odoo-psbe"],
        "annotation": "[56012] Investigate mysterious bug",
    }
    row.update(overrides)
    return row


class FakeTimewCli:
    """In-memory stand-in for the ``timew export`` command."""

    def __init__(self, rows):
        self.rows = list(rows)

    def __call__(self, *args, **kwargs):
        return types.SimpleNamespace(stdout=json.dumps(self.rows))


class MockedTimewCli:
    """Context manager wiring the timewarrior code to a faked CLI output."""

    def __init__(self, rows):
        self.rows = rows
        self._patcher = mock.patch(
            "timew_to_odoo.timewarrior.subprocess.run",
            side_effect=FakeTimewCli(self.rows),
        )

    def __enter__(self):
        self._patcher.start()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self._patcher.stop()
        return False


class TimewToOdooUploadTestCase(unittest.TestCase):
    def setUp(self):
        self.fake_odoo = FakeOdooXmlRpc()
        self.fake_odoo.add("project.project", {"id": 1, "name": "Odoo-psbe"})
        self.fake_odoo.add(
            "project.task", {"id": 56012, "name": "Task 56012", "project_id": [1, "Odoo-psbe"]}
        )
        self.fake_odoo.add(
            "project.task", {"id": 56013, "name": "Task 56013", "project_id": [1, "Odoo-psbe"]}
        )
        self.history = FakeShelf()
        self.history["_refs"] = {}

        self.converter = CustomChainedConverter(f"tests.{self._testMethodName}")
        self.converter.register(1)(OdooTask2Odoo)

    def upload(self, lines):
        with (
            mock.patch.object(
                upload_module, "OdooXmlRpc", return_value=self.fake_odoo
            ),
            mock.patch("shelve.open", return_value=self.history),
        ):
            upload_module.odoo_upload(
                lines,
                url="https://odoo.example.com",
                db="testdb",
                username="admin",
                password="secret",
                history_file="history",
            )

    def fetch_and_convert(self, rows, merge=False):
        with MockedTimewCli(rows):
            intervals = fetch_and_process(since=FROM, until=TO)
            lines = self.converter.convert(intervals, merge=merge)
        return intervals, lines

    # -- tests --------------------------------------------------------------

    def test_upload_mocked_timewarrior_entries(self):
        intervals, lines = self.fetch_and_convert(
            [
                make_interval_row(
                    id=1001,
                    start="20260809T090000Z",
                    end="20260809T100000Z",
                    annotation="[56012] Fix accounting module",
                ),
                make_interval_row(
                    id=1002,
                    start="20260809T140000Z",
                    end="20260809T143000Z",
                    annotation="[56013] Sync meeting",
                ),
            ]
        )
        self.assertEqual([e.id for e in intervals], [1001, 1002])
        self.assertEqual(len(lines), 2)

        self.upload(lines)
        analytics = self.fake_odoo.records["account.analytic.line"]
        self.assertEqual(len(analytics), 2)
        self.assertEqual(
            analytics[1],
            {
                "id": 1,
                "date": "2026-08-09",
                "project_id": 1,
                "task_id": 56012,
                "name": "Fix accounting module",
                "unit_amount": 1.0,
            },
        )
        self.assertEqual(analytics[2]["name"], "Sync meeting")
        self.assertEqual(analytics[2]["task_id"], 56013)
        self.assertEqual(analytics[2]["unit_amount"], 0.5)
        self.assertEqual(
            self.history["_refs"],
            {
                ("account.analytic.line", 1001): 1,
                ("account.analytic.line", 1002): 2,
            },
        )

    def test_upload_is_idempotent_across_runs(self):
        _, lines = self.fetch_and_convert([make_interval_row()])
        self.upload(lines)
        self.upload(lines)
        analytics = self.fake_odoo.records["account.analytic.line"]
        self.assertEqual(len(analytics), 1)
        self.assertEqual(
            self.history["_refs"], {("account.analytic.line", 1000): 1}
        )

    def test_upload_merges_matching_entries(self):
        _, lines = self.fetch_and_convert(
            [
                make_interval_row(
                    id=2001,
                    start="20260809T080000Z",
                    end="20260809T083000Z",
                    annotation="[56012] Unit tests",
                ),
                make_interval_row(
                    id=2002,
                    start="20260809T100000Z",
                    end="20260809T103500Z",
                    annotation="[56012] Unit tests",
                ),
            ],
            merge=True,
        )
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["unit_amount"], 1.25)
        self.assertEqual(lines[0]["_timew_ids"], {2001, 2002})

        self.upload(lines)
        analytics = self.fake_odoo.records["account.analytic.line"]
        self.assertEqual(len(analytics), 1)
        self.assertEqual(analytics[1]["unit_amount"], 1.25)
        self.assertEqual(
            self.history["_refs"],
            {
                ("account.analytic.line", 2001): 1,
                ("account.analytic.line", 2002): 1,
            },
        )

    def test_removed_entry_leaves_history_untouched(self):
        _, lines = self.fetch_and_convert([make_interval_row()])
        self.upload(lines)
        # Second fetch no longer contains the entry -> nothing to do.
        _, lines = self.fetch_and_convert([])
        self.assertEqual(lines, [])
        self.assertEqual(
            self.history["_refs"], {("account.analytic.line", 1000): 1}
        )

    def test_fetch_filters_intervals_by_any_tag(self):
        rows = [
            make_interval_row(id=2001, tags=["Odoo-psbe", "non-billable"]),
            make_interval_row(id=2002, tags=["Odoo-psbe", "urgent"]),
            make_interval_row(id=2003, tags=["Odoo-misc"]),
        ]
        with MockedTimewCli(rows):
            included = fetch_and_process(
                since=FROM, until=TO, tags_include=["Odoo-psbe"]
            )
            self.assertEqual([e.id for e in included], [2001, 2002])
            excluded = fetch_and_process(
                since=FROM, until=TO, tags_exclude=["non-billable"]
            )
            self.assertEqual([e.id for e in excluded], [2002, 2003])


class OdooConverterTestCase(unittest.TestCase):
    """Each converter registered in ``converters/odoo.py`` maps the timewarrior
    interval described in its name to a ``TimesheetLine``; one test per
    converter."""

    def convert(self, tags, description, **row_overrides):
        rows = [
            make_interval_row(tags=tags, annotation=description, **row_overrides)
        ]
        with MockedTimewCli(rows):
            intervals = fetch_and_process(since=FROM, until=TO)
            return converter2odoo.convert(intervals)

    def assert_line(self, line, **expected):
        line_dict = dict(line)
        date = line_dict.pop("date")
        self.assertEqual(date.isoformat(), "2026-08-09")
        full = {
            "project": "Odoo-whatever",
            "task": "Odoo-whatever",
            "name": "[56012] Fix accounting module",
            "unit_amount": 1.0,
            "_timew_ids": {1000},
        }
        full.update(expected)
        self.assertEqual(line_dict, full)

    def test_onboarding(self):
        [line] = self.convert(["Odoo-onboarding"], "Welcome to Odoo")
        self.assert_line(
            line,
            project="(PS) INT. TRAINING",
            task="(PS) INT. TRAINING",
            name="[functional][onboarding] - Welcome to Odoo",
        )

    def test_training_converter(self):
        [line] = self.convert(["Odoo-training"], "Docker deep dive")
        self.assert_line(
            line,
            project=12335,
            task=3901684,
            name="[technical] Docker deep dive",
        )

    def test_owndb_converter(self):
        [line] = self.convert(["Odoo-owndb"], "Upgrade server")
        self.assert_line(
            line,
            project="(PS) INT. TRAINING",
            task="(PS) INT. TRAINING",
            name="[technical+functional] owndb: Upgrade server",
        )

    def test_misc_converter(self):
        [line] = self.convert(["Odoo-misc"], "Order a laptop")
        self.assert_line(
            line,
            project=12337,
            task=3820301,
            name="Order a laptop",
        )

    def test_improvement_converter(self):
        [line] = self.convert(
            ["Odoo-improvement"], "[56012] Fix accounting module"
        )
        self.assert_line(
            line,
            project="(BS) IMPROVEMENT",
            task=56012,
            name="Fix accounting module",
        )

    def test_coaching_converter(self):
        [line] = self.convert(["Odoo-coaching"], "1:1 with Odoo")
        self.assert_line(
            line,
            project="(BS) COACHING",
            task="(BS) HELPING COLLEAGUES",
            name="1:1 with Odoo",
        )

    def test_review_converter(self):
        [line] = self.convert(["Odoo-review"], "review pos PR")
        self.assert_line(
            line,
            project=853,
            task="Code Review/PR Review",
            name="review pos PR",
        )

    def test_meeting_converter(self):
        [line] = self.convert(["Odoo-meeting"], "sync with PS team")
        self.assert_line(
            line,
            project=12336,
            task=3820297,
            name="sync with PS team",
        )

    def test_task_converter(self):
        [line] = self.convert(["Odoo-psbe"], "[56012] Fix accounting module")
        self.assertEqual(
            line,
            {
                "date": datetime(2026, 8, 9).date(),
                "task": 56012,
                "name": "Fix accounting module",
                "unit_amount": 1.0,
                "_timew_ids": {1000},
            },
        )

    def test_task_converter_with_several_tags(self):
        [line] = self.convert(
            ["non-billable", "Odoo-psbe"], "[56012] Fix accounting module"
        )
        self.assertEqual(
            line,
            {
                "date": datetime(2026, 8, 9).date(),
                "task": 56012,
                "name": "Fix accounting module",
                "unit_amount": 1.0,
                "_timew_ids": {1000},
            },
        )

    def test_competing_odoo_tags_pick_highest_priority(self):
        [line] = self.convert(
            ["Odoo-onboarding", "Odoo-psbe"], "[56012] Fix accounting module"
        )
        # Both tags match, but OdooTask (810) has a higher priority than
        # OdooOnboarding (110), so the task converter is the one that wins.
        self.assertEqual(line["task"], 56012)

    def test_extract_task_raises_on_unmatched_annotation(self):
        entry = TimeInterval(
            id=1,
            start=datetime(2026, 8, 9, 9, 0, tzinfo=timezone.utc),
            end=datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc),
            tags=["Odoo-psbe"],
            annotation="Fix accounting module",
        )
        with self.assertRaises(ValueError):
            extract_task(entry)


class OwndbConverterTestCase(unittest.TestCase):
    """Converter dispatch on the ``timew2owndb`` chain: with several tags an
    interval may match multiple converters, and the highest-priority match
    must win."""

    def convert(self, tags, description, **row_overrides):
        rows = [
            make_interval_row(tags=tags, annotation=description, **row_overrides)
        ]
        with MockedTimewCli(rows):
            intervals = fetch_and_process(since=FROM, until=TO)
            return converter2owndb.convert(intervals)

    def test_non_billable_tag_overrides_project_tag(self):
        [line] = self.convert(
            ["Odoo-psbe", "non-billable"], "[56012] Fix accounting module"
        )
        # The "non-billable" tag must win over the "Odoo-psbe" project tag:
        # OdooNonBillable2Owndb (9999) is registered above OdooTask2Owndb
        # (810). The line is posted to the Non-billable task with the raw
        # annotation, without extracting an Odoo task id from it.
        self.assertEqual(
            line,
            {
                "date": datetime(2026, 8, 9).date(),
                "project": "Odoo 2026",
                "task": "Non-billable",
                "name": "[56012] Fix accounting module",
                "unit_amount": 1.0,
                "_timew_ids": {1000},
            },
        )

    def test_unrelated_extra_tag_keeps_task_converter(self):
        [line] = self.convert(
            ["Odoo-psbe", "urgent"], "[56012] Fix accounting module"
        )
        self.assertEqual(line["task"], "[56012]")
        self.assertEqual(line["name"], "Fix accounting module")
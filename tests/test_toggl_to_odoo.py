"""End-to-end tests: upload Toggl time entries to Odoo.

The Toggl API is fully mocked: instead of a network call, the tests feed the
same report payloads the real API would return and let the normal
deserialization convert them into ``TimeEntry`` objects. The Odoo side is
replaced by an in-memory fake.
"""

import logging
import unittest
from datetime import datetime
from unittest import mock

from toggl import utils
from toggl.api import Client, Project, Workspace

from converters.odoo import CustomChainedConverter, OdooTask2Odoo, converter2odoo
from toggl_to_odoo import odoo_upload as upload_module
from toggl_to_odoo.processing import fetch_and_process

from .fakes import FakeOdooXmlRpc, FakeShelf

# The toggl library warns every time a class attribute of its ``Config`` is
# modified, which is exactly what ``mock.patch`` does in the tests below.
logging.getLogger("toggl.utils.metas").setLevel(logging.CRITICAL)


def make_client():
    """Return an Odoo client object with a stable id."""
    client = Client(name="Odoo")
    client.id = 2
    return client


def make_project(name, client=None):
    """Create a project in the fake client, resolving ``project.client``."""
    if client is None:
        client = make_client()
    project = Project(name=name)
    project.id = 1
    project.client_id = client.id
    return project


def make_toggl_config():
    """Return a Toggl config pointing at the fake workspace, no disk access."""
    cfg = utils.Config.factory(None)
    workspace = Workspace(name="Test workspace")
    workspace.id = 1
    cfg._default_workspace = workspace
    cfg.tz = "UTC"
    return cfg


def make_entry_row(**overrides):
    """Build one report row exactly as returned by the Toggl detailed report."""
    row = {
        "id": 1000,
        "pid": 1,
        "tid": 10,
        "uid": 7,
        "wid": 1,
        "billable": False,
        "description": "[56012] Investigate mysterious bug",
        "tags": [],
        "dur": 3600000,
        "start": "2026-08-09T09:00:00+00:00",
        "end": "2026-08-09T10:00:00+00:00",
    }
    row.update(overrides)
    return row


class FakeTogglApi:
    """In-memory stand-in for the Toggl detailed report endpoint."""

    def __init__(self, rows):
        self.rows = list(rows)
        self.requests = []

    def request(
        self, url, method="get", data=None, headers=None, config=None, address=None
    ):
        if method != "get":
            raise AssertionError(f"Unexpected Toggl HTTP method: {method}")
        self.requests.append((url, address))
        return {
            "data": self.rows,
            "per_page": 100,
            "total_count": len(self.rows),
        }


class MockedTogglApi:
    """Context manager wiring the Toggl-dependent code to a faked API.

    Patches the network call performed by ``report_detailed`` as well as the
    entity lookups a converter performs while reading ``entry.project`` and
    ``entry.project.client``.
    """

    def __init__(self, api, config, project, client):
        self.api = api
        self.config = config
        self.project = project
        self.client = client
        self._patchers = []

    def __enter__(self):
        self._patchers = [
            mock.patch.object(utils.Config, "factory", return_value=self.config),
            mock.patch.object(utils, "toggl", side_effect=self.api.request),
            mock.patch.object(Project.objects, "get", return_value=self.project),
            mock.patch.object(Client.objects, "get", return_value=self.client),
        ]
        for patcher in self._patchers:
            patcher.start()
        return self

    def __exit__(self, exc_type, exc, traceback):
        for patcher in reversed(self._patchers):
            patcher.stop()
        return False


class TogglToOdooUploadTestCase(unittest.TestCase):
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

        self.config = make_toggl_config()
        self.client = make_client()
        self.project = make_project("Odoo-psbe", client=self.client)

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
        api = FakeTogglApi(rows)
        with MockedTogglApi(api, self.config, self.project, self.client):
            entries = fetch_and_process(
                since=datetime(2026, 8, 9), until=datetime(2026, 8, 9)
            )
            lines = self.converter.convert(entries, merge=merge)
        return api, entries, lines

    # -- tests --------------------------------------------------------------

    def test_upload_mocked_toggl_entries(self):
        _, entries, lines = self.fetch_and_convert(
            [
                make_entry_row(
                    id=1001,
                    dur=3600000,
                    start="2026-08-09T09:00:00+00:00",
                    end="2026-08-09T10:00:00+00:00",
                    description="[56012] Fix accounting module",
                ),
                make_entry_row(
                    id=1002,
                    dur=1800000,
                    start="2026-08-09T14:00:00+00:00",
                    end="2026-08-09T14:30:00+00:00",
                    description="[56013] Sync meeting",
                ),
            ]
        )
        self.assertEqual([entry.id for entry in entries], [1001, 1002])
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
        _, _, lines = self.fetch_and_convert([make_entry_row()])
        self.upload(lines)
        self.upload(lines)
        analytics = self.fake_odoo.records["account.analytic.line"]
        self.assertEqual(len(analytics), 1)
        self.assertEqual(
            self.history["_refs"], {("account.analytic.line", 1000): 1}
        )

    def test_upload_merges_matching_entries(self):
        _, entries, lines = self.fetch_and_convert(
            [
                make_entry_row(
                    id=2001,
                    dur=1800000,
                    start="2026-08-09T08:00:00+00:00",
                    end="2026-08-09T08:30:00+00:00",
                    description="[56012] Unit tests",
                ),
                make_entry_row(
                    id=2002,
                    dur=2160000,
                    start="2026-08-09T10:00:00+00:00",
                    end="2026-08-09T10:35:00+00:00",
                    description="[56012] Unit tests",
                ),
            ],
            merge=True,
        )
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["unit_amount"], 1.25)
        self.assertEqual(lines[0]["_toggl_ids"], {2001, 2002})

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

def test_twice_removed_entry_leaves_history_untouched(self):
        _, _, lines = self.fetch_and_convert([make_entry_row()])
        self.upload(lines)
        # Second fetch no longer contains the entry -> nothing to do.
        _, _, lines = self.fetch_and_convert([])
        self.assertEqual(lines, [])
        self.assertEqual(
            self.history["_refs"], {("account.analytic.line", 1000): 1}
        )


class OdooConverterTestCase(unittest.TestCase):
    """Each converter registered in ``converters/odoo.py`` maps the toggl entry
    described in its name to a ``TimesheetLine``; one test per converter."""

    def setUp(self):
        self.config = make_toggl_config()

    def convert(self, project_name, project_id, description, **row_overrides):
        client = make_client()
        project = make_project(project_name, client=client)
        project.id = project_id
        api = FakeTogglApi([make_entry_row(description=description, **row_overrides)])
        with MockedTogglApi(api, self.config, project, client):
            entries = fetch_and_process(
                since=datetime(2026, 8, 9), until=datetime(2026, 8, 9)
            )
            return converter2odoo.convert(entries)

    def assert_line(self, line, **expected):
        line_dict = dict(line)
        date = line_dict.pop("date")
        self.assertEqual(date.isoformat(), "2026-08-09")
        full = {
            "project": "Odoo-whatever",
            "task": "Odoo-whatever",
            "name": "[56012] Fix accounting module",
            "unit_amount": 1.0,
            "_toggl_ids": {1000},
        }
        full.update(expected)
        self.assertEqual(line_dict, full)

    def test_onboarding(self):
        [line] = self.convert("Odoo-onboarding", 1, "Welcome to Odoo")
        self.assert_line(
            line,
            project="(PS) INT. TRAINING",
            task="(PS) INT. TRAINING",
            name="[functional][onboarding] - Welcome to Odoo",
        )

    def test_training_converter(self):
        [line] = self.convert("Odoo-training", 1, "Docker deep dive")
        self.assert_line(
            line,
            project=12335,
            task=3901684,
            name="[technical] Docker deep dive",
        )

    def test_owndb_converter(self):
        [line] = self.convert("Odoo-owndb", 1, "Upgrade server")
        self.assert_line(
            line,
            project="(PS) INT. TRAINING",
            task="(PS) INT. TRAINING",
            name="[technical+functional] owndb: Upgrade server",
        )

    def test_misc_converter(self):
        [line] = self.convert("Odoo-misc", 1, "Order a laptop")
        self.assert_line(
            line,
            project=12337,
            task=3820301,
            name="Order a laptop",
        )

    def test_improvement_converter(self):
        [line] = self.convert(
            "Odoo-improvement", 1, "[56012] Fix accounting module"
        )
        self.assert_line(
            line,
            project="(BS) IMPROVEMENT",
            task=56012,
            name="Fix accounting module",
        )

    def test_coaching_converter(self):
        [line] = self.convert("Odoo-coaching", 1, "1:1 with Odoo")
        self.assert_line(
            line,
            project="(BS) COACHING",
            task="(BS) HELPING COLLEAGUES",
            name="1:1 with Odoo",
        )

    def test_review_converter(self):
        [line] = self.convert("Odoo-review", 1, "review pos PR")
        self.assert_line(
            line,
            project=853,
            task="Code Review/PR Review",
            name="review pos PR",
        )

    def test_meeting_converter(self):
        [line] = self.convert("Odoo-meeting", 1, "sync with PS team")
        self.assert_line(
            line,
            project=12336,
            task=3820297,
            name="sync with PS team",
        )

    def test_task_converter(self):
        [line] = self.convert("Odoo-psbe", 1, "[56012] Fix accounting module")
        self.assertEqual(
            line,
            {
                "date": datetime(2026, 8, 9).date(),
                "task": 56012,
                "name": "Fix accounting module",
                "unit_amount": 1.0,
                "_toggl_ids": {1000},
            },
        )
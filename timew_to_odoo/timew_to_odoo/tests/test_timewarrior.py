import json
import types
import unittest
from datetime import datetime, timezone
from unittest import mock

from timew_to_odoo.timew_to_odoo.timewarrior import (
    TimeInterval,
    deserialize_interval,
    fetch_intervals,
    isofmt,
    parse_timestamp,
)

DT0 = datetime(2026, 8, 9, 9, 0, 0, tzinfo=timezone.utc)


class TimeIntervalTestCase(unittest.TestCase):
    def test_closed_interval(self):
        interval = TimeInterval(
            id=5,
            start=DT0,
            end=datetime(2026, 8, 9, 10, 0, 0, tzinfo=timezone.utc),
            tags=("Odoo-psbe", "urgent"),
            annotation="Fix accounting module",
        )
        self.assertEqual(interval.duration, 3600.0)
        self.assertEqual(interval.tags, ["Odoo-psbe", "urgent"])
        self.assertTrue(interval.has_tag("Odoo-psbe"))
        self.assertFalse(interval.has_tag("Odoo-misc"))

    def test_open_interval_has_no_duration(self):
        interval = TimeInterval(id=1, start=DT0, end=None)
        self.assertEqual(interval.duration, 0.0)
        self.assertIn("-> ...", repr(interval))

    def test_repr(self):
        interval = TimeInterval(
            id=5,
            start=DT0,
            end=datetime(2026, 8, 9, 10, 0, 0, tzinfo=timezone.utc),
            tags=["Odoo-psbe"],
            annotation="Fix accounting module",
        )
        text = repr(interval)
        self.assertIn("#5", text)
        self.assertIn("Odoo-psbe", text)
        self.assertIn("Fix accounting module", text)


class DeserializeTestCase(unittest.TestCase):
    def test_parse_timestamp(self):
        self.assertEqual(parse_timestamp("20260809T090000Z"), DT0)

    def test_closed_interval(self):
        interval = deserialize_interval(
            {
                "id": 1,
                "start": "20260809T090000Z",
                "end": "20260809T100000Z",
                "tags": ["a"],
                "annotation": "b",
            }
        )
        self.assertEqual(interval.id, 1)
        self.assertEqual(interval.end, datetime(2026, 8, 9, 10, tzinfo=timezone.utc))
        self.assertEqual(interval.annotation, "b")

    def test_open_interval_has_no_end(self):
        interval = deserialize_interval({"id": 2, "start": "20260809T090000Z"})
        self.assertIsNone(interval.end)
        self.assertEqual(interval.annotation, "")

    def test_isofmt(self):
        self.assertEqual(isofmt(DT0), "2026-08-09T09:00:00+00:00")


class FetchIntervalsTestCase(unittest.TestCase):
    def test_skips_open_intervals(self):
        payload = json.dumps(
            [
                {
                    "id": 1,
                    "start": "20260809T090000Z",
                    "end": "20260809T100000Z",
                    "tags": ["a"],
                    "annotation": "closed",
                },
                {"id": 2, "start": "20260809T110000Z", "tags": []},
            ]
        )
        with mock.patch(
            "timew_to_odoo.timew_to_odoo.timewarrior.subprocess.run",
            return_value=types.SimpleNamespace(stdout=payload),
        ):
            intervals = fetch_intervals()
        self.assertEqual([i.id for i in intervals], [1])
        self.assertEqual(intervals[0].annotation, "closed")
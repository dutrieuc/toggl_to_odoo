import unittest
from datetime import datetime, timezone

from timew_to_odoo.timew_to_odoo.processing import snap_entries
from timew_to_odoo.timew_to_odoo.timewarrior import TimeInterval

DT = datetime(2026, 8, 9, 9, 0, 0, tzinfo=timezone.utc)


def interval(id_, start_hour, start_min, end_hour, end_min):
    start = DT.replace(hour=start_hour, minute=start_min)
    end = DT.replace(hour=end_hour, minute=end_min)
    return TimeInterval(id=id_, start=start, end=end)


class SnapEntriesTestCase(unittest.TestCase):
    def test_snaps_close_entries(self):
        earlier = interval(1, 9, 0, 9, 30)
        later = interval(2, 9, 31, 10, 0)
        snapped = snap_entries([earlier, later], 120)
        self.assertEqual(snapped, 60)
        self.assertEqual(earlier.end, DT.replace(hour=9, minute=30, second=30))
        self.assertEqual(later.start, DT.replace(hour=9, minute=30, second=30))

    def test_leaves_distant_entries_untouched(self):
        earlier = interval(1, 9, 0, 9, 30)
        later = interval(2, 9, 45, 10, 0)
        snapped = snap_entries([earlier, later], 120)
        self.assertEqual(snapped, 0)
        self.assertEqual(earlier.end, DT.replace(hour=9, minute=30))
        self.assertEqual(later.start, DT.replace(hour=9, minute=45))

    def test_snapping_preserves_refs(self):
        """Snapping shifts an interval's start, but not its upload identity.

        The ref is what the upload history keys on: were it recomputed from
        the snapped start, running with and without ``--snap`` would upload
        the same work twice.
        """
        earlier = interval(1, 9, 0, 9, 30)
        later = interval(2, 9, 31, 10, 0)
        refs = [earlier.ref, later.ref]
        snap_entries([earlier, later], 120)
        self.assertEqual([earlier.ref, later.ref], refs)

    def test_handles_overlapping_entries(self):
        earlier = interval(1, 9, 0, 9, 30)
        later_start = DT.replace(hour=9, minute=29, second=30)
        later = TimeInterval(2, start=later_start, end=DT.replace(hour=10))
        snapped = snap_entries([earlier, later], 120)
        self.assertEqual(snapped, -30)
        self.assertEqual(earlier.end, DT.replace(hour=9, minute=29, second=45))
        self.assertEqual(later.start, DT.replace(hour=9, minute=29, second=45))
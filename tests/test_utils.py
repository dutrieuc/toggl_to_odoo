import unittest
from unittest import mock

from timew_to_odoo.utils import fmt_time, import_submodules


class FmtTimeTestCase(unittest.TestCase):
    def test_seconds_only(self):
        self.assertEqual(fmt_time(0), "0s")
        self.assertEqual(fmt_time(30), "30s")
        self.assertEqual(fmt_time(59.6), "60s")

    def test_minutes(self):
        self.assertEqual(fmt_time(60), "1m 00s")
        self.assertEqual(fmt_time(90), "1m 30s")

    def test_hours(self):
        self.assertEqual(fmt_time(3600), "1h 00m 00s")
        self.assertEqual(fmt_time(3661), "1h 01m 01s")

    def test_without_letters(self):
        self.assertEqual(fmt_time(3600, with_letters=False), "1:00:00")
        self.assertEqual(fmt_time(90, with_letters=False), "1:30")

"""Tests for the ``timew_to_odoo`` command-line entry point.

The timewarrior/Cli is not involved: ``fetch_and_process`` and ``odoo_upload``
are mocked. ``main()`` normally loads the converters from ``converters/`` on
its own path; the test-suite already imports that top-level ``converters``
package, so loading it a second time under the ``timew_to_odoo.converters``
namespace would re-register the converter chains and raise a name conflict.
``import_converters`` is therefore stubbed out and the pre-registered chain is
reused.
"""

import io
import unittest
from datetime import datetime, timezone
from unittest import mock

import converters.odoo  # noqa: F401  (ensure the chain is registered)
from timew_to_odoo.timew_to_odoo.__main__ import main

from timew_to_odoo.timew_to_odoo.timewarrior import TimeInterval

INTERVAL = TimeInterval(
    id=1000,
    start=datetime(2026, 8, 9, 9, 0, 0, tzinfo=timezone.utc),
    end=datetime(2026, 8, 9, 10, 0, 0, tzinfo=timezone.utc),
    tags=["Odoo-psbe", "task:56012"],
    annotation="Fix accounting module",
)


class CliTestCase(unittest.TestCase):
    def run_main(self, argv):
        with mock.patch("timew_to_odoo.timew_to_odoo.converters.import_converters"):
            with mock.patch("sys.argv", argv):
                main()

    def test_fetch_mode(self):
        with mock.patch(
            "timew_to_odoo.timew_to_odoo.__main__.fetch_and_process", return_value=[INTERVAL]
        ) as fetch:
            self.run_main(
                [
                    "timew_to_odoo",
                    "fetch",
                    "-ds",
                    "2026-08-09",
                    "-du",
                    "2026-08-09",
                ]
            )
        fetch.assert_called_once_with(
            since=datetime(2026, 8, 9),
            until=datetime(2026, 8, 9, 23, 59, 59, 999999),
            tags_include=None,
            tags_exclude=None,
            snap_seconds=None,
        )

    def test_fetch_with_tags_filter(self):
        with mock.patch(
            "timew_to_odoo.timew_to_odoo.__main__.fetch_and_process", return_value=[]
        ) as fetch:
            self.run_main(
                [
                    "timew_to_odoo",
                    "fetch",
                    "-ti",
                    "Odoo-psbe,urgent",
                    "-te",
                    "non-billable",
                ]
            )
        self.assertEqual(fetch.call_args.kwargs["tags_include"], ["Odoo-psbe", "urgent"])
        self.assertEqual(fetch.call_args.kwargs["tags_exclude"], ["non-billable"])

    def test_convert_mode(self):
        with (
            mock.patch(
                "timew_to_odoo.timew_to_odoo.__main__.fetch_and_process", return_value=[INTERVAL]
            ),
            mock.patch("timew_to_odoo.timew_to_odoo.__main__.odoo_upload") as upload,
        ):
            self.run_main(
                [
                    "timew_to_odoo",
                    "convert",
                    "timew2odoo",
                    "-ds",
                    "2026-08-09",
                    "-du",
                    "2026-08-09",
                ]
            )
        upload.assert_not_called()

    def run_upload_main(self, argv, stdin="secret\n"):
        """Run ``main()`` in upload mode with the API key piped in on stdin."""
        with (
            mock.patch(
                "timew_to_odoo.timew_to_odoo.__main__.fetch_and_process", return_value=[INTERVAL]
            ),
            mock.patch("timew_to_odoo.timew_to_odoo.__main__.odoo_upload") as upload,
            mock.patch("sys.stdin", io.StringIO(stdin)),
        ):
            self.run_main(argv)
        return upload

    def test_upload_mode(self):
        upload = self.run_upload_main(
            [
                "timew_to_odoo",
                "upload",
                "timew2odoo",
                "https://odoo.example.com",
                "testdb",
                "-u",
                "admin",
                "history",
                "--dry-run",
            ]
        )
        upload.assert_called_once()
        kwargs = upload.call_args.kwargs
        self.assertEqual(kwargs["url"], "https://odoo.example.com")
        self.assertEqual(kwargs["db"], "testdb")
        self.assertEqual(kwargs["username"], "admin")
        self.assertEqual(kwargs["password"], "secret")
        self.assertEqual(kwargs["history_file"], "history")
        self.assertTrue(kwargs["dry_run"])

    def test_upload_without_password_on_stdin_raises(self):
        with self.assertRaises(AttributeError) as ctx:
            self.run_upload_main(
                [
                    "timew_to_odoo",
                    "upload",
                    "timew2odoo",
                    "https://odoo.example.com",
                    "testdb",
                    "-u",
                    "admin",
                    "history",
                ],
                stdin="",
            )
        self.assertIn("No password on stdin", str(ctx.exception))

    def test_upload_rejects_a_password_in_the_url(self):
        """A password in the url would be as exposed as one in an argument."""
        with self.assertRaises(AttributeError) as ctx:
            self.run_upload_main(
                [
                    "timew_to_odoo",
                    "upload",
                    "timew2odoo",
                    "https://admin:secret@odoo.example.com",
                    "testdb",
                    "history",
                ]
            )
        self.assertIn("exposed in the process table", str(ctx.exception))
import unittest
from datetime import datetime, timezone

from toggl_to_odoo.convert import ChainedConverter, SimpleConverter, get_converter
from toggl_to_odoo.timewarrior import TimeInterval

DT0 = datetime(2026, 8, 9, 9, 0, 0, tzinfo=timezone.utc)


def interval(id_, start=DT0, end=None, annotation="same"):
    if end is None:
        end = DT0.replace(hour=10, minute=00, second=0)
    return TimeInterval(id=id_, start=start, end=end, tags=["t"], annotation=annotation)


class ExtractDateTestCase(unittest.TestCase):
    def test_start_date(self):
        self.assertEqual(
            SimpleConverter().extract_date(interval(1)), DT0.date()
        )

    def test_middle_date(self):
        entry = interval(
            1,
            start=DT0.replace(hour=23),
            end=DT0.replace(day=10, hour=1),
        )
        self.assertEqual(
            SimpleConverter(datetime_middle=True).extract_date(entry),
            datetime(2026, 8, 10).date(),
        )

    def test_nightly_cutoff(self):
        entry = interval(1, start=DT0.replace(hour=5))
        self.assertEqual(
            SimpleConverter(nightly_cutoff=8).extract_date(entry),
            datetime(2026, 8, 8).date(),
        )


class ChainedConverterTestCase(unittest.TestCase):
    def test_get_converter_unknown_name(self):
        with self.assertRaises(NameError):
            get_converter("does-not-exist")

    def test_conflicting_converter_names(self):
        ChainedConverter("test-conflict")
        with self.assertRaises(NameError):
            ChainedConverter("test-conflict")

    def test_register_duplicate_priority(self):
        chain = ChainedConverter("test-duplicate-priority")

        @chain.register(1)
        class First(SimpleConverter):
            ...

        with self.assertLogs(level="WARNING"):
            @chain.register(1)
            class Second(SimpleConverter):
                ...

        self.assertEqual(len(chain.converters), 2)
        self.assertEqual(sorted(chain.converters), [0.99999, 1])

    def test_convert_unmatched(self):
        chain = ChainedConverter("test-unmatched")

        @chain.register(1)
        class Never(SimpleConverter):
            def matches(self, entry):
                return False

        self.assertEqual(chain.convert([interval(1)], must_match=False), [])
        with self.assertRaises(LookupError):
            chain.convert([interval(1)])

    def test_merge_same_name(self):
        chain = ChainedConverter("test-merge")

        @chain.register(1)
        class Default(SimpleConverter):
            ...

        lines = chain.convert(
            [
                interval(1, start=DT0, end=DT0.replace(hour=10), annotation="same"),
                interval(
                    2,
                    start=DT0.replace(hour=11),
                    end=DT0.replace(hour=12),
                    annotation="same",
                ),
            ],
            merge=True,
        )
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["unit_amount"], 2.0)
        self.assertEqual(lines[0]["_timew_ids"], {1, 2})

    def test_merge_splits_on_different_names(self):
        chain = ChainedConverter("test-merge-split")

        @chain.register(1)
        class Default(SimpleConverter):
            ...

        lines = chain.convert(
            [
                interval(1, start=DT0, end=DT0.replace(hour=10), annotation="a"),
                interval(
                    2,
                    start=DT0.replace(hour=11),
                    end=DT0.replace(hour=12),
                    annotation="b",
                ),
            ],
            merge=True,
        )
        self.assertEqual(len(lines), 2)

    def test_merge_with_custom_keys(self):
        chain = ChainedConverter("test-merge-keys")

        @chain.register(1)
        class WithTask(SimpleConverter):
            def convert(self, entry):
                line = super().convert(entry)
                line["project"] = "Odoo-psbe"
                line["task"] = entry.tags[0]
                return line

        lines = chain.convert(
            [interval(1, annotation="a"), interval(2, annotation="b")],
            merge=True,
            merge_keys=("date", "project", "task"),
        )
        # Ignoring "name" merges the two annotations into a single line.
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["unit_amount"], 2.0)

    def test_convert_single_entry_accepts_non_collection(self):
        chain = ChainedConverter("test-single")

        @chain.register(1)
        class Default(SimpleConverter):
            ...

        lines = chain.convert(interval(1))
        self.assertEqual(len(lines), 1)
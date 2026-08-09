"""Timewarrior integration.

This replaces the former Toggl detailed-report dependency: intervals are
fetched through the ``timew export`` CLI command and wrapped into
:class:`TimeInterval` objects used by the fetching/processing pipeline.

Mapping to the old Toggl model:

-  Toggl ``project`` -> a Timewarrior ``tag`` of the same name
   (e.g. ``Odoo-psbe``).
-  Toggl time entry ``name``/``description`` -> the Timewarrior
   ``annotation``.
"""

import json
import subprocess
from datetime import datetime, timezone
from typing import Any, List, MutableMapping, Optional, Sequence


DATETIME_FORMAT = "%Y%m%dT%H%M%SZ"


def isofmt(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


class TimeInterval:
    """A single interval exported by Timewarrior."""

    def __init__(
        self,
        id: int,
        start: datetime,
        end: Optional[datetime],
        tags: Sequence[str] = (),
        annotation: Optional[str] = None,
    ):
        self.id: int = id
        self.start: datetime = start
        self.end: Optional[datetime] = end
        self.tags: List[str] = list(tags)
        self.annotation: str = annotation or ""

    @property
    def duration(self) -> float:
        if self.end is None:
            return 0.0
        return (self.end - self.start).total_seconds()

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def __repr__(self) -> str:
        end: str = isofmt(self.end) if self.end else "..."
        return (
            f"<{self.__class__.__name__} #{self.id}> "
            f"({isofmt(self.start)} -> {end}) "
            f"[tags={', '.join(self.tags)}] "
            f"{self.annotation}"
        )


def parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, DATETIME_FORMAT).replace(tzinfo=timezone.utc)


def deserialize_interval(raw: MutableMapping[str, Any]) -> TimeInterval:
    """Turn one ``timew export`` row into a :class:`TimeInterval`."""
    start: datetime = parse_timestamp(raw["start"])
    end: Optional[datetime] = parse_timestamp(raw["end"]) if raw.get("end") else None
    return TimeInterval(
        id=raw["id"],
        start=start,
        end=end,
        tags=raw.get("tags", []),
        annotation=raw.get("annotation"),
    )


def fetch_intervals() -> List[TimeInterval]:
    """Run ``timew export`` and deserialize the intervals it returns.

    Open (in-progress) intervals are skipped: they have no ``end`` yet and
    would only be picked up on a later export once they are closed.
    """
    # pylint: disable=subprocess-run-check
    completed: subprocess.CompletedProcess = subprocess.run(
        ["timew", "export"], capture_output=True, text=True, check=True
    )
    payload: List[MutableMapping[str, Any]] = json.loads(completed.stdout)
    intervals: List[TimeInterval] = []
    for raw in payload:
        interval: TimeInterval = deserialize_interval(raw)
        if interval.end is not None:
            intervals.append(interval)
    return intervals
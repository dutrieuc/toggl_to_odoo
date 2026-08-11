"""Timewarrior integration."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, List, Mapping, Optional, Sequence

DATETIME_FORMAT = "%Y%m%dT%H%M%SZ"


class TimewError(RuntimeError):
    """Raised when a Timewarrior command fails."""


def parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, DATETIME_FORMAT).replace(tzinfo=timezone.utc)


def start(tags: Sequence[str], annotation: Optional[str] = None) -> Optional[timedelta]:
    """Start a Timewarrior interval with ``tags`` and optionally the annotation.

    Returns the total time of the interval stopped to make way for the new
    one, or ``None`` when no interval was running.
    """
    stopped = None
    if is_tracking():
        stopped = stop()
    _run(["timew", "start", *tags], "timew start failed")
    if annotation:
        _run(["timew", "annotate", annotation], "timew annotate failed")
    return stopped


def stop() -> timedelta:
    """Stop the running Timewarrior interval and return its total time."""
    completed = _run(["timew", "stop"], "timew stop failed")
    intervals = _closed_intervals()
    if not intervals:
        raise TimewError(completed.stdout.strip() or "timew stop recorded no interval")
    last = max(intervals, key=lambda interval: parse_timestamp(interval["end"]))
    return parse_timestamp(last["end"]) - parse_timestamp(last["start"])


def is_tracking() -> bool:
    """Return ``True`` when a Timewarrior interval is currently running."""
    completed = _run(["timew", "get", "dom.active"], "timew get failed")
    return completed.stdout.strip() == "1"


def export(filters: Sequence[str] = ()) -> List[Mapping[str, Any]]:
    """Run ``timew export`` (optionally filtered) and return the JSON payload."""
    completed = _run(["timew", "export", *filters], "timew export failed")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise TimewError(
            "timew export returned unexpected output: %r"
            % completed.stdout.strip()[:200]
        ) from None


def recent_intervals(days: int = 14) -> List[Mapping[str, Any]]:
    """Return closed and open intervals from the last ``days`` days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [
        interval
        for interval in export()
        if parse_timestamp(interval["start"]) >= cutoff
    ]


def _closed_intervals() -> List[Mapping[str, Any]]:
    """Return all completed (closed) intervals from the export."""
    return [interval for interval in export() if "end" in interval]


def _run(
    command: Sequence[str], error_message: str
) -> subprocess.CompletedProcess:
    try:
        completed = subprocess.run(
            list(command), capture_output=True, text=True
        )
    except FileNotFoundError:
        raise TimewError(f"timew could not be found on PATH ({error_message})") from None
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or error_message
        raise TimewError(message)
    return completed
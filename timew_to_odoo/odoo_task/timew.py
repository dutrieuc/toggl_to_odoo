"""Timewarrior integration."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, List, Mapping, Sequence

DATETIME_FORMAT = "%Y%m%dT%H%M%SZ"


class TimewError(RuntimeError):
    """Raised when a Timewarrior command fails."""


def parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, DATETIME_FORMAT).replace(tzinfo=timezone.utc)


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
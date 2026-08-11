import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import (
    List,
    Union,
    DefaultDict,
    Mapping,
    Tuple,
    Optional,
    Callable,
    Set,
)

from .timewarrior import TimeInterval, fetch_intervals, isofmt
from .utils import fmt_time, OptionalStrOrCollection


logger: logging.Logger = logging.getLogger(__name__)


def snap_entries(time_intervals: List[TimeInterval], snap_seconds: float):
    @lru_cache(typed=True)
    def calc_window_id(timestamp: Union[float, datetime], window_size: float) -> int:
        if isinstance(timestamp, datetime):
            timestamp = timestamp.timestamp()
        return int(timestamp / window_size)

    time_intervals_with_midtime: List[Tuple[float, TimeInterval]]
    time_intervals_with_midtime = [
        (((e.start.timestamp() + e.end.timestamp()) / 2), e)
        for e in time_intervals
    ]
    time_intervals_with_midtime.sort(key=lambda te: te[0])
    start_windows: DefaultDict[int, List[Tuple[float, TimeInterval]]] = defaultdict(list)
    stop_windows: DefaultDict[int, List[Tuple[float, TimeInterval]]] = defaultdict(list)
    midtime: float
    entry: TimeInterval
    for midtime, entry in time_intervals_with_midtime:
        start_windows[calc_window_id(entry.start, snap_seconds)].append(
            (midtime, entry)
        )
        stop_windows[calc_window_id(entry.end, snap_seconds)].append((midtime, entry))
    snapped_seconds: float = 0.0
    for midtime, entry in time_intervals_with_midtime:
        # Only considering prev stop times to next start times once
        # start_window_id: int = calc_window_id(entry.start, snap_seconds)
        stop_window_id: int = calc_window_id(entry.end, snap_seconds)

        def extract_entries(
            windows: Mapping[int, List[Tuple[float, TimeInterval]]], window_id: int
        ) -> List[Tuple[float, TimeInterval]]:
            nonlocal entry
            return [e for e in windows.get(window_id, []) if e[1] is not entry]

        nearby_window_entries: List[Tuple[float, TimeInterval]] = [
            *extract_entries(start_windows, stop_window_id - 1),
            *extract_entries(start_windows, stop_window_id),
            *extract_entries(start_windows, stop_window_id + 1),
        ]
        snap_candidates: List[Tuple[float, TimeInterval]] = sorted(
            (
                (e_delta, e)
                for e_midtime, e in nearby_window_entries
                if abs(e_delta := (e.start - entry.end).total_seconds()) <= snap_seconds
                and e_midtime >= midtime
            ),
            key=lambda t: abs(t[0]),
        )

        # Only snap the closest
        if not snap_candidates:
            continue
        delta: float
        snap_entry: TimeInterval
        delta, snap_entry = snap_candidates[0]
        if delta < 0:
            logger.warning(f"Entries times overlap by {fmt_time(abs(delta))}")
            # TODO: consider if skipping negative entries (filter them out)
        logger.debug(
            f"Snapping entries by {fmt_time(delta)}: "
            f"#{entry.id} -> {isofmt(entry.end)} "
            f"| {isofmt(snap_entry.start)} -> #{snap_entry.id}"
        )
        entry.end += timedelta(seconds=delta / 2)
        snap_entry.start -= timedelta(seconds=delta / 2)
        snapped_seconds += delta
    logger.info(f"Total snapped time: {fmt_time(snapped_seconds)}")
    return snapped_seconds


def fetch_and_process(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    tags_include: OptionalStrOrCollection = None,
    tags_exclude: OptionalStrOrCollection = None,
    snap_seconds: Optional[float] = None,
):
    time_intervals: List[TimeInterval] = fetch_intervals()

    entry_filters: List[Callable[[TimeInterval], bool]] = []

    def entries_filters(entry: TimeInterval) -> bool:
        nonlocal entry_filters
        result = True
        for filter_fn in entry_filters:
            result = result and filter_fn(entry)
            if not result:
                break
        return result

    def normalize(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is not None and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    since = normalize(since)
    until = normalize(until)

    if since:
        entry_filters.append(lambda e: e.start >= since)
    if until:
        entry_filters.append(lambda e: e.start <= until)

    if tags_include:
        if isinstance(tags_include, str):
            tags_include = [tags_include]
        tags_include_names: Set[str] = set(tags_include)
        entry_filters.append(lambda e: set(e.tags).intersection(tags_include_names))
    if tags_exclude:
        if isinstance(tags_exclude, str):
            tags_exclude = [tags_exclude]
        tags_exclude_names: Set[str] = set(tags_exclude)
        entry_filters.append(
            lambda e: not set(e.tags).intersection(tags_exclude_names)
        )

    time_intervals = [e for e in time_intervals if entries_filters(e)]

    if snap_seconds:
        snap_entries(time_intervals, snap_seconds)

    time_intervals.sort(key=lambda e: e.start)

    return time_intervals

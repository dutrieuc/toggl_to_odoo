"""Construction of Timewarrior start requests and recent-task discovery."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from . import branch as branch_mod
from . import fzf as fzf_mod
from . import git as git_mod
from . import timew as timew_mod

PROJECT_TAG = "Odoo-psbe"
SPECIAL_TASKS = {
    "misc": "Odoo-misc",
    "meeting": "Odoo-meeting",
    "coaching": "Odoo-coaching",
    "training": "Odoo-training",
}


class RecentTaskError(RuntimeError):
    """Raised when no recent Odoo task can be found for --continue."""


@dataclass
class StartRequest:
    """A Timewarrior start request with tags."""

    tags: List[str]


def from_task_id(task_id: str) -> StartRequest:
    return StartRequest([PROJECT_TAG, f"task:{task_id}"])


def from_special(kind: str) -> StartRequest:
    return StartRequest([SPECIAL_TASKS[kind]])


def from_context() -> StartRequest:
    branch = git_mod.current_branch()
    task_id, task_slug = branch_mod.parse_branch(branch)
    repo = git_mod.current_repo()
    tags = ["Odoo-psbe", f"project:{repo}", f"task:{task_id}", task_slug]
    return StartRequest(tags)


def recent_tasks(days: int = 14) -> List[StartRequest]:
    """Group intervals from the last ``days`` days by task and order by recency."""
    latest: Dict[str, Dict[str, Any]] = {}
    for interval in timew_mod.recent_intervals(days):
        tags = sorted(set(interval.get("tags") or []))
        odoo_tags = [tag for tag in tags if tag.startswith("Odoo-")]
        if not odoo_tags:
            continue
        key = next(
            (tag for tag in tags if tag.startswith("task:")), odoo_tags[0]
        )
        start = timew_mod.parse_timestamp(interval["start"])
        current = latest.get(key)
        if current is None or start > current["start"]:
            latest[key] = {
                "start": start,
                "tags": tags,
            }
    ordered = sorted(latest.values(), key=lambda group: group["start"], reverse=True)
    return [StartRequest(group["tags"]) for group in ordered]


def pick_recent_task() -> Optional[StartRequest]:
    """Offer recent Odoo tasks through fzf and return the selection.

    Returns ``None`` when the user cancels fzf.
    """
    requests = recent_tasks()
    if not requests:
        raise RecentTaskError("no recent Odoo tasks found")
    entries = [(request, _display(request)) for request in requests]
    line = fzf_mod.pick([entry[1] for entry in entries])
    if line is None:
        return None
    for request, candidate in entries:
        if candidate == line:
            return request
    return None


def _task_key(tags: List[str]) -> str:
    for tag in tags:
        if tag.startswith("task:"):
            return tag
    for tag in tags:
        if tag.startswith("Odoo-"):
            return tag
    return " ".join(tags)


def _display(request: StartRequest) -> str:
    return _task_key(request.tags)
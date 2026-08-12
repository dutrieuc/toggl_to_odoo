"""Construction of Timewarrior start requests."""

from dataclasses import dataclass
from typing import List

from . import branch as branch_mod
from . import git as git_mod

PROJECT_TAG = "Odoo-psbe"
SPECIAL_TASKS = {
    "misc": "Odoo-misc",
    "meeting": "Odoo-meeting",
    "coaching": "Odoo-coaching",
    "training": "Odoo-training",
}


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
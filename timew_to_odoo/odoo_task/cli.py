"""odoo-task CLI."""

import sys
from typing import List, Optional, Tuple

import typer

from . import task as task_mod
from .branch import BranchParseError
from .fzf import FzfError
from .git import GitError
from .task import RecentTaskError
from .timew import TimewError

app = typer.Typer(
    help="Print the Timewarrior tags for an Odoo task."
)


def _complete_first_arg(
    ctx, args: List[str], incomplete: str
) -> List[Tuple[str, str]]:
    items: List[Tuple[str, str]] = []
    for kind in task_mod.SPECIAL_TASKS:
        if kind.startswith(incomplete):
            items.append(
                (
                    kind,
                    f"Special task tagged {task_mod.SPECIAL_TASKS[kind]}",
                )
            )
    for task_id in _recent_task_ids():
        if task_id.startswith(incomplete):
            items.append((task_id, "Recent Odoo task ID"))
    return items


@app.callback(invoke_without_command=True)
def odoo_task(
    task: Optional[str] = typer.Argument(
        None,
        metavar="[TASK_ID | misc | meeting | coaching | training]",
        help="Odoo task ID or a special task type",
        autocompletion=_complete_first_arg,
    ),
    continue_task: bool = typer.Option(
        False,
        "--continue",
        "-c",
        help="Select a recent Odoo task with fzf",
    ),
) -> None:
    try:
        request = _resolve(task, continue_task)
    except (UsageError, GitError, BranchParseError, TimewError, FzfError,
            RecentTaskError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(1)
    if request is None:
        return
    print(" ".join(request.tags))


def _resolve(
    task: Optional[str],
    continue_task: bool,
) -> Optional[task_mod.StartRequest]:
    if continue_task:
        if task is not None:
            raise UsageError("too many arguments with --continue")
        return task_mod.pick_recent_task()
    if task is None:
        return task_mod.from_context()
    if task in task_mod.SPECIAL_TASKS:
        return task_mod.from_special(task)
    if task.isdigit():
        return task_mod.from_task_id(task)
    raise UsageError("expected an Odoo task ID or a special task, not %r" % task)


def _recent_task_ids() -> List[str]:
    try:
        requests = task_mod.recent_tasks()
    except (TimewError, FzfError):
        return []
    task_ids: List[str] = []
    seen = set()
    for request in requests:
        for tag in request.tags:
            if tag.startswith("task:"):
                task_id = tag.split(":", 1)[1]
                if task_id not in seen:
                    seen.add(task_id)
                    task_ids.append(task_id)
    return task_ids


class UsageError(Exception):
    """Raised on invalid CLI argument combinations."""


def main() -> None:
    app()


if __name__ == "__main__":
    main()
"""odoo-task CLI."""

import sys
from typing import List, Optional, Tuple

import typer

from . import task as task_mod
from . import timew as timew_mod
from ..timew_to_odoo.utils import fmt_time
from .branch import BranchParseError
from .fzf import FzfError
from .git import GitError
from .task import RecentTaskError
from .timew import TimewError

app = typer.Typer(
    help="Start a Timewarrior task tagged with the appropriate Odoo project and task."
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
        metavar="[TASK_ID | misc | meeting | coaching | training | ANNOTATION]",
        help=(
            "Odoo task ID, a special task type, or the annotation when"
            " inferring the task from the Git branch"
        ),
        autocompletion=_complete_first_arg,
    ),
    annotation: Optional[str] = typer.Argument(None, help="Task annotation"),
    continue_task: bool = typer.Option(
        False,
        "--continue",
        "-c",
        help="Select a recent Odoo task with fzf",
    ),
) -> None:
    try:
        request = _resolve(task, annotation, continue_task)
    except (UsageError, GitError, BranchParseError, TimewError, FzfError,
            RecentTaskError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(1)
    if request is None:
        return
    try:
        stopped = timew_mod.start(request.tags, request.annotation or None)
        if stopped is not None:
            print(
                f"Stopped interval: total {fmt_time(stopped.total_seconds())}"
            )
        task_tag = next(
            (tag for tag in request.tags if tag.startswith("task:")), ""
        )
        details = " ".join(filter(None, [task_tag, request.annotation]))
        print(f"Started interval: {details}")
    except TimewError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(1)


def _resolve(
    task: Optional[str],
    annotation: Optional[str],
    continue_task: bool,
) -> Optional[task_mod.StartRequest]:
    if continue_task:
        if task is not None and annotation is not None:
            raise UsageError("too many arguments with --continue")
        override = annotation if annotation is not None else task
        return task_mod.pick_recent_task(override or "")
    if task is None:
        return task_mod.from_branch(annotation or "")
    if task in task_mod.SPECIAL_TASKS:
        return task_mod.from_special(task, annotation or "")
    if task.isdigit():
        return task_mod.from_task_id(task, annotation or "")
    if annotation is not None:
        raise UsageError("too many arguments: expected a single annotation")
    return task_mod.from_branch(task)


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
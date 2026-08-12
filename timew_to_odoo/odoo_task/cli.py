"""odoo-task CLI."""

import sys
from typing import List, Optional, Tuple

import typer

from . import task as task_mod
from .branch import BranchParseError
from .git import GitError

app = typer.Typer(help="Print the Timewarrior tags for an Odoo task.")


def _complete_first_arg(
    ctx, args: List[str], incomplete: str
) -> List[Tuple[str, str]]:
    return [
        (kind, f"Special task tagged {task_mod.SPECIAL_TASKS[kind]}")
        for kind in task_mod.SPECIAL_TASKS
        if kind.startswith(incomplete)
    ]


@app.callback(invoke_without_command=True)
def odoo_task(
    task: Optional[str] = typer.Argument(
        None,
        metavar="[TASK_ID | misc | meeting | coaching | training]",
        help="Odoo task ID or a special task type",
        autocompletion=_complete_first_arg,
    ),
) -> None:
    try:
        if task is None:
            request = task_mod.from_context()
        elif task in task_mod.SPECIAL_TASKS:
            request = task_mod.from_special(task)
        elif task.isdigit():
            request = task_mod.from_task_id(task)
        else:
            raise UsageError(
                "expected an Odoo task ID or a special task, not %r" % task
            )
    except (UsageError, GitError, BranchParseError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(1)
    print(" ".join(request.tags))


class UsageError(Exception):
    """Raised on invalid CLI argument combinations."""


def main() -> None:
    app()


if __name__ == "__main__":
    main()
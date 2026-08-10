"""Parser for Odoo task branch names.

Branches follow ``<version>-<task-id>-<ignored>-<annotation>``. The first
group is the version, the second is the task id, the third is discarded and
everything else (the fourth group, if any) is the annotation.
"""

from typing import Tuple


class BranchParseError(ValueError):
    """Raised when no Odoo task id can be extracted from a branch name."""


def parse_branch(branch: str) -> Tuple[str, str]:
    """Return ``(task_id, annotation)`` parsed from ``branch``.

    Raises :class:`BranchParseError` when no task id can be found.
    """
    parts = branch.split("-", 3)
    if len(parts) < 2 or not parts[1].isdigit():
        raise BranchParseError(
            "could not determine Odoo task ID from Git branch %r." % branch
        )
    annotation = parts[3].strip("-") if len(parts) > 3 else ""
    return parts[1], annotation
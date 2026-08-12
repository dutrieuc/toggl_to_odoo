"""Git integration helpers."""

import os
import subprocess
from typing import Optional


class GitError(RuntimeError):
    """Raised when the current Git branch cannot be determined."""


def current_repo() -> Optional[str]:
    """Return the name of the current Git repository, or ``None`` when not
    inside a Git repository or when no ``origin`` remote is configured.
    """
    completed = subprocess.run(
        ["git", "remote", "get-url", "origin"], capture_output=True, text=True
    )
    if completed.returncode != 0:
        return None
    name = os.path.basename(completed.stdout.rstrip("/").strip())
    if name.endswith(".git"):
        name = name[:-4]
    return name or None


def current_branch() -> str:
    """Return the name of the current Git branch.

    Raises :class:`GitError` when not inside a Git repository or when the
    branch cannot be determined (e.g. a detached HEAD).
    """
    completed = subprocess.run(
        ["git", "branch", "--show-current"], capture_output=True, text=True
    )
    if completed.returncode != 0:
        raise GitError("not inside a Git repository")
    branch = completed.stdout.strip()
    if not branch:
        raise GitError("could not determine the current Git branch (detached HEAD?)")
    return branch
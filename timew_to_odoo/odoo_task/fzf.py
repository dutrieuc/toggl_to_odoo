"""fzf integration for interactive task selection."""

import subprocess
from typing import List, Optional


class FzfError(RuntimeError):
    """Raised when fzf is required but unavailable."""


def pick(options: List[str]) -> Optional[str]:
    """Run fzf over ``options`` and return the selected line.

    Returns ``None`` when the user cancels fzf.
    """
    if not options:
        return None
    try:
        completed = subprocess.run(
            ["fzf", "--height", "40%", "--reverse"],
            input="\n".join(options) + "\n",
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        raise FzfError("fzf is required for --continue but could not be found on PATH") from None
    if completed.returncode != 0:
        return None
    selected = completed.stdout.strip()
    return selected or None
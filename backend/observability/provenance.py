"""Identifies the code a run executed on.

The prompt and judge versions recorded elsewhere are content hashes: join keys,
not content. Resolving one back to the text it stands for means reading the
repository at the commit that produced it, which only works if the recorded
commit is trustworthy. A tree with uncommitted changes is therefore reported as
dirty rather than quietly named by a commit whose files are not the ones that
ran.
"""

import subprocess

UNKNOWN = "unknown"
DIRTY_SUFFIX = "-dirty"


def git_sha() -> str:
    """Return the short SHA of HEAD, or ``"unknown"`` if git cannot be read.

    A tree carrying uncommitted changes yields ``"<sha>-dirty"``: the commit no
    longer identifies the code that ran, and saying so is the point.
    """
    try:
        sha = _git("rev-parse", "--short", "HEAD")
        dirty = bool(_git("status", "--porcelain"))
    except (OSError, subprocess.CalledProcessError):
        return UNKNOWN
    return f"{sha}{DIRTY_SUFFIX}" if dirty else sha


def is_dirty() -> bool:
    """Whether the code that ran differs from any recorded commit."""
    return git_sha().endswith(DIRTY_SUFFIX)


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], text=True, stderr=subprocess.DEVNULL
    ).strip()

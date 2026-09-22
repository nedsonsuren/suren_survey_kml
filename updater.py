"""
updater.py
----------
Self-update check for machines running this app from a `git clone` of its
GitHub repo. On startup we fetch and compare local HEAD against the
upstream branch; if we're behind, the caller can offer the user a
`git pull` before continuing. That's the whole update mechanism — no
installer, background service, or separate update channel required.
"""

import os
import subprocess


def _run(args, cwd):
    try:
        return subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(args, 1, "", str(exc))


def is_git_checkout(root):
    return os.path.isdir(os.path.join(root, ".git"))


def check_for_update(root):
    """
    Returns (status, detail):
      "up_to_date"        - already on the latest commit.
      "update_available"  - behind upstream; detail = commits-behind count (str).
      "not_a_checkout"    - root isn't a git clone, so there's nothing to check.
      "offline"           - fetch or the upstream lookup failed; detail = why.
    """
    if not is_git_checkout(root):
        return "not_a_checkout", None

    fetch = _run(["git", "fetch", "--quiet"], root)
    if fetch.returncode != 0:
        return "offline", (fetch.stderr or "couldn't reach the remote").strip()

    local = _run(["git", "rev-parse", "HEAD"], root)
    upstream = _run(["git", "rev-parse", "@{u}"], root)
    if local.returncode != 0 or upstream.returncode != 0:
        return "offline", "no upstream tracking branch configured"

    if local.stdout.strip() == upstream.stdout.strip():
        return "up_to_date", None

    count = _run(["git", "rev-list", "--count", "HEAD..@{u}"], root)
    behind = count.stdout.strip() if count.returncode == 0 else "some"
    return "update_available", behind


def apply_update(root):
    """`git pull --ff-only`. Returns (ok, message)."""
    result = _run(["git", "pull", "--ff-only"], root)
    if result.returncode == 0:
        return True, result.stdout.strip()
    return False, (result.stderr or result.stdout).strip()

#!/usr/bin/env python3
"""Resolving a repo-relative path from an artifact, from any directory.

WHY ARTIFACTS RECORD REPO-RELATIVE PATHS
----------------------------------------
An artifact that names its inputs absolutely names the machine it ran on.
king-tut's `edit_decisions.json` carried seventy paths beginning
`/Users/mac/Developer/wak3up-docs/runner/` — not merely long, but naming one
WORKTREE of one clone, so the EDL could not be read in the sibling worktree
six inches away. `renders/mix_report.json` had the opposite failure and the
same cause: it recorded bare basenames, and re-mixing king-tut from its own
report died on `exit status 254` while the beds sat in the project the whole
time.

Repo-relative fixes both, and it is the right unit rather than a compromise:
every worktree resolves `projects/king-tut/assets/...` to its own copy, which
is what a reader of that artifact in that worktree means.

WHY THIS IS A FALLBACK AND NEVER A REWRITE
------------------------------------------
It returns absolute paths untouched, and relative paths untouched when they
already resolve where the caller is standing. It only joins against the repo
root for a relative path that does not otherwise exist. So it can turn a
path that was failing into one that works and cannot change a path that was
already working — which is what makes it safe to put under the render, where
a resolution change applied to every film would be the riskiest kind of fix.

A path it cannot find is returned AS GIVEN, so the error names what the
artifact asked for rather than a rooted path nobody wrote.
"""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve(path: str) -> str:
    """An artifact's path, made findable without being rewritten."""
    if not path or not isinstance(path, str) or os.path.isabs(path):
        return path
    if os.path.exists(path):
        return path
    rooted = os.path.join(ROOT, path)
    return rooted if os.path.exists(rooted) else path


def relative(path: str, root: str | None = None) -> str | None:
    """`path` as a repo-relative path, or None if it is outside the repo.

    None is a real answer and callers must handle it: a bed from
    `/Users/mac/wak3up/assets/ambient_sources` is outside this repo, and
    `os.path.relpath` would cheerfully return `../../../Users/...`, which
    resolves to nothing on another machine while looking reproducible.
    """
    root = root or ROOT
    try:
        rel = os.path.relpath(os.path.abspath(path), root)
    except ValueError:                       # different drive, Windows only
        return None
    return None if rel.startswith(os.pardir) else rel

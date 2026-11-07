#!/usr/bin/env python3
"""Is there a half-made film on disk that should be finished first?

WHY THIS EXISTS
---------------
`run_weekly.sh` started at the top every time: pick a topic, write a script,
render, publish. That was fine while a run either finished or died early.

On 2026-11-06 the run died one minute after the audio mix completed — with a
script a human had approved, a scene plan, an asset bank, edit decisions,
425 KB of render props and a 235 MB final mix on disk. Everything but the
picture. Re-firing the runner would then have PICKED A NEW TOPIC: King Tut
was now a directory under `projects/`, and the topic picker (correctly)
excludes those, so the week's work would have been abandoned in favour of
Hiroshima and the approved film would never have been made.

An unfinished film is finished before a new one is started. That is true of
every week, not just this one: a run that dies after the human gate has
spent the only scarce thing in this pipeline, which is a person's attention.

    scripts/unfinished_film.py            # the slug to resume, or nothing
    scripts/unfinished_film.py --all      # every unfinished film, newest first
    scripts/unfinished_film.py --why      # with the reason

Exit 0 when there is one, 1 when there is not, so a shell can branch on it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

#: A film is only worth resuming once the EXPENSIVE, human-gated part is
#: done. Before the script is approved there is nothing a fresh run cannot
#: redo better, and resuming a run that died during research would re-enter
#: a stage that may have failed for a reason.
RESUMABLE_FROM = "script"

#: FINISHED MEANS IN THE PUBLISHED LEDGER, and that is not a detail.
#: `scripts/publish_doc.py` writes no checkpoint, so `publish` never shows as
#: a completed stage — and a "finished" test that waited for one would call
#: every delivered film unfinished for ever, and resume a published film
#: every Friday instead of making a new one. The ledger at
#: ~/Developer/wak3up-docs/state/published.json is the single record of what
#: the channel has, shared by every worktree, and `publish_doc.py` appends
#: the project slug to it. That is the end of a film.
FINISHED = "publish"


def freshness(project: Path) -> float:
    """When this project was last worked on, newest artifact first."""
    newest = 0.0
    for path in (project / "artifacts").glob("*.json"):
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            continue
    if not newest:
        try:
            newest = project.stat().st_mtime
        except OSError:
            newest = 0.0
    return newest


def published_slugs() -> set[str]:
    """Which projects are already on the channel.

    A missing or damaged ledger RAISES rather than reading as "nothing is
    published": that is the failure mode that re-makes every film the
    channel has, and it is why `read_published` refuses to guess.
    """
    sys.path.insert(0, str(ROOT / "lib"))
    import shared_state

    return {str(film.get("project") or "") for film in shared_state.published_films()}


def unfinished() -> list[tuple[str, str, float]]:
    """(slug, why, mtime) for every resumable film, newest first."""
    import resume_state

    done_already = published_slugs()
    projects = ROOT / "projects"
    if not projects.is_dir():
        return []
    found = []
    for project in sorted(projects.iterdir()):
        if not project.is_dir() or project.name.startswith("."):
            continue
        try:
            st = resume_state.state(project.name)
        except Exception:
            # A directory that is not a project of this pipeline is not a
            # reason to refuse to run the week.
            continue
        done = set(st.get("completed") or [])
        if project.name in done_already:
            continue
        if RESUMABLE_FROM not in done or FINISHED in done:
            continue
        nxt = st.get("next") or "?"
        why = (f"{len(done)} stage(s) finished through "
               f"{sorted(done, key=lambda s: [r['stage'] for r in st['stages']].index(s))[-1]}"
               f", next is {nxt}")
        found.append((project.name, why, freshness(project)))
    return sorted(found, key=lambda row: -row[2])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--why", action="store_true")
    args = ap.parse_args()

    rows = unfinished()
    if not rows:
        return 1
    for slug, why, _ in (rows if args.all else rows[:1]):
        print(f"{slug}  — {why}" if args.why else slug)
    return 0


if __name__ == "__main__":
    sys.exit(main())

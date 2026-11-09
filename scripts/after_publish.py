#!/usr/bin/env python3
"""Everything a film still owes once it is public, run on a timer.

Two things, both of which can only happen AFTER the scheduled publish
moment and neither of which anything upstream waits for:

  * the credits comment, because YouTube disables comments on a private
    video and a scheduled film is private until it goes live; and
  * the thumbnail, which was posted at delivery for approval and is set on
    an "ok", regenerated on a "no", and set anyway at its deadline.

ONE AGENT, NOT TWO. Both are "the film is out, finish the paperwork", both
are idempotent, and a second launchd agent is a second thing to notice has
stopped firing.

    .venv/bin/python scripts/after_publish.py --all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "scripts"))


def projects() -> list[str]:
    import shared_state
    return [f["project"] for f in shared_state.published_films(allow_missing=True)
            if f.get("project")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if bool(args.project) == bool(args.all):
        raise SystemExit("name --project or --all, and only one of them")

    slugs = [args.project] if args.project else projects()
    worst = 0
    for slug in slugs:
        # Each is wrapped: one film's failure must not stop the next film's
        # credits going up.
        try:
            import post_pending_credits
            worst = max(worst, post_pending_credits.post(slug))
        except SystemExit as stop:
            worst = max(worst, int(stop.code or 0))
        except Exception as error:          # noqa: BLE001
            print(f"{slug}: credits FAILED {type(error).__name__}: {error}")
            worst = max(worst, 1)
        try:
            import thumbnail_gate
            print(f"{slug}: thumbnail — {thumbnail_gate.resolve(slug)}")
        except Exception as error:          # noqa: BLE001
            print(f"{slug}: thumbnail FAILED {type(error).__name__}: {error}")
            worst = max(worst, 1)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())

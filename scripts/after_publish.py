#!/usr/bin/env python3
"""The one thing a film still owes once it is public, run on a timer.

The thumbnail. It is posted for approval at DELIVERY, hours or days before
the film goes out, and nothing upstream waits for the answer: it is set on
an "ok", regenerated on a "no", and set anyway at its deadline. So someone
has to come back and ask, and that someone is this agent.

IT USED TO DO TWO THINGS. The second was the credits comment, which a
scheduled film could not carry because YouTube disables comments on a
private video. That comment is gone — not failed, withdrawn. The
attribution is the hosted credits page the description links to, above the
fold and live before the upload runs, which is what CC BY 4.0 3(a)(2) asks
for; the comment was a second copy of the same list and the pin it asked
for by hand was never required. Comments already on the six published films
are left exactly as they are.

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
        # Wrapped: one film's failure must not stop the next film's thumbnail
        # being resolved.
        try:
            import thumbnail_gate
            print(f"{slug}: thumbnail — {thumbnail_gate.resolve(slug)}")
        except Exception as error:          # noqa: BLE001
            print(f"{slug}: thumbnail FAILED {type(error).__name__}: {error}")
            worst = max(worst, 1)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())

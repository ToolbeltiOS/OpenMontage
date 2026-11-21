#!/usr/bin/env python3
"""Free the render intermediates of films that are already public.

WHAT A FILM COSTS TO KEEP
-------------------------
A finished film leaves about 12 GB behind in `remotion-composer/out/<project>`:

    plate.mp4    ~1.5 GB   the picture, no type, no look        KEPT
    look.mp4     ~1.8 GB   the plate with the shader over it    DELETED
    type.mov     ~9.0 GB   the type pass, ProRes 4444 + alpha   DELETED
    final.mp4    ~1.8 GB   in projects/<p>/renders/             KEPT

`type.mov` is three quarters of it on its own, because it is ProRes with an
alpha channel. The two deleted passes are both REDERIVABLE from the plate
and the props — the look pass reads the stills and the type pass reads the
same React tree — at about eighty minutes for a twenty-minute film. The
plate is the expensive one (forty-four minutes) and the one that cannot be
rebuilt without re-rendering every cut, so it stays, and so does the
delivered film.

WHY "PUBLIC", NOT "IN THE LEDGER"
---------------------------------
A film is written to the ledger when it is UPLOADED, and the weekly upload
is private with a `publishAt` the following Monday 09:00. So "in the
ledger" includes a film that nobody outside the channel can watch yet —
film #5 was in the ledger on the Sunday, with `published: 2026-11-16`, a
date in the future. Deleting its look and type would have thrown away the
eighty minutes of recovery material for the one film still able to need it.

So eligibility is the published date having PASSED. A film the audience has
seen is a film whose intermediates are only a cache.

    scripts/retain_renders.py                 # say what would go
    scripts/retain_renders.py --apply         # and do it
    scripts/retain_renders.py --oneline       # one line, for the preflight
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.shared_state import published_films  # noqa: E402

#: Rederivable from the plate and the props. Named here and nowhere else.
DELETABLE = ("look.mp4", "type.mov")

#: Kept, and listed so the reason is on the record rather than implied by
#: absence from the line above.
KEPT = {
    "plate.mp4": "forty-four minutes and every cut re-rendered to rebuild",
    "final.mp4": "the film itself, and it is not in out/ anyway",
    "artifacts/": "the whole record of how the film was made",
}


def gigabytes(n: int) -> str:
    return f"{n / 1_073_741_824:.2f} GB"


def is_public(film: dict[str, Any], today: date) -> bool:
    """Has the audience actually seen it? See the module docstring."""
    stamp = str(film.get("published") or "")
    try:
        return date.fromisoformat(stamp) < today
    except ValueError:
        # A ledger row with no usable date is left alone. Guessing here
        # would delete the recovery material of the one film most likely to
        # have been written by a half-finished publish.
        return False


def survey(today: date | None = None, root: Path = ROOT
           ) -> tuple[list[dict[str, Any]], int]:
    """Every deletable file of every already-public film, and the total."""
    today = today or date.today()
    rows: list[dict[str, Any]] = []
    total = 0
    for film in published_films(allow_missing=True):
        project = film.get("project") or ""
        if not project or not is_public(film, today):
            continue
        out = root / "remotion-composer" / "out" / project
        for name in DELETABLE:
            path = out / name
            if path.exists():
                size = path.stat().st_size
                rows.append({"project": project, "name": name,
                             "path": path, "bytes": size})
                total += size
    return rows, total


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true",
                    help="delete them; without this nothing is touched")
    ap.add_argument("--oneline", action="store_true",
                    help="one line for the preflight")
    ap.add_argument("--root", default=None)
    ap.add_argument("--today", default=None,
                    help="the date to judge 'public' against, ISO format. "
                         "Only a rehearsal passes this — but without it this "
                         "program's behaviour depends on the wall clock, and "
                         "so did its test: the fixture's scheduled film went "
                         "public on 2026-11-16 and the test asserting it was "
                         "untouched passed for five days and then deleted it.")
    args = ap.parse_args(argv)

    root = Path(args.root) if args.root else ROOT
    today = date.fromisoformat(args.today) if args.today else None
    rows, total = survey(today=today, root=root)

    if args.oneline:
        if not rows:
            print("render retention: nothing to free")
        else:
            films = sorted({r["project"] for r in rows})
            print(f"render retention: {gigabytes(total)} in "
                  f"{len(rows)} file(s) across {len(films)} public film(s) "
                  f"— scripts/retain_renders.py --apply")
        return 0

    if not rows:
        print("nothing to free: no public film has a look or type pass left")
        return 0

    for row in rows:
        action = "deleting" if args.apply else "would free"
        print(f"  {action} {gigabytes(row['bytes']):>9}  "
              f"{row['project']}/{row['name']}")
        if args.apply:
            row["path"].unlink()

    print(f"{'freed' if args.apply else 'would free'} {gigabytes(total)} "
          f"across {len(rows)} file(s)")
    if not args.apply:
        print("nothing was deleted — pass --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

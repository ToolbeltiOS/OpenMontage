#!/usr/bin/env python3
"""Does this film's subject predate 1900, and so want a historical map?

WHY THE DECISION IS NOT IN THE BRIEF
------------------------------------
The research brief has no era field -- it carries a topic, sources, data
points and angles, and nothing that says when the subject happened. Adding
one would mean asking the research stage to assert a date it was never asked
to establish, and an era invented at brief time is exactly the kind of
unsourced fact the fact gate exists to catch.

So the era is READ OFF THE FILM'S OWN DATED CONTENT: the years the timeline
events carry and the years the claim ledger's sources are dated to. Those
are already established, already cited, and already in the artifacts. If the
film's own evidence is about the eighteenth century, the film is about the
eighteenth century, and nothing has to be taken on trust.

A route drawn across a modern satellite relief is a claim about the present.
Drawn across the chart the people in the film were actually using, it is a
claim about them.

    python3 lib/map_era.py --project easter-island
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: Before this, a historical plate is the truer base.
HISTORICAL_BEFORE = 1900

#: How many dated items the decision needs before it is worth making. One
#: stray year in a 169-cut film is not an era.
MIN_DATED = 3

#: Years outside this are not years: a "year" of 3 is a figure number, and
#: one of 2500 is a quantity. Negative years are BC and are kept.
PLAUSIBLE = (-4000, 2100)


def dated_years(project: str) -> list[int]:
    """Every year the film's own content is dated to."""
    art = ROOT / "projects" / project / "artifacts"
    years: list[int] = []

    props = art / "render_props.json"
    if props.exists():
        blob = json.loads(props.read_text())
        for cut in blob.get("cuts", []):
            for ev in (cut.get("events") or []):
                y = ev.get("year")
                if isinstance(y, int) and PLAUSIBLE[0] <= y <= PLAUSIBLE[1]:
                    years.append(y)

    # Source dates: "Petrie 1883", "Routledge, 1919", "(1774)"
    script = art / "script.json"
    if script.exists():
        text = script.read_text()
        for m in re.finditer(r"\b(1[0-9]{3}|20[0-2][0-9])\b", text):
            years.append(int(m.group(1)))
    return years


def decide(project: str) -> dict[str, Any]:
    """Which map base this project should use, and the evidence for it."""
    years = dated_years(project)
    if len(years) < MIN_DATED:
        return {"base": "terrain", "reason":
                f"only {len(years)} dated items found, under {MIN_DATED} — "
                f"not enough to call an era", "years": len(years)}
    years.sort()
    median = years[len(years) // 2]
    before = sum(1 for y in years if y < HISTORICAL_BEFORE)
    share = before / len(years)
    # THE MEDIAN, NOT THE MINIMUM. A film about Easter Island cites a 1774
    # chart and a 2017 survey; the minimum would make every documentary
    # historical, because every documentary cites something old.
    historical = median < HISTORICAL_BEFORE
    return {
        "base": "historical-plate" if historical else "terrain",
        "median_year": median,
        "earliest": years[0],
        "latest": years[-1],
        "dated_items": len(years),
        "share_before_1900": round(share, 3),
        "reason": (f"the median dated item is {median}, "
                   + ("before" if historical else "not before")
                   + f" {HISTORICAL_BEFORE}"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    d = decide(args.project)
    for k, v in d.items():
        print(f"  {k:<18} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""The year a map_route cut's event happened — not the year it was written up.

WHY THE DISTINCTION IS THE WHOLE POINT
---------------------------------------
Every ledger claim carries two dates and they are rarely close. The claim
text holds the DATED EVENT -- a landing, a survey, a radiocarbon range --
and `source_name` holds the PUBLICATION, which is usually modern. A route
dated from the publication would put La Perouse's 1786 anchorage on a 2024
satellite relief, or worse, pick a nineteenth-century chart for a claim
established last year.

So the year is read from the claim text only, and `source_name` is never
looked at.

WHAT HAPPENS WHEN THERE IS NO DATE
-----------------------------------
Terrain, with the reason "undated event". That is the instructed fallback
and it is the right one: a plate chosen for a claim that does not say when
anything happened is a guess wearing a date.

The match from cut to claim is DELIBERATELY STRICT. A wrong claim gives a
wrong year, which gives a wrong plate, which is a confident false statement
about what the mapped people were looking at. A weak match falls back to
terrain, which is merely plain.

    python3 lib/event_year.py --project easter-island
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: Token overlap a claim needs with the cut's description before it counts
#: as the claim that cut illustrates.
#:
#: THREE, AND IT IS MEANT TO ALMOST NEVER FIRE. Inferring the link from a
#: one-line scene description is not reliable and the failures are not
#: harmless. Measured on easter-island's four routes at an overlap of one:
#:
#:   c140 "Orongo on the crater rim ... with the swim drawn between them"
#:        best match dates the event to 1868 — the HMS Topaze visit, not the
#:        birdman swim, which is a recurring ritual with no single year
#:   c164 "the small statue's route, off the islet and out"
#:        best match is a 1914 expedition, matched on the word "small"
#:
#: A wrong year silently chooses a wrong plate, which is a confident false
#: statement about what the mapped people were looking at. "Undated event"
#: is merely plain. So the matcher is set where it refuses nearly
#: everything, and the real link is the scene's authored `claim_id`.
MIN_MATCH = 3

#: Words that match everything and so distinguish nothing.
STOP = {
    # grammar
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "by", "for",
    "with", "from", "its", "it", "is", "was", "were", "that", "this",
    "which", "who", "had", "has", "been", "are", "but", "not", "they",
    "them", "their", "there", "then", "than", "about", "into", "out", "up",
    "down", "off", "over", "under", "across", "between", "through", "after",
    "before", "during", "where", "when", "while",
    # counting words, which match any claim with a number in it
    "one", "two", "three", "four", "five", "first", "second", "last",
    "some", "many", "more", "most", "other", "another", "each", "both",
    # words every cut description in a documentary about one place contains
    "map", "route", "drawn", "shown", "line", "island", "sea", "coast",
    "shows", "showing", "view", "frame", "shot",
}

#: A year in a claim: 3-4 digits, optionally BC/BCE, optionally a range.
YEAR = re.compile(
    r"\b(\d{3,4})\s*(?:[-–—]\s*(\d{3,4}))?\s*(BCE?|BC|AD|CE)?\b", re.I)

#: Spans that are a quantity, not a date: "3,000 tonnes", "900 metres".
NOT_A_DATE = re.compile(
    r"\b\d{3,4}\s*(?:tonnes?|tons?|metres?|meters?|m|km|kg|miles?|feet|ft|"
    r"people|statues?|moai|years?\s+old|%|per\s*cent)\b", re.I)


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", (text or "").lower())
            if w not in STOP}


def claim_year(claim: str) -> int | None:
    """The earliest plausible event year stated in a claim, or None.

    THE EARLIEST, because a claim that spans a range ("1493-1509") is
    dating one event to within that range, and the start of it is the
    conservative read. A claim mentioning several years is usually dating a
    sequence, and the route depicts its beginning.
    """
    text = NOT_A_DATE.sub(" ", claim or "")
    found: list[int] = []
    for m in YEAR.finditer(text):
        a, b, era = m.group(1), m.group(2), (m.group(3) or "").upper()
        for raw in (a, b):
            if not raw:
                continue
            y = int(raw)
            if era.startswith("B"):
                y = -y
            elif not (100 <= y <= 2100):
                continue
            found.append(y)
    return min(found) if found else None


def section_claims(brief: dict, script: dict, section_id: str) -> list[dict]:
    """The ledger claims a script section cites."""
    ids: set[str] = set()
    for sec in script.get("sections", []):
        if sec.get("id") != section_id:
            continue
        ids |= set(re.findall(r"\b([cr]\d{1,3})\b", sec.get("source_ref") or "",
                              re.I))
    ids = {i.lower() for i in ids}
    return [d for d in brief.get("data_points", [])
            if str(d.get("id", "")).lower() in ids]


def claim_by_id(brief: dict, claim_id: str) -> dict | None:
    cid = (claim_id or "").lower()
    return next((d for d in brief.get("data_points", [])
                 if str(d.get("id", "")).lower() == cid), None)


def for_cut(cut: dict, scene: dict | None, brief: dict,
            script: dict) -> dict[str, Any]:
    """The event year for one map_route cut, and how it was reached.

    THE AUTHORED LINK FIRST, AND IT IS THE ONLY RELIABLE ONE. A scene that
    names the claim it illustrates (`claim_id`) is answered from that claim
    and nothing is inferred. The matcher below is a fallback, and it is
    deliberately almost impossible to satisfy -- see MIN_MATCH.
    """
    if not scene:
        return {"event_year": None, "why": "no scene plan entry for the cut"}

    authored = scene.get("claim_id") or cut.get("claim_id")
    if authored:
        claim = claim_by_id(brief, authored)
        if not claim:
            return {"event_year": None, "claim_id": authored,
                    "why": f"the scene names claim {authored} and the ledger "
                           f"has no such claim"}
        year = claim_year(claim.get("claim", ""))
        if year is None:
            return {"event_year": None, "claim_id": authored,
                    "why": f"claim {authored}, named by the scene, states no "
                           f"date — undated event"}
        return {"event_year": year, "claim_id": authored, "authored": True,
                "why": f"the scene names claim {authored}, whose text dates "
                       f"the event to {year}"}
    section = scene.get("script_section_id")
    claims = section_claims(brief, script, section)
    if not claims:
        return {"event_year": None,
                "why": f"section {section} cites no ledger claims"}

    want = tokens(scene.get("description", ""))
    scored = []
    for c in claims:
        overlap = want & tokens(c.get("claim", ""))
        if len(overlap) >= MIN_MATCH:
            scored.append((len(overlap), c, sorted(overlap)))
    if not scored:
        return {"event_year": None,
                "why": f"no claim in section {section} matches the cut's "
                       f"description on {MIN_MATCH} or more distinctive words"}
    scored.sort(key=lambda t: -t[0])
    best_n, best, words = scored[0]
    # A TIE IS A REFUSAL. Two claims matching the description equally well
    # means the description does not identify either of them, and picking
    # the first is picking at random. Measured on easter-island, the
    # untied matches were wrong anyway: "the small statue's route" ties
    # three claims and the best scorer dates a 1914 expedition.
    if len(scored) > 1 and scored[1][0] == best_n:
        return {"event_year": None,
                "why": f"{sum(1 for t in scored if t[0] == best_n)} claims "
                       f"match the description equally well — the cut does "
                       f"not identify which it illustrates"}
    year = claim_year(best.get("claim", ""))
    if year is None:
        return {"event_year": None, "claim_id": best.get("id"),
                "why": f"claim {best.get('id')} matched on {words} but states "
                       f"no date — undated event"}
    return {"event_year": year, "claim_id": best.get("id"),
            "matched_on": words,
            "why": f"claim {best.get('id')} matched on {words}; its text "
                   f"dates the event to {year}"}


def annotate(project: str, write: bool = False) -> list[dict]:
    art = ROOT / "projects" / project / "artifacts"
    props_path = art / "render_props.json"
    props = json.loads(props_path.read_text())
    brief = json.loads((art / "research_brief.json").read_text())
    script = json.loads((art / "script.json").read_text())
    plan = json.loads((art / "scene_plan.json").read_text())
    rows = plan if isinstance(plan, list) else next(
        (v for v in plan.values() if isinstance(v, list)), [])
    by_time = sorted(rows, key=lambda r: r.get("start_seconds", 0))

    out = []
    for cut in props.get("cuts", []):
        if cut.get("type") != "map_route":
            continue
        # THE SCENE THAT CONTAINS THE CUT, not one starting at the same
        # instant. Cut times are shifted from the plan by audio lead frames
        # and transition handles -- c004 begins 0.5s after its own scene --
        # so an exact start match finds nothing for exactly the cuts that
        # were adjusted.
        mid = (cut.get("in_seconds", 0) + cut.get("out_seconds", 0)) / 2
        scene = next((r for r in by_time
                      if r.get("start_seconds", 0) <= mid
                      <= r.get("end_seconds", 0)), None)
        got = for_cut(cut, scene, brief, script)
        if got["event_year"] is not None:
            cut["event_year"] = got["event_year"]
            cut["event_year_claim"] = got.get("claim_id")
        else:
            cut.pop("event_year", None)
            cut.pop("event_year_claim", None)
            cut["event_year_reason"] = "undated event"
        out.append({"cut": cut["id"], **got})
    if write:
        props_path.write_text(json.dumps(props, indent=1) + "\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    for r in annotate(args.project, args.write):
        y = r["event_year"]
        print(f"  {r['cut']}  {y if y is not None else 'undated event'}")
        print(f"     {r['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Should this route be drawn on a historical plate, and if so which one?

TWO SEPARATE QUESTIONS, AND CONFLATING THEM WAS THE FIRST MISTAKE
------------------------------------------------------------------
An earlier version decided from the median of every date the film cites.
That is the wrong question twice over.

  1. WHETHER to use a plate is a property of THE MAPPED EVENT, not of the
     film. A film about Rapa Nui cites a 1774 chart and a 2017 survey; the
     cut showing La Perouse's 1786 anchorage wants the chart, and the cut
     showing statues moved in the fourteenth century wants terrain, and
     they are the same film. Before about 1500 there is no survey of the
     right kind to draw on, so a plate would be an anachronism dressed as
     evidence.

  2. WHETHER the plate COVERS THE ROUTE is a property of geography. The
     Tiryns plate is a site plan a few hundred metres across. A route
     across the Argolid drawn on it would run off the paper.

The cited-date median decides neither. What it is good for is STYLE: a film
whose evidence is mostly eighteenth century should pick an engraved chart
over a lithographed one when both cover the ground.

    python3 lib/map_plate.py --project easter-island
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets" / "library" / "manifest.json"

#: Before this, no survey of the right kind exists and the route goes on
#: terrain. "~1500" as instructed: the earliest plates that read as charts
#: rather than as decorated schemata.
PLATE_ERA_FROM = 1500

#: The margin the plate must have beyond the route, as a FRACTION of the
#: route's own span, with a floor in degrees.
#:
#: A flat degree margin cannot work at both scales this has to serve. At
#: 0.01 degrees -- about 1.1km -- it rejected easter-island's c140, a haul
#: route 1.7km long sitting wholly inside the Rapa Nui chart, because its
#: southern point cleared the plate's edge by 0.006 and not 0.010. The same
#: 0.01 is meaningless against a transoceanic route spanning 120 degrees.
#:
#: So the margin is proportional: a plate must hold the route plus a
#: twentieth of its span, never less than the floor.
EDGE_MARGIN_FRACTION = 0.05
EDGE_MARGIN_FLOOR_DEG = 0.002


def plates() -> list[dict[str, Any]]:
    if not MANIFEST.exists():
        return []
    blob = json.loads(MANIFEST.read_text())
    return [a for a in blob.get("assets", []) if a.get("kind") == "map-plate"]


def route_extent(route: list[list[float]]) -> tuple[float, float, float, float]:
    """(west, south, east, north) of a route, in degrees."""
    lons = [p[0] for p in route]
    lats = [p[1] for p in route]
    return (min(lons), min(lats), max(lons), max(lats))


def covers(plate: dict, route: list[list[float]]) -> bool:
    """Does the plate's box contain the route, with a margin?"""
    if not route:
        return False
    w, s, e, n = route_extent(route)
    pw, ps, pe, pn = plate["bbox"]
    span = max(e - w, n - s)
    m = max(EDGE_MARGIN_FLOOR_DEG, EDGE_MARGIN_FRACTION * span)
    return (pw <= w - m and ps <= s - m and pe >= e + m and pn >= n + m)


def style_median(project: str) -> int | None:
    """The median year the film's own evidence is dated to.

    Read off the film's dated content -- timeline years and the years in the
    script -- because the research brief has no era field and inventing one
    would assert a date nobody sourced. It chooses BETWEEN plates; it never
    decides whether to use one.
    """
    art = ROOT / "projects" / project / "artifacts"
    years: list[int] = []
    props = art / "render_props.json"
    if props.exists():
        for cut in json.loads(props.read_text()).get("cuts", []):
            for ev in (cut.get("events") or []):
                y = ev.get("year")
                if isinstance(y, int) and -4000 <= y <= 2100:
                    years.append(y)
    script = art / "script.json"
    if script.exists():
        years += [int(m.group(1)) for m in
                  re.finditer(r"\b(1[0-9]{3}|20[0-2][0-9])\b",
                              script.read_text())]
    if len(years) < 3:
        return None
    years.sort()
    return years[len(years) // 2]


def choose(route: list[list[float]], event_year: int | None,
           project: str | None = None) -> dict[str, Any]:
    """The base for this route, and why.

    `event_year` is the year of the thing the route depicts -- a voyage, an
    expedition, a haul -- and NOT the year of a source describing it.
    """
    if event_year is None:
        return {"base": "terrain",
                "reason": "the cut does not say what year its route depicts, "
                          "and a plate chosen without one is a guess"}
    if event_year < PLATE_ERA_FROM:
        return {"base": "terrain", "event_year": event_year,
                "reason": f"the mapped event is {event_year}, before "
                          f"{PLATE_ERA_FROM} — no survey of the right kind "
                          f"exists, and a plate would be an anachronism "
                          f"dressed as evidence"}
    fits = [p for p in plates() if covers(p, route)]
    if not fits:
        w, s, e, n = route_extent(route) if route else (0, 0, 0, 0)
        return {"base": "terrain", "event_year": event_year,
                "route_extent": [round(v, 3) for v in (w, s, e, n)],
                "reason": f"no plate covers the route "
                          f"({len(plates())} available); a route drawn on a "
                          f"plate that does not reach it runs off the paper"}
    # STYLE, and only now. Prefer the plate published closest to the film's
    # own centre of evidence, so an eighteenth-century film gets the
    # eighteenth-century chart when two would both fit.
    median = style_median(project) if project else None
    if median is not None:
        fits.sort(key=lambda p: abs(p.get("published", 0) - median))
        why = f"closest published date to the film's median evidence ({median})"
    else:
        fits.sort(key=lambda p: abs(p.get("published", 0) - event_year))
        why = f"closest published date to the mapped event ({event_year})"
    chosen = fits[0]
    return {
        "base": "historical-plate",
        "event_year": event_year,
        "plate": chosen["name"],
        "plate_path": chosen["path"],
        "plate_licence": chosen["licence"],
        "plate_attribution": chosen["attribution"],
        "plate_credit": f"{chosen['attribution']}, {chosen['published']}",
        "plate_source": chosen["url"],
        "candidates": [p["name"] for p in fits],
        "reason": f"the mapped event is {event_year}, the plate covers the "
                  f"route, and it was chosen by {why}",
    }


#: What `annotate` writes onto a cut. Listed so a reader can see exactly
#: what a map_route cut gains, and so nothing else is quietly added.
CUT_FIELDS = ("mapPlate", "mapPlateCredit", "map_plate_licence",
              "map_plate_attribution", "map_plate_source", "map_plate_reason")


def annotate(cuts: list[dict], project: str) -> list[dict]:
    """Record the chosen base, and its licence, on every map_route cut.

    THE LICENCE TRAVELS WITH THE PICTURE. A plate is a sourced asset like
    any photograph in the film, so the cut carries where it came from and
    under what terms -- not a pointer to a manifest somebody has to go and
    look up while the credits are being written.

    The reason is recorded too, including when the answer is terrain,
    because "this route is on terrain" is a decision and the next person
    should not have to re-derive whether it was the right one.
    """
    touched = []
    for cut in cuts:
        if cut.get("type") != "map_route" or not cut.get("route"):
            continue
        for k in CUT_FIELDS:
            cut.pop(k, None)
        d = choose(cut["route"], cut.get("event_year"), project)
        cut["map_plate_reason"] = d["reason"]
        if d["base"] == "historical-plate":
            # THE PUBLISHED PATH, NOT THE REPO PATH. The library is served
            # from the bundle at `library/...` via a symlink; writing
            # `assets/library/...` onto the cut makes staticFile look for
            # `public/assets/library/...`, which does not exist, and the
            # route renders over nothing with no error anywhere.
            cut["mapPlate"] = "library/" + str(
                Path(d["plate_path"]).relative_to("assets/library")).replace(
                    "\\", "/")
            cut["mapPlateCredit"] = d["plate_credit"]
            cut["map_plate_licence"] = d["plate_licence"]
            cut["map_plate_attribution"] = d["plate_attribution"]
            cut["map_plate_source"] = d["plate_source"]
        touched.append({"cut": cut["id"], **d})
    return touched


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--event-year", type=int, default=None)
    ap.add_argument("--write", action="store_true",
                    help="record the decision on each map_route cut in "
                         "render_props.json")
    args = ap.parse_args()

    if args.write:
        path = (ROOT / "projects" / args.project / "artifacts"
                / "render_props.json")
        blob = json.loads(path.read_text())
        rows = annotate(blob["cuts"], args.project)
        path.write_text(json.dumps(blob, indent=1) + "\n")
        for r in rows:
            print(f"  {r['cut']}  {r['base']}"
                  + (f"  {r.get('plate')}" if r.get("plate") else ""))
            print(f"     {r['reason']}")
        print(f"\n  {len(rows)} map_route cut(s) recorded")
        return 0
    props = ROOT / "projects" / args.project / "artifacts" / "render_props.json"
    blob = json.loads(props.read_text())
    n = 0
    for cut in blob.get("cuts", []):
        if cut.get("type") != "map_route" or not cut.get("route"):
            continue
        n += 1
        d = choose(cut["route"], args.event_year or cut.get("event_year"),
                   args.project)
        print(f"  {cut['id']}  {d['base']}")
        print(f"     {d['reason']}")
        if d.get("plate"):
            print(f"     {d['plate']} — {d['plate_credit']} — {d['plate_licence']}")
    if not n:
        print("  no map_route cuts with a route")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

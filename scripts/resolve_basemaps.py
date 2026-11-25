#!/usr/bin/env python3
"""Turn an authored `basemap: "terrain"` into the tile the composer needs.

WHAT WAS WRONG
--------------
Six `map_route` cuts of the Pearl Harbor film carried

    "basemap": "terrain", "basemap_drift": 1.3

and every one of them rendered on the dark fill. Three separate things were
true at once:

  * `Explainer` never passed `basemap` on, so the prop could not have drawn
    whatever its value had been (fixed 2026-11-24, same change as this);
  * `"terrain"` is a REQUEST FOR A KIND, and `MapRoute` wants a tile —
    `{src, bounds}` — because the warp has to know what ground it is
    looking at. The two were never the same type, and the string could not
    have worked;
  * 1.3 is 16x the schema's 0.08 ceiling, and live it is a map zoomed 2.3x
    and slid 52% out of frame.

So the request was never nonsense; it was unresolved. This resolves it, in
the stage that writes the edit, which is the only place a fix survives:
`render_props.json` is rebuilt from `edit_decisions.json` on every render,
so a patch applied downstream is overwritten by the next build.

WHY THE BOUNDS ARE COMPUTED AND NOT AUTHORED
--------------------------------------------
A tile whose bounds are guessed puts the route in the sea
(`scripts/build_basemap_tile.py` says so, and it is right). The bounds are
therefore derived from the projection the component will actually use —
`geoMercator().center(centroid).scale(scale).translate(w/2, h/2)` — by
inverting the four corners of the frame. The same arithmetic, in Python.
`MapRoute`'s own defaults are mirrored here, and
`tests/composer/test_basemap_wiring.py` pins them to the component so the
two cannot drift apart.

WHEN THERE IS NO RASTER
-----------------------
The 700 MB Natural Earth source is gitignored and lives in whichever
worktree holds the asset library, so a runner may not have it. A film is
NOT blocked for that: the request is dropped, the drop is reported with the
exact command that would cut the tile, and the map draws as it has drawn on
films #1-#6. A reported absence is the whole point — the old behaviour was
the same absence with nothing said about it.

    .venv/bin/python scripts/resolve_basemaps.py --project attack-on-pearl-harbor
    .venv/bin/python scripts/resolve_basemaps.py --project <slug> --dry-run
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TILES = ROOT / "remotion-composer" / "public" / "basemaps"
BUILDER = ROOT / "scripts" / "build_basemap_tile.py"

#: `MapRoute`'s own defaults, and the composition's size. Pinned to the
#: component by test_basemap_wiring.py rather than remembered.
DEFAULT_SCALE = 1400.0
FRAME_W = 1920
FRAME_H = 1080

#: Mercator cannot show the poles, and Natural Earth's raster stops short of
#: them anyway.
MAX_LAT = 84.0

#: The ceiling, read out of the TypeScript that both the schema and the
#: component import, so this file cannot hold a third copy of it.
DRIFT_CONSTANTS = ROOT / "remotion-composer" / "src" / "design" / "basemap.ts"


def _ts_number(name: str) -> float:
    """A constant out of `design/basemap.ts`, which is where they live.

    The gate enforces the ratio and this script frames maps to satisfy it;
    a second copy of the number here is a copy that drifts, which is the
    fault that let `basemap_drift` sit 16x over its limit for six films.
    """
    src = DRIFT_CONSTANTS.read_text(encoding="utf-8")
    found = re.search(rf"{name}\s*=\s*([0-9.]+)", src)
    if not found:
        raise SystemExit(
            f"{name} not found in {DRIFT_CONSTANTS} — refusing rather than "
            f"assuming a limit the gate will judge against.")
    return float(found.group(1))


#: A map never shows less than this much longitude: a route of 1 km framed
#: to itself would be a scale of millions, against a raster of 1/60 of a
#: degree per pixel. Film #6's c121 spans 0.01 degrees.
MIN_EXTENT_DEG = _ts_number("MIN_EXTENT_DEG")

#: At most this many times the route's own span. The gate judges against
#: the same two numbers; see design/basemap.ts for why they live there.
MAX_EXTENT_RATIO = _ts_number("MAX_EXTENT_RATIO")

#: Past this a Mercator map is a world map and the raster has run out.
MAX_EXTENT_DEG = 170.0

#: How much of the frame the route's own bounding box is given. The rest is
#: context: a route drawn edge to edge has nowhere to be going.
ROUTE_FILL = 0.66

#: A covering tile may be this much wider than the frame before it is worth
#: cutting a new one. Covering is not the only question: a 37-degree tile
#: reused for a 1-degree frame stretches 2,200 source pixels over the whole
#: width of the picture.
MAX_TILE_OVERSHOOT = 4.0


def max_drift() -> float:
    """The ceiling, from `design/basemap.ts`.

    Read rather than restated: the drift sat 16x over its limit for six
    films because the number existed in two places and only one of them was
    ever consulted.
    """
    return _ts_number("MAX_BASEMAP_DRIFT")



def route_span_deg(route: list[list[float]]) -> float:
    lons = [p[0] for p in route]
    lats = [p[1] for p in route]
    return max(max(lons) - min(lons), max(lats) - min(lats))


def extent_deg(scale: float, width: int = FRAME_W) -> float:
    """How much longitude the frame shows at this projection scale."""
    return math.degrees(width / scale)


def scale_for_extent(degrees_across: float, width: int = FRAME_W) -> float:
    return width / math.radians(degrees_across)


def fit_extent(route: list[list[float]]) -> tuple[tuple[float, float], float]:
    """The centre and scale a route's map should have. NEVER AUTHORED.

    An extent is not an editorial decision — it is a consequence of the
    route, and every time it was left to be authored it was left alone.
    Four of film #6's six map cuts authored no scale at all and took d3's
    default of 1400: 78.6 degrees of longitude, a third of the planet, for
    routes of 17 to 594 km. The other two films that authored one chose
    sensibly, which is exactly why nobody noticed the default.

    So the resolver computes it: the route's bounding box plus margin,
    centred on the box, held between MIN_EXTENT_DEG and MAX_EXTENT_DEG and
    inside the raster's own edges.
    """
    lons = [p[0] for p in route]
    lats = [p[1] for p in route]
    centre = ((min(lons) + max(lons)) / 2.0, (min(lats) + max(lats)) / 2.0)

    # The frame is wider than it is tall, and Mercator stretches latitude,
    # so the height is the binding constraint more often than it looks.
    want_lon = (max(lons) - min(lons)) / ROUTE_FILL
    lat_rad = math.radians(max(-MAX_LAT, min(MAX_LAT, centre[1])))
    want_lat = ((max(lats) - min(lats)) / ROUTE_FILL
                * (FRAME_W / FRAME_H) / max(0.2, math.cos(lat_rad)))
    across = max(want_lon, want_lat, MIN_EXTENT_DEG)

    # Never off the end of the raster: a frame that crosses the antimeridian
    # cannot be covered by one tile, which is the finding that started this.
    room = 2 * min(180.0 - abs(centre[0]), 180.0)
    across = min(across, MAX_EXTENT_DEG, max(MIN_EXTENT_DEG, room))
    return centre, scale_for_extent(across)


def covers(tile_bounds: list[float] | tuple[float, ...],
           need: tuple[float, float, float, float]) -> bool:
    tw, ts, te, tn = tile_bounds
    nw, ns, ne, nn = need
    return tw <= nw and ts <= ns and te >= ne and tn >= nn


def good_enough(tile_bounds: list[float] | tuple[float, ...],
                need: tuple[float, float, float, float]) -> bool:
    """Covers it, and is not so much bigger that the terrain goes soft."""
    if not covers(tile_bounds, need):
        return False
    tile_w = tile_bounds[2] - tile_bounds[0]
    need_w = max(need[2] - need[0], 1e-6)
    return tile_w <= need_w * MAX_TILE_OVERSHOOT


def existing_tiles() -> list[dict[str, Any]]:
    """Every cut tile with a sidecar, newest last."""
    out = []
    for side in sorted(TILES.glob("*.json")):
        try:
            meta = json.loads(side.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not meta.get("src") or not meta.get("bounds"):
            continue
        if not (TILES / Path(meta["src"]).name).exists():
            continue
        out.append(meta)
    return out


def raster() -> Path | None:
    """The Natural Earth source, if this checkout can reach it.

    `OM_BASEMAP_RASTER` overrides, because the raster is gitignored and
    lives in one worktree while the film is rendered from another.
    """
    env = os.environ.get("OM_BASEMAP_RASTER")
    if env:
        p = Path(env)
        return p if p.exists() else None
    p = ROOT / "assets" / "basemaps" / "NE2_HR_LC_SR" / "NE2_HR_LC_SR.tif"
    return p if p.exists() else None


def cut_command(name: str, need: tuple[float, float, float, float]) -> str:
    w, s, e, n = need
    return (f".venv/bin/python scripts/build_basemap_tile.py --name {name} "
            f"--bounds {w:.2f} {s:.2f} {e:.2f} {n:.2f}")


def build_tile(name: str, need: tuple[float, float, float, float]
               ) -> dict[str, Any] | None:
    """Cut one tile. Returns its sidecar, or None if the source is absent."""
    source = raster()
    if source is None:
        return None
    env = dict(os.environ)
    env.setdefault("OM_BASEMAP_RASTER", str(source))
    w, s, e, n = need
    ran = subprocess.run(
        [sys.executable, str(BUILDER), "--name", name,
         "--bounds", f"{w:.4f}", f"{s:.4f}", f"{e:.4f}", f"{n:.4f}"],
        capture_output=True, text=True, cwd=str(ROOT), env=env)
    side = TILES / f"{name}.json"
    if ran.returncode != 0 or not side.exists():
        print(f"  tile {name}: the builder exited {ran.returncode}")
        for line in (ran.stderr or "").strip().splitlines()[-4:]:
            print(f"    {line}")
        return None
    return json.loads(side.read_text(encoding="utf-8"))


def props_of(cut: dict[str, Any]) -> dict[str, Any]:
    """An authored cut's props live under `scene`; older cuts carry them flat.

    Returns the dict to MUTATE, which is the point: the caller writes the
    artifact back and the shape it was authored in has to survive.
    """
    scene = cut.get("scene")
    return scene if isinstance(scene, dict) else cut


def resolve(cuts: list[dict[str, Any]], *, apply_tiles: bool = True
            ) -> list[dict[str, str]]:
    """Resolve every map_route cut's basemap request. Returns one note each."""
    ceiling = max_drift()
    tiles = existing_tiles()
    notes: list[dict[str, str]] = []

    for cut in cuts:
        props = props_of(cut)
        if (props.get("type") or cut.get("type")) != "map_route":
            continue
        cid = cut.get("id") or "<no id>"
        route = props.get("route")

        drift = props.get("basemap_drift")
        # `isinstance(True, int)` is True in Python, and king-tut c065
        # carries `basemap_drift: true`. Clamping a boolean to 0.08 would
        # turn a type error into a plausible-looking number and hide it from
        # the gate, which is the one thing that can say what it is.
        if (isinstance(drift, (int, float)) and not isinstance(drift, bool)
                and drift > ceiling):
            props["basemap_drift"] = ceiling
            notes.append({"cut": cid, "what": "drift",
                          "note": f"{drift} -> {ceiling} (the schema's "
                                  f"ceiling; live it was scale {1 + drift:.2f} "
                                  f"and {drift * 40:.0f}% of the frame)"})

        # THE EXTENT IS COMPUTED, NOT READ. Whatever the cut authored (or
        # did not), the map is framed to its own route — basemap or no
        # basemap, which is why this sits above the basemap branch: film
        # #4's one map cut carries `basemap: null` and still showed 122
        # degrees of longitude for a 600 km route.
        placeable = isinstance(route, list) and len(route) >= 2
        centre, scale = ((None, None) if not placeable
                         else fit_extent(route))
        was_scale = props.get("scale")
        was_centre = props.get("center")
        if placeable:
            props["scale"] = round(scale, 1)
            props["center"] = [round(centre[0], 4), round(centre[1], 4)]
        if placeable and (was_scale != props["scale"]
                          or was_centre != props["center"]):
            before = (f"{float(was_scale):g}" if was_scale
                      else f"unset (d3's default {DEFAULT_SCALE:g})")
            notes.append({
                "cut": cid, "what": "extent",
                "note": f"scale {before} -> {props['scale']:g}: "
                        f"{extent_deg(float(was_scale or DEFAULT_SCALE)):.1f}"
                        f" -> {extent_deg(scale):.1f} degrees across, for a "
                        f"route spanning {route_span_deg(route):.2f}"})


        asked = props.get("basemap")
        if isinstance(asked, dict):
            continue                      # already a tile, nothing to do
        if asked is None:
            continue
        if not isinstance(asked, str):
            notes.append({"cut": cid, "what": "basemap",
                          "note": f"dropped {asked!r}: a basemap is a tile "
                                  f"or the word 'terrain', not a "
                                  f"{type(asked).__name__}"})
            props.pop("basemap", None)
            continue
        if asked.strip().lower() != "terrain":
            notes.append({"cut": cid, "what": "basemap",
                          "note": f"dropped {asked!r}: the only basemap kind "
                                  f"that can be cut is 'terrain'"})
            props.pop("basemap", None)
            continue
        if not isinstance(route, list) or len(route) < 2:
            notes.append({"cut": cid, "what": "basemap",
                          "note": "dropped: terrain needs a route to cover "
                                  "and this cut has none"})
            props.pop("basemap", None)
            continue

        need = mercator_bounds(centre, scale)

        # Natural Earth is ONE equirectangular raster from -180 to 180, so a
        # frame that runs off either end cannot be covered by one tile. That
        # is not a tiling problem, it is a scale problem: all six Pearl
        # Harbor map cuts author no `scale` at all and so are drawn at d3's
        # default 1400 — 78.6 degrees of longitude for a route of about 230
        # km. Every other film authors one. Said here because this is the
        # step that discovers it.
        unclamped_w = centre[0] - math.degrees((FRAME_W / 2) / scale)
        unclamped_e = centre[0] + math.degrees((FRAME_W / 2) / scale)
        if unclamped_w < -180.0 or unclamped_e > 180.0:
            props.pop("basemap", None)
            notes.append({
                "cut": cid, "what": "basemap",
                "note": "terrain asked for and NOT drawn: even framed to "
                        f"its own route this shot spans "
                        f"{unclamped_e - unclamped_w:.1f} degrees of "
                        "longitude and runs off the end of the raster, so "
                        "no single tile can cover it. The route is "
                        f"{route_km(route):.0f} km and spans "
                        f"{route_span_deg(route):.1f} degrees, which is "
                        "most of the world the hard way."})
            continue
        # The SMALLEST tile that covers the frame, and only if it is not
        # wildly bigger than the frame: a tile is a fixed number of pixels,
        # so a tile four times too wide is a quarter of the detail.
        fits = sorted((t for t in tiles if good_enough(t["bounds"], need)),
                      key=lambda t: t["bounds"][2] - t["bounds"][0])
        have = fits[0] if fits else None
        if have is None and apply_tiles:
            name = f"{cut.get('project') or 'film'}_{cid}"
            have = build_tile(name, need)
            if have:
                tiles.append(have)
        if have is None:
            props.pop("basemap", None)
            notes.append({
                "cut": cid, "what": "basemap",
                "note": "terrain asked for and NOT drawn: no tile covers "
                        f"[{need[0]:.1f} {need[1]:.1f} {need[2]:.1f} "
                        f"{need[3]:.1f}]"
                        + ("" if raster() else " and the Natural Earth raster "
                                               "is not in this checkout")
                        + f". Cut one with:\n      "
                        + cut_command(f"film_{cid}", need)})
            continue

        props["basemap"] = {"src": have["src"], "bounds": have["bounds"]}
        notes.append({"cut": cid, "what": "basemap",
                      "note": f"terrain -> {have['src']} "
                              f"{have['bounds']}"})
    return notes


def write_like(path: Path, blob: Any, original: str) -> None:
    """Write `blob` back the way `original` was written.

    Indentation and `ensure_ascii` are recovered by trying the plausible
    combinations against the text that was read and keeping whichever
    reproduces it. When none does — a hand-edited file, say — the most
    common convention in this repo is used and the diff is what it is.
    """
    for indent in (1, 2, 4):
        for ascii_only in (True, False):
            candidate = json.dumps(blob, indent=indent,
                                   ensure_ascii=ascii_only)
            if json.loads(candidate) == json.loads(original):
                probe = json.dumps(json.loads(original), indent=indent,
                                   ensure_ascii=ascii_only) + "\n"
                if probe == original:
                    path.write_text(candidate + "\n", encoding="utf-8")
                    return
    path.write_text(json.dumps(blob, indent=1, ensure_ascii=True) + "\n",
                    encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--artifacts", default=None,
                    help="override the artifacts directory (tests use this)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change and write nothing")
    ap.add_argument("--no-cut", action="store_true",
                    help="never cut a new tile; use only what is already in "
                         "public/basemaps")
    args = ap.parse_args()

    art = (Path(args.artifacts) if args.artifacts
           else ROOT / "projects" / args.project / "artifacts")
    path = art / "edit_decisions.json"
    if not path.exists():
        print(f"no edit_decisions.json at {path} — nothing to resolve")
        return 0

    raw = path.read_text(encoding="utf-8")
    ed = json.loads(raw)
    cuts = ed.get("cuts") or []
    for cut in cuts:
        cut.setdefault("project", args.project)
    notes = resolve(cuts, apply_tiles=not (args.dry_run or args.no_cut))
    for cut in cuts:
        cut.pop("project", None)

    maps = sum(1 for c in cuts
               if (props_of(c).get("type") or c.get("type")) == "map_route")
    drawn = sum(1 for n in notes if n["what"] == "basemap"
                and n["note"].startswith("terrain ->"))
    print(f"{args.project}: {maps} map_route cut(s), {len(notes)} change(s)")
    for note in notes:
        print(f"  {note['cut']} {note['what']}: {note['note']}")
    print(f"  terrain drawn on {drawn} of {maps}")

    if args.dry_run:
        print("dry run: nothing written")
        return 0
    if notes:
        # THE FILE'S OWN CONVENTIONS, not this script's. An artifact
        # rewritten with different indentation or unescaped unicode is a
        # 9,000-line diff in which the change nobody can find is the one
        # that matters.
        write_like(path, ed, raw)
        print(f"written: {path}")
    return 0


#: A map never shows less than this much longitude: a route of 1 km framed
#: to itself would be a scale of millions, against a raster of 1/60 of a
#: degree per pixel. Film #6's c121 spans 0.01 degrees.
MIN_EXTENT_DEG = _ts_number("MIN_EXTENT_DEG")

#: At most this many times the route's own span.
MAX_EXTENT_RATIO = _ts_number("MAX_EXTENT_RATIO")


def max_drift() -> float:
    """The ceiling, from `design/basemap.ts`.

    Read rather than restated: the drift sat 16x over its limit for six
    films because the number existed in two places and only one of them was
    ever consulted.
    """
    src = DRIFT_CONSTANTS.read_text(encoding="utf-8")
    found = re.search(r"MAX_BASEMAP_DRIFT\s*=\s*([0-9.]+)", src)
    if not found:
        raise SystemExit(
            f"MAX_BASEMAP_DRIFT not found in {DRIFT_CONSTANTS} — refusing "
            f"rather than assuming a ceiling. A clamp against a guessed "
            f"limit is not a clamp.")
    return float(found.group(1))


def mercator_bounds(center: tuple[float, float], scale: float,
                    width: int = FRAME_W, height: int = FRAME_H
                    ) -> tuple[float, float, float, float]:
    """[west, south, east, north] of what the shot will actually show.

    d3's geoMercator with `.center(c).scale(s).translate([w/2, h/2])`:
    x = s * (lon - lon0) in radians, y = -s * (mercY(lat) - mercY(lat0)).
    Inverting the corners gives the extent the tile has to cover; a tile
    that covers less leaves terrain in part of the frame and nothing in the
    rest.
    """
    lon0, lat0 = center
    half_w_rad = (width / 2.0) / scale
    half_h_rad = (height / 2.0) / scale

    west = lon0 - math.degrees(half_w_rad)
    east = lon0 + math.degrees(half_w_rad)

    def merc_y(lat_deg: float) -> float:
        lat = math.radians(max(-MAX_LAT, min(MAX_LAT, lat_deg)))
        return math.log(math.tan(math.pi / 4 + lat / 2))

    def inv_merc_y(y: float) -> float:
        return math.degrees(2 * math.atan(math.exp(y)) - math.pi / 2)

    y0 = merc_y(lat0)
    north = inv_merc_y(y0 + half_h_rad)
    south = inv_merc_y(y0 - half_h_rad)

    return (max(-180.0, west), max(-MAX_LAT, south),
            min(180.0, east), min(MAX_LAT, north))


def centroid(route: list[list[float]]) -> tuple[float, float]:
    """`MapRoute`'s own centre when the cut authors none: the mean."""
    return (sum(p[0] for p in route) / len(route),
            sum(p[1] for p in route) / len(route))


def route_km(route: list[list[float]]) -> float:
    """Great-circle length of the route, for saying how wrong a scale is."""
    total = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(route, route[1:]):
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dl = math.radians(lon2 - lon1)
        a = (math.sin((p2 - p1) / 2) ** 2
             + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
        total += 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a)))
    return total


def suggest_scale(route: list[list[float]], fill: float = 0.6,
                  width: int = FRAME_W) -> int:
    """A projection scale that puts the route across `fill` of the frame.

    Advisory, not applied: how big a map shot should be is an editorial
    decision and this script does not get to make it. But a cut that
    authors no scale gets d3's default 1400, which is 78 degrees of
    longitude — a third of the planet for a route of a couple of hundred
    kilometres — so the number worth having is in the report rather than in
    somebody's head.
    """
    lons = [p[0] for p in route]
    lats = [p[1] for p in route]
    span_lon = math.radians(max(1e-6, max(lons) - min(lons)))
    span_lat = math.radians(max(1e-6, max(lats) - min(lats)))
    by_lon = (width * fill) / span_lon
    by_lat = (FRAME_H * fill) / span_lat
    return int(round(min(by_lon, by_lat) / 50.0) * 50)


if __name__ == "__main__":
    raise SystemExit(main())

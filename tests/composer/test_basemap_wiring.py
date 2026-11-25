"""Terrain that was asked for and never drawn.

WHAT WAS WRONG, IN THREE PARTS
------------------------------
Six `map_route` cuts of the Pearl Harbor film (#6, published) carried

    "basemap": "terrain", "basemap_drift": 1.3

and all six rendered on the dark fill. Three independent faults, each of
which alone was enough:

1. `Explainer.tsx` built `<MapRoute .../>` without `basemap` or
   `basemap_drift`. Whatever the edit authored could not reach the
   component.
2. `"terrain"` is a request for a KIND of base; `MapRoute` takes a TILE,
   `{src, bounds}`, because the warp has to know what ground it is looking
   at. The two were never the same type.
3. 1.1 to 1.5 against a 0.08 ceiling. Harmless while the prop was dropped;
   live, `TerrainBase` reads it as `scale(1 + drift)` and
   `translateX(-drift * 40 * progress)%`, so 1.3 is a map zoomed 2.3x and
   slid 52% out of the frame.

The scene-props gate (2026-11-22) reported all 12 as failures and was
right. Fixing it by relaxing the schema would have blessed a silent drop,
so the props are wired through, the drift is clamped against one shared
constant, and `scripts/resolve_basemaps.py` turns the request into a tile
in the stage that writes the edit.

THE FOURTH THING, WHICH THESE TESTS ALSO PIN
--------------------------------------------
None of those six cuts authors a `scale`, so each was drawn at d3's default
1400 — 78.6 degrees of longitude, a third of the planet, for routes of 17
to 594 km. Every other film authors one. A frame that wide runs off the end
of a raster that stops at 180, so no single tile can cover it: the resolver
says so, with the route's length and a scale that would frame it, instead
of cutting a tile that covers three quarters of the shot.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import build_render_props as B                          # noqa: E402

spec = importlib.util.spec_from_file_location(
    "resolve_basemaps", ROOT / "scripts" / "resolve_basemaps.py")
RB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RB)

EXPLAINER = ROOT / "remotion-composer" / "src" / "Explainer.tsx"
MAP_ROUTE = ROOT / "remotion-composer" / "src" / "components" / "MapRoute.tsx"
SCHEMAS = ROOT / "remotion-composer" / "src" / "schemas" / "docComponents.ts"
CONSTANTS = ROOT / "remotion-composer" / "src" / "design" / "basemap.ts"
ROOT_TSX = ROOT / "remotion-composer" / "src" / "Root.tsx"

#: c112's real geometry: Oahu to Niihau, 229 km.
C112_ROUTE = [[-157.98, 21.47], [-159.5, 21.75], [-160.15, 21.9]]

#: The drift the six cuts actually carried.
AUTHORED_DRIFTS = {"c006": 1.3, "c043": 1.2, "c070": 1.5,
                   "c094": 1.2, "c112": 1.3, "c121": 1.1}


def cut(**over) -> dict:
    c = {"id": "c112", "type": "map_route", "route": C112_ROUTE}
    c.update(over)
    return c


@pytest.fixture()
def tiles(tmp_path, monkeypatch):
    """An empty tile directory, so a tile cut on this machine cannot make a
    test pass that would fail on a clean checkout —
    `remotion-composer/public/` is gitignored."""
    d = tmp_path / "basemaps"
    d.mkdir()
    monkeypatch.setattr(RB, "TILES", d)
    monkeypatch.delenv("OM_BASEMAP_RASTER", raising=False)
    monkeypatch.setattr(RB, "raster", lambda: None)
    return d


#: Enough pixels to clear the resolution floor for the frames these tests
#: fit. The C112 route needs 292 source px per degree at the 0.5 floor;
#: Natural Earth 10m has about 60, which is why film #6 gets no terrain
#: and why that is tested below rather than wished away here. These
#: fixtures are about WIRING — terrain becoming a tile — so they state a
#: resolution that lets the wiring be seen.
FINE_PX_PER_DEGREE = 400
NATURAL_EARTH_10M_PX_PER_DEGREE = 60


def put_tile(d: Path, name: str, bounds: list[float],
             px_per_degree: float = FINE_PX_PER_DEGREE) -> dict:
    (d / f"{name}.jpg").write_bytes(b"\xff\xd8\xff")
    pixels = [max(1, round((bounds[2] - bounds[0]) * px_per_degree)),
              max(1, round((bounds[3] - bounds[1]) * px_per_degree))]
    meta = {"name": name, "src": f"basemaps/{name}.jpg", "bounds": bounds,
            "pixels": pixels}
    (d / f"{name}.json").write_text(json.dumps(meta))
    return meta


class TestThePropsReachTheComponent:
    def test_explainer_passes_both(self):
        """THE FIRST FAULT. Anchored on the call site, not on a line."""
        src = EXPLAINER.read_text()
        call = src[src.index("<MapRoute"):]
        call = call[:call.index("/>")]
        assert "basemap={cut.basemap}" in call
        assert "basemap_drift={cut.basemap_drift}" in call

    def test_the_component_clamps_what_it_is_given(self):
        """THE THIRD FAULT, at the component: a props file edited by hand
        cannot reach TerrainBase with 1.3 even so."""
        src = MAP_ROUTE.read_text()
        assert "clampBasemapDrift" in src
        assert "drift={drift}" in src, "TerrainBase must take the clamped value"
        assert "drift={basemap_drift}" not in src

    def test_the_ceiling_exists_once(self):
        """The reason `note` survived in callout_type and the reason the
        drift sat 16x over its limit for six films: the rule existed twice
        and one copy was never consulted."""
        assert "MAX_BASEMAP_DRIFT = 0.08" in CONSTANTS.read_text()
        assert 'from "../design/basemap"' in MAP_ROUTE.read_text()
        assert 'from "../design/basemap"' in SCHEMAS.read_text()
        assert "max(MAX_BASEMAP_DRIFT)" in SCHEMAS.read_text()
        assert ".max(0.08)" not in SCHEMAS.read_text()

    def test_python_reads_the_same_ceiling(self):
        assert RB.max_drift() == 0.08

    def test_a_missing_constant_refuses_rather_than_guessing(self, tmp_path,
                                                             monkeypatch):
        stub = tmp_path / "basemap.ts"
        stub.write_text("export const SOMETHING_ELSE = 1;\n")
        monkeypatch.setattr(RB, "DRIFT_CONSTANTS", stub)
        with pytest.raises(SystemExit) as refused:
            RB.max_drift()
        assert "MAX_BASEMAP_DRIFT not found" in str(refused.value)


class TestTheDriftIsClamped:
    @pytest.mark.parametrize("cid,drift", sorted(AUTHORED_DRIFTS.items()))
    def test_every_authored_value_comes_down_to_the_ceiling(self, cid, drift,
                                                            tiles):
        """THE CONTROL: the six cuts exactly as the published film had
        them."""
        c = cut(id=cid, basemap_drift=drift)
        RB.resolve([c])
        assert c["basemap_drift"] == 0.08

    def test_a_drift_inside_the_ceiling_is_left_alone(self, tiles):
        c = cut(basemap_drift=0.02)
        RB.resolve([c])
        assert c["basemap_drift"] == 0.02

    def test_the_note_says_what_it_would_have_looked_like(self, tiles):
        notes = RB.resolve([cut(basemap_drift=1.3)])
        drift = next(n for n in notes if n["what"] == "drift")
        assert "1.3 -> 0.08" in drift["note"]
        assert "2.30" in drift["note"] and "52%" in drift["note"]

    def test_a_non_numeric_drift_is_not_touched_here(self, tiles):
        """king-tut c065 carries `basemap_drift: true`. Clamping cannot
        repair a boolean and must not pretend to: the gate refuses it by
        type, which is the right answer."""
        c = cut(basemap_drift=True)
        RB.resolve([c])
        assert c["basemap_drift"] is True


class TestTerrainBecomesATile:
    def test_a_covering_tile_is_used(self, tiles):
        """THE SECOND FAULT. `"terrain"` resolves to {src, bounds}, which is
        what MapRoute has always taken."""
        # Sized to the frame the resolver will FIT, not to the frame the
        # cut asked for: the extent is computed from the route now.
        put_tile(tiles, "kauai", [-162, 19, -156, 24])
        c = cut(basemap="terrain")
        RB.resolve([c], apply_tiles=False)
        assert c["basemap"] == {"src": "basemaps/kauai.jpg",
                                "bounds": [-162, 19, -156, 24]}

    def test_a_tile_at_the_real_rasters_resolution_is_refused(self, tiles):
        """Covering the ground is not the same as having the pixels.

        This is film #6's actual case. The tile covers the frame and is not
        too wide, so it passed every bound this check had until 2026-11-25
        — and it is a 32x upscale that draws as a pastel smear.
        """
        put_tile(tiles, "coarse", [-162, 19, -156, 24],
                 px_per_degree=NATURAL_EARTH_10M_PX_PER_DEGREE)
        c = cut(basemap="terrain")
        RB.resolve([c], apply_tiles=False)
        assert "basemap" not in c, (
            "a tile with 60 px per degree must not be stretched over a "
            "1920-wide frame")

    def test_a_tile_already_written_in_is_re_judged(self, tiles):
        """The resolver must be able to correct its own earlier output.

        Film #6's five tiles were resolved before there was a floor. If a
        dict short-circuits the branch, a re-run keeps every one of them.
        """
        meta = put_tile(tiles, "coarse", [-162, 19, -156, 24],
                        px_per_degree=NATURAL_EARTH_10M_PX_PER_DEGREE)
        c = cut(basemap={"src": meta["src"], "bounds": meta["bounds"]})
        RB.resolve([c], apply_tiles=False)
        assert "basemap" not in c, (
            "a tile resolved before the floor existed must be dropped on "
            "the re-run, not kept because it is already a dict")

    def test_a_tile_that_does_not_cover_the_frame_is_not_used(self, tiles):
        """A tile claimed to cover more than it does puts the route off the
        edge of the paper — build_basemap_tile.py's own words."""
        put_tile(tiles, "tiny", [-158.5, 21.0, -157.5, 22.0])
        c = cut(basemap="terrain")
        RB.resolve([c], apply_tiles=False)
        assert "basemap" not in c

    def test_an_absent_tile_is_dropped_and_reported_with_the_command(self,
                                                                     tiles):
        """NOT a refusal: films #1-#6 all drew these maps without terrain
        and a missing 700 MB raster must not stop a film. A reported absence
        is the whole change — the old behaviour was the same absence with
        nothing said."""
        c = cut(basemap="terrain")
        notes = RB.resolve([c], apply_tiles=False)
        assert "basemap" not in c
        note = next(n for n in notes if n["what"] == "basemap")
        assert "NOT drawn" in note["note"]
        assert "build_basemap_tile.py --name" in note["note"]

    def test_a_tile_object_that_fits_is_left_alone(self, tiles):
        """A dict used to be a free pass, and should not be.

        This case was written with noah's Bosporus tile on the C112 Hawaii
        route and asserted it survived untouched — which it did, because
        the branch returned on `isinstance(dict)` before looking at
        anything. A tile on the wrong side of the planet does not cover
        this frame, and a tile that does not cover the frame puts the route
        off the edge of the paper. The rule is the same for a dict as for
        the word: it has to cover the frame and have the pixels.
        """
        meta = put_tile(tiles, "fits", [-162, 19, -156, 24])
        already = {"src": meta["src"], "bounds": meta["bounds"]}
        c = cut(basemap=dict(already))
        RB.resolve([c], apply_tiles=False)
        assert c["basemap"] == already

    def test_a_tile_object_for_the_wrong_place_is_dropped(self, tiles):
        """noah's Bosporus tile, on the Hawaii route, as it used to pass."""
        put_tile(tiles, "noah_bosporus", [18.0, 32.0, 44.0, 50.0])
        c = cut(basemap={"src": "basemaps/noah_bosporus.jpg",
                         "bounds": [18.0, 32.0, 44.0, 50.0]})
        RB.resolve([c], apply_tiles=False)
        assert "basemap" not in c, (
            "a tile that does not cover the frame cannot be kept just "
            "because somebody already wrote it in")

    def test_an_unknown_kind_is_dropped(self, tiles):
        c = cut(basemap="satellite")
        notes = RB.resolve([c], apply_tiles=False)
        assert "basemap" not in c
        note = next(n for n in notes if n["what"] == "basemap")
        assert "only basemap kind" in note["note"]

    def test_terrain_without_a_route_is_dropped(self, tiles):
        c = {"id": "c900", "type": "map_route", "basemap": "terrain"}
        notes = RB.resolve([c], apply_tiles=False)
        assert "basemap" not in c, (
            "a terrain request with no route cannot be framed OR covered")
        assert notes == [] or all(n["what"] != "extent" for n in notes)

    def test_props_under_scene_are_resolved_in_place(self, tiles):
        """An authored cut's props live under `scene`
        (docs/STAGE_CONTRACT.md). Resolving the flattened copy would write
        the fix into a file nobody reads."""
        put_tile(tiles, "kauai", [-162, 19, -156, 24])
        c = {"id": "c112", "scene": {"type": "map_route", "route": C112_ROUTE,
                                     "basemap": "terrain",
                                     "basemap_drift": 1.3}}
        RB.resolve([c])
        assert c["scene"]["basemap"]["src"] == "basemaps/kauai.jpg"
        assert c["scene"]["basemap_drift"] == 0.08
        assert "basemap" not in c


class TestTheExtentIsComputedAndNeverAuthored:
    """A map's extent is a consequence of its route, not a taste decision.

    Four of film #6's six map cuts authored no `scale` at all, so each took
    d3's default of 1400 — 78.6 degrees of longitude, a third of the
    planet, for routes of 17 to 594 km. c121's route spans 0.01 degrees and
    was drawn across 10,477 times its own width. The two films that DID
    author a scale chose sensibly, which is exactly why the default went
    unnoticed for six films.

    So the resolver computes the centre and the scale from the route's own
    bounding box plus margin, and `docComponents.ts` gates anything that
    did not come through it at MAX_EXTENT_RATIO times the route's span.
    """

    def test_a_cut_that_authored_nothing_gets_a_frame(self, tiles):
        c = cut()
        RB.resolve([c], apply_tiles=False)
        assert c["scale"] > 1400
        assert c["center"]

    def test_the_frame_is_within_the_gate_s_ratio(self, tiles):
        c = cut()
        RB.resolve([c], apply_tiles=False)
        span = RB.route_span_deg(C112_ROUTE)
        assert (RB.extent_deg(c["scale"])
                <= max(span * RB.MAX_EXTENT_RATIO, RB.MIN_EXTENT_DEG))

    def test_the_route_fills_a_useful_share_of_it(self, tiles):
        """Framed to itself, not lost in it: 3.3 degrees for a route
        spanning 2.17, where d3's default gave 78.6."""
        c = cut()
        RB.resolve([c], apply_tiles=False)
        shows = RB.extent_deg(c["scale"])
        assert RB.route_span_deg(C112_ROUTE) / shows > 0.4

    def test_an_authored_scale_is_replaced_and_the_change_is_reported(self,
                                                                      tiles):
        c = cut(scale=1400)
        notes = RB.resolve([c], apply_tiles=False)
        note = next(n for n in notes if n["what"] == "extent")
        assert "78.6" in note["note"] and "degrees across" in note["note"]
        assert c["scale"] != 1400

    def test_a_route_of_almost_no_width_still_gets_a_readable_map(self,
                                                                  tiles):
        """c121 spans 0.01 degrees. Framed to itself that is a scale of
        millions against a raster of 1/60 of a degree per pixel, so the
        extent has a floor."""
        c = cut(route=[[-157.98, 21.47], [-157.99, 21.47]])
        RB.resolve([c], apply_tiles=False)
        assert RB.extent_deg(c["scale"]) >= RB.MIN_EXTENT_DEG - 1e-6

    def test_the_fit_keeps_the_frame_on_the_raster(self, tiles):
        """Hawaii at d3's default reaches past 180, where the raster ends
        and no single tile can cover the frame. Framed to its route it does
        not."""
        c = cut()
        RB.resolve([c], apply_tiles=False)
        half = RB.extent_deg(c["scale"]) / 2
        assert c["center"][0] - half >= -180.0
        assert c["center"][0] + half <= 180.0

    def test_the_limits_are_read_from_the_gate_s_own_file(self):
        src = (ROOT / "remotion-composer" / "src" / "design"
               / "basemap.ts").read_text()
        assert f"MAX_EXTENT_RATIO = {RB.MAX_EXTENT_RATIO:g}" in src
        assert f"MIN_EXTENT_DEG = {RB.MIN_EXTENT_DEG:g}" in src


class TestTheGateRefusesAMapThatIsNotOfItsRoute:
    def test_film_6_as_published_is_refused(self):
        """THE CONTROL: 78.6 degrees for a 2.17-degree route."""
        failures = B.scene_prop_report({"cuts": [cut()], "overlays": []})[
            "failures"]
        assert any(f["field"] == "scale" for f in failures), failures

    def test_a_fitted_frame_passes(self, tiles):
        c = cut()
        RB.resolve([c], apply_tiles=False)
        assert B.scene_prop_report({"cuts": [c], "overlays": []})[
            "failures"] == []

    def test_the_message_names_both_numbers(self):
        failures = B.scene_prop_report({"cuts": [cut()], "overlays": []})[
            "failures"]
        rule = next(f["rule"] for f in failures if f["field"] == "scale")
        assert "78.6 degrees" in rule and "2.17" in rule
        assert "resolve_basemaps.py" in rule

    def test_a_close_shot_of_one_site_is_not_the_defect(self):
        """Film #2 draws a 2 km route across 0.6 degrees — 36 times its
        span, and entirely right. The ratio is taken against a floor."""
        tiny = cut(route=[[-109.44, -27.19], [-109.42, -27.19]],
                   scale=180000)
        assert B.scene_prop_report({"cuts": [tiny], "overlays": []})[
            "failures"] == []


class TestTheProjectionArithmeticMatchesTheComponent:
    def test_the_defaults_are_the_components_defaults(self):
        """Mirrored constants, pinned to their source. A resolver that
        computes bounds for a different frame than the one that gets
        rendered cuts the wrong tile."""
        assert "scale = 1400," in MAP_ROUTE.read_text()
        assert RB.DEFAULT_SCALE == 1400.0
        root = ROOT_TSX.read_text()
        assert f"width={{{RB.FRAME_W}}}" in root
        assert f"height={{{RB.FRAME_H}}}" in root

    def test_the_half_width_is_the_mercator_one(self):
        """x = scale * (lon - lon0) in radians, so half the frame is
        960/scale radians and nothing else."""
        west, _s, east, _n = RB.mercator_bounds((0.0, 0.0), 1400.0)
        assert round(east - west, 3) == round(
            2 * math.degrees(960 / 1400.0), 3)

    def test_latitude_is_inverted_through_mercator_not_linearly(self):
        """The y axis is log-tan; treating it as linear puts the tile's top
        edge in the wrong place, and the route in the sea."""
        _w, south, _e, north = RB.mercator_bounds((0.0, 45.0), 3000.0)
        assert north - 45.0 != pytest.approx(45.0 - south, abs=1e-6)
        assert 45.0 < north < 56.0 and 34.0 < south < 45.0

    def test_it_never_leaves_the_raster(self):
        for lon in (-179.0, 0.0, 179.0):
            w, s, e, n = RB.mercator_bounds((lon, 0.0), 700.0)
            assert -180.0 <= w and e <= 180.0
            assert -RB.MAX_LAT <= s and n <= RB.MAX_LAT


class TestTheGateAgrees:
    def test_the_twelve_failures_clear(self, tiles):
        """END TO END, through the composer's own zod schemas: the six cuts
        as published fail on both fields, and the same six resolved pass."""
        put_tile(tiles, "pacific", [-180, -10, -120, 50])
        published = [cut(id=cid, basemap="terrain", basemap_drift=d,
                         draw_seconds=3.0, draw_at=1.2)
                     for cid, d in sorted(AUTHORED_DRIFTS.items())]
        failures = B.scene_prop_report({"cuts": published,
                                        "overlays": []})["failures"]
        assert len(failures) == 12
        assert {f["field"] for f in failures} == {"basemap", "basemap_drift"}

        resolved = [cut(id=cid, basemap="terrain", basemap_drift=d,
                        scale=3000, draw_seconds=3.0, draw_at=1.2)
                    for cid, d in sorted(AUTHORED_DRIFTS.items())]
        RB.resolve(resolved, apply_tiles=False)
        after = B.scene_prop_report({"cuts": resolved,
                                     "overlays": []})["failures"]
        assert after == [], after


class TestAStringCannotReachTheWarp:
    """Wiring a prop through makes its bad values live for the first time.

    Until 2026-11-24 `Explainer` dropped `basemap`, so the string "terrain"
    that six delivered cuts carry was harmless. Passed through, a non-empty
    string is TRUTHY: `TerrainBase` would destructure `"terrain".bounds`
    and the render would die on the frame the cut starts — the exact shape
    of the two renders lost in November, reintroduced by the fix for them.

    `render_film.py` reads `render_props.json` as it finds it and does not
    rebuild, so the props gate cannot be the only defence: a film whose
    props were written before the resolver existed is still renderable
    input. The component takes a tile or nothing.
    """

    def test_the_component_checks_the_shape_before_it_warps(self):
        src = MAP_ROUTE.read_text()
        guard = src[src.index("const tile ="):src.index("? (basemap as")]
        assert 'typeof basemap === "object"' in guard
        assert "Array.isArray" in guard
        assert "length === 4" in guard

    def test_terrain_base_is_handed_the_checked_value(self):
        src = MAP_ROUTE.read_text()
        assert "tile={tile}" in src
        assert "tile={basemap}" not in src, (
            "that is the unchecked prop reaching the warp")

    def test_nothing_else_still_treats_the_raw_prop_as_a_tile(self):
        """`basemap ? ...` anywhere else would re-introduce the truthiness
        bug in the coastline and fill decisions instead of the warp."""
        src = MAP_ROUTE.read_text()
        body = src[src.index("const tile ="):]
        for bad in ("basemap || scale", "basemap ? 0.8", "basemap ? 0.65",
                    "basemap || mapPlate"):
            assert bad not in body, bad


class TestATileThatIsNotThere:
    """public/basemaps is gitignored, so props can outlive their tiles."""

    def test_a_basemap_naming_a_missing_tile_is_dropped(self, tiles):
        """Film #6's exact state in the runner: the artifact carried tiles
        cut in the dev worktree, and the runner has none of them. Kept, it
        is a missing-image box under the route."""
        c = cut(basemap={"src": "basemaps/gone.jpg",
                         "bounds": [-162, 19, -156, 24]})
        RB.resolve([c], apply_tiles=False)
        assert "basemap" not in c

    def test_a_basemap_naming_a_present_tile_survives(self, tiles):
        meta = put_tile(tiles, "here", [-162, 19, -156, 24])
        c = cut(basemap={"src": meta["src"], "bounds": meta["bounds"]})
        RB.resolve([c], apply_tiles=False)
        assert c["basemap"]["src"] == "basemaps/here.jpg", (
            "the floor must not drop a tile that is present and fine")

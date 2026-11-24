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


def put_tile(d: Path, name: str, bounds: list[float]) -> dict:
    (d / f"{name}.jpg").write_bytes(b"\xff\xd8\xff")
    meta = {"name": name, "src": f"basemaps/{name}.jpg", "bounds": bounds}
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
        put_tile(tiles, "pacific", [-180, -10, -120, 50])
        c = cut(basemap="terrain", scale=3000)
        RB.resolve([c], apply_tiles=False)
        assert c["basemap"] == {"src": "basemaps/pacific.jpg",
                                "bounds": [-180, -10, -120, 50]}

    def test_a_tile_that_does_not_cover_the_frame_is_not_used(self, tiles):
        """A tile claimed to cover more than it does puts the route off the
        edge of the paper — build_basemap_tile.py's own words."""
        put_tile(tiles, "tiny", [-158.5, 21.0, -157.5, 22.0])
        c = cut(basemap="terrain", scale=3000)
        RB.resolve([c], apply_tiles=False)
        assert "basemap" not in c

    def test_an_absent_tile_is_dropped_and_reported_with_the_command(self,
                                                                     tiles):
        """NOT a refusal: films #1-#6 all drew these maps without terrain
        and a missing 700 MB raster must not stop a film. A reported absence
        is the whole change — the old behaviour was the same absence with
        nothing said."""
        c = cut(basemap="terrain", scale=3000)
        notes = RB.resolve([c], apply_tiles=False)
        assert "basemap" not in c
        note = next(n for n in notes if n["what"] == "basemap")
        assert "NOT drawn" in note["note"]
        assert "build_basemap_tile.py --name" in note["note"]

    def test_a_tile_object_is_left_alone(self, tiles):
        already = {"src": "basemaps/noah_bosporus.jpg",
                   "bounds": [18.0, 32.0, 44.0, 50.0]}
        c = cut(basemap=dict(already))
        RB.resolve([c], apply_tiles=False)
        assert c["basemap"] == already

    def test_an_unknown_kind_is_dropped(self, tiles):
        c = cut(basemap="satellite")
        notes = RB.resolve([c], apply_tiles=False)
        assert "basemap" not in c
        assert "only basemap kind" in notes[0]["note"]

    def test_terrain_without_a_route_is_dropped(self, tiles):
        c = {"id": "c900", "type": "map_route", "basemap": "terrain"}
        notes = RB.resolve([c], apply_tiles=False)
        assert "basemap" not in c
        assert "needs a route" in notes[0]["note"]

    def test_props_under_scene_are_resolved_in_place(self, tiles):
        """An authored cut's props live under `scene`
        (docs/STAGE_CONTRACT.md). Resolving the flattened copy would write
        the fix into a file nobody reads."""
        put_tile(tiles, "pacific", [-180, -10, -120, 50])
        c = {"id": "c112", "scene": {"type": "map_route", "route": C112_ROUTE,
                                     "scale": 3000, "basemap": "terrain",
                                     "basemap_drift": 1.3}}
        RB.resolve([c])
        assert c["scene"]["basemap"]["src"] == "basemaps/pacific.jpg"
        assert c["scene"]["basemap_drift"] == 0.08
        assert "basemap" not in c


class TestTheFrameThatRunsOffTheRaster:
    def test_the_default_scale_crosses_the_antimeridian(self, tiles):
        """THE FOURTH FAULT. All six cuts author no scale, so each is drawn
        at 1400 — and Hawaii at 1400 reaches past 180, where the raster
        ends."""
        c = cut(basemap="terrain")                     # no scale authored
        notes = RB.resolve([c], apply_tiles=False)
        note = next(n for n in notes if n["what"] == "basemap")
        assert "runs off the end of the raster" in note["note"]
        assert "authors no scale" in note["note"]

    def test_it_says_how_long_the_route_is_and_what_scale_would_fit(self,
                                                                    tiles):
        notes = RB.resolve([cut(basemap="terrain")], apply_tiles=False)
        note = next(n for n in notes if n["what"] == "basemap")
        assert "229 km" in note["note"]

    def test_an_authored_scale_is_not_blamed_on_d3(self, tiles):
        notes = RB.resolve([cut(basemap="terrain", scale=200)],
                           apply_tiles=False)
        note = next(n for n in notes if n["what"] == "basemap")
        assert "runs off the end" in note["note"]
        assert "authors no scale" not in note["note"]

    def test_the_route_length_is_the_measured_one(self):
        """229 km, which is also what the distance_callout patched into c112
        on 2026-11-23 says — the same haversine over the same route."""
        assert round(RB.route_km(C112_ROUTE)) == 229


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

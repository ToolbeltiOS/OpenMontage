"""A tile must have pixels, not just cover the ground.

Written 2026-11-25. `good_enough` was written to stop a tile FAR WIDER than
the frame being used (a quarter of the detail, four times too wide). It had
no bound in the other direction, so the five tiles cut for film #6 all
passed it while measuring 0.03 to 0.25 source pixels per frame pixel:
Natural Earth 10m is about 60 px per degree, and a 17 km route asks for
about one degree. The 60x32 crop blown to 1920 is a pastel smear with JPEG
blocking; the best of them draws the Hawaiian islands as lumps on a blank
ocean with a stray green square in open water.

The published films draw these maps as vectors, because `Explainer` never
passed the basemap on. Refusing a tile returns them to exactly that, with
the extent fixed — which is the actual defect the shot had.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "resolve_basemaps", ROOT / "scripts" / "resolve_basemaps.py")
RB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RB)

#: What film #6's six map cuts actually resolved to on 2026-11-25, measured
#: off the sidecars the resolver wrote. need == the tile's own bounds for
#: each, because the resolver cuts a tile to the frame it needs.
FILM6 = [
    ("c006", (60, 32), (-158.483333, 21.0, -157.483333, 21.533333)),
    ("c043", (291, 151), (-160.9, 19.4, -156.05, 21.9)),
    ("c070", (476, 247), (-161.5, 18.3, -153.6, 22.4)),
    ("c094", (60, 32), (-158.3, 21.1, -157.3, 21.63)),
    ("c121", (60, 32), (-158.25, 21.15, -157.25, 21.68)),
]


@pytest.mark.parametrize("cut,pixels,bounds", FILM6,
                         ids=[c for c, _, _ in FILM6])
def test_every_film6_tile_is_refused(cut, pixels, bounds):
    tile = {"bounds": list(bounds), "pixels": list(pixels),
            "src": f"basemaps/{cut}.jpg"}
    detail = RB.source_detail(tile, bounds)
    assert detail < RB.MIN_SOURCE_PX_PER_FRAME_PX, (
        f"{cut} measures {detail:.3f} source px per frame px — if this now "
        f"clears the floor the raster changed, and the tiles should be "
        f"looked at by eye before they ship")
    assert not RB.good_enough(tile, bounds), (
        f"{cut} is a {1 / detail:.0f}x upscale and must not be drawn")


def test_a_tile_with_the_pixels_is_accepted():
    """The floor must not refuse everything — a real tile still passes."""
    bounds = (-10.0, 40.0, 10.0, 50.0)
    tile = {"bounds": list(bounds), "pixels": [1920, 960], "src": "ok.jpg"}
    assert RB.source_detail(tile, bounds) == pytest.approx(1.0)
    assert RB.good_enough(tile, bounds)


def test_half_resolution_is_the_edge_and_is_allowed():
    bounds = (-10.0, 40.0, 10.0, 50.0)
    tile = {"bounds": list(bounds), "pixels": [960, 480], "src": "edge.jpg"}
    assert RB.source_detail(tile, bounds) == pytest.approx(0.5)
    assert RB.good_enough(tile, bounds), "0.5 is the floor, not below it"


def test_just_under_half_is_refused():
    bounds = (-10.0, 40.0, 10.0, 50.0)
    tile = {"bounds": list(bounds), "pixels": [959, 480], "src": "under.jpg"}
    assert not RB.good_enough(tile, bounds)


def test_the_upper_bound_still_holds():
    """A world tile is still refused for a city, floor or no floor."""
    need = (-0.1, 51.4, 0.1, 51.6)
    world = {"bounds": [-180.0, -90.0, 180.0, 90.0],
             "pixels": [21600, 10800], "src": "world.jpg"}
    assert RB.covers(world["bounds"], need)
    assert not RB.good_enough(world, need), "360 degrees for 0.2 is too wide"


def test_a_sidecar_with_no_pixels_is_refused_rather_than_trusted():
    bounds = (-10.0, 40.0, 10.0, 50.0)
    assert RB.source_detail({"bounds": list(bounds)}, bounds) == 0.0
    assert not RB.good_enough({"bounds": list(bounds)}, bounds)

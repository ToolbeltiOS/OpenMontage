"""Two map labels must not be drawn on top of each other.

WHAT SHIPPED
------------
Film #6, published 2026-11-23. Both of its map cuts that carry more than
one marker drew their labels overlapping:

    c006   "RELEASED FROM FLEET SUBMARINES"  over  "HARBOUR ENTRANCE"
    c112   "NIIHAU — A ZERO CAME DOWN HERE"  over  "OAHU"

The delivered frame at 12:13 reads "NIIHAU_OAHU" with the two words
interleaved. `MapRoute` drew every label at its marker plus a fixed offset
and never asked whether another label was already there.

The maps being 78.6 degrees wide made it worse — every marker collapses
towards the middle of the frame at that scale — so these tests place the
labels at BOTH extents: the one the film shipped, and the one
`resolve_basemaps.fit_extent` now computes. The rule has to hold at either,
because two places on a route are often close together however well the
map is framed.

The rule: a label whose box intersects one already placed is pushed along
its own leader until clear. Along the leader because that line is what
tells a reader which mark the label belongs to.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "remotion-composer" / "src" / "design" / "mapLabels"
ESBUILD = ROOT / "remotion-composer" / "node_modules" / ".bin" / "esbuild"

#: Film #6's own marker sets, from projects/attack-on-pearl-harbor.
C006 = [{"lon": -157.99, "lat": 21.19,
         "label": "RELEASED FROM FLEET SUBMARINES", "at": 0.9},
        {"lon": -157.983, "lat": 21.305, "label": "HARBOUR ENTRANCE",
         "at": 3.2}]
C112 = [{"lon": -157.98, "lat": 21.47, "label": "OAHU", "at": 0.8},
        {"lon": -160.15, "lat": 21.9,
         "label": "NIIHAU — A ZERO CAME DOWN HERE", "at": 2.8}]

#: `TYPE.labelSm`, the size MapRoute draws a marker label at.
FONT = 26

#: What the film shipped, and what the resolver computes for c112's route.
SHIPPED_SCALE = 1400.0
FITTED_SCALE = 33458.6

FRAME_W, FRAME_H = 1920, 1080


def project(lon: float, lat: float, centre: tuple[float, float],
            scale: float) -> tuple[float, float]:
    """d3.geoMercator().center(c).scale(s).translate([w/2, h/2])."""
    def merc_y(d: float) -> float:
        r = math.radians(max(-84.0, min(84.0, d)))
        return math.log(math.tan(math.pi / 4 + r / 2))
    x = scale * math.radians(lon - centre[0]) + FRAME_W / 2
    y = FRAME_H / 2 - scale * (merc_y(lat) - merc_y(centre[1]))
    return x, y


def anchors(markers: list[dict], scale: float) -> list[dict]:
    centre = (sum(m["lon"] for m in markers) / len(markers),
              sum(m["lat"] for m in markers) / len(markers))
    out = []
    for m in markers:
        x, y = project(m["lon"], m["lat"], centre, scale)
        out.append({"x": x, "y": y, "label": m["label"]})
    return out


def place(anchor_list: list[dict]) -> list[dict]:
    """Run the composer's own rule, bundled and executed under node."""
    with tempfile.TemporaryDirectory() as work:
        entry = Path(work) / "probe.ts"
        entry.write_text(
            f'import {{ placeLabels }} from "{MODULE}";\n'
            f"console.log(JSON.stringify(placeLabels("
            f"{json.dumps(anchor_list)}, {FONT})));\n")
        bundle = Path(work) / "probe.cjs"
        built = subprocess.run(
            [str(ESBUILD), str(entry), "--bundle", "--platform=node",
             "--format=cjs", f"--outfile={bundle}", "--log-level=error"],
            capture_output=True, text=True)
        if built.returncode != 0:
            pytest.skip(f"esbuild could not bundle: {built.stderr[:200]}")
        ran = subprocess.run(["node", str(bundle)], capture_output=True,
                             text=True)
        assert ran.returncode == 0, ran.stderr
        return json.loads(ran.stdout)


def overlaps(boxes: list[dict]) -> list[tuple[int, int]]:
    out = []
    for i, a in enumerate(boxes):
        for j, b in enumerate(boxes[i + 1:], start=i + 1):
            if (a["x"] < b["x"] + b["w"] and a["x"] + a["w"] > b["x"]
                    and a["y"] < b["y"] + b["h"] and a["y"] + a["h"] > b["y"]):
                out.append((i, j))
    return out


def unplaced(markers: list[dict], scale: float) -> list[dict]:
    """The boxes as MapRoute drew them before the rule: marker + 24,7."""
    out = []
    for a in anchors(markers, scale):
        w = len(a["label"]) * FONT * 0.72
        h = FONT * 1.25
        out.append({"x": a["x"] + 24, "y": a["y"] + 7 - h * 0.78,
                    "w": w, "h": h})
    return out


@pytest.mark.parametrize("name,markers", [("c006", C006), ("c112", C112)])
class TestFilm6sOwnLabelSets:
    def test_they_overlapped_before_the_rule(self, name, markers):
        """THE CONTROL. Without it these are the frames that shipped."""
        assert overlaps(unplaced(markers, SHIPPED_SCALE)), (
            f"{name} did not overlap at the scale it shipped at — then this "
            f"test is not about the defect")

    def test_they_do_not_overlap_after_it(self, name, markers):
        boxes = place(anchors(markers, SHIPPED_SCALE))
        assert overlaps(boxes) == [], f"{name}: {overlaps(boxes)}"

    def test_nor_at_the_extent_the_resolver_computes(self, name, markers):
        """A correctly framed map still puts two close places close
        together."""
        boxes = place(anchors(markers, FITTED_SCALE))
        assert overlaps(boxes) == []

    def test_the_first_label_keeps_the_place_it_asked_for(self, name, markers):
        boxes = place(anchors(markers, SHIPPED_SCALE))
        assert boxes[0]["pushed"] == 0
        assert (boxes[0]["dx"], boxes[0]["dy"]) == (24, 7)

    def test_only_what_had_to_move_moved(self, name, markers):
        boxes = place(anchors(markers, SHIPPED_SCALE))
        assert sum(1 for b in boxes if b["pushed"]) == 1


class TestTheRuleItself:
    def test_a_label_is_pushed_along_its_leader(self):
        """Not sideways: the leader is what points at the mark."""
        same = [{"x": 500, "y": 500, "label": "ALPHA"},
                {"x": 500, "y": 500, "label": "BETA"}]
        boxes = place(same)
        moved = boxes[1]
        # default leader is (24, 7); the push keeps that direction
        assert moved["dx"] > 24 and moved["dy"] > 7
        assert abs((moved["dy"] - 7) / (moved["dx"] - 24) - 7 / 24) < 0.05

    def test_an_authored_offset_sets_the_direction(self):
        up = [{"x": 500, "y": 500, "label": "ALPHA", "dx": 0, "dy": -40},
              {"x": 500, "y": 500, "label": "BETA", "dx": 0, "dy": -40}]
        boxes = place(up)
        assert boxes[1]["dy"] < -40, "a label pointing up is pushed up"
        assert abs(boxes[1]["dx"]) < 1e-6

    def test_labels_far_apart_are_left_alone(self):
        apart = [{"x": 100, "y": 100, "label": "ALPHA"},
                 {"x": 100, "y": 900, "label": "BETA"},
                 {"x": 1500, "y": 500, "label": "GAMMA"}]
        boxes = place(apart)
        assert all(b["pushed"] == 0 for b in boxes)
        assert overlaps(boxes) == []

    def test_a_third_label_clears_both_of_the_others(self):
        pile = [{"x": 500, "y": 500, "label": "ALPHA"},
                {"x": 500, "y": 500, "label": "BETA"},
                {"x": 500, "y": 500, "label": "GAMMA"}]
        boxes = place(pile)
        assert overlaps(boxes) == []
        assert [b["pushed"] for b in boxes][0] == 0
        assert boxes[2]["pushed"] > boxes[1]["pushed"]

    def test_it_gives_up_rather_than_running_off_the_map(self):
        """A cap, so a crowded map cannot push a label into the next
        county. It still returns a box for every label."""
        crowd = [{"x": 500, "y": 500, "label": f"LABEL {i}"}
                 for i in range(40)]
        boxes = place(crowd)
        assert len(boxes) == 40
        assert max(b["pushed"] for b in boxes) <= 14

    def test_placement_does_not_depend_on_what_has_appeared(self):
        """Determinism is the whole reason this runs over every marker:
        a label that moved when a later one faded in is type that moves,
        which type lock fails a film for."""
        once = place(anchors(C112, SHIPPED_SCALE))
        twice = place(anchors(C112, SHIPPED_SCALE))
        assert once == twice


class TestItIsWiredIn:
    def test_map_route_uses_the_placement(self):
        src = (ROOT / "remotion-composer" / "src" / "components"
               / "MapRoute.tsx").read_text()
        assert "placeLabels" in src
        assert "placed ? placed.dx" in src
        assert "x={xy[0] + (m.dx ?? 24)}" not in src

    def test_it_is_computed_over_every_marker(self):
        src = (ROOT / "remotion-composer" / "src" / "components"
               / "MapRoute.tsx").read_text()
        block = src[src.index("const labelBoxes"):src.index("const drawStart")]
        assert "markers.map" in block
        assert "appear(" not in block, (
            "placement must not depend on which markers have appeared")

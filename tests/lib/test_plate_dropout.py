"""A frame whose picture never arrived, and the gate that can see it.

WHY THIS GATE EXISTS
--------------------
Nothing else in the delivery could see it. Frame count sees a frame that is
PRESENT. Frame motion sees that one frame is not a freeze. Frame order
compares the delivered file against the PLATE, and the defect is in the
plate, so the two agree perfectly. they-said-it-couldnt-be-built is
published with eight of these in it, and king-tut's first delivery had five
— two plain to the eye — under 7 of 7 green gates.

WHAT THE CONTROL HAS TO PROVE
-----------------------------
Both halves, or the gate means nothing:

  * it FINDS a frame darkened by what a lost backdrop actually cost, on
    film-like material that is already moving; and
  * it does NOT report a hard cut, which is the thing a naive
    frame-differs-from-its-neighbours test fires on constantly.

The clip is synthesised rather than fixtured so the truth is known exactly:
two injected frames at known indices and a hard cut at a known index.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import verify_plate_dropout as V  # noqa: E402

#: What a lost backdrop measured on the film it was found in. The injected
#: frames are darkened by this much and no more, so the control is as hard
#: as the real case rather than an obvious black frame.
MEASURED_COST = 5.5

INJECTED = {17, 42}
CUT_AT = 30


@pytest.fixture(scope="module")
def clip() -> str:
    """A film-like clip: a picture panning slowly under grain, a hard cut in
    the middle, and two frames that lost their backdrop."""
    from PIL import Image

    rng = np.random.default_rng(11)
    yy, xx = np.mgrid[0:V.H, 0:V.W].astype("float32")
    scene_a = 60 + 40 * np.sin(xx / 61.0) * np.cos(yy / 47.0)
    scene_b = 150 + 50 * np.sin(xx / 23.0 + 2) * np.cos(yy / 31.0 + 1)
    base = np.empty((60, V.H, V.W), dtype="float32")
    for i in range(60):
        scene = scene_a if i < CUT_AT else scene_b
        base[i] = (np.roll(scene, int(i * 1.5), axis=1)
                   + rng.normal(0, 0.6, (V.H, V.W)))
    for i in INJECTED:
        base[i] = np.clip(base[i] - MEASURED_COST, 0, 255)

    tmp = tempfile.mkdtemp()
    raw = Path(tmp) / "raw"
    raw.mkdir()
    for i, f in enumerate(base):
        Image.fromarray(f.astype("uint8")).save(raw / f"f_{i:04d}.png")
    out = Path(tmp) / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "30",
                    "-i", str(raw / "f_%04d.png"), "-c:v", "libx264",
                    "-crf", "10", "-pix_fmt", "yuv420p", str(out)], check=True)
    return str(out)


class TestTheInjectedFrameControl:
    def test_it_finds_every_injected_frame(self, clip):
        hits, total = V.scan(clip)
        assert total == 60, f"decoded {total} frames of 60"
        assert {h["frame"] for h in hits} >= INJECTED, (
            f"missed an injected dropout: found {sorted(h['frame'] for h in hits)}")

    def test_it_does_not_report_the_hard_cut(self, clip):
        """The failure mode of every naive version of this check."""
        hits, _ = V.scan(clip)
        found = {h["frame"] for h in hits}
        assert CUT_AT not in found and CUT_AT - 1 not in found, (
            f"the hard cut at {CUT_AT} was reported as a dropout: {sorted(found)}")

    def test_it_reports_nothing_else(self, clip):
        hits, _ = V.scan(clip)
        assert {h["frame"] for h in hits} == INJECTED

    def test_the_same_defect_reads_differently_in_faster_material(self, clip):
        """WHY `CERTAIN_RATIO` IS A LABEL AND NOT A THRESHOLD.

        Both injected frames are darkened by exactly MEASURED_COST. Frame
        17 sits in the slow first scene and reads 0.196; frame 42 sits in
        the faster second one and reads 0.546. Identical defect, one either
        side of a 0.25 line — so a gate that blocked only on the strong
        readings would pass the weak half of its own control."""
        hits, _ = V.scan(clip)
        by_frame = {h["frame"]: h["decisiveness"] for h in hits}
        assert by_frame[17] < V.CERTAIN_RATIO < by_frame[42], by_frame

    def test_the_gate_fails_the_film_for_both_and_says_where(self, clip):
        """Both, including the one that reads weakly."""
        problems, measured = V.check(clip)
        assert len(problems) == len(INJECTED), problems
        assert measured["certain"] + measured["marginal"] == len(INJECTED)
        import re
        for problem in problems:
            assert "the picture is gone for one frame" in problem
            # A timestamp of the right shape, not a literal second: the two
            # injected frames are 25 frames apart and land in different ones.
            assert re.search(r"at \d\d:\d\d\.\d\d\d:", problem), problem
        assert sorted(measured["certain_frames"]
                      + measured["marginal_frames"]) == sorted(INJECTED)


class TestACleanClipPasses:
    """The other half of the control: no injected frame, no finding. A gate
    that fires on correct material is a gate that gets switched off."""

    @pytest.fixture(scope="class")
    def clean(self) -> str:
        from PIL import Image

        rng = np.random.default_rng(5)
        yy, xx = np.mgrid[0:V.H, 0:V.W].astype("float32")
        scene = 60 + 40 * np.sin(xx / 61.0) * np.cos(yy / 47.0)
        tmp = tempfile.mkdtemp()
        raw = Path(tmp) / "raw"
        raw.mkdir()
        for i in range(60):
            frame = (np.roll(scene, int(i * 1.5), axis=1)
                     + rng.normal(0, 0.6, (V.H, V.W)))
            Image.fromarray(np.clip(frame, 0, 255).astype("uint8")).save(
                raw / f"f_{i:04d}.png")
        out = Path(tmp) / "clean.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "30",
                        "-i", str(raw / "f_%04d.png"), "-c:v", "libx264",
                        "-crf", "10", "-pix_fmt", "yuv420p", str(out)],
                       check=True)
        return str(out)

    def test_it_passes(self, clean):
        problems, measured = V.check(clean)
        assert problems == [], problems
        assert measured["certain"] == 0


class TestTheDecodeInventsNothing:
    def test_vsync_zero_is_in_the_decode(self):
        """Without it ffmpeg resamples a 29.9959fps file to CFR and INVENTS
        frames: they-said-it decoded 36,244 from a container indexing
        36,238, and every index after each invention was shifted. The hit at
        32,992 was reported at 32,996, and checking 32,996 showed an
        ordinary frame — which looks exactly like the scan hallucinating."""
        source = (ROOT / "lib" / "verify_plate_dropout.py").read_text()
        decode = source[source.index("def frames("):source.index("def scan(")]
        assert '"-vsync", "0"' in decode

    def test_the_reason_is_written_down_where_it_would_be_removed(self):
        source = (ROOT / "lib" / "verify_plate_dropout.py").read_text()
        assert "IS NOT OPTIONAL" in source


class TestItIsABlockingGate:
    def test_the_delivery_runs_it(self):
        source = (ROOT / "lib" / "film_render.py").read_text()
        gates = source[source.index("def gates("):]
        assert '"plate-dropout": check_dropout(str(dest), fps)' in gates
        assert "from verify_plate_dropout import check as check_dropout" in gates

    def test_it_runs_on_the_delivered_file_not_the_plate(self):
        """The plate is where the defect IS. Scanning it would find the
        dropout and call the film clean."""
        source = (ROOT / "lib" / "film_render.py").read_text()
        gates = source[source.index("def gates("):]
        assert "check_dropout(str(dest)" in gates
        assert "check_dropout(str(picture)" not in gates

    def test_its_findings_reach_the_report(self):
        source = (ROOT / "lib" / "film_render.py").read_text()
        assert "| plate-dropout |" in source


class TestEveryHitIsABlockingHit:
    """Settled by the one film with known ground truth. king-tut's first
    delivery had 13 frames uncovered by the timeline arithmetic; the scan
    found five of them, two reading 0.125 and 0.205 and three reading
    0.377, 0.256 and 0.518. All five are in the list of thirteen, so the
    three weak readings were real dropouts in a film that passed 7 of 7
    gates."""

    RUN_ONE_HITS = {6902: 0.125, 18765: 0.205,
                    5381: 0.377, 9136: 0.256, 19940: 0.518}
    KNOWN_GAP_FRAMES = {2803, 4212, 5381, 6902, 9136, 10483, 11659, 13158,
                        18765, 19940, 25813, 33168, 34560}

    def test_every_hit_that_film_produced_was_a_real_gap_frame(self):
        assert set(self.RUN_ONE_HITS) <= self.KNOWN_GAP_FRAMES

    def test_three_of_the_five_would_have_passed_a_certain_only_gate(self):
        weak = [f for f, d in self.RUN_ONE_HITS.items()
                if d >= V.CERTAIN_RATIO]
        assert len(weak) == 3 and set(weak) <= self.KNOWN_GAP_FRAMES

    def test_the_gate_reports_a_problem_for_every_hit(self, tmp_path):
        """Read off the code rather than a film: `check` iterates the hits,
        not the certain ones."""
        source = (ROOT / "lib" / "verify_plate_dropout.py").read_text()
        body = source[source.index("def check("):]
        assert "for h in hits:" in body
        assert "for h in certain:" not in body


class TestTheFilmThatShipped:
    """king-tut's delivered final.mp4 is the passing fixture: the same film
    whose FIRST delivery had two certain dropouts and three marginal, all
    five of them gap frames. Opt-in because it decodes 36,803 frames."""

    FILM = Path("/Users/mac/Developer/wak3up-docs/runner/projects/king-tut"
                "/renders/final.mp4")

    @pytest.mark.slow_decode
    def test_king_tut_is_clean(self):
        """Measured at 99.7s for 36,803 frames when this was written, which
        is what the module's cost claim rests on."""
        if not self.FILM.exists():
            pytest.skip("king-tut's delivery is not on this machine")
        problems, measured = V.check(str(self.FILM))
        assert measured["frames"] == 36803, measured
        assert problems == [], problems
        assert measured["certain"] == 0 and measured["marginal"] == 0, measured


class TestTheNameIsTheSameInBothPlaces:
    """`verdict(name)` marks a gate FAIL by matching `name + ":"` against
    the problem strings, and the problems are built from the GATES DICT KEY
    while the report row carries its own literal. If those two ever differ
    — a space for a hyphen, a capital — every dropout in the film would be
    listed as a problem and the row would still read PASS."""

    SOURCE = (ROOT / "lib" / "film_render.py").read_text()

    def test_this_gate_is_keyed_and_rowed_as_plate_dropout(self):
        import re
        gates = self.SOURCE[self.SOURCE.index("def gates("):]
        keys = re.findall(r'^\s*"([a-z \-]+)": check_', gates, re.M)
        assert "plate-dropout" in keys, keys
        assert "| plate-dropout |" in self.SOURCE

    def test_every_gate_key_has_a_row_with_that_exact_name(self):
        """Not just this gate: the same trap is open for all of them."""
        import re
        gates = self.SOURCE[self.SOURCE.index("def gates("):]
        keys = re.findall(r'^\s*"([a-z \-]+)": check_', gates, re.M)
        assert len(keys) >= 5, keys
        for key in keys:
            assert f"| {key} |" in self.SOURCE, (
                f"gate {key!r} produces problems prefixed {key + ':'!r} but "
                f"no report row is named {key!r}, so its verdict can never "
                f"read FAIL")

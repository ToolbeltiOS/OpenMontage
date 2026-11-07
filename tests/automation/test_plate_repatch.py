"""A spliced plate is only as good as its seams.

WHY THIS EXISTS
---------------
king-tut, 2026-11-07. Three delivery gates failed; two of them were one
defect in three components, touching 18 of 161 cuts — 3,643 frames, 9.9% of
the film. The plate those frames belong to had taken 2h47m to render and the
other 33,160 frames in it were correct.

So the ranges are re-rendered and spliced into the stills the look pass
reads, and the plate is rebuilt from those stills.

THE DEFECT A SPLICE CAN INTRODUCE AND A FULL RE-RENDER CANNOT
-------------------------------------------------------------
A one-frame offset. `-start_number` is one-based while the frame indices are
zero-based, so writing a range at `a` instead of `a + 1` puts a correct
picture in the wrong frame — and then EVERY DELIVERY GATE STILL PASSES:

  - frame count is unchanged,
  - frame motion is unchanged (the same pictures, in the same order),
  - plate purity is unchanged (the same words, a thirtieth of a second out),
  - frame order correlates the delivered film against the plate, and both
    were built from the same wrongly-placed stills, so they agree perfectly.

The only thing that knows is the picture the patch overwrote. A range is
padded by `PAD` frames of the neighbouring cut, which the change does not
touch, so those frames must come back identical AT THE SAME INDEX. That is
what `seam_alignment` measures, and it is the whole reason the padding is
there.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


def repatch():
    spec = importlib.util.spec_from_file_location(
        "repatch_plate", ROOT / "scripts" / "repatch_plate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rp = repatch()


def run(n: int, shift: int = 0, seed: int = 7):
    """A run of frames with real content: no two alike, and not a gradient.

    A synthetic run that is smooth in time would score well against itself at
    any shift, which is the one thing this measurement must not do.
    """
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, size=(n + 4, 270, 480)).astype("float32")
    # a little temporal continuity, as a film has
    for i in range(1, len(base)):
        base[i] = 0.55 * base[i] + 0.45 * base[i - 1]
    return base[2 + shift:2 + shift + n]


class TestASeamIsCheckedAgainstWhatItOverwrote:
    """Two defects, two measurements.

    The first version of this class got its calibration from synthetic noise
    and was wrong about real film — see `SEAM_OUTLIER`. The numbers below are
    king-tut's own, from the patch that found the lead-in frame.
    """

    def test_an_aligned_patch_reads_as_aligned(self):
        before = run(14)
        after = before.copy()           # a re-render of the same frames
        m = rp.seam_alignment(before, after)
        assert m["worst"] == pytest.approx(0.0, abs=1e-6)
        assert m["best_shift"] == 0
        assert rp.check_seams([{"range": "0-13", "edge": "head",
                                "measured": m}]) == []

    def test_a_re_render_that_differs_slightly_is_still_aligned(self):
        """Two encodes of the same frames are not bit-identical, and the
        check must not demand that. The worst correct per-frame difference
        measured on this film's 36 seams was 0.78."""
        before = run(14)
        after = before + np.random.default_rng(3).normal(0, 0.7, before.shape)
        m = rp.seam_alignment(before, after.astype("float32"))
        assert m["worst"] < rp.SEAM_CEILING
        assert rp.check_seams([{"range": "0-13", "edge": "head",
                                "measured": m}]) == []

    def test_one_bad_frame_in_an_otherwise_good_window_is_caught(self):
        """THE DEFECT THAT HAPPENED.

        `--frames=1548-1747` came back with frame 1548 differing from the
        full render by 6.2876 while 1549 differed by 0.1552 and the rest by
        less. One frame in 36,803, inside a fade — not a freeze, not a
        dropped frame, and invisible to every delivery gate.
        """
        before = run(14)
        after = before.copy()
        after[0] += 7.0                 # the first frame, and only it
        m = rp.seam_alignment(before, after)
        assert m["worst_at"] == 0
        assert m["worst"] > rp.SEAM_OUTLIER * m["median"]
        problems = rp.check_seams([{"range": "1548-1747", "edge": "head",
                                    "measured": m}])
        assert problems and "does not touch" in problems[0]

    def test_a_window_that_is_wrong_all_through_is_caught_too(self):
        """No outlier, because every frame is equally wrong. The ceiling is
        what catches this one."""
        before = run(14)
        after = before + 3.0
        m = rp.seam_alignment(before, after)
        assert m["median"] > rp.SEAM_CEILING
        assert m["worst"] < rp.SEAM_OUTLIER * m["median"], (
            "this case has to be caught by the ceiling, not the outlier rule")
        assert rp.check_seams([{"range": "0-13", "edge": "head",
                                "measured": m}])

    def test_a_patch_one_frame_out_is_caught(self):
        """The other control: correct pictures, wrong index."""
        before = run(14)
        after = run(14, shift=1)
        m = rp.seam_alignment(before, after)
        assert m["best_shift"] != 0, m["curve"]
        problems = rp.check_seams([{"range": "0-13", "edge": "head",
                                    "measured": m}])
        assert any("wrong place" in p for p in problems)

    def test_a_patch_one_frame_early_is_caught_too(self):
        before = run(14)
        after = run(14, shift=-1)
        m = rp.seam_alignment(before, after)
        assert m["best_shift"] != 0, m["curve"]

    def test_the_real_seams_of_king_tut_would_pass(self):
        """Regression on the calibration itself.

        These are measured windows from the patch: the per-frame differences
        of a correct head seam (near-black, barely moving) and a correct tail
        seam (a bright photograph, where two encodes disagree most). The rule
        that fired on nine correct seams would fail here.
        """
        for label, frames in (
            ("1548-1747 tail", [0.0004, 0.0316, 0.1676, 0.3044, 0.2582,
                                0.2632, 0.3635, 0.3984, 0.3925, 0.4744]),
            ("18155-18354 head", [0.0429] * 10),
        ):
            per_frame = np.array(frames, dtype="float32")
            m = {"per_frame": list(per_frame), "median": float(np.median(per_frame)),
                 "worst": float(per_frame.max()), "worst_at": int(per_frame.argmax()),
                 "best_shift": 0, "curve": {}}
            assert rp.check_seams([{"range": label, "edge": "head",
                                    "measured": m}]) == [], label


class TestTheRangesCoverTheCutsAndNothingElse:
    CUTS = [
        {"id": "c001", "in_seconds": 0.0, "out_seconds": 10.0, "type": "still"},
        {"id": "c002", "in_seconds": 10.0, "out_seconds": 17.0, "type": "text_card"},
        {"id": "c003", "in_seconds": 17.0, "out_seconds": 24.0, "type": "still"},
        {"id": "c004", "in_seconds": 24.0, "out_seconds": 30.0, "type": "stat_card"},
        {"id": "c005", "in_seconds": 30.0, "out_seconds": 36.0, "type": "stat_card"},
    ]
    TOTAL = 36 * 30

    def test_a_range_is_the_cut_plus_its_padding(self):
        got = rp.ranges_for(self.CUTS, {"text_card"}, "type", self.TOTAL, pad=10)
        assert got == [(290, 519, ["c002"])]

    def test_adjacent_cuts_become_one_range(self):
        """c004 and c005 touch, so patching both is one render, not two."""
        got = rp.ranges_for(self.CUTS, {"stat_card"}, "type", self.TOTAL, pad=10)
        assert got == [(710, 1079, ["c004", "c005"])]

    def test_the_padding_never_leaves_the_film(self):
        got = rp.ranges_for(self.CUTS, {"c001", "c005"}, "id", self.TOTAL, pad=10)
        assert got[0][0] == 0, "padded off the front of the film"
        assert got[-1][1] == self.TOTAL - 1, "padded off the end of the film"

    def test_naming_nothing_that_matches_gives_no_ranges(self):
        assert rp.ranges_for(self.CUTS, {"schematic"}, "type", self.TOTAL) == []

    def test_the_frame_arithmetic_is_the_compositions_own(self):
        """`Explainer` sequences a cut at round(in*fps) for round(dur*fps)."""
        got = rp.ranges_for(self.CUTS, {"c003"}, "id", self.TOTAL, pad=0)
        assert got == [(510, 719, ["c003"])]
        assert got[0][1] - got[0][0] + 1 == round((24.0 - 17.0) * 30)


class TestTheStillsAreOneBased:
    def test_a_range_written_at_a_lands_on_f_a_plus_one(self, tmp_path):
        """`extract_frames` writes `f_00001.jpg` for frame 0, so a patch that
        forgets the offset is the one-frame error this whole file is about."""
        import PIL.Image

        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        for n in range(1, 21):
            PIL.Image.fromarray(
                np.full((54, 96), n * 10, dtype="uint8")).save(
                    frames_dir / f"f_{n:05d}.jpg")

        raw = tmp_path / "raw"
        raw.mkdir()
        for i in range(3):
            PIL.Image.fromarray(
                np.full((54, 96), 250 - i, dtype="uint8")).save(raw / f"s_{i:04d}.png")
        segment = tmp_path / "seg.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "30",
                        "-i", str(raw / "s_%04d.png"), "-c:v", "libx264",
                        "-crf", "0", "-pix_fmt", "yuv420p", str(segment)],
                       check=True)

        rp.stills_from(segment, frames_dir, 5)   # global frames 5,6,7

        import PIL.Image as I
        assert np.asarray(I.open(frames_dir / "f_00005.jpg")).mean() == pytest.approx(50, abs=3)
        assert np.asarray(I.open(frames_dir / "f_00006.jpg")).mean() > 200
        assert np.asarray(I.open(frames_dir / "f_00008.jpg")).mean() > 200
        assert np.asarray(I.open(frames_dir / "f_00009.jpg")).mean() == pytest.approx(90, abs=3)


class TestTheRendererIsAskedForTheRangeAndNothingMore:
    """`--frames=a-b`, or the 17-minute patch is a 2h47m re-render."""

    def _command(self, monkeypatch, **kwargs):
        import sys
        sys.path.insert(0, str(ROOT / "lib"))
        import film_render

        seen = {}

        def fake(cmd, cwd, label, count, cuts=None, output=None):
            seen["cmd"] = cmd
            seen["count"] = count
            seen["label"] = label

        monkeypatch.setattr(film_render, "run_watched", fake)
        film_render.render_plate(Path("props.json"), Path("/tmp/x/out.mp4"),
                                 36803, None, **kwargs)
        return seen

    def test_a_range_renders_that_range_and_a_lead_in(self, monkeypatch):
        """`LEAD_IN` frames in front, because the first frame a range render
        paints can be wrong — king-tut's 1548 came back 6.2876 from the full
        render while 1549 came back 0.1552."""
        import film_render
        seen = self._command(monkeypatch, frames=(14087, 14331))
        lead = film_render.LEAD_IN
        assert f"--frames={14087 - lead}-14331" in seen["cmd"]
        assert seen["count"] == 245 + lead, (
            "the watchdog counts the frames of THIS render, not the film's")

    def test_the_caller_is_told_where_the_lead_in_ends(self, monkeypatch):
        """Otherwise the discarded frames get written over good stills."""
        import film_render
        import sys
        sys.path.insert(0, str(ROOT / "lib"))
        monkeypatch.setattr(film_render, "run_watched",
                            lambda *a, **k: None)
        first = film_render.render_plate(Path("p.json"), Path("/tmp/x/o.mp4"),
                                         36803, None, frames=(14087, 14331))
        assert first == 14087 - film_render.LEAD_IN

    def test_a_range_at_the_very_start_cannot_lead_in_past_zero(self, monkeypatch):
        seen = self._command(monkeypatch, frames=(0, 99))
        assert "--frames=0-99" in seen["cmd"]

    def test_no_range_still_renders_the_whole_film(self, monkeypatch):
        seen = self._command(monkeypatch)
        assert "--frames=0-36802" in seen["cmd"]
        assert seen["count"] == 36803

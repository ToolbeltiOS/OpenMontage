"""No cut lands on top of a cut the source already had.

A third of this film's shots are clips, and a clip is rarely one take. Cutting
away eight frames before the source's own cut gives the viewer two cuts a
quarter of a second apart, and they read the second one as a mistake. The EDL
cannot see it; it knows the clip starts at 31.98s and runs 6.6 seconds.

The fixtures are built rather than borrowed, because the thing being tested is
a distance in frames and a synthetic clip can put a cut exactly where the test
wants one.
"""
from __future__ import annotations

import subprocess

import numpy as np
import pytest

from lib import verify_source_cuts as vsc

pytest.importorskip("scenedetect")


def clip(path, plan, fps=30):
    """A clip from a plan of (frames, scene index) — each scene a new subject."""
    from PIL import Image

    raw = path.parent / f"raw_{path.stem}"
    raw.mkdir(exist_ok=True)
    n = 0
    for frames, scene in plan:
        for i in range(frames):
            rng = np.random.default_rng(scene * 1000)
            arr = rng.integers(0, 255, (90, 160, 3), dtype="uint8")
            arr = np.clip(arr.astype("int16") + scene * 7, 0, 255).astype("uint8")
            Image.fromarray(arr).save(raw / f"f_{n:04d}.png")
            n += 1
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps),
                    "-i", str(raw / "f_%04d.png"), "-c:v", "libx264", "-crf", "14",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def timelapse(path, steps=10, fps=30):
    """One subject, advanced in steps: a jump in content, not a cut.

    The real case is a satellite sequence of an eruption, and what makes it a
    step rather than a cut is that the COMPOSITION survives while the content
    changes. The fixture reproduces that as a fixed luminance structure —
    bright in the middle, dark at the edges — under a colour that changes
    every step.

    Two fixtures were tried before this one and neither was detectable at all:
    re-rolling fine detail, and changing exposure. PySceneDetect's content
    detector weighs hue and saturation heavily and these frames had neither,
    so a greyscale timelapse is invisible to it however violently the detail
    moves. That is worth knowing on its own — the step problem only arises in
    colour material.
    """
    import colorsys

    from PIL import Image

    raw = path.parent / f"raw_{path.stem}"
    raw.mkdir(exist_ok=True)
    height, width = 180, 320
    yy, xx = np.mgrid[0:height, 0:width]
    centre = np.exp(-(((xx - width / 2) / (width / 3.2)) ** 2
                      + ((yy - height / 2) / (height / 3.2)) ** 2))
    luma = 30 + 170 * centre                     # the shape that persists

    n = 0
    for step in range(steps):
        r, g, b = colorsys.hsv_to_rgb((step * 0.37) % 1.0, 0.75, 1.0)
        frame = np.stack([luma * r, luma * g, luma * b], axis=2)
        rng = np.random.default_rng(step)
        frame = np.clip(frame + rng.normal(0, 12, frame.shape), 0, 255).astype("uint8")
        for _ in range(15):
            Image.fromarray(frame).save(raw / f"f_{n:04d}.png")
            n += 1
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps),
                    "-i", str(raw / "f_%04d.png"), "-c:v", "libx264", "-crf", "12",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


class TestDetection:
    def test_a_cut_is_found_where_it_was_put(self, tmp_path):
        film = clip(tmp_path / "two.mp4", [(60, 1), (60, 2)])
        changes = vsc.scene_changes(str(film))
        assert changes, "no cut found in a clip with a cut in it"
        assert min(abs(c - 2.0) for c in changes) < 0.2

    def test_one_continuous_shot_has_no_cuts(self, tmp_path):
        film = clip(tmp_path / "one.mp4", [(90, 3)])
        assert vsc.scene_changes(str(film)) == []


class TestTheRule:
    def _cuts(self, source, source_in, length=2.0):
        return [{"id": "c001", "source": str(source),
                 "source_in_seconds": source_in,
                 "in_seconds": 0.0, "out_seconds": length}]

    def test_a_boundary_on_top_of_a_source_cut_fails(self, tmp_path):
        film = clip(tmp_path / "two.mp4", [(60, 1), (60, 2)])
        problems, _ = vsc.check(self._cuts(film, 2.0, 1.0), 30.0, root=tmp_path)
        assert problems, "a boundary exactly on a source cut was allowed"
        assert "read as one mistake" in problems[0]

    def test_a_boundary_ten_frames_away_still_fails(self, tmp_path):
        film = clip(tmp_path / "two.mp4", [(60, 1), (60, 2)])
        problems, _ = vsc.check(self._cuts(film, 2.0 + 10 / 30, 1.0), 30.0,
                                root=tmp_path)
        assert problems

    def test_a_boundary_well_clear_of_one_passes(self, tmp_path):
        film = clip(tmp_path / "two.mp4", [(60, 1), (120, 2)])
        problems, _ = vsc.check(self._cuts(film, 2.0 + 40 / 30, 1.0), 30.0,
                                root=tmp_path)
        assert problems == [], problems

    def test_a_cut_inside_a_shot_is_a_note_and_not_a_failure(self, tmp_path):
        """It may be exactly what the shot is for; it must never be a surprise."""
        film = clip(tmp_path / "two.mp4", [(60, 1), (60, 2)])
        problems, measured = vsc.check(self._cuts(film, 0.0, 4.0), 30.0,
                                       root=tmp_path)
        assert problems == [], problems
        assert measured["cuts_inside_a_shot_count"] == 1

    def test_a_still_is_not_examined(self, tmp_path):
        problems, measured = vsc.check(
            [{"id": "c1", "source": "a/photo.jpg",
              "in_seconds": 0.0, "out_seconds": 6.0}], 30.0, root=tmp_path)
        assert problems == [] and measured["video_cuts_checked"] == 0


class TestTimelapse:
    """The satellite sequence that made this necessary."""

    def test_a_step_is_not_a_cut(self, tmp_path):
        film = timelapse(tmp_path / "lapse.mp4")
        changes = vsc.scene_changes(str(film))
        assert changes, "the fixture produced no detectable steps"
        assert all(vsc.is_a_step(str(film), t) for t in changes), (
            "a step in one continuous subject was read as a cut to another")

    def test_a_real_cut_is_not_a_step(self, tmp_path):
        film = clip(tmp_path / "two.mp4", [(60, 1), (60, 5)])
        for change in vsc.scene_changes(str(film)):
            assert not vsc.is_a_step(str(film), change)

    def test_a_boundary_beside_a_step_does_not_fail(self, tmp_path):
        film = timelapse(tmp_path / "lapse.mp4")
        changes = vsc.scene_changes(str(film))
        problems, measured = vsc.check(
            [{"id": "c1", "source": str(film), "source_in_seconds": changes[0],
              "in_seconds": 0.0, "out_seconds": 0.4}], 30.0, root=tmp_path)
        assert problems == [], problems
        assert measured["timelapse_steps_ignored"] >= 1

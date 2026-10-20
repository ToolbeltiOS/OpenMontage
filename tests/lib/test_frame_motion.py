"""The freeze check, against synthetic films with known content.

The act 2 demo had the right frame count, a constant frame rate, every
timestamp exactly 1/30 apart and a green rhythm gate, and its picture was
frozen for 51% of its running time. Nothing compared one frame to the next.
"""
from __future__ import annotations

import subprocess

import numpy as np
import pytest

from lib import verify_frame_motion as vfm


def render(path, frames, fps=30):
    """Encode a list of greyscale levels as a video, one frame each."""
    import PIL.Image

    raw = path.parent / "raw"
    raw.mkdir(exist_ok=True)
    for i, level in enumerate(frames):
        arr = np.full((270, 480), level, dtype="uint8")
        # Structure keyed to the LEVEL, not the frame index: two frames with
        # the same level must be byte-identical, or the "frozen" fixture is
        # not frozen and the test passes for the wrong reason.
        x = (level * 7) % 440
        arr[:, x:x + 40] = min(255, level + 60)
        PIL.Image.fromarray(arr).save(raw / f"f_{i:04d}.png")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-framerate", str(fps),
         "-i", str(raw / "f_%04d.png"), "-c:v", "libx264", "-crf", "12",
         "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


class TestFreezes:
    def test_a_moving_film_passes(self, tmp_path):
        film = render(tmp_path / "moving.mp4", list(range(40, 100)))
        problems, measured = vfm.check(str(film))
        assert problems == [], problems
        assert measured["runs_over_limit"] == 0

    def test_a_long_freeze_is_caught(self, tmp_path):
        frames = list(range(40, 60)) + [60] * 30 + list(range(60, 80))
        film = render(tmp_path / "frozen.mp4", frames)
        problems, measured = vfm.check(str(film))
        assert problems, "a 30-frame freeze went unreported"
        assert measured["longest_freeze_seconds"] >= 0.9
        assert "identical frames" in problems[0]

    def test_two_identical_frames_are_allowed(self, tmp_path):
        frames = list(range(40, 60)) + [60, 60] + list(range(61, 80))
        film = render(tmp_path / "pair.mp4", frames)
        problems, _ = vfm.check(str(film))
        assert problems == [], problems

    def test_a_hold_on_black_is_not_a_freeze(self, tmp_path):
        """The fade through black at an act boundary is the one planned hold."""
        frames = list(range(40, 60)) + [0] * 30 + list(range(60, 80))
        film = render(tmp_path / "black.mp4", frames)
        problems, _ = vfm.check(str(film))
        assert problems == [], problems


class TestCalibration:
    def test_the_measurement_scale_is_not_the_thumbnail_one(self):
        """160x90 averages away the sub-pixel motion of a legitimate slow move.

        Measured on the same material: a moving scene reads as 54% duplicate
        frames at 160x90 and 0% at 480x270.
        """
        assert vfm.MEASURE_SIZE == (480, 270)

    def test_identical_frames_are_exactly_zero_not_merely_small(self, tmp_path):
        film = render(tmp_path / "flat.mp4", [80] * 12)
        frames = vfm.decode(str(film))
        mad = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
        assert mad.max() < vfm.SAME_FRAME_MAD

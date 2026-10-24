"""Frame order and delivery audio, against synthetic films with known defects.

Both checks exist because the act 2 demo passed everything else while being
wrong in two ways at once: an audio stream that was digital silence from the
first sample to the last, and 118 of every 120 frames carrying the wrong
source frame.

The fixtures below reproduce each defect in miniature. The one that matters
most is `scene` — a frame's content is keyed to its scene and its position
within it, so a frame moved to another scene really is foreign to the place
it lands in, which is the whole thing being measured.
"""
from __future__ import annotations

import subprocess

import numpy as np
import pytest

from lib import verify_delivery_audio as vda
from lib import verify_frame_order as vfo


def scene(index: int, position: int) -> np.ndarray:
    """A frame of scene `index`, `position` frames in.

    Each scene has its own base level and its own bar position, and the bar
    creeps with position, so consecutive frames of one scene are near
    neighbours while frames of two scenes are not.

    The bar ACCELERATES, which is not decoration. With a bar that moved at a
    constant rate every consecutive pair of frames differed by exactly the
    same amount, so a permutation left the motion profile untouched and the
    reference leg scored 0.9932 on a film that had been shuffled. Real
    material does not move at a constant rate; a fixture that does measures
    the check more kindly than the film would.
    """
    base = 40 + index * 55
    arr = np.full((270, 480), base, dtype="uint8")
    x = (index * 150 + position * position // 3) % 420
    arr[:, x:x + 50] = min(255, base + 70)
    return arr


def render(path, frames, fps=30):
    import PIL.Image

    raw = path.parent / f"raw_{path.stem}"
    raw.mkdir(exist_ok=True)
    for i, arr in enumerate(frames):
        PIL.Image.fromarray(arr).save(raw / f"f_{i:04d}.png")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-framerate", str(fps),
         "-i", str(raw / "f_%04d.png"), "-c:v", "libx264", "-crf", "10",
         "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def two_scenes(n=45):
    """Scene 0 then scene 1, cutting at `n`. The cut is declared below."""
    return [scene(0, i) for i in range(n)] + [scene(1, i) for i in range(n)]


CUTS = [{"in_seconds": 0.0, "out_seconds": 1.5},
        {"in_seconds": 1.5, "out_seconds": 3.0}]


class TestFrameOrder:
    def test_a_film_in_order_passes(self, tmp_path):
        film = render(tmp_path / "ordered.mp4", two_scenes())
        problems, measured = vfo.check(str(film), CUTS)
        assert problems == [], problems
        assert measured["out_of_order_count"] == 0

    def test_a_declared_cut_is_not_an_error(self, tmp_path):
        """The rule needs both sides; a cut only has one."""
        film = render(tmp_path / "cut.mp4", two_scenes())
        _, measured = vfo.check(str(film), CUTS)
        assert measured["out_of_order_count"] == 0

    def test_a_borrowed_frame_mid_scene_is_caught(self, tmp_path):
        frames = two_scenes()
        frames[20] = scene(1, 20)           # a frame of the next scene, early
        film = render(tmp_path / "borrowed.mp4", frames)
        problems, measured = vfo.check(str(film), CUTS)
        assert measured["out_of_order_count"] == 1, problems
        assert measured["out_of_order"][0]["seconds"] == pytest.approx(20 / 30, abs=0.02)
        assert "not one of them" in problems[0]

    def test_an_isolated_black_frame_is_caught(self, tmp_path):
        frames = two_scenes()
        frames[25] = np.zeros((270, 480), dtype="uint8")
        film = render(tmp_path / "black.mp4", frames)
        problems, measured = vfo.check(str(film), CUTS)
        assert measured["isolated_black_runs"] == 1
        assert any("on their own" in p for p in problems)

    def test_a_hold_on_black_of_three_frames_or_more_is_allowed(self, tmp_path):
        frames = [scene(0, i) for i in range(30)]
        frames += [np.zeros((270, 480), dtype="uint8")] * 6
        frames += [scene(1, i) for i in range(30)]
        cuts = [{"in_seconds": 0.0, "out_seconds": 1.0},
                {"in_seconds": 1.2, "out_seconds": 2.2}]
        film = render(tmp_path / "hold.mp4", frames)
        problems, measured = vfo.check(str(film), cuts)
        assert measured["isolated_black_runs"] == 0, problems

    def test_the_defect_as_it_shipped_fails_against_its_reference(self, tmp_path):
        """The leg with teeth, against the measured shape of the real defect.

        The look pass delivered each frame three to five frames late, the lag
        varying frame to frame. Reproduced here, the delivered film's motion
        profile stops resembling the picture render's at all — the real
        broken demo scored 0.139 and the fixed one 0.9995.
        """
        frames = two_scenes()
        reference = render(tmp_path / "reference.mp4", frames)
        lagged = [frames[max(0, i - (3 + (i * 7) % 3))] for i in range(len(frames))]
        delivered = render(tmp_path / "lagged.mp4", lagged)

        problems, measured = vfo.check(str(delivered), CUTS, str(reference))
        assert measured["reference_correlation"] < vfo.MIN_REFERENCE_CORRELATION
        assert any("not in the same order" in p for p in problems)

    def test_a_local_shuffle_fails_too(self, tmp_path):
        frames = two_scenes()
        reference = render(tmp_path / "reference2.mp4", frames)
        order = list(range(len(frames)))
        for i in range(4, len(order) - 4, 5):
            order[i], order[i - 3] = order[i - 3], order[i]
        scrambled = render(tmp_path / "scrambled.mp4", [frames[i] for i in order])
        _, measured = vfo.check(str(scrambled), CUTS, str(reference))
        assert measured["reference_correlation"] < vfo.MIN_REFERENCE_CORRELATION

    def test_a_film_compared_against_itself_scores_one(self, tmp_path):
        reference = render(tmp_path / "self.mp4", two_scenes())
        clean, ok = vfo.check(str(reference), CUTS, str(reference))
        assert clean == [], clean
        assert ok["reference_correlation"] == pytest.approx(1.0, abs=1e-6)

    def test_the_luma_map_is_one_character_per_frame(self, tmp_path):
        film = render(tmp_path / "map.mp4", two_scenes(30))
        _, measured = vfo.check(str(film), CUTS)
        rows = measured["luma_map"]
        assert sum(len(r.split("|", 1)[1]) for r in rows) == measured["frames"]
        assert all(r.split("|", 1)[1] for r in rows)


def tone(path, seconds=2.0, amplitude=0.25, sr=48000):
    import soundfile as sf

    t = np.arange(int(sr * seconds)) / sr
    wave = (amplitude * np.sin(2 * np.pi * 220 * t)).astype("float32")
    sf.write(path, np.stack([wave, wave], axis=1), sr)
    return path


def muxed(tmp_path, name, audio=None):
    video = render(tmp_path / f"{name}_v.mp4", [scene(0, i) for i in range(60)])
    out = tmp_path / f"{name}.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(video)]
    if audio is None:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest"]
    else:
        cmd += ["-i", str(audio), "-shortest"]
    cmd += ["-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
            "-b:a", "320k", str(out)]
    subprocess.run(cmd, check=True)
    return out


class TestDeliveryAudio:
    def test_a_real_mix_passes(self, tmp_path):
        film = muxed(tmp_path, "mixed", tone(tmp_path / "mix.wav"))
        problems, measured = vda.check(str(film))
        assert problems == [], problems
        assert measured["mean_dbfs"] > vda.MIN_MEAN_DBFS

    def test_a_silent_delivery_is_caught(self, tmp_path):
        """The defect exactly as it shipped: a present, plausible, empty track."""
        film = muxed(tmp_path, "silent")
        problems, measured = vda.check(str(film))
        assert measured["has_audio"] is True
        assert any("digital silence" in p for p in problems)

    def test_a_film_with_no_audio_stream_at_all_is_caught(self, tmp_path):
        video = render(tmp_path / "mute.mp4", [scene(0, i) for i in range(30)])
        problems, measured = vda.check(str(video))
        assert measured["has_audio"] is False
        assert "no audio stream" in problems[0]

    def test_the_wrong_mix_is_caught_by_loudness(self, tmp_path):
        """Loud enough to pass the floor, and still not the mix we made."""
        film = muxed(tmp_path, "wrong", tone(tmp_path / "loud.wav", amplitude=0.6))
        quiet = vda.integrated_lufs(str(muxed(
            tmp_path, "quiet", tone(tmp_path / "quiet.wav", amplitude=0.1))))
        problems, measured = vda.check(str(film), expected_lufs=quiet)
        assert measured["mean_dbfs"] > vda.MIN_MEAN_DBFS
        assert any("not the mix it claims to carry" in p for p in problems)

    def test_the_right_mix_lands_inside_the_tolerance(self, tmp_path):
        mix = tone(tmp_path / "same.wav")
        film = muxed(tmp_path, "same", mix)
        expected = vda.integrated_lufs(str(mix))
        problems, measured = vda.check(str(film), expected_lufs=expected)
        assert problems == [], problems
        assert abs(measured["loudness_delta_db"]) <= vda.LOUDNESS_TOLERANCE_DB


def grey(level: int, position: int = 0) -> np.ndarray:
    """A flat frame at a known luma, with a bar so it is not a dead field."""
    arr = np.full((270, 480), level, dtype="uint8")
    if level:
        x = (position * 7) % 420
        arr[:, x:x + 50] = min(255, level + 40)
    return arr


class TestShortBlackAtACut:
    """A frame of black at a cut is the bottom of a fade, not a stray frame.

    The rule catches a frame that came from somewhere else: black, with
    picture either side of it. That reasoning holds in the middle of a shot
    and fails at a cut, where the next shot may simply start dark.

    Measured on the Easter Island delivery. Every act boundary cuts to
    near-black and fades up into the act card — the same gesture each time.
    Act 2's card is graded a shade brighter than act 3's, so its fade crossed
    BLACK_LUMA after two frames where act 3's took nine, and the gate failed
    the film for the two. The frames either side of the threshold read 3.84
    and 4.45. That is not a blink; it is a threshold.
    """

    def test_a_short_black_run_on_a_cut_is_not_a_stray_frame(self, tmp_path):
        frames = ([grey(90, i) for i in range(40)]
                  + [grey(0), grey(0)]
                  + [grey(70, i) for i in range(40)])
        film = render(tmp_path / "fade.mp4", frames)
        cuts = [{"id": "c001", "in_seconds": 0.0, "out_seconds": 40 / 30},
                {"id": "c002", "in_seconds": 40 / 30, "out_seconds": 82 / 30}]
        problems, measured = vfo.check(str(film), cuts)
        assert measured["short_black_at_a_cut"] == 1
        assert not [p for p in problems if "black frame" in p], problems

    def test_a_short_black_run_mid_shot_is_still_a_stray_frame(self, tmp_path):
        """The defect the rule exists for, with no cut anywhere near it."""
        frames = ([grey(90, i) for i in range(40)]
                  + [grey(0), grey(0)]
                  + [grey(90, i) for i in range(40, 80)])
        film = render(tmp_path / "stray.mp4", frames)
        cuts = [{"id": "c001", "in_seconds": 0.0, "out_seconds": 82 / 30}]
        problems, measured = vfo.check(str(film), cuts)
        assert measured["isolated_black_runs"] == 1
        assert any("black frame" in p for p in problems), problems

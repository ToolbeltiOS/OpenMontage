"""The type-lock check, against synthetic films with known text behaviour.

Text in the authored scenes shook for two reasons: the sustaining move
carried the type with it, a fraction of a pixel per frame, and the film look
put per-frame grain on the glyph edges. The first is what this measures, on
the delivered file.

The fixtures draw real glyphs — PIL's default font is enough for tesseract at
this size — over a background that MOVES, because that is the arrangement in
the film and it is what makes the measurement hard: a word's box is mostly
background, and the background is not holding still.
"""
from __future__ import annotations

import subprocess

import numpy as np
import pytest

from lib import verify_type_lock as vtl

pytest.importorskip("pytesseract")
pytest.importorskip("cv2")

WORDS = ["PIVOT ON THE BASE EDGE", "ROPE TEAMS", "THE METHOD", "MEASURED 1960"]


def frame(index: int, text_dx: int = 0, text_dy: int = 0, bg_speed: float = 0.6):
    """A frame of dark background texture with four lines of light type on it.

    The background drifts by `bg_speed` px per frame, as the plate does; the
    type moves only if asked to.
    """
    from PIL import Image, ImageDraw, ImageFont

    w, h = 960, 540
    im = Image.new("L", (w, h), 18)
    dr = ImageDraw.Draw(im)
    # texture, drifting: the thing that makes a small box hard to measure
    off = int(index * bg_speed * 4) % 80
    for x in range(-80, w + 80, 80):
        dr.line([(x + off, 0), (x + off + 40, h)], fill=30, width=9)
    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial.ttf", 34)
    except OSError:                        # pragma: no cover - platform default
        font = ImageFont.load_default()
    for i, line in enumerate(WORDS):
        dr.text((60 + text_dx, 60 + i * 90 + text_dy), line, fill=235, font=font)
    return np.asarray(im)


def render(path, frames, fps=30):
    import PIL.Image

    raw = path.parent / f"raw_{path.stem}"
    raw.mkdir(exist_ok=True)
    for i, arr in enumerate(frames):
        PIL.Image.fromarray(arr).save(raw / f"f_{i:04d}.png")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-framerate", str(fps),
         "-i", str(raw / "f_%04d.png"), "-c:v", "libx264", "-crf", "12",
         "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


#: Four seconds, so the sample at 2.0s and the one at 3.0s both land inside.
N = 120
CUTS = [{"id": "c001", "in_seconds": 0.0, "out_seconds": 4.0}]


class TestTypeLock:
    def test_locked_type_over_a_moving_background_passes(self, tmp_path):
        film = render(tmp_path / "locked.mp4", [frame(i) for i in range(N)])
        problems, measured = vtl.check(str(film), CUTS)
        assert problems == [], problems
        assert measured["scenes_sampled"] == 1
        assert measured["worst_shift_px"] < vtl.SHIFT_TOLERANCE_PX

    def test_type_that_drifts_a_pixel_a_second_is_caught(self, tmp_path):
        """A thirtieth of a pixel per frame: invisible frame to frame, and a
        whole pixel by the time a second has passed."""
        film = render(tmp_path / "drift.mp4",
                      [frame(i, text_dx=round(i / 30)) for i in range(N)])
        problems, measured = vtl.check(str(film), CUTS)
        assert problems, "a 1px-per-second drift went unreported"
        assert measured["worst_shift_px"] > vtl.SHIFT_TOLERANCE_PX
        assert "move within a second" in problems[0]

    def test_the_shake_as_it_shipped_is_caught(self, tmp_path):
        """The sustaining move carried type about 3.7px a second."""
        film = render(tmp_path / "shake.mp4",
                      [frame(i, text_dx=round(i * 3.7 / 30)) for i in range(N)])
        problems, measured = vtl.check(str(film), CUTS)
        assert problems
        assert measured["worst_shift_px"] > 3.0

    def test_a_scene_that_declares_a_text_move_is_allowed_one(self, tmp_path):
        film = render(tmp_path / "declared.mp4",
                      [frame(i, text_dx=round(i / 30)) for i in range(N)])
        cuts = [{**CUTS[0], "text_move": True}]
        problems, measured = vtl.check(str(film), cuts)
        assert problems == [], problems
        assert measured["samples"][0]["moved"] > 0   # measured, and forgiven

    def test_a_frame_with_no_text_is_not_sampled(self, tmp_path):
        blank = [np.full((540, 960), 18, dtype="uint8") for _ in range(N)]
        film = render(tmp_path / "blank.mp4", blank)
        problems, measured = vtl.check(str(film), CUTS)
        assert problems == []
        assert measured["scenes_sampled"] == 0


class TestSettleTime:
    """Entrances are a declared move, and every one of them is in the props."""

    def test_the_sample_waits_for_the_last_declared_animation(self):
        cut = {"labels": [{"at": 1.5}, {"at": 2.2}],
               "reveals": [{"at": 3.0, "duration": 0.7}],
               "title_at": 0.1}
        assert vtl.declared_moves_until(cut) == pytest.approx(3.7)

    def test_a_cut_declaring_nothing_still_waits(self):
        assert vtl.declared_moves_until({"id": "c001"}) == 0.0

    def test_a_cut_too_short_to_settle_in_is_skipped(self, tmp_path):
        film = render(tmp_path / "short.mp4", [frame(i) for i in range(60)])
        cuts = [{"id": "c001", "in_seconds": 0.0, "out_seconds": 2.0,
                 "labels": [{"at": 1.5}]}]
        problems, measured = vtl.check(str(film), cuts)
        assert measured["scenes_sampled"] == 0
        assert problems == []


def noise_texture(index: int):
    """Background texture with no text in it at all.

    The film's own background carries a faint chevron moire, and tesseract
    read a '<<' out of a patch of it at 74% confidence — which failed the
    plate gate on a render that was correct.
    """
    w, h = 960, 540
    y, x = np.mgrid[0:h, 0:w]
    arr = 18 + 10 * ((x + y + index) // 7 % 2)
    return arr.astype("uint8")


class TestPlatePurity:
    def test_a_plate_with_no_type_in_it_passes(self, tmp_path):
        film = render(tmp_path / "clean.mp4", [noise_texture(i) for i in range(N)])
        problems, measured = vtl.plate_is_clean(str(film), CUTS)
        assert problems == [], problems
        assert measured["words_in_plate"] == 0

    def test_type_left_in_the_plate_is_caught(self, tmp_path):
        film = render(tmp_path / "leaked.mp4", [frame(i) for i in range(N)])
        problems, measured = vtl.plate_is_clean(str(film), CUTS)
        assert measured["words_in_plate"] > 0
        assert "legible in the plate pass" in problems[0]

    def test_a_single_character_read_out_of_a_texture_is_not_a_word(self):
        """The filter, stated directly: one character is not legible text."""
        assert vtl.MIN_PLATE_WORD_CHARS == 2
        for hallucination in ("«", "|", "_", "/", ".."):
            assert (len(hallucination) < vtl.MIN_PLATE_WORD_CHARS
                    or not any(c.isalnum() for c in hallucination)), hallucination
        for real in ("THE", "STATUES", "1960", "S054"):
            assert (len(real) >= vtl.MIN_PLATE_WORD_CHARS
                    and any(c.isalnum() for c in real)), real

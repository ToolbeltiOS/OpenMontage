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

#: The cut the frames above are a render OF — so it asks for the words they
#: draw, the way a real cut does. Plate purity reads this to tell an element
#: that lost its type class from a word printed inside the photograph; a cut
#: that declares nothing would make every leak look like picture text. The
#: lines carry no `at`, so the type-lock sampling is unchanged.
CUTS = [{"id": "c001", "in_seconds": 0.0, "out_seconds": 4.0,
         "lines": [{"text": line} for line in WORDS]}]

#: The same four seconds of film, as a cut that never asked for any words:
#: an archival map, whose place names are in the picture and cannot be
#: tagged. This is the Easter Island case, which failed a correct render.
PICTURE_ONLY_CUTS = [{"id": "c085", "in_seconds": 0.0, "out_seconds": 4.0,
                      "source": "/proxies/wm_580033251.jpg",
                      "sourceLine": "wikimedia · Public domain"}]


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

    def test_words_the_cut_never_asked_for_are_the_picture(self, tmp_path):
        """The same leaked film, read against a cut with no authored text.

        Identical frames to `test_type_left_in_the_plate_is_caught`. The only
        difference is whether the cut asked for those words — which is the
        whole of the distinction between a missed element and an engraved
        place name.
        """
        film = render(tmp_path / "map.mp4", [frame(i) for i in range(N)])
        problems, measured = vtl.plate_is_clean(str(film), PICTURE_ONLY_CUTS)
        assert problems == [], problems
        assert measured["words_in_plate"] == 0
        assert measured["words_in_picture"] > 0, (
            "the reading must still be counted, or a plate that changed "
            "character would pass in silence")

    def test_a_single_character_read_out_of_a_texture_is_not_a_word(self):
        """The filter, stated directly: one character is not legible text."""
        assert vtl.MIN_PLATE_WORD_CHARS == 2
        for hallucination in ("«", "|", "_", "/", ".."):
            assert (len(hallucination) < vtl.MIN_PLATE_WORD_CHARS
                    or not any(c.isalnum() for c in hallucination)), hallucination
        for real in ("THE", "STATUES", "1960", "S054"):
            assert (len(real) >= vtl.MIN_PLATE_WORD_CHARS
                    and any(c.isalnum() for c in real)), real


class TestThePlateReadsThePictureToo:
    """Plate purity asks the cut, instead of assuming.

    The gate's premise was that anything legible in the plate is type that
    was missed. That is true of a film whose pictures are photographs. The
    Easter Island film is built from nineteenth-century maps and documents,
    where the PICTURE is covered in printed words: the gate read 32 of them
    — 'Cooks Bay', 'ANCIENT ROADS', 'RANO RARAKU', 'PHYSICAL' — and failed a
    film in which not one element had been missed. Twenty-eight of the 32
    were on bare sourced stills, cuts that carry no authored text at all and
    so cannot possibly have untagged type.

    Asking the cut separates them: a word the cut asked to be put on screen,
    found in the plate, is still the defect the gate was written for.
    """

    def test_a_word_the_picture_carries_is_not_a_missed_element(self):
        cut = {"id": "c085", "source": "/proxies/wm_580033251.jpg",
               "sourceLine": "wikimedia · Public domain",
               "actTitle": "A hundred and eleven people", "sceneIndex": "S 039"}
        for engraved in ("Cooks", "Bay", "PHYSICAL", "RARAKU", "Pérouse"):
            assert not vtl.plate_word_is_authored(engraved, cut), (
                f"{engraved!r} is printed on the map; no tagging removes it")

    def test_an_untagged_authored_word_still_fails(self):
        """The defect the gate exists for has to keep failing."""
        cut = {"id": "c058", "type": "document_reveal",
               "headline": "What it was for",
               "lines": [{"text": "“Easter Island is Earth writ small”", "at": 2.0}],
               "source": "Jared Diamond",
               "caption": "It travelled further than almost any other"}
        for authored in ("What", "Easter", "Diamond", "travelled"):
            assert vtl.plate_word_is_authored(authored, cut), (
                f"{authored!r} is a word this cut puts on screen — finding it "
                f"in the plate means it never got the type class")

    def test_a_diagnostic_field_is_never_a_word(self):
        """A field that explains a decision is not text on screen.

        `music_rise_reason` was added to cleared cuts and reads "bed not
        rising here (-0.162 sd/s against a floor of 0.02)". That put 'of'
        into the cut's authored words; OCR read 'of' off an 1886 map in the
        same cut; and plate purity failed a film that had not changed a
        frame. The rule is on the NAME, so the next `*_reason` added to a
        cut cannot do it again.
        """
        cut = {"id": "c083",
               "music_rise_reason": "bed not rising here (-0.162 sd/s "
                                    "against a floor of 0.02)",
               "reason": "meaning_change | act2_s037",
               "lead_reason": "landing: the picture holds through the air"}
        assert vtl.authored_words(cut) == set()
        for word in ("of", "bed", "rising", "landing", "picture", "holds"):
            assert not vtl.plate_word_is_authored(word, cut), word

    def test_a_filename_is_never_a_word(self):
        """`source` is a credit line on a document and a path on a still."""
        cut = {"id": "c085", "source": "/proxies/wm_580033251.jpg"}
        assert not vtl.plate_word_is_authored("wm_580033251", cut)
        assert not vtl.plate_word_is_authored("proxies", cut)

    def test_the_picture_text_is_counted_not_hidden(self):
        """A pass must still say what it read.

        A film whose plate suddenly reads a hundred picture words has
        changed, pass or not, so the number stays beside the verdict.
        """
        import inspect
        body = inspect.getsource(vtl.plate_is_clean)
        assert "words_in_picture" in body
        assert "picture_text" in body


class TestWhatTypeLockMeasures:
    """It measures our words, and only the ones big enough to measure.

    The Easter Island delivery failed on eight scenes, and not one of them
    was type that moved:

      - five on a single '/' out of twenty to thirty-two words, reading 0.66
        to 0.77px against a 0.65 tolerance. The scene-index chrome that '/'
        belongs to moved 0.004px over the same second, correlating at 0.95.
        A box around one glyph is mostly background, which the module header
        already gives as the reason the tolerance is not zero.
      - 'TUPAHOTU' moving 26px on c081, and '-' and 'e' moving 12px on c096.
        Both cuts are AUTHORED to move — a push and a pull — and both are
        pictures with print in them, a map and a filmed texture. The print
        travelled because the camera asked it to.

    Filtering to our own words cost nothing: 143 scenes sampled before and
    after, 3113 words still measured, worst shift 0.58px.
    """

    def test_one_glyph_is_not_a_measurable_target(self):
        for noise in ("/", "-", "e", "+", "|", "4"):
            assert not vtl.measurable(noise), noise
        for real in ("La", "1960", "TUPAHOTU", "S039"):
            assert vtl.measurable(real), real

    def test_chrome_is_type_and_is_measured(self):
        """The frame paints words. They are ours, and they must hold still."""
        cut = {"id": "c003", "sceneIndex": "S 003 / NEVER LEFT",
               "actTitle": "Never left", "sourceLine": "wikimedia · Public domain"}
        words = vtl.authored_words(cut, chrome=True)
        for painted in ("s", "003", "never", "left", "wikimedia"):
            assert painted in words, (
                f"{painted!r} is painted by the frame — type lock has to "
                f"measure it, or chrome that crawls goes unseen")

    def test_chrome_is_not_an_untagged_element(self):
        """Plate purity must not read the frame's own words as a leak."""
        cut = {"id": "c003", "sceneIndex": "S 003 / NEVER LEFT",
               "actTitle": "Never left"}
        assert "003" not in vtl.authored_words(cut)
        assert not vtl.plate_word_is_authored("003", cut)

    def test_a_word_the_picture_carries_is_not_measured(self):
        cut = {"id": "c081", "source": "/proxies/wm_348295582.jpg",
               "sceneIndex": "S 035"}
        assert "tupahotu" not in vtl.authored_words(cut, chrome=True)

    def test_type_that_moves_is_still_caught_after_the_filter(self, tmp_path):
        """The whole point of the gate, with the filter in place.

        Same fixture as `test_type_that_drifts_a_pixel_a_second_is_caught`;
        this asserts the filter did not quietly empty the measurement.
        """
        film = render(tmp_path / "drift.mp4",
                      [frame(i, text_dx=i / 30.0) for i in range(N)])
        problems, measured = vtl.check(str(film), CUTS)
        assert problems, "type that drifts a pixel a second is no longer caught"
        assert measured["scenes_with_movement"] == 1

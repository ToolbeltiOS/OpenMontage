"""Telling a plate from a page, in a scanned book.

A documentary wants the PLATES out of Petrie's 1883 Gizeh volume — the
sections, the plans, the measured drawings — which are perhaps twenty pages of
three hundred and are listed nowhere. Everything else is type.

The fixtures are built rather than fetched, so each threshold can be pinned
against a page whose character is known. The three that cost something to
learn are all here: a toned scan, a blank leaf with mottled paper, and a page
whose white scanner surround is brighter than its paper.
"""
from __future__ import annotations

import numpy as np
import pytest

from tools.video.stock_sources import archive_texts as at

pytest.importorskip("pytesseract")


def page(path, *, kind, paper=255, surround=None, size=(1200, 1600)):
    """One page scan. `kind` is what is printed on it."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = size
    image = Image.new("L", size, paper)
    draw = ImageDraw.Draw(image)
    if kind == "type":
        # REAL glyphs, because the thing being measured is what OCR reads.
        # Drawn as rectangles the "text" scored zero words, which is what a
        # plate looks like.
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Times New Roman.ttf", 30)
        except OSError:                    # pragma: no cover - platform default
            font = ImageFont.load_default()
        line = ("the casing stones were measured in place and their angle "
                "taken from the mean of nine")
        for row in range(34):
            draw.text((110, 110 + row * 42), line,
                      fill=max(0, paper - 220), font=font)
    elif kind == "plate":
        # a drawing: large shapes and long lines, almost no text
        draw.rectangle([150, 200, width - 150, height - 300],
                       outline=max(0, paper - 220), width=6)
        for i in range(14):
            draw.line([150, 200 + i * 70, width - 150, 260 + i * 70],
                      fill=max(0, paper - 200), width=5)
        draw.text((160, height - 240), "PLATE XI", fill=0)
    elif kind == "blank":
        rng = np.random.default_rng(3)
        mottle = rng.normal(0, 9, (height, width))
        image = Image.fromarray(
            np.clip(np.asarray(image, dtype="float32") + mottle, 0, 255
                    ).astype("uint8"))
    if surround is not None:
        framed = Image.new("L", (width + 300, height + 300), surround)
        framed.paste(image, (150, 150))
        image = framed
    image.convert("RGB").save(path, quality=92)
    return path


class TestTellingThemApart:
    def test_a_page_of_type_is_not_a_plate(self, tmp_path):
        measured = at.measure_page(page(tmp_path / "t.jpg", kind="type"))
        assert measured["words"] > at.MAX_WORDS_ON_A_PLATE
        assert not at.is_a_plate(measured)

    def test_a_plate_is(self, tmp_path):
        measured = at.measure_page(page(tmp_path / "p.jpg", kind="plate"))
        assert measured["words"] <= at.MAX_WORDS_ON_A_PLATE
        assert measured["ink"] >= at.MIN_INK_ON_A_PLATE
        assert at.is_a_plate(measured)

    def test_a_blank_leaf_is_not(self, tmp_path):
        measured = at.measure_page(page(tmp_path / "b.jpg", kind="blank"))
        assert measured["ink"] == 0.0
        assert not at.is_a_plate(measured)

    def test_both_tests_are_needed(self, tmp_path):
        """Ink alone keeps the dense pages; words alone keeps the blanks."""
        type_page = at.measure_page(page(tmp_path / "t2.jpg", kind="type"))
        blank = at.measure_page(page(tmp_path / "b2.jpg", kind="blank"))
        assert type_page["ink"] >= at.MIN_INK_ON_A_PLATE     # ink alone fails
        assert blank["words"] <= at.MAX_WORDS_ON_A_PLATE     # words alone fails
        assert not at.is_a_plate(type_page) and not at.is_a_plate(blank)


class TestTheThingsThatCostSomethingToLearn:
    def test_a_toned_scan_reads_as_type_not_as_a_plate(self, tmp_path):
        """Petrie's volume on the Archive is TWO scans in one item: a clean
        greyscale, and a colour scan whose paper sits at 170. Counting pixels
        darker than a constant measured the PAPER and called a page of
        numerical tables a plate."""
        toned = at.measure_page(page(tmp_path / "toned.jpg", kind="type", paper=175))
        assert toned["paper"] < 200, "the page's own paper level was not found"
        assert not at.is_a_plate(toned)

    def test_the_white_scanner_surround_is_not_the_paper(self, tmp_path):
        """With the surround in frame, 'the page's paper' taken over the whole
        scan came back 255 — the colour of the border — and the page itself
        measured as ink."""
        framed = at.measure_page(
            page(tmp_path / "framed.jpg", kind="type", paper=175, surround=255))
        assert framed["paper"] < 200
        assert not at.is_a_plate(framed)

    def test_a_blank_toned_leaf_is_not_a_plate(self, tmp_path):
        """It measured 0.35 ink, because the threshold is a fraction of the
        page's own contrast and that page's contrast was its own mottling.
        A page with no genuinely dark pixel has nothing printed on it."""
        measured = at.measure_page(
            page(tmp_path / "bt.jpg", kind="blank", paper=200, surround=255))
        assert measured["ink"] == 0.0
        assert not at.is_a_plate(measured)


class TestRights:
    def test_a_licence_url_is_preferred(self):
        assert at.rights_of({"metadata": {
            "licenseurl": "http://creativecommons.org/publicdomain/zero/1.0/",
            "possible-copyright-status": "NOT_IN_COPYRIGHT"}}).endswith("zero/1.0/")

    def test_not_in_copyright_is_the_archive_s_determination(self):
        from tools.video.stock_sources.licences import classify

        rights = at.rights_of({"metadata": {
            "possible-copyright-status": "NOT_IN_COPYRIGHT"}})
        assert rights == "NOT_IN_COPYRIGHT"
        assert classify(rights).permitted

    def test_a_scan_that_says_nothing_is_refused(self):
        from tools.video.stock_sources.licences import classify

        assert at.rights_of({"metadata": {}}) == ""
        assert not classify("").permitted


class TestTimeout:
    def test_the_search_waits_a_minute(self):
        """Both Archive search endpoints timed out during this work and
        answered in 0.42s an hour later. A short timeout turns a slow day
        into an empty catalogue."""
        assert at.TIMEOUT_S >= 60

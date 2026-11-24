"""A credit is a licence obligation, so the name has to be the name.

TWO DEFECTS, PUBLISHED ON SIX FILMS
-----------------------------------
`lib/asset_bank` read Wikimedia's `Artist` field with

    re.sub("<[^>]+>", "", value).strip()

which deletes tags instead of separating them and never decodes an entity.
Across the six delivered films' banks that produced:

  * 30 doubled names — "Unknown authorUnknown author or not provided" (14)
    and "Unknown authorUnknown author" (16). Commons renders an unknown
    author as a short visible label beside a longer machine-readable one,
    and the two closed up into one word with no space at the seam.
  * 21 encoded names — "Harris &amp; Ewing, photographer".

Every one of them went onto a published credits page and into a pinned
comment. Nothing about the licences was wrong; the names were.

THE REPAIR RUNS IN TWO PLACES AND IS ONE FUNCTION
-------------------------------------------------
At the fetcher, so new banks are clean, and in
`build_listing.credits_rows`, because six banks on disk already hold the
old strings and nobody is going to re-fetch 991 assets to repair a name.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "scripts"))

from asset_bank import plain                                   # noqa: E402
import build_listing as BL                                     # noqa: E402


class TestTheDoubling:
    @pytest.mark.parametrize("raw,want", [
        ("Unknown authorUnknown author or not provided",
         "Unknown author or not provided"),
        ("Unknown authorUnknown author", "Unknown author"),
        ("<a>Unknown author</a><span>Unknown author or not provided</span>",
         "Unknown author or not provided"),
    ])
    def test_the_exact_strings_six_films_published(self, raw, want):
        assert plain(raw) == want

    def test_tags_separate_rather_than_vanish(self):
        assert plain("<a>Olaf</a><span>Tausch</span>") == "Olaf Tausch"

    def test_a_camel_cased_name_is_not_a_doubling(self):
        """THE SAFETY RULE. A seam is only accepted when splitting on it
        reveals an exact repetition, so a real name survives."""
        for name in ("McDonald", "LaPerouse", "MacGregor", "DeWitt",
                     "van der MeerVan", "iPhone"):
            assert plain(name) == name

    def test_a_repetition_that_is_really_there_is_left_alone(self):
        """Two separate words that happen to repeat, with a space already
        between them, are the artist's own spelling."""
        assert plain("rawpixel.com rawpixel") == "rawpixel.com rawpixel"
        assert plain("Florian Klauer florianklauer") == (
            "Florian Klauer florianklauer")


class TestTheEntities:
    def test_an_ampersand_is_an_ampersand(self):
        assert plain("Harris &amp; Ewing, photographer") == (
            "Harris & Ewing, photographer")

    def test_other_entities_decode_too(self):
        assert plain("Mus&eacute;e d&#39;Orsay") == "Musée d'Orsay"


class TestItIsOneRuleAndNotACopy:
    def test_the_fetcher_uses_it(self):
        src = (ROOT / "lib" / "asset_bank.py").read_text()
        assert 'plain((meta.get("Artist")' in src
        assert 'plain((meta.get("Credit")' in src
        assert 're.sub("<[^>]+>", "", (meta' not in src

    def test_the_credits_reader_uses_the_same_function(self):
        src = (ROOT / "scripts" / "build_listing.py").read_text()
        assert "from asset_bank import plain" in src
        assert 'artist = plain(' in src

    def test_a_bank_row_with_the_old_string_renders_clean(self, tmp_path):
        """END TO END over a bank as it exists on disk today."""
        import json
        art = tmp_path
        (art / "asset_bank.json").write_text(json.dumps({"subjects": {
            "s1": {"assets": [{
                "asset_id": "wm_52092619",
                "artist": "Unknown authorUnknown author or not provided",
                "licence": "Public domain",
                "credit": "Harris &amp; Ewing",
                "page": "https://commons.wikimedia.org/wiki/File:X.jpg"}]}}}))
        props = {"cuts": [{"id": "c124",
                           "backgroundImage": "/proxies/wm_52092619.jpg"}]}
        rows, _att = BL.credits_rows(art, props)
        assert len(rows) == 1
        assert rows[0]["artist"] == "Unknown author or not provided"
        assert rows[0]["notice"] == "Harris & Ewing"

    def test_an_empty_artist_still_reads_as_not_supplied(self, tmp_path):
        import json
        (tmp_path / "asset_bank.json").write_text(json.dumps({"subjects": {
            "s1": {"assets": [{"asset_id": "wm_1", "artist": "",
                               "licence": "CC0", "page": "p"}]}}}))
        rows, _ = BL.credits_rows(
            tmp_path, {"cuts": [{"id": "c1", "image": "/x/wm_1.jpg"}]})
        assert rows[0]["artist"] == "(not supplied)"


class TestTheDeliveredBanks:
    @pytest.mark.parametrize("slug", [
        "king-tut", "atomic-bombings-of-hiroshima-and-nagasaki",
        "attack-on-pearl-harbor"])
    def test_no_delivered_film_still_credits_a_doubled_name(self, slug):
        import json
        art = Path("/Users/mac/Developer/wak3up-docs/runner/projects") / slug \
            / "artifacts"
        props = art / "render_props.json"
        if not props.exists():
            pytest.skip(f"{slug} has no render_props on this machine")
        rows, _ = BL.credits_rows(art, json.loads(props.read_text()))
        assert rows
        bad = [r["artist"] for r in rows
               if r["artist"].count("Unknown author") > 1
               or "&amp;" in r["artist"] or "&amp;" in r["notice"]]
        assert bad == []

"""The licence filter, tested in both directions.

The channel is monetised and the films are re-cut, so NonCommercial and
NoDerivatives are both unusable. Every NC and ND string also contains "BY",
so a substring check for "CC BY" accepts exactly the licences that must be
refused. That is the failure these tests exist to prevent.
"""
from __future__ import annotations

import pytest

from tools.video.stock_sources.licences import classify, filter_candidates, is_permitted


class TestPermitted:
    @pytest.mark.parametrize("text", [
        "CC0", "CC0 1.0", "CC0 1.0 Universal", "Creative Commons Zero",
        "Public Domain", "Public Domain Mark 1.0", "pdm",
        "No Known Copyright Restrictions",
        "CC BY", "CC BY 4.0", "cc-by-4.0", "Creative Commons Attribution 3.0",
        "CC BY-SA", "CC BY-SA 4.0", "cc_by_sa", "Attribution-ShareAlike",
    ])
    def test_these_are_usable(self, text):
        assert is_permitted(text), text


class TestRefused:
    @pytest.mark.parametrize("text", [
        "CC BY-NC", "CC BY-NC 4.0", "CC BY-NC-SA 4.0", "CC BY-NC-ND 4.0",
        "Creative Commons Attribution-NonCommercial",
        "cc-by-nc-sa", "CC BY-ND", "CC BY-ND 4.0",
        "Creative Commons Attribution-NoDerivatives",
        "In Copyright", "All Rights Reserved",
        "In Copyright - Educational Use Permitted",
        "Editorial use only", "rights reserved",
    ])
    def test_these_are_not(self, text):
        assert not is_permitted(text), text

    def test_an_nc_string_is_not_read_as_cc_by(self):
        """The whole point: "CC BY-NC-SA 4.0" contains both "CC BY" and "SA"."""
        assert classify("CC BY-NC-SA 4.0").code == "CC-BY-NC"

    def test_an_nd_string_is_not_read_as_cc_by(self):
        assert classify("CC BY-ND 4.0").code == "CC-BY-ND"


class TestUnknownIsNotPermission:
    @pytest.mark.parametrize("text", ["", None, "   ", "Museum Licence",
                                      "Open Access", "Free to use"])
    def test_an_unrecognised_string_is_refused(self, text):
        assert not is_permitted(text)
        assert classify(text).code in {"UNKNOWN", "RESTRICTED"}

    def test_the_rejected_string_is_kept_for_reading(self):
        """A missing pattern should surface as a rejection, not as silence."""
        assert classify("Some Museum Terms v2").raw == "Some Museum Terms v2"


class FakeCandidate:
    def __init__(self, licence):
        self.license = licence
        self.extra = {}


class TestFilterAtFetchTime:
    def test_only_permitted_survive(self):
        cands = [FakeCandidate(x) for x in
                 ["CC0", "CC BY-NC 4.0", "CC BY-SA 4.0", "In Copyright", ""]]
        kept = filter_candidates(cands)
        assert [c.license for c in kept] == ["CC0", "CC BY-SA 4.0"]

    def test_the_family_is_recorded_not_the_spelling(self):
        kept = filter_candidates([FakeCandidate("cc-by-sa-4.0")])
        assert kept[0].extra["licence_code"] == "CC-BY-SA"
        assert kept[0].extra["share_alike"] is True
        assert kept[0].extra["attribution_required"] is True

    def test_public_domain_needs_no_attribution(self):
        kept = filter_candidates([FakeCandidate("Public Domain")])
        assert kept[0].extra["attribution_required"] is False

    def test_rejections_are_reported(self):
        seen = []
        filter_candidates([FakeCandidate("CC BY-NC 4.0"), FakeCandidate("")],
                          on_reject=lambda c, l: seen.append(l.code))
        assert seen == ["CC-BY-NC", "UNKNOWN"]


class TestPixabay:
    """A licence that is permissive and is not one of the four families.

    It matters because 28 assets already in the bank carry it — the whole
    `elemental_texture` subject — and because calling it UNKNOWN would claim
    we could not read it when we can read it perfectly well.
    """

    RAW = "Pixabay Content License (free, no attribution required)"

    def test_it_is_recognised_rather_than_unknown(self):
        from tools.video.stock_sources.licences import classify

        assert classify(self.RAW).code == "PIXABAY"

    def test_it_is_commercial_and_derivable(self):
        from tools.video.stock_sources.licences import classify

        licence = classify(self.RAW)
        assert licence.commercial and licence.derivatives
        assert not licence.attribution and not licence.share_alike

    def test_it_is_permitted_by_the_owner_s_decision(self):
        """Admitted 2026-10-21, as a NAMED licence and not folded into CC0."""
        from tools.video.stock_sources.licences import PERMITTED, PERMITTED_EXTRA, classify

        assert "PIXABAY" in PERMITTED_EXTRA
        assert "PIXABAY" not in PERMITTED      # named, not a CC family
        assert classify(self.RAW).permitted

    def test_admitting_it_admitted_nothing_else(self, monkeypatch):
        from tools.video.stock_sources import licences

        assert not licences.classify("CC BY-NC 4.0").permitted
        assert not licences.classify("CC BY-ND 4.0").permitted
        assert not licences.classify("").permitted
        assert not licences.classify("In copyright").permitted

    def test_its_scope_is_narrower_than_cc0_and_recorded(self):
        """Permitted is one bit; a licence is not.

        Pixabay allows use WITHIN a produced video and not redistribution of
        the asset on its own. Nothing the pipeline does breaches that, but a
        future step that publishes assets rather than films would.
        """
        from tools.video.stock_sources.licences import use_scope

        pixabay = use_scope("PIXABAY")
        assert pixabay["in_produced_video"] is True
        assert pixabay["commercial"] is True
        assert pixabay["standalone_redistribution"] is False
        assert use_scope("CC0")["standalone_redistribution"] is True

    def test_the_scope_is_carried_onto_the_asset(self):
        from dataclasses import dataclass, field

        from tools.video.stock_sources.licences import filter_candidates

        @dataclass
        class _C:
            license: str
            extra: dict = field(default_factory=dict)

        pixabay, cc0 = _C(self.RAW), _C("CC0 1.0")
        filter_candidates([pixabay, cc0])
        assert pixabay.extra["no_standalone_redistribution"] is True
        assert "no_standalone_redistribution" not in cc0.extra

    def test_attribution_is_unchanged_by_admitting_it(self):
        """Pixabay asks for none, and admitting it asks for none."""
        from tools.video.stock_sources.licences import classify

        assert classify(self.RAW).attribution is False

    def test_it_is_not_mistaken_for_cc0(self):
        """Its own text says 'free' and 'no attribution', which is CC0's shape."""
        from tools.video.stock_sources.licences import classify

        assert classify(self.RAW).code != "CC0"
        assert classify("CC0 1.0 Universal").code == "CC0"

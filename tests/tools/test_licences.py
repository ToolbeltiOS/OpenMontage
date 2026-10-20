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

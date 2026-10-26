"""Membership in the subject's OWN category is evidence; a match is not.

`_usable` applied one filename test to two different things: the members of a
category curated as this subject, and the results of a fuzzy text search. The
second needs it — searching Commons for "Durupınar" returns photographs of
Mount Ararat. The first does not, and the test was destructive there:
`Category:Durupınar Site` holds thirteen photographs named in Turkish, Polish
and Czech, the filename test kept ONE, and the subject was reported as
unsourceable at 0.5 usable assets against a floor of 8.

A film was about to be re-planned around satellite imagery for a subject that
has thirteen CC BY photographs, four of them over 3,800 pixels wide.
"""
from __future__ import annotations

from lib import source_depth as sd


class TestWhichCategoryIsTheSubjectsOwn:
    def test_an_exact_title_is_the_subject(self):
        assert sd._is_own_category("Mount Ararat", "Mount Ararat")

    def test_a_generic_trailing_noun_is_still_the_subject(self):
        assert sd._is_own_category("Durupınar", "Durupınar Site")
        assert sd._is_own_category("durupınar", "Durupınar site")

    def test_a_parenthetical_qualifier_is_a_different_subject(self):
        """INJECTED: the hill in South Africa.

        `find_categories` returns it for "Mount Ararat" because it contains
        every significant word, and its farm photographs are not this film.
        """
        assert not sd._is_own_category("Mount Ararat",
                                       "Mount Ararat (Free State)")
        assert not sd._is_own_category("Mount Ararat",
                                       "Mount Ararat Baptist Church")

    def test_an_unrelated_title_is_not_the_subject(self):
        assert not sd._is_own_category("Great Pyramid",
                                       "Plates from Piazzi Smyth 1877")


class TestTheTwoFilters:
    FILES = ["File:Arka Noego - Üzengili.jpg", "File:Noemova archa (01).jpg",
             "File:NuhunGemisi.jpg", "File:The Durupinar site in 2019.jpg",
             "File:notes.pdf"]

    def test_media_keeps_every_picture_whatever_it_is_called(self):
        kept = sd._media(self.FILES)
        assert len(kept) == 4, kept
        assert "notes.pdf" not in kept

    def test_the_name_test_discards_all_four(self):
        """Which is correct for a search result and wrong for a member.

        It keeps NONE of them, and the last one is the second reason why: the
        entity is spelled with a Turkish ı and the English filename uses an
        ASCII i, so even the file that names the subject in English does not
        match the needle.
        """
        assert sd._usable(self.FILES, "Durupınar") == []

    def test_the_diacritic_alone_loses_the_english_filename(self):
        english = ["File:The Durupinar site in 2019.jpg"]
        assert sd._usable(english, "Durupınar") == []
        assert sd._usable(english, "Durupinar") == [
            "The Durupinar site in 2019.jpg"]

    def test_the_two_disagree_by_the_whole_finding(self):
        assert len(sd._media(self.FILES)) == 4
        assert len(sd._usable(self.FILES, "Durupınar")) == 0


class TestTheWikidataLookupDeclinesRatherThanGuessing:
    """wbsearchentities returns the NEAREST item, which is a different
    question from the same item.

    Measured: "Ark van Noach" — the 2012 Dutch full-scale build — returns
    Q7747, "Noah's Ark", because the Dutch phrase is an alias of the biblical
    vessel. Counting that category would have credited the build with 56
    files of a different subject.
    """

    def test_an_inexact_label_is_refused(self, monkeypatch):
        calls = {}

        def fake_get(params, timeout=30, api=None):
            calls["action"] = params.get("action")
            return {"search": [{"id": "Q7747", "label": "Noah's Ark"}]}

        monkeypatch.setattr(sd, "_get", fake_get)
        assert sd.commons_category("Ark van Noach") is None

    def test_an_exact_label_is_accepted(self, monkeypatch):
        def fake_get(params, timeout=30, api=None):
            if params.get("action") == "wbsearchentities":
                return {"search": [{"id": "Q1267546",
                                    "label": "Durupınar site"}]}
            return {"entities": {"Q1267546": {
                "claims": {"P373": [{"mainsnak": {"datavalue": {
                    "value": "Durupınar Site"}}}]}, "sitelinks": {}}}}

        monkeypatch.setattr(sd, "_get", fake_get)
        assert sd.commons_category("Durupınar site") == "Durupınar Site"

    def test_a_network_failure_is_not_an_answer(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("offline")

        monkeypatch.setattr(sd, "_get", boom)
        assert sd.commons_category("anything") is None

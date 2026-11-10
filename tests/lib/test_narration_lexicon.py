"""The narration lexicon: every respelling must be a word, not a notation.

WHY THIS FILE EXISTS
--------------------
Version 1 of the lexicon respelled names in the style a dictionary uses —
"kar-NAR-von", "too-tan-KAH-moon", "er-ih-SIP-uh-las". A dictionary's reader
knows that is a notation. A synthesiser does not: it read the hyphens as
pauses and the capitals as emphasis and said the notation out loud, mid
sentence. On 2026-11-10 that lost an A/B against the take with no lexicon
at all.

The fix is not a better notation, it is no notation: a lowercase string of
letters that looks like an ordinary English word. Kokoro says
"tootankahmoon" as Tutankhamun. These tests are what keep a later editor
from reaching for the dictionary style again, because it is the obvious
thing to reach for and it is wrong.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LEXICON = ROOT / "assets" / "narration" / "lexicon.json"


@pytest.fixture(scope="module")
def lexicon() -> dict:
    assert LEXICON.exists(), f"the lexicon is missing: {LEXICON}"
    return json.loads(LEXICON.read_text())


@pytest.fixture(scope="module")
def entries(lexicon) -> list[dict]:
    assert lexicon["entries"], "an empty lexicon is a mistake, not a state"
    return lexicon["entries"]


class TestEveryValueIsLettersOnly:
    """THE RULE. Everything else in this file is a corollary of it."""

    def test_every_say_value_is_letters_only(self, entries):
        bad = [e for e in entries if not re.fullmatch(r"[a-zA-Z]+", e["say"])]
        assert not bad, [(e["word"], e["say"]) for e in bad]

    def test_no_hyphens(self, entries):
        """A hyphen is read as a pause. "kar-NAR-von" became "car. Na-von"."""
        assert not [e for e in entries if "-" in e["say"]]

    def test_no_capitals(self, entries):
        """A capital inside a word is read as emphasis, or spelled out."""
        assert not [e for e in entries if e["say"] != e["say"].lower()]

    def test_no_stress_or_phoneme_marks(self, entries):
        """IPA, slashes, dots and brackets are all spoken aloud by this path.

        Handed misaki's [word](/ipa/) form, Kokoro said "slash
        second-restress TU-length and T-Schwar". The syntax belongs to the
        kokoro/misaki python pipeline; hyperframes tts is kokoro-onnx with
        an espeak phonemizer and has no phoneme input at all.
        """
        for mark in "ˈˌː/.()[]' ":
            assert not [e for e in entries if mark in e["say"]], mark


class TestTheWordSideIsUntouched:
    """The script keeps its real spelling; only what is SPOKEN changes.

    The written word reaches the captions, the transcript and the fact gate.
    A lexicon that rewrote the script would put "tootankahmoon" on screen.
    """

    def test_the_word_is_spelled_as_a_reader_expects(self, entries):
        for e in entries:
            assert re.fullmatch(r"[A-Za-z'\- ]+", e["word"]), e["word"]

    def test_the_respelling_differs_from_the_word(self, entries):
        """An entry that changes nothing is noise in a file read by hand."""
        for e in entries:
            if e["respelled"]:
                assert e["say"].lower() != e["word"].lower(), e["word"]


class TestEveryEntryIsEvidenced:
    """A lexicon grows until it is doing harm. Each entry pays its way.

    Version 1 respelled 19 names because they looked foreign. Only six of
    them were actually misheard; the other thirteen were respelled into a
    notation that then got read aloud. So an entry must name the thing the
    transcriber actually said.
    """

    def test_each_respelling_records_what_was_misheard(self, entries):
        for e in entries:
            if not e["respelled"]:
                continue
            assert e.get("misheard_as"), e["word"]
            assert e["misheard_as"].lower() != e["word"].lower(), e["word"]

    def test_each_entry_says_why(self, entries):
        for e in entries:
            assert len(e.get("why", "")) > 20, e["word"]

    def test_names_that_were_heard_correctly_are_absent(self, entries):
        """Correct pronunciation, conventional spelling. Not a mishearing.

        Saqqara came back "Sakara" and haematopoietic came back
        "hematopoietic". Respelling either one would replace a correct
        reading with a guess.
        """
        listed = {e["word"].lower() for e in entries}
        for ok in ("saqqara", "haematopoietic", "reid", "bethell",
                   "fellowes", "giza", "flavus", "carnarvon"):
            assert ok not in listed, ok


class TestApplicationIsWholeWordAndCaseInsensitive:
    """How the substitution is made, which is where the last bug would hide."""

    def apply(self, text: str, entries: list[dict]) -> str:
        for e in entries:
            if e["respelled"]:
                text = re.sub(rf"\b{re.escape(e['word'])}\b", e["say"], text)
        return text

    def test_a_name_is_replaced(self, entries):
        out = self.apply("The tomb of Tutankhamun was opened.", entries)
        assert "tootankahmoon" in out
        assert "Tutankhamun" not in out

    def test_a_possessive_is_replaced(self, entries):
        """"Tutankhamun's" was the worst mishearing in the take."""
        out = self.apply("Tutankhamun's priests sealed it.", entries)
        assert out.startswith("tootankahmoon's")

    def test_a_word_merely_containing_a_name_is_left_alone(self, entries):
        """\\b, not a bare replace: "Gouldian" is not Gould."""
        assert self.apply("A Gouldian finch.", entries) == "A Gouldian finch."

    def test_the_replacement_is_not_itself_replaced(self, entries):
        """Applying twice must give the same string as applying once."""
        once = self.apply("Geiger counters near Tutankhamun.", entries)
        assert self.apply(once, entries) == once

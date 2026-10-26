"""Every factual sentence carries a ledger claim, and the claim has a source.

Calibrated on the two delivered films, which is where the finding came from:

  they-said-it-couldnt-be-built   205 sentences, 114 need a claim,  2 uncovered
  easter-island                   182 sentences, 112 need a claim, 30 uncovered

Run #1's two are its sign-off. Easter Island's thirty are act 4 ENTIRE — all
twenty-eight of its factual sentences — plus the same sign-off, because act
4's `source_ref` cites c32 and c46 to c58 against a fifteen-claim ledger.
Forty-two of the fifty-four ids that film cites do not exist under any
reading.
"""
from __future__ import annotations

import pytest

from lib import verify_fact_coverage as fc

LEDGER = {"data_points": [
    {"claim": "The cliff drops 300 m.", "source_url": "https://example.test/a"},
    {"claim": "Fifty-three houses.", "source_url": "https://example.test/b"},
    {"claim": "No source here.", "source_url": ""},
]}


def script_of(text: str, **section):
    return {"sections": [{"id": "act1", "text": text, **section}]}


class TestWhatCountsAsAFactualSentence:
    def _t(self, sentence):
        return fc.triggers(sentence, "capitalisation")

    def test_a_year_is_a_date(self):
        assert "date" in self._t("George Smith read it in 1872.")

    def test_a_month_is_a_date(self):
        assert "date" in self._t("It happened in March that year.")

    def test_digits_are_a_number(self):
        assert "<digits>" in self._t("It is 3.9 hectares.")["number"]

    def test_a_number_spelled_out_is_still_a_number(self):
        """The channel spells them out; a digits-only rule sees none of them.

        Measured on the delivered films, this is the overwhelming majority of
        every figure in the catalogue.
        """
        got = self._t("Three hundred and ninety-four are unfinished.")
        assert "number" in got
        assert "hundred" in got["number"]

    def test_a_quotation_is_a_claim(self):
        assert "quotation" in self._t(
            'He called it “a problem of transport” in his report.')

    def test_a_proper_noun_is_a_claim(self):
        assert "Orongo" in self._t("The village at Orongo.")["proper_noun"]

    def test_a_sentence_with_none_of_them_needs_nothing(self):
        assert self._t("But nobody can say why.") == {}

    def test_the_whitelist_is_short_enough_to_mean_something(self):
        """Every word here is a word the gate stops asking about."""
        assert len(fc.WHITELIST) < 80


class TestTheLedger:
    def test_ids_are_positional_when_the_ledger_has_none(self):
        book = fc.ledger(LEDGER)
        assert sorted(book) == ["c01", "c02", "c03"]

    def test_an_explicit_id_wins(self):
        book = fc.ledger({"data_points": [{"id": "c42", "claim": "x"}]})
        assert list(book) == ["c42"]

    def test_ids_are_read_out_of_a_free_text_source_ref(self):
        assert fc.cited_in("research_brief claim ledger c17, c07 — path.json") \
            == ["c17", "c07"]

    def test_a_claims_list_is_read_directly(self):
        assert fc.cited_in(["c01", "C02"]) == ["c01", "c02"]


class TestCoverage:
    def test_a_sourced_claim_covers_the_sentence(self):
        problems, m = fc.check(
            script_of("Fifty-three houses stood there.", claims=["c02"]),
            LEDGER, "capitalisation")
        assert problems == [], problems
        assert m["sentences_uncovered"] == 0

    def test_a_claim_with_no_source_url_does_not(self):
        problems, _ = fc.check(
            script_of("Fifty-three houses stood there.", claims=["c03"]),
            LEDGER, "capitalisation")
        assert problems, "a claim with an empty source_url was accepted"

    def test_an_id_that_does_not_resolve_does_not(self):
        """INJECTED: the defect in the published film.

        act 4 cites c46 to c58 against a fifteen-claim ledger.
        """
        problems, m = fc.check(
            script_of("Fifty-three houses stood there.", claims=["c58"]),
            LEDGER, "capitalisation")
        assert problems
        assert "none resolve" in problems[0]
        assert m["ids_that_do_not_resolve"] == ["c58"]

    def test_citing_nothing_does_not(self):
        problems, _ = fc.check(
            script_of("Fifty-three houses stood there."), LEDGER,
            "capitalisation")
        assert problems and "cites nothing" in problems[0]

    def test_a_sentence_with_no_facts_needs_no_claim(self):
        problems, m = fc.check(script_of("But nobody can say why."),
                               LEDGER, "capitalisation")
        assert problems == []
        assert m["sentences_needing_a_claim"] == 0


class TestWhereTheClaimsAreLookedFor:
    def test_the_paragraph_wins_over_the_section(self):
        script = {"sections": [{
            "id": "act1", "text": "Fifty-three houses stood there.",
            "claims": ["c58"],
            "paragraphs": [{"text": "...", "claims": ["c02"]}],
        }]}
        problems, m = fc.check(script, LEDGER, "capitalisation")
        assert problems == [], problems
        assert m["attribution_levels"] == ["paragraph"]

    def test_the_section_is_used_when_the_paragraph_has_none(self):
        _, m = fc.check(script_of("Fifty-three houses.", claims=["c02"]),
                        LEDGER, "capitalisation")
        assert m["attribution_levels"] == ["section"]

    def test_the_weaker_level_is_reported_as_such(self):
        """A pass at section level is not a pass at the level asked for."""
        _, m = fc.check(script_of("Fifty-three houses.",
                                  source_ref="ledger c02 — x.json"),
                        LEDGER, "capitalisation")
        assert m["attribution_levels"] == ["section"]


class TestTheDetectorIsNotSwappedQuietly:
    def test_the_substitute_only_over_flags(self):
        """Its count is an UPPER bound on what spaCy would find.

        It calls any non-whitelisted capitalised word a proper noun, which is
        wrong about "Something" and right about "Noah". The error direction
        matters: a false positive asks for a citation that was not strictly
        required; a false negative lets an unsourced claim through.
        """
        got = fc._propn_capitalised("Something else was happening.")
        assert got == ["Something"], got

    def test_the_whitelist_catches_the_common_openers(self):
        assert fc._propn_capitalised("The village was empty.") == []
        assert fc._propn_capitalised("Almost every statue came from there.") == []

    def test_the_report_names_which_backend_ran(self):
        _, m = fc.check(script_of("x"), LEDGER, "capitalisation")
        assert m["backend"] == "capitalisation"

    def test_the_runner_names_it_too_rather_than_defaulting_in_silence(self):
        from pathlib import Path

        body = Path("scripts/run_weekly.sh").read_text()
        assert "FACT_BACKEND=" in body
        assert "--backend \"$FACT_BACKEND\"" in body
        assert "DELETE THIS LINE" in body, (
            "the substitute has to be visibly temporary")


class TestItBlocksBeforeTheHuman:
    def test_the_runner_runs_it_before_the_script_gate(self):
        from pathlib import Path

        body = Path("scripts/run_weekly.sh").read_text()
        assert body.index("verify_fact_coverage.py") < body.index(
            'say "script gate')

    def test_a_failure_fails_the_run(self):
        from pathlib import Path

        body = Path("scripts/run_weekly.sh").read_text()
        i = body.index("verify_fact_coverage.py")
        assert 'fail "fact coverage"' in body[i:i + 400]

    def test_the_prompt_tells_the_stage_what_is_required(self):
        from pathlib import Path

        body = Path("scripts/run_weekly.sh").read_text()
        assert "EVERY FACTUAL SENTENCE MUST BE ATTRIBUTED" in body
        assert "Do not invent a claim id" in body


class TestSentenceAndParagraphSplitting:
    def test_production_markers_are_not_narration(self):
        got = fc.sentences("[beat: exposition | awe]\nIt was there.\n[air 1.5s]")
        assert got == ["It was there."]

    def test_paragraphs_split_on_blank_lines(self):
        assert len(fc.paragraphs("one\n\ntwo\n\n\nthree")) == 3

    def test_a_sentence_ending_in_a_number_is_not_split(self):
        got = fc.sentences("It is 3.9 hectares. Nobody lives there.")
        assert len(got) == 2, got

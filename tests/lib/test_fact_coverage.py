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

    def test_the_runner_names_the_backend_rather_than_defaulting_in_silence(self):
        """It is spaCy now; en_core_web_sm was installed 2026-10-26.

        The line stays, naming the backend explicitly, so that any future
        substitution appears in the log of every run that uses it rather than
        inside a default argument nobody reads.
        """
        from pathlib import Path

        body = Path("scripts/run_weekly.sh").read_text()
        assert 'FACT_BACKEND="${FACT_BACKEND:-spacy}"' in body
        assert '--backend "$FACT_BACKEND"' in body

    def test_the_substitute_is_still_there_for_a_machine_without_the_model(self):
        assert "capitalisation" in fc.BACKENDS
        assert "spacy" in fc.BACKENDS


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


class TestExemptBySectionTypeNotBySentence:
    """A per-sentence whitelist turns the gate off one line at a time, and the
    line that most wants exempting is always the one that most needs checking.

    The outro asserts nothing about the world — it is the sign-off, and it
    trips the gate only because it contains numerals. Both delivered films
    fail on exactly those two sentences and on nothing else outside act 4.
    """

    def test_the_outro_is_exempt(self):
        assert "outro" in fc.exempt_sections({})

    def test_the_cold_open_is_not(self):
        assert "cold_open" not in fc.exempt_sections({})
        assert "cold_open" in fc.NEVER_EXEMPT

    def test_the_playbook_is_where_the_list_lives(self):
        import yaml

        pb = yaml.safe_load(open("styles/wak3up-documentary.yaml",
                                 encoding="utf-8"))
        assert pb["fact_gate"]["exempt_sections"] == ["outro"]
        assert "cold_open" in pb["fact_gate"]["never_exempt"]
        assert pb["fact_gate"]["exempt_reason"]["outro"]

    def test_a_playbook_exempting_the_argument_is_refused(self):
        """INJECTED: the list must not be a way to switch the gate off.

        Exempting a section that carries the argument is a change to the
        module, in a commit, with a reason — not an entry in a list.
        """
        with pytest.raises(SystemExit, match="carry the film's argument"):
            fc.exempt_sections({"fact_gate": {
                "exempt_sections": ["outro", "cold_open"]}})

    def test_an_exempt_section_is_not_examined_at_all(self):
        script = {"sections": [
            {"id": "outro", "text": "Four open files, and we closed one."},
            {"id": "act1", "text": "Fifty-three houses.", "claims": ["c02"]},
        ]}
        problems, m = fc.check(script, LEDGER, "capitalisation", {})
        assert problems == []
        assert m["exempt_sections"] == ["outro"]
        assert all(r["section"] != "outro" for r in m["rows"])

    def test_the_cold_open_is_still_examined(self):
        script = {"sections": [
            {"id": "cold_open", "text": "Fifty-three houses stood there."}]}
        problems, _ = fc.check(script, LEDGER, "capitalisation", {})
        assert problems, "the cold open was not checked"


class TestClaimIdsMayCarryAPrefix:
    """A repair's ids are not c-numbers, and the pattern has to know that.

    Numbering a repair in the c-space risks colliding with an id the script
    already cites — on easter-island, c16-c41 would have made c32 resolve,
    and c32 is one of act 4's fourteen dangling citations. So the repair uses
    r01-r26, and a pattern that only matched `c` read a section citing all
    twenty-six as citing nothing at all.
    """

    def test_an_r_id_is_read_out_of_prose(self):
        assert fc.cited_in("claim ledger r01, r26 — brief.json") == ["r01", "r26"]

    def test_c_ids_still_work(self):
        assert fc.cited_in("ledger c07, c12") == ["c07", "c12"]

    def test_both_at_once(self):
        assert fc.cited_in("c01 and r09") == ["c01", "r09"]

    def test_a_repair_id_resolves_when_the_ledger_carries_it(self):
        book = fc.ledger({"data_points": [{"id": "r01", "claim": "x",
                                           "source_url": "https://e.test"}]})
        assert "r01" in book


class TestNamingADeadIdInAsourceRefReCitesIt:
    """The field IS the citation list, so a note about an id is a citation.

    Writing "the ids this field carried — c32, c46-c58 — never existed" into
    act 4's source_ref put c32, c46 and c58 straight back into its citation
    list, and the gate failed on the explanation of the fix. The same shape as
    the `music_rise_reason` diagnostic that once failed plate purity.
    """

    def test_a_note_mentioning_an_id_is_indistinguishable_from_citing_it(self):
        assert fc.cited_in("repaired; c32 never existed") == ["c32"]

    def test_the_delivered_source_ref_names_no_dead_ids(self):
        import json

        script = json.loads(
            open("projects/easter-island/artifacts/script.json",
                 encoding="utf-8").read())
        act4 = next(s for s in script["sections"] if s["id"] == "act4")
        assert fc.cited_in(act4["source_ref"]) == [f"r{i:02d}"
                                                   for i in range(1, 27)]


class TestTheTelegramLine:
    def test_it_reports_the_two_numbers_asked_for(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("scripts").resolve()))
        from telegram_gate import fact_line

        line = fact_line("easter-island",
                         Path("projects/easter-island/artifacts/script.json"))
        assert line.startswith("fact gate: ")
        assert "sentences need a claim" in line
        assert "uncovered" in line

    def test_it_says_when_cited_ids_do_not_resolve(self):
        """Coverage can read zero while a section cites ids that are not
        there, because one resolving id covers a whole section."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("scripts").resolve()))
        from telegram_gate import fact_line

        line = fact_line("easter-island",
                         Path("projects/easter-island/artifacts/script.json"))
        assert "do not resolve" in line

    def test_it_never_raises(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("scripts").resolve()))
        from telegram_gate import fact_line

        assert "could not be summarised" in fact_line(
            "no-such-project", Path("no-such-script.json"))

    def test_it_is_in_the_header_beside_the_script(self):
        from pathlib import Path

        src = Path("scripts/telegram_gate.py").read_text()
        i = src.index("header = (")
        assert "fact_line(project, script_path)" in src[i:i + 400]

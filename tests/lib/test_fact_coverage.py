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


def covered_by(text: str, claims: list[str]):
    """A one-paragraph section whose PARAGRAPH carries the claims.

    Section-level claims stopped covering anything on 2026-10-26; a fixture
    that still used them would be testing a rule that no longer exists.
    """
    return {"sections": [{"id": "act1", "text": text,
                          "paragraphs": [{"text": text, "claims": claims}]}]}


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
            covered_by("Fifty-three houses stood there.", ["c02"]),
            LEDGER, "capitalisation", {})
        assert problems == [], problems
        assert m["sentences_uncovered"] == 0

    def test_a_claim_with_no_source_url_does_not(self):
        problems, _ = fc.check(
            covered_by("Fifty-three houses stood there.", ["c03"]),
            LEDGER, "capitalisation", {})
        assert problems, "a claim with an empty source_url was accepted"

    def test_an_id_that_does_not_resolve_does_not(self):
        """INJECTED: the defect in the published film.

        act 4 cites c46 to c58 against a fifteen-claim ledger.
        """
        problems, m = fc.check(
            covered_by("Fifty-three houses stood there.", ["c58"]),
            LEDGER, "capitalisation", {})
        assert problems
        assert m["ids_that_do_not_resolve"] == ["c58"]

    def test_citing_nothing_does_not(self):
        problems, _ = fc.check(
            script_of("Fifty-three houses stood there."), LEDGER,
            "capitalisation", {})
        assert problems and "no claim names this sentence" in problems[0]

    def test_a_sentence_with_no_facts_needs_no_claim(self):
        problems, m = fc.check(script_of("But nobody can say why."),
                               LEDGER, "capitalisation", {})
        assert problems == []
        assert m["sentences_needing_a_claim"] == 0


class TestWhereTheClaimsAreLookedFor:
    """Sentence first, then the paragraph. A SECTION COVERS NOTHING.

    It used to be paragraph, then section, then the ids in `source_ref`, and
    the last two are how one resolving claim carried a whole act.
    """

    def test_a_claim_naming_the_sentence_wins_over_the_paragraph(self):
        book = {"data_points": [
            {"id": "c02", "claim": "a", "source_url": "https://e.test/a"},
            {"id": "r01", "claim": "b", "source_url": "https://e.test/b",
             "supports": "Fifty-three houses stood there."}]}
        script = {"sections": [{
            "id": "act1", "text": "Fifty-three houses stood there.",
            "paragraphs": [{"text": "...", "claims": ["c02"]}]}]}
        _, m = fc.check(script, book, "capitalisation", {})
        assert m["rows"][0]["attribution"] == "sentence"
        assert m["rows"][0]["cited"] == ["r01"]

    def test_the_paragraph_is_used_when_no_claim_names_the_sentence(self):
        _, m = fc.check(covered_by("Fifty-three houses.", ["c02"]),
                        LEDGER, "capitalisation", {})
        assert m["rows"][0]["attribution"] == "paragraph"

    def test_a_section_source_ref_attributes_nothing(self):
        _, m = fc.check(script_of("Fifty-three houses.",
                                  source_ref="ledger c02 — x.json"),
                        LEDGER, "capitalisation", {})
        assert m["rows"][0]["attribution"] == "none"
        assert m["rows"][0]["covered"] is False

    def test_but_its_ids_are_still_checked_for_resolving(self):
        _, m = fc.check(script_of("Nothing factual.",
                                  source_ref="ledger c02, c99 — x.json"),
                        LEDGER, "capitalisation", {})
        assert m["ids_that_do_not_resolve"] == ["c99"]


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
            {"id": "act1", "text": "Fifty-three houses.",
             "paragraphs": [{"text": "x", "claims": ["c02"]}]},
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


class TestCoverageIsPerSentenceNotPerSection:
    """TIGHTENED 2026-10-26. One claim used to carry a whole act.

    Measured on easter-island: act 3 cited sixteen ids, ONE resolved, and it
    passed on it. Act 2 cited fifteen and two resolved. Act 4 failed only
    because none of its fourteen landed inside the real range — it was not
    uniquely broken, it was uniquely unlucky.
    """

    SCRIPT = {"sections": [{
        "id": "act1",
        "text": "Fifty-three houses stood there.\n\nThe cliff drops 300 m.",
        "source_ref": "research_brief claim ledger c02",
    }]}

    def test_a_section_level_citation_no_longer_covers(self):
        problems, m = fc.check(self.SCRIPT, LEDGER, "capitalisation", {})
        assert problems, "a section-level bag of ids still covered its sentences"
        assert all(r["attribution"] in ("none", "sentence") for r in m["rows"])

    def test_a_paragraph_level_citation_does(self):
        script = {"sections": [{
            "id": "act1", "text": "Fifty-three houses stood there.",
            "paragraphs": [{"text": "...", "claims": ["c02"]}]}]}
        problems, m = fc.check(script, LEDGER, "capitalisation", {})
        assert problems == [], problems
        assert m["rows"][0]["attribution"] == "paragraph"

    def test_a_ledger_claim_naming_the_sentence_also_does(self):
        """Per-sentence attribution held in the LEDGER, so a delivered film
        can be repaired without its script being touched."""
        book = {"data_points": [{
            "id": "r01", "claim": "53 houses at Orongo.",
            "source_url": "https://example.test/a",
            "supports": "Fifty-three houses stood there."}]}
        script = {"sections": [{"id": "act1",
                                "text": "Fifty-three houses stood there."}]}
        problems, m = fc.check(script, book, "capitalisation", {})
        assert problems == [], problems
        assert m["rows"][0]["attribution"] == "sentence"

    def test_repairs_sentence_is_accepted_as_well_as_supports(self):
        book = {"data_points": [{
            "id": "r01", "claim": "x", "source_url": "https://example.test/a",
            "repairs_sentence": "Fifty-three houses stood there."}]}
        idx = fc.sentence_index(fc.ledger(book))
        assert idx["Fifty-three houses stood there."] == ["r01"]

    def test_one_claim_cannot_carry_a_whole_act(self):
        """INJECTED: act 3's shape — many sentences, one resolving id."""
        script = {"sections": [{
            "id": "act3",
            "text": ("Fifty-three houses stood there.\n\n"
                     "The cliff drops 300 m.\n\n"
                     "The crater is a mile across."),
            "claims": ["c01"]}]}
        _, m = fc.check(script, LEDGER, "capitalisation", {})
        covered = [r for r in m["rows"] if r["needs_claim"] and r["covered"]]
        assert covered == [], "a single section-level claim still covered them"


class TestADanglingCitationIsItselfAFailure:
    def test_an_unknown_id_fails_even_when_the_sentence_is_covered(self):
        """The rule that catches acts 2 and 3: a citation that does not
        resolve is not a citation, whatever else is in the same breath."""
        book = {"data_points": [{
            "id": "r01", "claim": "x", "source_url": "https://example.test/a",
            "supports": "Fifty-three houses stood there."}]}
        script = {"sections": [{
            "id": "act1", "text": "Fifty-three houses stood there.",
            "source_ref": "ledger r01, c58"}]}
        problems, m = fc.check(script, book, "capitalisation", {})
        assert m["rows"][0]["covered"] is True
        assert problems, "the dangling c58 was tolerated"
        assert "not a citation" in problems[0]
        assert m["ids_that_do_not_resolve"] == ["c58"]

    def test_it_says_which_section_cited_it(self):
        book = {"data_points": [{"id": "c01", "claim": "x",
                                 "source_url": "https://e.test"}]}
        script = {"sections": [{"id": "act2", "text": "Nothing factual here.",
                                "source_ref": "ledger c99"}]}
        _, m = fc.check(script, book, "capitalisation", {})
        assert m["dangling_citations"] == [{"section": "act2", "id": "c99"}]

    def test_an_exempt_section_is_not_checked_for_them_either(self):
        book = {"data_points": [{"id": "c01", "claim": "x",
                                 "source_url": "https://e.test"}]}
        script = {"sections": [{"id": "outro", "text": "Four open files.",
                                "source_ref": "ledger c99"}]}
        problems, _ = fc.check(script, book, "capitalisation", {})
        assert problems == []


class TestTheCauseIsCheckedAtWriteTime:
    """A gate that runs once, at the end, tells the writer that something
    somewhere is wrong — after the act has been composed around a claim that
    was never in the brief."""

    def test_the_per_act_script_exists_and_scopes_to_one_section(self):
        from pathlib import Path

        src = Path("scripts/check_claims.py").read_text()
        assert '"--section"' in src
        assert "cited_anywhere" in src and "sentence_index" in src

    def test_the_prompt_tells_the_stage_to_run_it_after_each_act(self):
        from pathlib import Path

        body = Path("scripts/run_weekly.sh").read_text()
        assert "AFTER EACH ACT, BEFORE WRITING THE NEXT ONE" in body
        assert "check_claims.py --project $SLUG --section" in body

    def test_the_prompt_forbids_renumbering_to_something_that_exists(self):
        from pathlib import Path

        body = Path("scripts/run_weekly.sh").read_text()
        assert "do not renumber one to something that happens" in body

    def test_the_prompt_says_a_section_ref_no_longer_covers(self):
        from pathlib import Path

        body = Path("scripts/run_weekly.sh").read_text()
        assert "DOES NOT COVER ANYTHING any more" in body

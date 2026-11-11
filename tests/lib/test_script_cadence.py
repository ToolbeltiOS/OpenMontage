"""Write For The Voice: the rules, and the evidence behind each number.

THE NUMBERS ARE THE OWNER'S, GIVEN WHOLE. They replaced a looser earlier set
(mean 16, hard max 30) on the owner's instruction, and this file is how they
stay stated. One number is NOT the owner's — BREATH_COMMA_WORDS — and its
test says so, because "commas at breath points" names no threshold.

They came out of four rounds of voice A/Bs in which the synthesiser was
changed three different ways and the prose was the thing at fault.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import script_cadence as SC  # noqa: E402


def rules(text: str) -> set[str]:
    return {v.rule for v in SC.check(text, "act1")[0]}


def one(fn, sentence: str):
    return fn(sentence)


class TestTheNumbersAreTheOwnersAndUnchanged:
    def test_the_length_limits(self):
        assert SC.MAX_WORDS == 20
        assert SC.HARD_MAX_WORDS == 28
        assert SC.MEAN_MAX == 15.0
        assert SC.SHORT_WORDS == 8
        assert SC.SHORT_MIN_FRACTION == 0.20

    def test_the_rest(self):
        assert SC.MAX_SUBORDINATE_CLAUSES == 1
        assert SC.RHYTHM_RUN == 3
        assert SC.RHYTHM_BAND_WORDS == 3
        assert SC.LANDING_MAX_WORDS == 8
        assert SC.MAX_EM_DASHES_PER_PARAGRAPH == 2
        assert SC.MIN_QUESTIONS_PER_ACT == 1

    def test_the_one_number_that_is_not_the_owners_is_marked_as_mine(self):
        """If this is ever presented as a given, the comment is the record."""
        assert SC.BREATH_COMMA_WORDS == 16
        src = (ROOT / "lib" / "script_cadence.py").read_text()
        assert "MINE, NOT THE OWNER'S" in src

    def test_the_director_quotes_the_same_numbers(self):
        """A skill that drifts from the lint sends the writer to fix the
        wrong thing, which is how a limit becomes folklore."""
        doc = " ".join((ROOT / "skills" / "pipelines" /
                        "narrated-documentary" /
                        "script-director.md").read_text().split())
        assert f"≤ {SC.MAX_WORDS}, hard maximum {SC.HARD_MAX_WORDS}" in doc
        assert f"≤ {SC.MEAN_MAX:.0f}" in doc
        assert f"under {SC.SHORT_WORDS} words | ≥ {SC.SHORT_MIN_FRACTION:.0%}" in doc
        assert f"≤ {SC.LANDING_MAX_WORDS} words" in doc


class TestLength:
    def test_twenty_words_passes(self):
        assert one(SC.check_length, " ".join(["word"] * 20) + ".") == []

    def test_twenty_one_is_over_the_limit(self):
        v = one(SC.check_length, " ".join(["word"] * 21) + ".")
        assert len(v) == 1 and "20-word limit" in v[0].detail

    def test_twenty_nine_is_the_hard_maximum(self):
        v = one(SC.check_length, " ".join(["word"] * 29) + ".")
        assert "HARD MAXIMUM" in v[0].detail

    def test_only_one_of_the_two_is_reported(self):
        """A 35-word sentence is one problem, not two."""
        assert len(one(SC.check_length, " ".join(["w"] * 35) + ".")) == 1

    def test_a_numeral_counts_as_one_word(self):
        assert SC.words("It was 1922.") == 3


class TestOneIdeaPerSentence:
    def test_two_subordinate_clauses_fail(self):
        v = one(SC.check_one_idea,
                "The officials who repacked it left chips which were sealed.")
        assert any("two subordinate clauses" in x.detail for x in v)

    def test_one_is_fine(self):
        assert one(SC.check_one_idea,
                   "The officials who repacked it left chips.") == []

    def test_a_semicolon_fails(self):
        v = one(SC.check_one_idea, "He went in; he came out.")
        assert any("semicolon" in x.detail for x in v)

    def test_a_parenthesis_fails(self):
        v = one(SC.check_one_idea, "He went in (twice) that winter.")
        assert any("parenthesis" in x.detail for x in v)

    def test_the_marker_list_deliberately_omits_the_ambiguous_ones(self):
        """"as", "that", "if", "since", "before", "after" are far more often
        prepositions here, and this blocks a gate."""
        for word in ("as", "that", "if", "since", "before", "after"):
            assert word not in SC.SUBORDINATORS, word

    def test_and_so_it_under_reports_rather_than_inventing(self):
        """A real two-clause sentence built only from omitted markers is
        missed. That is the chosen direction of error."""
        assert one(SC.check_one_idea,
                   "He said that it failed because of the heat.") == []


class TestContractions:
    @pytest.mark.parametrize("text,want", [
        ("It is disputed.", "it's"),
        ("That is the claim.", "that's"),
        ("He did not go.", "didn't"),
        ("It was not sealed.", "wasn't"),
        ("The journal is not peer-reviewed.", "isn't"),
    ])
    def test_an_expansion_is_reported_with_its_contraction(self, text, want):
        v = one(SC.check_contractions, text)
        assert v and want in v[0].detail

    @pytest.mark.parametrize("bad", ["could've", "would've", "should've",
                                     "there'll", "it'll"])
    def test_the_forbidden_ones_fail(self, bad):
        v = one(SC.check_contractions, f"They {bad} known.")
        assert v and bad in v[0].detail

    def test_a_contraction_already_in_use_is_fine(self):
        assert one(SC.check_contractions, "It's disputed, and that's that.") == []


class TestSpokenForms:
    def test_digits_fail(self):
        v = one(SC.check_spoken_forms, "It opened in 1922.")
        assert v and "digits" in v[0].detail

    def test_the_words_pass(self):
        assert one(SC.check_spoken_forms,
                   "It opened in nineteen twenty-two.") == []

    @pytest.mark.parametrize("sym,say", [("%", "per cent"), ("$", "dollars"),
                                         ("°", "degrees"), ("&", "and")])
    def test_a_symbol_is_reported_with_what_to_say(self, sym, say):
        v = one(SC.check_spoken_forms, f"About five {sym} of them.")
        assert any(say in x.detail for x in v)

    def test_a_written_abbreviation_fails(self):
        v = one(SC.check_spoken_forms, "The report, e.g. the second one.")
        assert any("e.g." in x.detail for x in v)

    def test_an_acronym_spoken_as_letters_is_allowed(self):
        """"BBC" is what the narrator says. "Dr." is not."""
        assert one(SC.check_spoken_forms, "The BBC and NASA agreed.") == []
        assert one(SC.check_spoken_forms, "Dr. Nelson agreed.") != []


class TestEyeWords:
    @pytest.mark.parametrize("phrase", ["the former", "the latter",
                                        "respectively", "aforementioned"])
    def test_each_one_fails(self, phrase):
        v = one(SC.check_eye_words, f"Consider {phrase} case here.")
        assert v and phrase in v[0].detail

    def test_mid_sentence_however_fails(self):
        v = one(SC.check_eye_words, "The claim, however, was never tested.")
        assert v and "however" in v[0].detail

    def test_however_opening_a_sentence_is_allowed(self):
        """Opening, it is a signpost the listener hears in time."""
        assert one(SC.check_eye_words, "However, the claim was tested.") == []


class TestAttributionLeads:
    def test_a_trailing_attribution_fails(self):
        v = one(SC.check_attribution,
                "The tomb was never sealed twice, says Carter.")
        assert any("trails" in x.detail for x in v)

    def test_said_is_reported(self):
        v = one(SC.check_attribution, "Weigall said he had watched him.")
        assert any("'said'" in x.detail for x in v)

    def test_a_leading_attribution_with_says_passes(self):
        assert one(SC.check_attribution,
                   "Carter says the tomb was never sealed twice.") == []

    def test_wrote_passes(self):
        assert one(SC.check_attribution, "The Lancet wrote that it was not.") == []


class TestTitleOnFirstMention:
    def test_an_untitled_attributed_name_fails(self):
        v = SC.check_titles("Nelson says the odds were low. He went on.")
        assert v and "Nelson" in v[0].detail

    def test_a_title_satisfies_it(self):
        assert SC.check_titles("Doctor Mark Nelson says the odds were low.") == []

    def test_an_identifying_phrase_satisfies_it(self):
        """"of the Daily Mail" identifies the source without a title word."""
        assert SC.check_titles(
            "Arthur Weigall of the Daily Mail says he watched him.") == []

    def test_the_tail_of_an_organisation_is_not_read_as_a_person(self):
        """IT WAS. "Arthur Weigall of the Daily Mail said" reported `Mail`
        as an untitled source — the last word of the organisation."""
        v = SC.check_titles(
            "Arthur Weigall of the Daily Mail said he watched him.")
        assert not any("Mail" == x.detail.split()[0] for x in v), v


class TestBreath:
    def test_a_long_sentence_with_no_comma_fails(self):
        v = one(SC.check_breath, " ".join(["word"] * 17) + ".")
        assert v and "nowhere to breathe" in v[0].detail

    def test_a_comma_satisfies_it(self):
        assert one(SC.check_breath,
                   " ".join(["word"] * 8) + ", " + " ".join(["word"] * 9) + ".") == []

    def test_a_short_sentence_needs_none(self):
        assert one(SC.check_breath, "He went in.") == []


class TestRhythm:
    def test_three_sentences_of_a_length_fail(self):
        text = ("Then he went and found their obituaries. "
                "Mean survival after exposure was twenty years. "
                "For the unexposed it was twenty-eight years.")
        v = SC.check_rhythm(text, "act1")
        assert v and "consecutive sentences" in v[0].detail

    def test_a_varied_run_passes(self):
        text = "He went in. The chamber had been opened twice before that winter. Nobody wrote it down."
        assert SC.check_rhythm(text, "act1") == []

    def test_a_run_of_fragments_is_allowed(self):
        """A real collision between two of the rules.

        "at least a fifth under 8 words" is satisfied by putting short lines
        together, and a literal band then refuses them. "Arthur Mace. Mervyn
        Herbert. Richard Bethell." is [2, 2, 2] and is the OPPOSITE of the
        uniform mid-length prose the rule is against.
        """
        assert SC.check_rhythm(
            "Arthur Mace. Mervyn Herbert. Richard Bethell.", "act1") == []

    def test_but_a_run_of_mid_length_sentences_is_not(self):
        """The exemption is for fragments, not for anything short-ish.

        Every sentence here is ten words — over the 8-word fragment line, so
        the exemption does not apply and the band does.
        """
        text = ("He went inside the burial chamber entirely alone that night. "
                "She waited beside the stairs outside for several long hours. "
                "They sealed the heavy door again the following morning "
                "quietly.")
        lengths = [SC.words(x) for x in
                   ["He went inside the burial chamber entirely alone that night.",
                    "She waited beside the stairs outside for several long hours.",
                    "They sealed the heavy door again the following morning quietly."]]
        assert all(n >= SC.SHORT_WORDS for n in lengths), lengths
        assert max(lengths) - min(lengths) <= SC.RHYTHM_BAND_WORDS, lengths
        assert SC.check_rhythm(text, "act1") != []

    def test_a_run_is_reported_once(self):
        text = " ".join(["Nine words in this sentence here right now."] * 6)
        assert len(SC.check_rhythm(text, "act1")) == 2


class TestQuestionsAndLandings:
    def test_an_act_with_no_question_fails(self):
        text = "He went in. It was sealed. Nobody wrote it down. He left. It stood."
        assert any(v.rule == "questions" for v in SC.check(text, "act1")[0])

    def test_one_question_satisfies_it(self):
        text = "He went in. Who sealed it? Nobody wrote it down. He left. It stood."
        assert not any(v.rule == "questions"
                       for v in SC.check(text, "act1")[0])

    def test_a_long_landing_line_fails(self):
        text = ("[beat: landing]\n"
                "The case closes. " + " ".join(["word"] * 12) + ".")
        v = SC.check_landings(text, "act1")
        assert v and "landing line" in v[0].detail

    def test_a_fragment_landing_passes(self):
        text = "[beat: landing]\nThe case closes. Nobody wrote it down."
        assert SC.check_landings(text, "act1") == []

    def test_only_landing_beats_are_held_to_it(self):
        text = ("[beat: exposition]\n" + " ".join(["word"] * 14) + ".")
        assert SC.check_landings(text, "act1") == []


class TestEmDashes:
    def test_three_in_a_paragraph_fail(self):
        para = "He went in — alone — at night — and sealed it."
        v = SC.check_paragraph_dashes(para, "act1")
        assert v and "em dashes" in v[0].detail

    def test_two_are_allowed(self):
        assert SC.check_paragraph_dashes("He went in — alone — at night.",
                                         "act1") == []


class TestMarkersAreNeverCounted:
    def test_production_markers_are_not_words(self):
        plain = SC.measure("The tomb was opened.")
        marked = SC.measure("[beat: reveal]\nThe tomb was opened. [air 2.5s]")
        assert marked["mean"] == plain["mean"] == 4.0


class TestEveryViolationCarriesItsSentence:
    """The owner's requirement: report each violation WITH the sentence."""

    def test_each_one_has_a_sentence_and_a_rule(self):
        text = ("It is disputed in 1922. " + " ".join(["word"] * 31) + ". "
                "He went in; he came out.")
        violations, _ = SC.check(text, "act1")
        assert violations
        for v in violations:
            assert v.rule and v.detail and v.sentence
            assert v.where == "act1"

    def test_the_rendered_line_shows_the_sentence(self):
        v = SC.check("It is disputed.", "act1")[0][0]
        assert "It is disputed." in v.line()


class TestTheDeliveredFilmsAreTheBaselineItWasDerivedFrom:
    FILMS = ("noah", "easter-island", "they-said-it-couldnt-be-built",
             "king-tut")

    @pytest.mark.parametrize("film", FILMS)
    def test_it_fails_the_delivered_script(self, film):
        path = ROOT / "projects" / film / "artifacts" / "script.json"
        if not path.exists():
            pytest.skip(f"{film} is not in this worktree")
        violations, _ = SC.check_script(json.loads(path.read_text()))
        assert violations, f"{film} unexpectedly writes for the voice"

    @pytest.mark.parametrize("film", FILMS)
    def test_and_almost_never_asks_a_question(self, film):
        """noah 0 in 178 sentences, they-said-it 1 in 205, easter-island 1 in
        182, king-tut 0 in act 1. Measured 2026-11-10."""
        path = ROOT / "projects" / film / "artifacts" / "script.json"
        if not path.exists():
            pytest.skip(f"{film} is not in this worktree")
        _, rows = SC.check_script(json.loads(path.read_text()))
        assert sum(r["questions"] for r in rows) <= 1, film


class TestItIsWiredIntoTheGate:
    """A lint nobody runs is the same mistake as a gate nothing feeds."""

    @staticmethod
    def _code(path: Path) -> str:
        return "\n".join(ln for ln in path.read_text().splitlines()
                         if not ln.strip().startswith("#"))

    def test_check_claims_runs_it(self):
        body = self._code(ROOT / "scripts" / "check_claims.py")
        assert "SC.check(" in body
        assert "import script_cadence" in body

    def test_check_claims_blocks_on_it(self):
        body = self._code(ROOT / "scripts" / "check_claims.py")
        assert "SC.verdict(" in body
        assert "return 0 if not (failed or not ok) else 1" in body

    def test_it_reports_the_two_apart(self):
        """One gate, two verdicts: the writer needs to know which edit."""
        body = self._code(ROOT / "scripts" / "check_claims.py")
        assert '"CLAIMS:"' in body
        assert '"VOICE:"' in body

    def test_the_fact_path_is_untouched_by_it(self):
        """check_section is the sourcing check and knows nothing of this."""
        src = (ROOT / "scripts" / "check_claims.py").read_text()
        body = src[src.index("def check_section"):src.index("def main")]
        assert "SC." not in body
        assert "cadence" not in body.lower()

    def test_the_weekly_script_stage_runs_it(self):
        body = self._code(ROOT / "scripts" / "run_weekly.sh")
        assert "scripts/check_claims.py --project $SLUG --section" in body


class TestContractionsAreAdvisory:
    """A writer's call, which a regular expression cannot make.

    "The chronology is not the part anyone disputes" is the line act one
    turns on, and `isn't` would weaken it. So the rule reports and never
    counts.
    """

    def test_contractions_is_the_advisory_rule(self):
        assert SC.ADVISORY_RULES == ("contractions",)

    def test_a_contraction_violation_does_not_block(self):
        """A section with a question, so the no-question rule stays quiet
        and the contraction is the only thing left to find."""
        text = ("The chronology is not the part anyone disputes. "
                "Who sealed it? Nobody wrote it down. He left. It stood.")
        violations, _ = SC.check(text, "act1")
        assert any(v.rule == "contractions" for v in violations)
        parts = SC.classify(violations)
        assert parts["blocking"] == [], parts["blocking"]
        assert len(parts["advisory"]) >= 1

    def test_the_fixture_above_really_is_otherwise_clean(self):
        """Or the test would pass for the wrong reason."""
        text = ("The chronology is not the part anyone disputes. "
                "Who sealed it? Nobody wrote it down. He left. It stood.")
        violations, _ = SC.check(text, "act1")
        assert {v.rule for v in violations} == {"contractions"}

    def test_a_film_of_nothing_but_contractions_passes(self):
        """Twenty-five advisory violations is still a PASS."""
        violations = [SC.Violation("contractions", "x", "y")] * 25
        ok, reasons = SC.verdict(violations)
        assert ok and reasons == []

    def test_it_is_still_reported(self):
        """Advisory is not silent. It is counted and shown."""
        violations = [SC.Violation("contractions", "x", "y")] * 3
        assert len(SC.classify(violations)["advisory"]) == 3


class TestTheBudget:
    """Six blocking per film, and zero on the two audible faults."""

    def test_the_budget_is_six(self):
        assert SC.VOICE_BUDGET == 6

    def test_the_zero_tolerance_rules(self):
        assert SC.ALWAYS_BLOCKING == ("length-hard", "landing")

    @staticmethod
    def _blocking(n: int, rule: str = "length") -> list[SC.Violation]:
        return [SC.Violation(rule, f"detail {i}", f"sentence {i}")
                for i in range(n)]

    def test_six_blocking_passes(self):
        ok, reasons = SC.verdict(self._blocking(6))
        assert ok, reasons

    def test_seven_fails(self):
        ok, reasons = SC.verdict(self._blocking(7))
        assert not ok
        assert "over the budget of 6" in reasons[0]

    def test_the_message_says_how_many_to_fix(self):
        """So a 60-turn stage knows the size of the job, not just that it
        failed."""
        _, reasons = SC.verdict(self._blocking(20))
        assert "Fix the worst 14" in reasons[0]

    def test_zero_blocking_passes(self):
        assert SC.verdict([])[0] is True

    def test_one_hard_max_sentence_fails_on_its_own(self):
        """Inside the budget and still a failure."""
        ok, reasons = SC.verdict(self._blocking(1, "length-hard"))
        assert not ok
        assert "length-hard" in reasons[0]

    def test_one_long_landing_line_fails_on_its_own(self):
        ok, reasons = SC.verdict(self._blocking(1, "landing"))
        assert not ok
        assert "landing" in reasons[0]

    def test_a_hard_fault_is_named_with_its_sentence(self):
        _, reasons = SC.verdict(
            [SC.Violation("landing", "too long", "The case closes slowly.")])
        assert "The case closes slowly." in reasons[0]

    def test_the_twenty_word_limit_is_budgeted_not_zero_tolerance(self):
        """Over 20 is a tendency; over 28 is audible. Only one is absolute."""
        assert "length" not in SC.ALWAYS_BLOCKING
        assert SC.verdict(self._blocking(3, "length"))[0] is True


class TestTheBudgetIsAWholeFilmNumber:
    """Six across a film is not six per act.

    Enforced per act it would pass a film carrying five in each of six
    acts, which is thirty.
    """

    @staticmethod
    def _blocking(n: int) -> list[SC.Violation]:
        return [SC.Violation("length", f"d{i}", f"s{i}") for i in range(n)]

    def test_a_single_act_run_does_not_judge_the_budget(self):
        ok, reasons = SC.verdict(self._blocking(20), whole_film=False)
        assert ok, reasons

    def test_but_it_still_refuses_a_hard_fault(self):
        ok, _ = SC.verdict([SC.Violation("length-hard", "d", "s")],
                           whole_film=False)
        assert not ok

    def test_the_whole_film_run_does_judge_it(self):
        assert SC.verdict(self._blocking(20), whole_film=True)[0] is False


class TestTheDeliveredScriptsAgainstTheBudget:
    """What the budget actually means on real material, measured 2026-11-10."""

    FILMS = ("king-tut", "noah", "easter-island",
             "they-said-it-couldnt-be-built")

    @pytest.mark.parametrize("film", FILMS)
    def test_every_delivered_film_is_over_budget(self, film):
        """They are the flat prose the rule was written against. If one ever
        passes, the lint has stopped measuring the thing it was built for."""
        path = ROOT / "projects" / film / "artifacts" / "script.json"
        if not path.exists():
            pytest.skip(f"{film} is not in this worktree")
        violations, _ = SC.check_script(json.loads(path.read_text()))
        ok, reasons = SC.verdict(violations)
        assert not ok, film
        assert reasons

    def test_the_advisory_share_is_real(self):
        """A quarter of king-tut's violations are the writer's call, and
        making them advisory is not a rounding change."""
        path = ROOT / "projects" / "king-tut" / "artifacts" / "script.json"
        if not path.exists():
            pytest.skip("king-tut is not in this worktree")
        violations, _ = SC.check_script(json.loads(path.read_text()))
        parts = SC.classify(violations)
        assert len(parts["advisory"]) >= 20
        assert len(parts["blocking"]) < len(violations)


class TestTheGateAppliesTheBudget:
    @staticmethod
    def _code(path: Path) -> str:
        return "\n".join(ln for ln in path.read_text().splitlines()
                         if not ln.strip().startswith("#"))

    def test_check_claims_uses_the_verdict_and_not_a_bare_count(self):
        body = self._code(ROOT / "scripts" / "check_claims.py")
        assert "SC.verdict(" in body
        assert "SC.classify(" in body

    def test_it_accumulates_across_sections_before_judging(self):
        """A per-section verdict could not apply a per-film budget."""
        body = self._code(ROOT / "scripts" / "check_claims.py")
        assert "all_violations" in body
        assert "whole_film" in body

    def test_the_director_states_the_budget_and_the_exceptions(self):
        doc = " ".join((ROOT / "skills" / "pipelines" /
                        "narrated-documentary" /
                        "script-director.md").read_text().split())
        assert f"six or fewer blocking violations" in doc
        assert "none at all" in doc
        assert "Contractions are advisory" in doc
        assert "sixty turns" in doc

    def test_the_module_says_why_the_budget_is_not_zero(self):
        src = (ROOT / "lib" / "script_cadence.py").read_text()
        assert "NOT ZERO, AND THAT IS THE POINT" in src


class TestTheTitleRuleIgnoresWordsCapitalisedByPosition:
    """"Nobody wrote it down" reported `Nobody` as an untitled source.

    Found by a test fixture that was meant to be clean and was not. It uses
    the same WHITELIST as the capitalisation backend in
    verify_fact_coverage, so the two cannot disagree about what a name is.
    """

    @pytest.mark.parametrize("sentence", [
        "Nobody wrote it down.",
        "Nothing says otherwise.",
        "They wrote it down.",
        "No one says so.",
        "Some say it was never sealed.",
    ])
    def test_a_pronoun_is_not_an_untitled_source(self, sentence):
        assert SC.check_titles(sentence) == [], sentence

    def test_a_real_name_still_is(self):
        assert SC.check_titles("Nelson says the odds were low.") != []

    def test_the_whitelist_is_the_shared_one(self):
        src = (ROOT / "lib" / "script_cadence.py").read_text()
        assert "from verify_fact_coverage import" in src
        assert "WHITELIST" in src

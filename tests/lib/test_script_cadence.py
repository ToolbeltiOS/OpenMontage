"""The cadence lint: the measurable part of the ear-rewrite rule.

THE THREE NUMBERS ARE THE OWNER'S, GIVEN WHOLE. They are not derived,
tuned or defaulted, and this file is how they stay stated. They came out
of four rounds of voice A/Bs in which the synthesiser was changed three
different ways and the prose was the thing actually at fault.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import script_cadence as SC  # noqa: E402


class TestTheNumbersAreTheOwnersAndUnchanged:
    def test_the_three_enforced_limits(self):
        assert SC.MEAN_MAX == 16.0
        assert SC.SHORT_WORDS == 8
        assert SC.SHORT_MIN_FRACTION == 0.20
        assert SC.LONG_MAX == 30


class TestWhatCountsAsAWord:
    def test_production_markers_are_not_words(self):
        """`[air 2.5s]` and `[beat: reveal]` are instructions, not narration.

        Counting them would make a marked-up act read longer than it is and
        a writer would cut real prose to satisfy the lint.
        """
        plain = SC.measure("The tomb was opened.")
        marked = SC.measure("[beat: reveal]\nThe tomb was opened. [air 2.5s]")
        assert marked["mean"] == plain["mean"] == 4.0

    def test_a_numeral_is_one_word(self):
        assert SC.words("It was 1922.") == 3

    def test_a_hyphenated_name_is_one_word(self):
        assert SC.words("Rano Raraku's crater") == 3


class TestTheMeanLimit:
    FLAT = ("The tomb was opened in November of 1922, and the men who went "
            "in found a chamber that had been broken into twice before. The "
            "officials who repacked it left limestone chips across the "
            "floor, which were sealed over again by priests afterwards.")

    def test_uniform_mid_length_prose_fails(self):
        problems, m = SC.check(self.FLAT, "act1")
        assert m["mean"] > SC.MEAN_MAX
        assert any("mean sentence length" in p for p in problems)

    def test_the_message_names_the_fix(self):
        """A lint that says only "too long" gets satisfied by a comma."""
        problems, _ = SC.check(self.FLAT, "act1")
        assert any("subordinate clause" in p for p in problems)

    def test_speech_shaped_prose_passes(self):
        good = ("The tomb was opened. November, 1922. The men who went in "
                "found a chamber broken into twice before — and sealed "
                "twice. Officials had repacked it. They left limestone "
                "chips across the floor. Who sealed it the second time? "
                "Nobody wrote it down.")
        problems, m = SC.check(good, "act1")
        assert problems == [], problems
        assert m["mean"] <= SC.MEAN_MAX
        assert m["short_fraction"] >= SC.SHORT_MIN_FRACTION


class TestTheLongSentenceLimit:
    def test_a_sentence_over_thirty_words_fails(self):
        long = " ".join(["word"] * 31) + "."
        problems, m = SC.check(long, "act2")
        assert m["longest"] == 31
        assert any("longest sentence" in p for p in problems)

    def test_exactly_thirty_passes(self):
        """A limit is a limit, not a suggestion one word either side."""
        _, m = SC.check(" ".join(["word"] * 30) + ".", "act2")
        problems, _ = SC.check(" ".join(["word"] * 30) + ".", "act2")
        assert m["longest"] == 30
        assert not any("longest sentence" in p for p in problems)

    def test_the_offending_sentence_is_quoted(self):
        """So the writer does not have to find it by counting."""
        text = ("Short one. " + " ".join(["elephant"] * 35) + ".")
        problems, _ = SC.check(text, "act2")
        assert any("elephant" in p for p in problems)


class TestTheShortSentenceFraction:
    def test_too_few_landing_lines_fails(self):
        """Ten sentences, every one of them nine words long."""
        text = " ".join(["The tomb was opened again that winter, twice."] * 10)
        problems, m = SC.check(text, "act3")
        assert m["sentences"] == 10
        assert m["short_fraction"] == 0.0
        assert any("under 8 words" in p for p in problems)

    def test_a_sentence_of_exactly_eight_words_is_not_short(self):
        """"under 8", so 8 is not under it. The boundary, asserted."""
        assert SC.words("The tomb was opened again that cold winter") == 8
        m = SC.measure("The tomb was opened again that cold winter.")
        assert m["short"] == 0
        assert SC.measure("The tomb was opened again that winter.")["short"] == 1

    def test_it_is_not_enforced_on_a_tiny_section(self):
        """One short sentence in three is 33% and means nothing."""
        problems, m = SC.check("A very long sentence indeed about the tomb "
                               "and its chambers. Then this. And that.",
                               "outro")
        assert m["sentences"] < SC.MIN_SENTENCES
        assert not any("under 8 words" in p for p in problems)
        assert m["short_fraction_enforced"] is False

    def test_but_the_other_two_limits_still_are(self):
        """A short section is not exempt from the things that do generalise."""
        problems, _ = SC.check(" ".join(["word"] * 40) + ".", "outro")
        assert any("longest sentence" in p for p in problems)


class TestQuestionsAndDashesAreReportedNotEnforced:
    """"One question per paragraph WHERE NATURAL" is not a number.

    Forcing a question into a paragraph that does not want one writes
    worse prose than the flatness being fixed, so these are counted and
    shown and never block.
    """

    def test_a_question_is_counted(self):
        m = SC.measure("Who sealed it? Nobody knows.")
        assert m["questions"] == 1

    def test_a_dash_is_counted(self):
        m = SC.measure("He went in — and found nothing.")
        assert m["dashes"] == 1

    def test_no_questions_at_all_does_not_fail(self):
        problems, m = SC.check("Short line. Another short line. A third one. "
                               "A fourth here. And a fifth one too.", "act1")
        assert m["questions"] == 0
        assert problems == []


class TestTheWholeScript:
    def test_sections_are_checked_independently(self):
        script = {"sections": [
            {"id": "act1", "text": "Short. Tiny. Brief. Quick. Fast."},
            {"id": "act2", "text": " ".join(["word"] * 40) + "."}]}
        problems, rows = SC.check_script(script)
        assert [r["id"] for r in rows] == ["act1", "act2"]
        assert all("act2" in p for p in problems), problems

    def test_a_section_filter_is_honoured(self):
        script = {"sections": [
            {"id": "act1", "text": " ".join(["word"] * 40) + "."},
            {"id": "act2", "text": " ".join(["word"] * 40) + "."}]}
        problems, rows = SC.check_script(script, only=["act2"])
        assert [r["id"] for r in rows] == ["act2"]

    def test_a_silent_section_is_not_a_problem(self):
        problems, rows = SC.check_script(
            {"sections": [{"id": "title_sequence", "text": ""}]})
        assert problems == []
        assert rows[0]["sentences"] == 0


class TestTheDeliveredFilmsAreTheBaselineItWasDerivedFrom:
    """These four scripts are what the rule was written against.

    Every one of them fails, which is the point: they are the flat prose
    the owner heard. If a change to this module ever makes them all pass,
    the module has stopped measuring the thing it was built for.
    """

    FILMS = ("noah", "easter-island", "they-said-it-couldnt-be-built")

    @pytest.mark.parametrize("film", FILMS)
    def test_it_fails_the_delivered_script(self, film):
        path = ROOT / "projects" / film / "artifacts" / "script.json"
        if not path.exists():
            pytest.skip(f"{film} is not in this worktree")
        problems, _ = SC.check_script(json.loads(path.read_text()))
        assert problems, f"{film} unexpectedly passes the cadence lint"

    @pytest.mark.parametrize("film", FILMS)
    def test_and_almost_never_asks_a_question(self, film):
        """The flatness, in one number: at most ONE question per film.

        Measured 2026-11-10 — noah 0 questions in 178 sentences,
        they-said-it 1 in 205, easter-island 1 in 182. That is the habit
        the ear-rewrite rule is against, and the reason the rule asks for
        a question per paragraph where one is natural.
        """
        path = ROOT / "projects" / film / "artifacts" / "script.json"
        if not path.exists():
            pytest.skip(f"{film} is not in this worktree")
        _, rows = SC.check_script(json.loads(path.read_text()))
        asked = sum(r["questions"] for r in rows)
        said = sum(r["sentences"] for r in rows)
        assert asked <= 1, (film, asked)
        assert said > 150, (film, said)


class TestItIsActuallyWiredIn:
    """A lint nobody runs is the same mistake as a gate nothing feeds.

    Three gates have been built in this repo with no consumer and revoked.
    These tests are the consumer check for this one: the rule is in the
    director the writer reads, and the command is in the stage prompt the
    unattended run executes.
    """

    @staticmethod
    def _code(path: Path) -> str:
        """Code and prose, but never a line that is only a comment.

        Twice this session a test passed against a comment describing the
        behaviour instead of the behaviour.
        """
        return "\n".join(
            ln for ln in path.read_text().splitlines()
            if not ln.strip().startswith("#"))

    def test_the_weekly_script_stage_runs_the_lint(self):
        body = self._code(ROOT / "scripts" / "run_weekly.sh")
        assert "scripts/check_cadence.py --project $SLUG --section" in body

    def test_it_runs_beside_the_claims_check_not_instead_of_it(self):
        """The fact gate is unchanged; this is an addition, not a swap."""
        body = self._code(ROOT / "scripts" / "run_weekly.sh")
        assert "scripts/check_claims.py --project $SLUG --section" in body

    def test_the_director_carries_the_rewrite_rule(self):
        doc = (ROOT / "skills" / "pipelines" / "narrated-documentary" /
               "script-director.md").read_text()
        assert "Step 5b" in doc
        for clause in ("under 8 words", "question per paragraph",
                       "dash before each turn", "subordinate clause",
                       "fragment"):
            assert clause in doc, clause

    def test_the_director_quotes_the_same_numbers_the_code_enforces(self):
        """A skill that drifts from the lint sends the writer to fix the
        wrong thing, which is how a "16-word limit" becomes folklore."""
        doc = (ROOT / "skills" / "pipelines" / "narrated-documentary" /
               "script-director.md").read_text()
        assert f"{SC.MEAN_MAX:.0f} words" in doc
        assert f"{SC.SHORT_WORDS} words" in doc
        assert f"{SC.LONG_MAX} words" in doc
        assert f"{SC.SHORT_MIN_FRACTION:.0%}" in doc

    def test_the_director_says_the_lint_is_a_floor(self):
        doc = (ROOT / "skills" / "pipelines" / "narrated-documentary" /
               "script-director.md").read_text()
        assert "floor, not the goal" in doc

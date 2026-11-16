"""The channel's angle, at research, proposal and script.

The angle is what is disputed, hidden or unexplained about a subject. A film
can lose it at any of three places, and each loss looks different: research
can hand on a tidy summary, a proposal can be given a disputed brief and
build the textbook anyway, and a script can be built on a disputed proposal
and still assert every theory in the narrator's own voice.

Counted across the four films that existed when this was written, from each
brief's own ledger:

    they-said-it-couldnt-be-built   43 claims,  0 contested   0.0% of script
    easter-island                   83 claims,  0 contested   0.0%
    king-tut                        53 claims, 16 contested  41.5%
    atomic-bombings                 33 claims, 13 contested  48.4%

The two with nothing contested are films #1 and #2, which is what the rule
is for.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import verify_channel_angle as A  # noqa: E402

#: Real artifacts this repo tracks, so the pins below are measurements and
#: not fixtures agreeing with themselves.
REAL = ROOT / "projects"


def film(slug: str) -> tuple[dict, dict]:
    art = REAL / slug / "artifacts"
    return (json.loads((art / "research_brief.json").read_text()),
            json.loads((art / "script.json").read_text()))


def claim(cid: str, contested: bool = True, source: bool = True) -> dict:
    out = {"id": cid, "claim": f"claim {cid}", "credibility": "primary_source",
           "contested": contested}
    if source:
        out["source_url"] = f"https://example.invalid/{cid}"
    return out


def brief_with(n: int, **kw) -> dict:
    """A brief carrying `n` disputed entries over `n` contested claims."""
    kinds = list(A.DISPUTED_KINDS)
    return {
        "data_points": [claim(f"c{i:02d}", **kw) for i in range(1, n + 1)],
        "disputed": [{"claim_id": f"c{i:02d}", "kind": kinds[i % len(kinds)]}
                     for i in range(1, n + 1)],
    }


class TestTheBriefMustCarryTheAngle:
    def test_five_disputed_items_pass(self):
        problems, m = A.check_brief(brief_with(5))
        assert problems == [], problems
        assert m["usable_disputed"] == 5

    def test_four_do_not(self):
        problems, m = A.check_brief(brief_with(4))
        assert problems
        assert m["usable_disputed"] == 4

    def test_an_entry_naming_a_claim_that_is_not_contested_does_not_count(self):
        b = brief_with(5)
        b["data_points"][0]["contested"] = False
        problems, m = A.check_brief(b)
        assert m["usable_disputed"] == 4
        assert any("not marked contested" in p for p in problems)

    def test_an_entry_whose_claim_has_no_source_is_refused(self):
        """A theory has to be traceable to whoever said it."""
        b = brief_with(5)
        b["data_points"][0].pop("source_url")
        problems, _ = A.check_brief(b)
        assert any("no source_url" in p for p in problems)

    def test_an_unresolvable_claim_id_is_refused(self):
        b = brief_with(5)
        b["disputed"][0]["claim_id"] = "c99"
        problems, _ = A.check_brief(b)
        assert any("no such claim" in p for p in problems)

    def test_five_entries_pointing_at_three_claims_are_three_threads(self):
        b = brief_with(5)
        for entry in b["disputed"][1:]:
            entry["claim_id"] = "c01"
        problems, m = A.check_brief(b)
        assert m["usable_disputed"] == 1
        assert any("already named" in p for p in problems)

    def test_a_kind_outside_the_four_is_refused(self):
        b = brief_with(5)
        b["disputed"][0]["kind"] = "interesting"
        problems, _ = A.check_brief(b)
        assert any("is not one of" in p for p in problems)

    def test_there_are_exactly_four_kinds(self):
        assert len(A.DISPUTED_KINDS) == 4


class TestWhoseFaultItIs:
    """The two answers are opposite: re-run the stage, or take the next
    topic. The first version of this conflated them and told a brief holding
    thirteen contested claims to go and find another subject."""

    def test_a_brief_that_holds_the_angle_and_hides_it_is_a_stage_problem(self):
        b = brief_with(8)
        b.pop("disputed")
        problems, m = A.check_brief(b)
        assert problems
        assert m["topic_has_no_angle"] is False
        assert any("the angle is here and the section does not name it"
                   in p.lower() for p in problems)

    def test_a_brief_with_nothing_contested_is_a_topic_problem(self):
        b = brief_with(8, contested=False)
        b.pop("disputed")
        problems, m = A.check_brief(b)
        assert problems
        assert m["topic_has_no_angle"] is True
        assert any("TOPIC has no angle" in p for p in problems)

    @pytest.mark.parametrize("slug,contested,topic_problem", [
        ("king-tut", 16, False),
        ("easter-island", 0, True),
        ("they-said-it-couldnt-be-built", 0, True),
    ])
    def test_on_the_real_films(self, slug, contested, topic_problem):
        brief, _ = film(slug)
        problems, m = A.check_brief(brief)
        assert m["contested_claims"] == contested, m
        assert problems, "no film yet carries a disputed section"
        assert m["topic_has_no_angle"] is topic_problem


class TestTheProposalMustRestOnIt:
    def proposal(self, **concept) -> dict:
        return {"selected_concept": {"concept_id": "x"},
                "concept_options": [{"id": "x", **concept}]}

    def test_an_angle_and_disputed_grounding_pass(self):
        b = brief_with(5)
        problems, m = A.check_proposal(self.proposal(
            angle="what the record does not say",
            grounded_in=["c01", "c02"],
            disputed_grounding=["c01"]), b)
        assert problems == [], problems
        assert m["angle"]

    def test_a_concept_with_no_angle_is_refused(self):
        problems, _ = A.check_proposal(self.proposal(
            grounded_in=["c01"], disputed_grounding=["c01"]), brief_with(5))
        assert any("states no `angle`" in p for p in problems)

    def test_acts_that_retell_the_textbook_are_refused(self):
        """Grounded entirely in uncontested claims."""
        b = brief_with(5)
        b["data_points"].append(claim("c90", contested=False))
        problems, _ = A.check_proposal(self.proposal(
            angle="a line", grounded_in=["c90"]), b)
        assert any("retell the standard account" in p for p in problems)

    def test_disputed_grounding_must_name_real_disputes(self):
        problems, _ = A.check_proposal(self.proposal(
            angle="a line", grounded_in=["c01"],
            disputed_grounding=["c01", "c77"]), brief_with(5))
        assert any("c77" in p for p in problems)

    def test_a_selected_concept_that_is_not_there_says_so(self):
        problems, _ = A.check_proposal(
            {"selected_concept": {"concept_id": "nope"},
             "concept_options": [{"id": "x"}]}, brief_with(5))
        assert any("not among" in p for p in problems)


class TestTheScriptMustBeAboutIt:
    @pytest.mark.parametrize("slug,share,passes", [
        ("king-tut", 0.415, True),
        ("easter-island", 0.0, False),
        ("they-said-it-couldnt-be-built", 0.0, False),
    ])
    def test_the_contested_share_of_the_real_films(self, slug, share, passes):
        brief, script = film(slug)
        problems, m = A.check_script(script, brief, backend="capitalisation")
        assert m["share_of_all"] == pytest.approx(share, abs=0.02), m
        assert (not problems) is passes, problems

    def test_the_floor_is_thirty_percent(self):
        assert A.MIN_CONTESTED_SHARE == 0.30

    def test_both_denominators_are_reported(self):
        """They answer different questions, and on the real films they
        barely differ — 41.5% against 42.0% on king-tut."""
        brief, script = film("king-tut")
        _problems, m = A.check_script(script, brief, backend="capitalisation")
        assert m["share_of_factual"] >= m["share_of_all"]


class TestTheCliSeparatesTheTwoFailures:
    def run(self, slug: str, stage: str) -> int:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_channel_angle.py"),
             "--project", slug, "--stage", stage, "--root", str(ROOT),
             "--backend", "capitalisation"],
            capture_output=True, text=True).returncode

    def test_a_topic_with_no_angle_exits_three(self):
        assert self.run("easter-island", "research") == 3

    def test_a_stage_that_hid_the_angle_exits_one(self):
        assert self.run("king-tut", "research") == 1

    def test_three_is_reserved_for_the_topic(self):
        import check_channel_angle as C
        assert C.NO_ANGLE_IN_THE_TOPIC == 3


class TestTheGateShowsItToTheOwner:
    def test_the_message_never_raises(self, tmp_path):
        """A reporting extra must not be why an approval request fails."""
        import telegram_gate as G
        lines = G.angle_lines("no-such-film", tmp_path / "nope.json")
        assert lines and "could not be summarised" in lines[0]

    def test_it_names_the_angle_the_share_and_the_threads(self, monkeypatch,
                                                          tmp_path):
        import telegram_gate as G
        art = tmp_path / "projects" / "f" / "artifacts"
        art.mkdir(parents=True)
        b = brief_with(5)
        (art / "research_brief.json").write_text(json.dumps(b))
        (art / "proposal_packet.json").write_text(json.dumps(
            {"selected_concept": {"concept_id": "x"},
             "concept_options": [{"id": "x", "angle": "THE ANGLE LINE"}]}))
        script = art / "script.json"
        script.write_text(json.dumps({"sections": []}))
        monkeypatch.setattr(G, "ROOT", tmp_path)
        lines = G.angle_lines("f", script)
        assert "THE ANGLE LINE" in lines[0]
        assert "rest on a contested claim" in lines[1]
        assert len([x for x in lines if x[:2] in
                    ("1.", "2.", "3.", "4.", "5.")]) == 5

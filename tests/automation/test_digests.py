"""The agent reads a digest, and the digest cannot lose a claim.

WHY THIS TEST EXISTS
--------------------
`claude -p` re-reads its whole context on every turn, so a file read once at
turn 20 of a 308-turn stage is read 288 more times at $0.50 per million
cache-read tokens. Measured on the 2026-11-06 script stage: the playbook was
read TWICE (88,555 bytes of tool output, ~22,000 tokens), AGENT_GUIDE.md
once (50,519), verify_fact_coverage.py (28,385), the pipeline manifest
(27,547) and run_weekly.sh (18,238) — 258 KB, about 65,000 tokens, carried
for the rest of the stage. Nineteen million tokens of cache reads, $9.50,
for five files it had already understood.

So the stages read digests. That buys nothing if a digest can quietly drop
the one claim a sentence needed, so the properties worth asserting are not
about size:

  * every claim id in the brief survives into the digest, because the script
    cites ids and an id it cannot see is a sentence it cannot write;
  * a claim with no source_url is flagged, not hidden — citing one fails the
    gate, and easter-island shipped citing forty-two ids that never existed;
  * every section of the playbook belongs to some stage, so trimming cannot
    orphan a rule nobody reads;
  * an unknown stage gets the WHOLE playbook, because a stage silently given
    a playbook with holes in it is worse than an expensive one.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts import brief_digest as bd
from scripts import playbook_digest as pd

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = ROOT / "styles" / "wak3up-documentary.yaml"
MANIFEST = ROOT / "pipeline_defs" / "narrated-documentary.yaml"

A_BRIEF = {
    "topic": {"title": "King Tut"},
    "research_summary": "Four questions, four verdicts.",
    "data_points": [
        {"id": "c01", "claim": "The staircase was found on 4 November 1922.",
         "source_url": "https://en.wikipedia.org/wiki/Tomb_of_Tutankhamun",
         "kind": "date", "confidence": "established"},
        {"id": "c02", "claim": "The dagger's iron is meteoritic.",
         "source_url": "https://example.org/dagger", "kind": "figure",
         "contested": True, "confidence": "contested"},
        {"id": "c03", "claim": "A claim nobody sourced.",
         "kind": "claim"},
    ],
    "gaps": [{"looked_for": "the 1922 field notes",
              "why_it_matters": "the exact wording of Carter's reply"}],
    "angles_discovered": [{"angle": "the deleted king",
                           "why": "his successors left him off the king list"}],
}


class TestTheDigestKeepsEveryClaim:
    @staticmethod
    @pytest.fixture(scope="class")
    def text():
        return bd.digest(A_BRIEF)

    @pytest.mark.parametrize("claim_id", ["c01", "c02", "c03"])
    def test_every_id_survives(self, text, claim_id):
        assert claim_id in text, (
            f"{claim_id} is missing from the digest. The script cites ids; an "
            f"id it cannot see is a sentence it cannot write.")

    def test_an_unsourced_claim_is_flagged_not_dropped(self, text):
        assert "NO SOURCE_URL" in text and "NOT CITEABLE" in text
        assert "c03" in text, (
            "dropping it would make it invisible; the script would not cite "
            "it and would also never know why.")

    def test_a_contested_claim_says_so(self, text):
        assert "CONTESTED" in text, (
            "the playbook forbids narrating a disputed question as settled.")

    def test_the_gaps_come_through(self, text):
        assert "1922 field notes" in text, (
            "a gap says which sentences may never be written. Losing it "
            "turns a known hole into an invented fact.")

    def test_the_count_is_stated(self, text):
        assert "53 entries" not in text
        assert "3 entries" in text, (
            "the stage should be able to tell at a glance that it has the "
            "whole ledger.")

    def test_it_says_what_it_left_out(self, text):
        assert "WHAT IS NOT HERE" in text, (
            "a digest that does not admit to being one invites the stage to "
            "trust it as complete.")

    def test_a_long_claim_is_truncated_but_marked(self):
        long_one = {"data_points": [{"id": "c99", "claim": "x" * 900,
                                     "source_url": "https://e.org/"}]}
        text = bd.digest(long_one, max_claim=100)
        assert "c99" in text and "…" in text
        assert "x" * 200 not in text


class TestTheRealBriefShrinks:
    @pytest.mark.skipif(
        not (ROOT / "projects" / "king-tut" / "artifacts"
             / "research_brief.json").exists(),
        reason="needs the king-tut brief on this machine")
    def test_it_is_much_smaller_and_keeps_every_id(self):
        path = (ROOT / "projects" / "king-tut" / "artifacts"
                / "research_brief.json")
        brief = json.loads(path.read_text())
        text = bd.digest(brief)
        ids = [p["id"] for p in brief["data_points"] if p.get("id")]
        assert ids, "the brief should carry ids at all"
        for claim_id in ids:
            assert claim_id in text, claim_id
        assert len(text) < len(path.read_text()) / 2


class TestThePlaybookIsSplitWithoutOrphans:
    @staticmethod
    @pytest.fixture(scope="class")
    def book():
        return pd.load(PLAYBOOK)

    def test_every_pipeline_stage_has_a_section_list(self):
        manifest = yaml.safe_load(MANIFEST.read_text())
        stages = [s.get("id") or s.get("name") or s.get("stage")
                  for s in manifest["stages"]]
        for stage in stages:
            assert pd.sections_for(stage) is not None, (
                f"the {stage} stage would be handed the whole 44 KB "
                f"playbook. Add it to STAGE_SECTIONS.")

    def test_no_playbook_section_belongs_to_nobody(self, book):
        claimed = set(pd.ALWAYS)
        for sections in pd.STAGE_SECTIONS.values():
            claimed.update(sections)
        orphans = sorted(set(book) - claimed - set(pd.UNREAD))
        assert not orphans, (
            f"no stage reads {orphans}. Either a stage needs it and is being "
            f"starved of a rule, or it is dead weight in the playbook — "
            f"both are worth knowing, and silence about it is what makes a "
            f"trimmed playbook dangerous. If nothing reads it, say so in "
            f"playbook_digest.UNREAD with the reason.")

    def test_every_knowingly_unread_section_still_exists(self, book):
        """A stale excuse is worse than no excuse: it hides a live rule."""
        for name, reason in pd.UNREAD.items():
            assert name in book, (
                f"playbook_digest.UNREAD still excuses {name!r}, which the "
                f"playbook no longer has. Delete the entry.")
            assert len(reason) > 40, (
                f"{name!r} is excused without a reason anybody can act on.")

    def test_the_unread_sections_are_not_quietly_routed_anyway(self, book):
        routed = set(pd.ALWAYS)
        for sections in pd.STAGE_SECTIONS.values():
            routed.update(sections)
        both = sorted(set(pd.UNREAD) & routed)
        assert not both, (
            f"{both} are listed as read by nobody AND routed to a stage. One "
            f"of the two is wrong.")

    def test_no_stage_asks_for_a_section_that_does_not_exist(self, book):
        for stage, sections in pd.STAGE_SECTIONS.items():
            missing = [s for s in sections if s not in book]
            assert not missing, (
                f"the {stage} stage asks for {missing}, which the playbook "
                f"does not have — a rename would silently starve it.")

    @pytest.mark.parametrize("stage", sorted(pd.STAGE_SECTIONS))
    def test_each_stage_gets_less_than_the_whole_thing(self, book, stage):
        whole = len(yaml.safe_dump(book, sort_keys=False, allow_unicode=True))
        text, unknown = pd.digest(book, stage)
        assert not unknown
        assert len(text) < whole, stage

    @pytest.mark.parametrize("stage", sorted(pd.STAGE_SECTIONS))
    def test_what_the_film_is_travels_to_every_stage(self, book, stage):
        """A stage that does not know the identity makes something wrong."""
        text, _ = pd.digest(book, stage)
        for always in pd.ALWAYS:
            if always in book:
                assert always in text, (stage, always)

    def test_the_digest_says_what_it_dropped(self, book):
        text, _ = pd.digest(book, "script")
        assert "NOT HERE" in text
        assert "playbook_digest.py" in text, (
            "a stage that finds a rule missing must know where to say so.")

    def test_an_unknown_stage_gets_everything_and_a_warning(self, book):
        text, unknown = pd.digest(book, "a-stage-that-does-not-exist")
        assert unknown
        assert len(text) > len(pd.digest(book, "script")[0])
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "playbook_digest.py"),
             "--stage", "a-stage-that-does-not-exist"],
            capture_output=True, text=True)
        assert done.returncode == 0
        assert "no section list" in done.stderr, (
            "it must say so: a stage silently given a playbook with holes in "
            "it is worse than an expensive one.")

    def test_the_digest_is_generated_not_copied(self, tmp_path):
        """Change the playbook, and the digest changes with it."""
        book = {"identity": {"name": "test"}, "quality_rules": ["one"],
                "taste_profile": {}, "script_rules": {"rule": "ORIGINAL"},
                "motion": {"unused": True}}
        path = tmp_path / "book.yaml"
        path.write_text(yaml.safe_dump(book))
        first, _ = pd.digest(pd.load(path), "script")
        assert "ORIGINAL" in first and "unused" not in first
        book["script_rules"]["rule"] = "CHANGED"
        path.write_text(yaml.safe_dump(book))
        second, _ = pd.digest(pd.load(path), "script")
        assert "CHANGED" in second and "ORIGINAL" not in second

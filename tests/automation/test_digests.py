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


class TestTheEditExemplarDigest:
    """The edit stage was refused the exemplar, then died at its cap twice.

    WHY THIS EXISTS
    ---------------
    Run #5, 2026-11-13. The edit stage spent one of its 30 turns trying to
    read `projects/king-tut/artifacts/edit_decisions.json` to learn the
    shape of the artifact it had been asked to write, was refused, and ran
    out of turns twice without producing it. The schema says what is legal;
    a delivered film says what is NORMAL, and that is the cheaper teacher.

    Reading it whole is not the answer either — 252 KB, 161 cuts, 95
    distinct keys, carried on every turn after the one that read it. So the
    stage reads a digest, and the properties worth asserting are the ones
    that would make the digest a liability:

      * a key that EVERY cut carries must appear, or the stage writes an
        artifact missing a field every real cut has;
      * every component type in use must appear, or the stage reaches for a
        component the renderer has never been asked for;
      * the prose must be truncated, or the stage inherits King Tut's
        sentences as if they were a template;
      * and a missing exemplar must FAIL, because a digest that prints
        nothing on a missing file teaches the stage that there is nothing
        to know.
    """

    EXEMPLAR = "king-tut"

    @pytest.fixture(scope="class")
    def runner_projects(self):
        """The delivered films live in the runner worktree."""
        path = Path("/Users/mac/Developer/wak3up-docs/runner/projects")
        if not (path / self.EXEMPLAR / "artifacts"
                / "edit_decisions.json").exists():
            pytest.skip(f"no delivered exemplar at {path}")
        return path

    @pytest.fixture(scope="class")
    def rendered(self, runner_projects):
        from scripts import edit_decisions_digest as edd
        blob = json.loads((runner_projects / self.EXEMPLAR / "artifacts"
                           / "edit_decisions.json").read_text())
        return blob, edd.digest(blob, self.EXEMPLAR)

    def test_every_universally_carried_key_is_named(self, rendered):
        blob, text = rendered
        cuts = blob["cuts"]
        universal = [k for k in {k for c in cuts for k in c}
                     if sum(1 for c in cuts if k in c) == len(cuts)]
        assert universal, "the exemplar has no universal keys — check it"
        missing = [k for k in universal if k not in text]
        assert missing == [], (
            f"a key every cut carries is invisible in the digest: {missing}")

    def test_every_component_type_in_use_is_named(self, rendered):
        blob, text = rendered
        types = {c.get("type") or (c.get("scene") or {}).get("type")
                 for c in blob["cuts"]}
        types.discard(None)
        missing = [t for t in types if t not in text]
        assert missing == [], f"components the stage cannot see: {missing}"

    def test_a_conditional_key_carries_how_conditional_it_is(self, rendered):
        """`source` on 132 of 161 cuts is a different instruction from
        `source` on all of them."""
        blob, text = rendered
        cuts = blob["cuts"]
        n = sum(1 for c in cuts if "source" in c)
        assert n < len(cuts), "pick a different key: source is universal here"
        assert f"{n}/{len(cuts)}" in text

    def test_it_is_a_digest_and_not_the_file(self, rendered):
        from scripts import edit_decisions_digest as edd
        blob, text = rendered
        whole = len(json.dumps(blob))
        assert len(text) < whole / 10, (
            f"{len(text)} bytes against {whole} is not a digest")
        assert len(text.encode()) <= edd.SIZE_BUDGET_BYTES

    def test_the_prose_is_truncated_not_reproduced(self, rendered):
        """The stage should learn that `reason` holds a sentence, without
        inheriting King Tut's sentence."""
        from scripts import edit_decisions_digest as edd
        blob, text = rendered
        long_prose = [c["attribution"] for c in blob["cuts"]
                      if isinstance(c.get("attribution"), str)
                      and len(c["attribution"]) > edd.PROSE_CHARS]
        assert long_prose, "no long prose in the exemplar to truncate"
        for value in long_prose:
            assert value not in text, "a long prose field survived whole"

    def test_the_digest_says_your_film_is_not_this_film(self, rendered):
        """An exemplar read as a template is a worse failure than no
        exemplar: it is how four films come out identical."""
        _, text = rendered
        assert "not this film" in text.lower()

    def test_a_missing_exemplar_fails_rather_than_printing_nothing(
            self, tmp_path):
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "edit_decisions_digest.py"),
             "--project", "no-such-film", "--projects-dir", str(tmp_path)],
            capture_output=True, text=True)
        assert done.returncode == 1
        assert "no exemplar" in done.stderr
        assert done.stdout == ""

    def test_an_exemplar_with_no_cuts_is_not_an_exemplar(self, tmp_path):
        art = tmp_path / "hollow" / "artifacts"
        art.mkdir(parents=True)
        (art / "edit_decisions.json").write_text(json.dumps({"cuts": []}))
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "edit_decisions_digest.py"),
             "--project", "hollow", "--projects-dir", str(tmp_path)],
            capture_output=True, text=True)
        assert done.returncode == 1
        assert "no cuts" in done.stderr

    def test_the_edit_prompt_names_it(self):
        """The whole point: the stage is TOLD, not left to discover."""
        weekly = (ROOT / "scripts" / "run_weekly.sh").read_text()
        edit_block = weekly[weekly.index('pipeline_stage edit "$TURNS_EDIT"'):]
        edit_block = edit_block[:edit_block.index("# ── 4a.")]
        assert "scripts/edit_decisions_digest.py" in edit_block
        assert "king-tut" in edit_block, "name the exemplar, not just the tool"
        assert "do NOT read the exemplar whole" in edit_block or \
               "not read the exemplar whole" in edit_block

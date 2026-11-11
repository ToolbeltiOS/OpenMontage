"""Research, proposal and script are three stages with three caps.

WHY THE SPLIT EXISTS, MEASURED
------------------------------
They were one `claude -p` with one cap of 60. The 2026-11-11 rehearsal —
the first run with the voice lint in place — spent transcript turns 7–34 on
research and 36–66 on the proposal, wrote its first script at turn 77, and
hit the cap at 61 SDK turns with the cold open and act 1 written and acts 2,
3, 4 and the outro empty.

The prose it did write was good: three blocking violations in 73 sentences
against a budget of six, 0 zero-tolerance, mean 8.72 words, 48% of sentences
under eight. So the rules were never what exhausted the cap, and neither was
the lint loop — that cost 8 turns of 99. The bundling did.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WEEKLY = ROOT / "scripts" / "run_weekly.sh"


@pytest.fixture(scope="module")
def weekly() -> str:
    return WEEKLY.read_text()


class TestTheThreeCaps:
    """The numbers, and the derivation beside them."""

    def test_each_stage_has_its_own_cap(self, weekly):
        assert 'TURNS_RESEARCH="${TURNS_RESEARCH:-30}"' in weekly
        assert 'TURNS_PROPOSAL="${TURNS_PROPOSAL:-25}"' in weekly
        assert 'TURNS_SCRIPT="${TURNS_SCRIPT:-120}"' in weekly

    def test_the_old_single_cap_of_sixty_is_gone(self):
        assert 'TURNS_SCRIPT:-60' not in WEEKLY.read_text()

    def test_the_derivation_of_120_is_recorded_beside_it(self):
        """120 IS MEASURED, NOT ROUND, and a round number is what a later
        reader would assume. The arithmetic has to be on the page."""
        body = WEEKLY.read_text()
        head = body[:body.index('TURNS_SCRIPT="${TURNS_SCRIPT:-120}"')]
        for fact in ("120 IS MEASURED, NOT ROUND", "6 x 20 = 120",
                     "turns 7–34", "36–66", "cap landed at 61"):
            assert fact in head, fact

    def test_it_says_why_a_cap_is_not_raised_to_pass(self, weekly):
        # flattened: the sentence spans a comment line break, and a test
        # that depends on where the wrap falls is testing the wrap
        flat = " ".join(weekly.replace("#:", " ").split())
        assert "a cap raised to make a run pass measures nothing" in flat


class TestTheStagesAreSeparateCalls:
    def test_research_is_its_own_stage(self, weekly):
        assert 'pipeline_stage research "$TURNS_RESEARCH"' in weekly

    def test_proposal_is_its_own_stage(self, weekly):
        assert 'pipeline_stage proposal "$TURNS_PROPOSAL"' in weekly

    def test_the_script_is_still_its_own_call(self, weekly):
        assert 'claude_stage "script" "$LOGDIR/script_stage"' in weekly
        assert '"$TURNS_SCRIPT"' in weekly

    def test_research_is_told_not_to_write_a_proposal_or_a_script(self, weekly):
        block = weekly[weekly.index("pipeline_stage research"):
                       weekly.index("pipeline_stage proposal")]
        assert "Do not write a proposal and do not write a" in block

    def test_proposal_is_told_not_to_write_a_script(self, weekly):
        block = weekly[weekly.index("pipeline_stage proposal"):
                       weekly.index("# ── 2a. the script")]
        assert "Do not write a word of script." in block

    def test_the_gate_still_follows_the_script(self, weekly):
        assert weekly.index('claude_stage "script"') < weekly.index(
            "telegram_gate.py")


class TestTheHelpersAreDefinedBeforeTheyAreUsed:
    """A shell function used above its definition is a runtime failure.

    `pipeline_stage` and `stage_preamble` were defined AFTER the old script
    stage, which only worked because that stage was hand-rolled and used
    neither. Moving the first use above them would have broken the run on
    the night, not in a test.
    """

    @pytest.mark.parametrize("fn", ["stage_preamble", "pipeline_stage"])
    def test_the_definition_comes_first(self, weekly, fn):
        definition = weekly.index(f"{fn}() {{")
        uses = [i for i in range(len(weekly))
                if weekly.startswith(fn, i) and not weekly.startswith(
                    f"{fn}() {{", i)]
        first_use = min((i for i in uses if i != definition), default=None)
        assert first_use is not None, f"{fn} is never used"
        assert definition < first_use, (
            f"{fn} is used at {first_use} and defined at {definition}")

    def test_the_script_passes_bash_syntax(self):
        assert subprocess.run(["bash", "-n", str(WEEKLY)]).returncode == 0


class TestEachStageReadsADigestNotATranscript:
    """The saving. A context that carried the research conversation into the
    proposal and both into the script paid 57 K tokens a turn for
    conversation it could have read in 4 KB."""

    def test_the_proposal_reads_the_brief_digest(self, weekly):
        block = weekly[weekly.index("pipeline_stage proposal"):
                       weekly.index("# ── 2a. the script")]
        assert "scripts/brief_digest.py --project $SLUG" in block

    def test_the_script_reads_both_digests(self, weekly):
        block = weekly[weekly.index("# ── 2a. the script"):
                       weekly.index("# ── 2b.")]
        assert "scripts/brief_digest.py --project $SLUG" in block
        assert "scripts/proposal_digest.py --project $SLUG" in block

    def test_the_script_is_told_not_to_read_the_packet_whole(self, weekly):
        block = weekly[weekly.index("# ── 2a. the script"):
                       weekly.index("# ── 2b.")]
        assert "Do not read proposal_packet.json whole" in block

    def test_the_script_is_told_it_did_not_do_the_research(self, weekly):
        block = weekly[weekly.index("# ── 2a. the script"):
                       weekly.index("# ── 2b.")]
        assert "YOU DID NOT DO THE RESEARCH OR CHOOSE THE CONCEPT" in block

    def test_the_script_cannot_add_to_the_brief(self, weekly):
        """The research stage is finished; its artifact is the ledger the
        gate resolves against. The old prompt told the writer to research a
        missing fact, which it can no longer do."""
        block = weekly[weekly.index("# ── 2a. the script"):
                       weekly.index("# ── 2b.")]
        assert "you cannot add to the brief from here" in block


class TestTheExitCodeInstruction:
    """The denial that cost the 2026-11-11 rehearsal turns."""

    def test_the_prompt_forbids_a_chained_echo(self, weekly):
        block = weekly[weekly.index("# ── 2a. the script"):
                       weekly.index("# ── 2b.")]
        assert "READ THE VERDICT FROM ITS OWN LAST TWO LINES" in block
        assert "judges it separately" in block

    def test_the_director_says_the_same_thing(self):
        doc = " ".join((ROOT / "skills" / "pipelines" /
                        "narrated-documentary" /
                        "script-director.md").read_text().split())
        assert "Read the verdict from the command's own last two lines" in doc
        assert 'Do not append `; echo "RC=$?"`' in doc

    def test_the_director_also_rules_out_a_heredoc(self):
        """A heredoc is a program, and a stage authoring programs is what
        STAGE_CONTRACT forbids. The 2026-11-11 rehearsal wrote itself an
        assemble_script.py."""
        doc = " ".join((ROOT / "skills" / "pipelines" /
                        "narrated-documentary" /
                        "script-director.md").read_text().split())
        assert "a heredoc is a program" in doc.lower()
        assert "STAGE_CONTRACT" in doc


class TestEchoIsAllowed:
    def test_the_allow_list_permits_echo(self):
        s = json.loads((ROOT / ".claude" / "settings.json").read_text())
        assert "Bash(echo:*)" in s["permissions"]["allow"]

    def test_heredocs_are_still_not_blanket_allowed(self):
        """Only `.venv/bin/python:*` and friends are allowed, and the
        director tells the stage not to pipe a heredoc into them."""
        s = json.loads((ROOT / ".claude" / "settings.json").read_text())
        allow = s["permissions"]["allow"]
        assert "Bash(bash:*)" not in allow
        assert "Bash(sh:*)" not in allow

    def test_the_dangerous_ones_are_still_denied(self):
        s = json.loads((ROOT / ".claude" / "settings.json").read_text())
        deny = s["permissions"]["deny"]
        for rule in ("Bash(rm -rf:*)", "Bash(git push:*)", "Bash(sudo:*)"):
            assert rule in deny, rule


class TestResumeStateKnowsAllThree:
    """Three stages means three checkpoints, and the resume map already had
    them — the single stage was writing checkpoint_research.json and
    checkpoint_proposal.json all along."""

    def test_the_map_covers_research_proposal_and_script(self):
        src = (ROOT / "scripts" / "resume_state.py").read_text()
        for stage, artifact in (("research", "research_brief.json"),
                                ("proposal", "proposal_packet.json"),
                                ("script", "script.json")):
            assert f'"{stage}": "{artifact}"' in src, stage

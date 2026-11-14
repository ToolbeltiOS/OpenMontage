"""A stage that finished and then overran is not a failed stage.

WHAT HAPPENED
-------------
The 2026-11-11 proposal stage wrote five concepts, selected one, and
checkpointed `completed` — and `scripts/write_checkpoint.py` validates the
artifact against its own schema before writing, so that file is proof the
packet is good. Then it spent its last turn and the runner failed the whole
run for it, with every artifact on disk and `resume_state` reading
research [x] proposal [x] script not started.

On a Friday that is a film abandoned over bookkeeping, after the work was
done.

THE BLOCK IS EXECUTED HERE, NOT GREPPED FOR, the same way
tests/automation/test_node_modules_is_real.py executes the node_modules
start check. A decision nobody has run is a comment — and the control
matters as much as the pass: a cap hit with NO completed checkpoint must
STILL FAIL, or this change would let a half-written artifact through to the
next stage.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_weekly.sh"

START = "# ── MAX_TURNS DECISION"
END = "# ── END MAX_TURNS DECISION ──"


def the_decision() -> str:
    text = RUNNER.read_text()
    assert START in text, "the max_turns decision block is gone or renamed"
    assert END in text, "the END marker is gone — the slice is unbounded"
    block = text[text.index(START):text.index(END)]
    assert "stage_finished_anyway" in block, (
        "the block no longer consults the checkpoint, so this test would "
        "pass against a version that failed every overrun")
    assert "reconcile_stage" in block, (
        "the block no longer consults the ARTIFACT, so run #5's scene_plan "
        "would be failed again — see TestTheArtifactIsTheAuthority")
    return block


def run_decision(tmp_path: Path, *, checkpoint_done: bool,
                 artifact_valid: bool = False
                 ) -> subprocess.CompletedProcess:
    """Execute the REAL block with both predicates stubbed.

    TWO predicates now, which is the 2026-11-14 change:

      `stage_finished_anyway` — did the stage SAY it finished (a completed
      checkpoint)? This was the only question, and run #5 showed it being
      wrong in both directions in one night.

      `reconcile_stage` — does the stage's canonical ARTIFACT validate? If
      it does, the runner writes the checkpoint the stage never got to and
      the run carries on; if it is missing or invalid, nothing changes and
      the stage still fails.

    Stubbing the predicates rather than $PY keeps this test about the
    DECISION, which is what has the branches in it. The predicates
    themselves are tested in tests/lib/test_checkpoint_reconcile.py.
    """
    harness = tmp_path / "decide.sh"
    harness.write_text(
        "set -uo pipefail\n"
        'say()    { echo "SAY: $*"; }\n'
        'notify() { echo "NOTIFY: $*"; }\n'
        f'stage_finished_anyway() {{ return {0 if checkpoint_done else 1}; }}\n'
        'reconcile_stage() { echo "reconcile: '
        + ("WROTE" if artifact_valid else "MISSING")
        + '"; return '
        + ("0" if artifact_valid else "1")
        + '; }\n'
        f'REPO="{tmp_path}"\n'
        'SLUG="a-film"\n'
        'name="proposal"\n'
        'cap=25\n'
        'base="/tmp/stage"\n'
        'kind="max_turns"\n'
        "decide() {\n"
        + the_decision()
        + "\n  return 77\n}\n"
          "decide\n"
          'echo "RC=$?"\n')
    return subprocess.run(["bash", str(harness)], capture_output=True,
                          text=True)


class TestItPassesWhenTheStageCheckpointedCompleted:
    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory):
        return run_decision(tmp_path_factory.mktemp("done"),
                            checkpoint_done=True)

    def test_it_returns_zero(self, result):
        assert "RC=0" in result.stdout, result.stdout

    def test_it_warns_in_the_run_log(self, result):
        assert "SAY:" in result.stdout
        assert "AFTER checkpointing completed" in result.stdout
        assert "warning, not failing" in result.stdout

    def test_it_warns_on_telegram_too(self, result):
        assert "NOTIFY:" in result.stdout
        assert "had already finished" in result.stdout

    def test_the_warning_says_the_run_carries_on(self, result):
        assert "The run CARRIES ON" in result.stdout

    def test_it_still_flags_the_lack_of_margin(self, result):
        """Passing is not the same as being fine: a stage that finishes on
        its last turn may not finish at all on a harder topic."""
        assert "no margin" in result.stdout


class TestTheControlItStillFailsWithoutACheckpoint:
    """THE CONTROL. Without this the change would pass a half-written
    artifact to the next stage."""

    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory):
        return run_decision(tmp_path_factory.mktemp("notdone"),
                            checkpoint_done=False)

    def test_it_returns_nine(self, result):
        assert "RC=9" in result.stdout, result.stdout

    def test_it_does_not_claim_the_stage_finished(self, result):
        assert "AFTER checkpointing completed" not in result.stdout
        assert "had already finished" not in result.stdout

    def test_it_says_why_it_failed(self, result):
        assert "No completed checkpoint" in result.stdout
        assert "the artifact is missing or does not validate" in result.stdout

    def test_it_reports_what_the_artifact_check_said(self, result):
        """The failure has to carry the reason, or the owner is left to
        rediscover it at 23:00."""
        assert "reconcile: MISSING" in result.stdout

    def test_it_still_offers_the_re_fire_line(self, result):
        assert "--resume" in result.stdout


class TestTheTwoPathsAreActuallyDifferent:
    """Both fixtures run the same bytes; only the stub's exit code differs.

    If this ever fails, the decision has stopped reading the checkpoint and
    both classes above are testing one branch twice.
    """

    def test_the_outcomes_diverge(self, tmp_path_factory):
        done = run_decision(tmp_path_factory.mktemp("a"),
                            checkpoint_done=True)
        not_done = run_decision(tmp_path_factory.mktemp("b"),
                                checkpoint_done=False)
        assert "RC=0" in done.stdout
        assert "RC=9" in not_done.stdout
        assert done.stdout != not_done.stdout


class TestTheCapsAfterThisChange:
    @pytest.fixture(scope="class")
    def flat(self) -> str:
        body = RUNNER.read_text()
        return " ".join(body.replace("#:", " ").split())

    def test_research_is_forty(self):
        assert 'TURNS_RESEARCH="${TURNS_RESEARCH:-40}"' in RUNNER.read_text()

    def test_and_it_is_recorded_as_a_margin_not_a_derivation(self, flat):
        """The measurement still says ~24. 40 is a judgement about an
        unattended Friday, and conflating the two is how a derivation
        becomes folklore."""
        assert "MARGIN DECISION, NOT A DERIVATION" in flat
        assert "~24 SDK turns of real work" in flat
        assert "The derivation did not change; the margin did." in flat

    def test_it_says_why_research_cost_varies(self, flat):
        assert "depends on the TOPIC" in flat

    def test_proposal_stays_at_twenty_five(self):
        assert 'TURNS_PROPOSAL="${TURNS_PROPOSAL:-25}"' in RUNNER.read_text()

    def test_the_script_cap_is_unchanged(self):
        assert 'TURNS_SCRIPT="${TURNS_SCRIPT:-120}"' in RUNNER.read_text()


class TestTheScriptStageCannotApproveItsOwnGate:
    """THE REGRESSION OF 2026-11-11, AND IT WAS MINE.

    The split commit gave the script stage `stage_preamble`, which told
    every stage to "AUTO-APPROVE YOUR OWN GATE ... write your checkpoint
    completed with human_approved=True". That instruction is for the
    bookkeeping gates after the script. The script stage obeyed it, wrote
    human_approved=True on a stage whose human_approval_required is True,
    and a `--resume` run then read `stage_done script` and skipped the only
    human gate in the pipeline — straight into scene_plan and assets, $24
    on a film nobody had read.

    `telegram_gate.py` writes no checkpoint at all, so before this fix the
    only writer of that flag for the script stage WAS the script stage. The
    skip branch's comment claimed the approval was "a fact on disk, not a
    flag this script is trusting itself about". It was a fact on disk
    written by the machine.
    """

    @pytest.fixture(scope="class")
    def runner(self) -> str:
        return RUNNER.read_text()

    def test_the_preamble_carves_the_script_stage_out(self, runner):
        assert "AUTO-APPROVE YOUR OWN GATE, UNLESS YOU ARE THE SCRIPT STAGE" \
            in runner

    def test_it_tells_the_script_stage_to_write_awaiting_human(self, runner):
        assert "--stage script --artifact script --status awaiting_human" \
            in runner

    def test_it_tells_the_script_stage_not_to_pass_the_flag(self, runner):
        flat = " ".join(runner.replace("\\`", "`").split())
        assert "DO NOT pass --human-approved" in flat

    def test_it_says_what_went_wrong(self, runner):
        flat = " ".join(runner.replace("\\`", "`").split())
        assert "has approved its own script" in flat

    def test_the_awaiting_human_warning_no_longer_contradicts_it(self, runner):
        """The preamble also says awaiting_human "stops the film". For the
        script stage stopping is the point, and both sentences are in the
        same prompt."""
        # the prompt is a heredoc, so its backticks are backslash-escaped in
        # the source; strip the escapes before matching prose
        flat = " ".join(runner.replace("\\`", "`").split())
        assert ("The script stage is the exception and writes "
                "`awaiting_human` ON PURPOSE") in flat

    def test_the_runner_records_the_approval_itself(self, runner):
        """And it must, or the resume-skip has no honest way to be true."""
        gate = runner[runner.index('case "$GATE" in'):]
        gate = gate[:gate.index("esac")]
        assert "write_checkpoint.py" in gate
        assert "--human-approved" in gate

    def test_recording_the_approval_is_not_allowed_to_fail_silently(self,
                                                                    runner):
        gate = runner[runner.index('case "$GATE" in'):]
        gate = gate[:gate.index("esac")]
        assert "fail " in gate

    def test_the_skip_comment_records_the_correction(self, runner):
        assert "CORRECTED 2026-11-11" in runner
        flat = " ".join(runner.split())
        assert "written by the SCRIPT STAGE" in flat

    def test_the_skip_still_requires_a_resume(self, runner):
        """A fresh run always asks. That is what kept the blast radius to
        resumes rather than every Friday."""
        assert 'if stage_done script && [[ -n "$RESUME" ]]; then' in runner


class TestTheArtifactIsTheAuthority:
    """THE GENERAL CASE THE RULE ABOVE MISSED, AND IT COST A FILM A NIGHT.

    Run #5, 2026-11-13. The scene_plan stage wrote a 158-scene
    `scene_plan.json` at 20:56 — schema-valid, 0.0 to 1191.9s with no gaps,
    matching the approved script exactly — and hit its 40-turn cap at 20:57,
    one turn before it could write the checkpoint. `stage_finished_anyway`
    had nothing to read, so the run was failed and $5.83 of correct work was
    thrown away over bookkeeping. The checkpoint had to be written by hand
    at 21:05 before the film could carry on.

    A checkpoint is bookkeeping; the ARTIFACT is the work. So when the
    checkpoint is absent the runner asks the artifact, and if it validates
    against its own schema it writes the checkpoint itself and carries on
    with a warning.

    The control is the whole reason this is safe: a MISSING or INVALID
    artifact must still fail, and the class above holds that.
    """

    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory):
        return run_decision(tmp_path_factory.mktemp("noteyet"),
                            checkpoint_done=False, artifact_valid=True)

    def test_it_returns_zero(self, result):
        assert "RC=0" in result.stdout, result.stdout

    def test_it_does_not_pretend_the_stage_checkpointed(self, result):
        """It did not. Saying so would make the run log a liar about the one
        thing this rule turns on."""
        assert "AFTER checkpointing completed" not in result.stdout

    def test_it_says_the_artifact_is_what_saved_it(self, result):
        assert "ARTIFACT VALIDATES" in result.stdout
        assert "the runner wrote the checkpoint" in result.stdout

    def test_it_warns_rather_than_passing_quietly(self, result):
        assert "warning, not failing" in result.stdout
        assert "NOTIFY:" in result.stdout
        assert "The run CARRIES ON" in result.stdout

    def test_the_telegram_message_names_the_measurement(self, result):
        """So the next person to read it knows which failure this is."""
        assert "scene_plan" in result.stdout
        assert "5.83" in result.stdout

    def test_it_still_flags_the_lack_of_margin(self, result):
        assert "no margin" in result.stdout

    def test_the_three_outcomes_are_three(self, tmp_path_factory):
        """Checkpointed, not-checkpointed-but-valid, and neither. If any two
        of these are the same bytes, a branch has stopped existing."""
        checkpointed = run_decision(tmp_path_factory.mktemp("c"),
                                    checkpoint_done=True)
        reconciled = run_decision(tmp_path_factory.mktemp("r"),
                                  checkpoint_done=False, artifact_valid=True)
        failed = run_decision(tmp_path_factory.mktemp("f"),
                              checkpoint_done=False, artifact_valid=False)
        assert "RC=0" in checkpointed.stdout
        assert "RC=0" in reconciled.stdout
        assert "RC=9" in failed.stdout
        assert len({checkpointed.stdout, reconciled.stdout,
                    failed.stdout}) == 3

    def test_a_checkpointed_stage_is_not_reconciled_twice(self,
                                                          tmp_path_factory):
        """The cheap path stays cheap: if the stage said it finished, the
        artifact check is not run at all."""
        done = run_decision(tmp_path_factory.mktemp("d"),
                            checkpoint_done=True, artifact_valid=True)
        assert "reconcile:" not in done.stdout


class TestTheWallCapUsesTheSameRule:
    """One rule, two clocks. The wall cap killed run #5's assets stage, and
    the same question — does the artifact validate — belongs there.
    """

    @pytest.fixture(scope="class")
    def block(self) -> str:
        text = RUNNER.read_text()
        start = "# ── WALL_CLOCK DECISION"
        end = "# ── END WALL_CLOCK DECISION ──"
        assert start in text and end in text
        return text[text.index(start):text.index(end)]

    def test_it_consults_the_artifact_too(self, block):
        assert "reconcile_stage" in block

    def test_it_asks_the_checkpoint_first(self, block):
        """Cheapest question first: the checkpoint is one file read."""
        assert block.index("stage_finished_anyway") < \
            block.index("reconcile_stage")

    def test_its_failure_still_names_the_wall(self, block):
        assert "ran out of time" in block

    def test_its_failure_carries_the_artifact_verdict(self, block):
        assert "$reconcile_out" in block


class TestTheCapsReMeasuredFromRunFive:
    """The 2026-11-11 rehearsal never reached scene_plan, assets or edit, so
    their caps were converted guesses. Run #5 ran all three on a real
    158-scene film and two of them failed. These assert that the numbers in
    the file are the measured ones, and — the part that rots first — that
    the file still says WHERE they came from.
    """

    @pytest.fixture(scope="class")
    def runner(self) -> str:
        return RUNNER.read_text()

    @pytest.fixture(scope="class")
    def flat(self, runner) -> str:
        return " ".join(runner.replace("#:", " ").split())

    def test_scene_plan_is_fifty_five(self, runner):
        assert 'TURNS_SCENE_PLAN="${TURNS_SCENE_PLAN:-55}"' in runner

    def test_and_it_is_41_plus_a_third(self, flat):
        """41 is a COMPLETION measurement: the artifact was written one turn
        before the cap landed, so the need is known rather than bounded."""
        assert "41 SDK TURNS" in flat
        assert "41 + a third = 54.67 -> 55" in flat
        assert "completion measurement" in flat.lower()

    def test_edit_is_eighty_one(self, runner):
        assert 'TURNS_EDIT="${TURNS_EDIT:-81}"' in runner

    def test_and_it_is_61_plus_a_third(self, flat):
        assert "61 + a third = 81.3 -> 81" in flat

    def test_edits_floor_is_recorded_as_weaker_than_a_need(self, flat):
        """THE HONEST PART. 61 turns did not finish the stage, so 61 is a
        floor. A derivation that hides that is folklore by Friday."""
        assert "61 SDK TURNS AND IT WAS NOT ENOUGH" in flat
        assert "is a FLOOR" in flat
        assert "nobody has measured a finished edit stage" in flat

    def test_it_says_what_makes_81_plausible(self, flat):
        """Three costs inside the 61 were removed the same day. If someone
        reverts one of those, this derivation stops holding."""
        assert "edit_decisions_digest.py" in flat
        assert "align_narration.py now skips" in flat
        assert "4 of the 61" in flat

    def test_it_refuses_the_next_doubling_in_advance(self, flat):
        """A cap raised to make a run pass measures nothing — the rule this
        file already holds, applied to the number most likely to be raised
        again at 23:00 on a Friday."""
        assert "the answer is NOT 108" in flat

    def test_assets_was_deliberately_not_re_measured(self, flat):
        """It hit the WALL cap with its checkpoint already written. Turns
        were not its constraint, so a turn cap derived from it would be a
        number about nothing."""
        assert 'TURNS_ASSETS="${TURNS_ASSETS:-30}"' in RUNNER.read_text()
        assert "NOT RE-MEASURED AND LEFT AT 30" in flat

    def test_the_margin_is_labelled_a_margin(self, flat):
        assert "It is a MARGIN, not a derivation." in flat

    def test_the_untouched_caps_are_untouched(self, runner):
        """Only the two the owner named moved."""
        assert 'TURNS_RESEARCH="${TURNS_RESEARCH:-40}"' in runner
        assert 'TURNS_PROPOSAL="${TURNS_PROPOSAL:-25}"' in runner
        assert 'TURNS_SCRIPT="${TURNS_SCRIPT:-120}"' in runner

    def test_every_cap_in_the_file_is_still_in_sdk_turns(self, flat):
        """The unit error of 2026-11-11, which halved every cap derived from
        a transcript index."""
        assert "THESE CAPS ARE IN SDK TURNS" in flat

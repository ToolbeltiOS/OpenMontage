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
    assert "resume_state.py" in block, (
        "the block no longer consults the checkpoint, so this test would "
        "pass against a version that failed every overrun")
    return block


def run_decision(tmp_path: Path, *, checkpoint_done: bool) -> subprocess.CompletedProcess:
    """Execute the REAL block with a stubbed resume_state.

    `--is-done` exits 0 when the stage is complete and 1 when it is not,
    which is the only thing the decision reads.
    """
    fake_py = tmp_path / "python"
    fake_py.write_text(textwrap.dedent(f"""\
        #!/bin/sh
        # stands in for $PY; the decision only ever calls resume_state.py
        exit {0 if checkpoint_done else 1}
        """))
    fake_py.chmod(0o755)

    harness = tmp_path / "decide.sh"
    harness.write_text(
        "set -uo pipefail\n"
        'say()    { echo "SAY: $*"; }\n'
        'notify() { echo "NOTIFY: $*"; }\n'
        f'PY="{fake_py}"\n'
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
        assert "half-written or absent" in result.stdout

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

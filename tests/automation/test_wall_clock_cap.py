"""The wall clock is the real budget. SDK turns are only a runaway stop.

WHY, MEASURED 2026-11-11
------------------------
SDK turns and work are unrelated. The script stage did the most work of any
stage that day — 209 transcript turns, 32 minutes, $18.86 — inside 15 of its
120 SDK turns. The proposal stage blew its cap of 25 on 50 transcript turns
and $2.91. The transcript-to-SDK ratio across four stages ran from 1.6 to
13.9, so no amount of measuring will make a turn cap track cost or effort.

Cost tracks TIME, because a `claude -p` stage re-reads its context on every
turn and the bill is context times turns. 32 minutes bought $18.86; 9
minutes bought $2.91.

macOS ships no timeout(1) and no gtimeout — `command -v timeout` finds
nothing on this machine — so the watchdog is built in the runner: claude in
the background, a second background process that sleeps the budget and
signals it, and a marker file to tell a killed claude from one that failed
on its own. Both of those come back non-zero.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_weekly.sh"

START = "# ── WALL_CLOCK DECISION"
END = "# ── END WALL_CLOCK DECISION ──"


def the_decision() -> str:
    text = RUNNER.read_text()
    assert START in text, "the wall-clock decision block is gone or renamed"
    assert END in text, "the END marker is gone — the slice is unbounded"
    block = text[text.index(START):text.index(END)]
    assert "stage_finished_anyway" in block, (
        "the wall cap no longer consults the checkpoint, so a stage that "
        "finished and ran over the clock would be failed")
    return block


def run_decision(tmp_path: Path, *, timed_out: bool,
                 checkpoint_done: bool) -> subprocess.CompletedProcess:
    marker = tmp_path / "stage.timedout"
    if timed_out:
        marker.write_text("")
    harness = tmp_path / "decide.sh"
    harness.write_text(
        "set -uo pipefail\n"
        'say()    { echo "SAY: $*"; }\n'
        'notify() { echo "NOTIFY: $*"; }\n'
        f'stage_finished_anyway() {{ return {0 if checkpoint_done else 1}; }}\n'
        f'marker="{marker}"\n'
        'name="script"\n'
        'wall_min=60\n'
        'wall_var="WALL_SCRIPT"\n'
        'base="/tmp/stage"\n'
        'SLUG="a-film"\n'
        "decide() {\n" + the_decision() + "\n  return 77\n}\n"
        "decide\n"
        'echo "RC=$?"\n')
    return subprocess.run(["bash", str(harness)], capture_output=True,
                          text=True)


class TestNoTimeoutMeansNoDecision:
    def test_the_block_is_skipped_when_the_marker_is_absent(self, tmp_path):
        r = run_decision(tmp_path, timed_out=False, checkpoint_done=False)
        assert "RC=77" in r.stdout, r.stdout
        assert "SAY:" not in r.stdout


class TestTimedOutAndFinished:
    @pytest.fixture
    def result(self, tmp_path):
        return run_decision(tmp_path, timed_out=True, checkpoint_done=True)

    def test_it_returns_zero(self, result):
        assert "RC=0" in result.stdout, result.stdout

    def test_it_warns_in_the_log_and_on_telegram(self, result):
        assert "AFTER checkpointing completed" in result.stdout
        assert "NOTIFY:" in result.stdout
        assert "had already finished" in result.stdout

    def test_it_says_the_run_carries_on(self, result):
        assert "The run CARRIES ON" in result.stdout

    def test_it_names_the_cap_in_minutes(self, result):
        assert "60-minute wall cap" in result.stdout

    def test_it_clears_the_marker(self, tmp_path):
        """Or the next attempt in the retry loop would read a stale one and
        believe it timed out before it started."""
        marker = tmp_path / "stage.timedout"
        run_decision(tmp_path, timed_out=True, checkpoint_done=True)
        assert not marker.exists()


class TestTheControlTimedOutAndNotFinished:
    @pytest.fixture
    def result(self, tmp_path):
        return run_decision(tmp_path, timed_out=True, checkpoint_done=False)

    def test_it_fails(self, result):
        assert "RC=11" in result.stdout, result.stdout

    def test_it_reports_the_checkpoint_state(self, result):
        """The owner's requirement: the failure says what state the stage
        was left in, not just that the clock ran out."""
        assert "checkpoint: <b>not completed</b>" in result.stdout

    def test_it_does_not_claim_the_stage_finished(self, result):
        assert "had already finished" not in result.stdout

    def test_it_says_why_the_clock_is_the_budget(self, result):
        assert "cost tracks TIME" in result.stdout
        assert "$18.86" in result.stdout

    def test_it_offers_the_per_stage_override(self, result):
        """Named by variable, so the re-fire raises THIS stage's budget and
        not every stage's."""
        assert "WALL_SCRIPT=120" in result.stdout

    def test_it_says_what_survives(self, result):
        assert "Nothing is lost that was checkpointed" in result.stdout


class TestTheTwoPathsDiverge:
    def test_same_bytes_opposite_outcomes(self, tmp_path_factory):
        done = run_decision(tmp_path_factory.mktemp("a"), timed_out=True,
                            checkpoint_done=True)
        not_done = run_decision(tmp_path_factory.mktemp("b"), timed_out=True,
                                checkpoint_done=False)
        assert "RC=0" in done.stdout
        assert "RC=11" in not_done.stdout


class TestTheCaps:
    @pytest.fixture(scope="class")
    def runner(self) -> str:
        return RUNNER.read_text()

    @pytest.mark.parametrize("stage,minutes", [
        ("RESEARCH", 25), ("PROPOSAL", 20), ("SCRIPT", 60),
        ("SCENE_PLAN", 40), ("ASSETS", 60), ("EDIT", 60)])
    def test_the_owners_wall_cap(self, runner, stage, minutes):
        assert f'WALL_{stage}="${{WALL_{stage}:-{minutes}}}"' in runner

    def test_the_turn_caps_survive_as_a_runaway_stop(self, runner):
        for name, cap in (("RESEARCH", 40), ("PROPOSAL", 25), ("SCRIPT", 120)):
            assert f'TURNS_{name}="${{TURNS_{name}:-{cap}}}"' in runner

    def test_the_measurement_is_recorded_beside_both(self, runner):
        flat = " ".join(runner.replace("#:", " ").split())
        assert "SDK TURNS AND WORK ARE UNRELATED" in flat
        assert "1.6 to 13.9" in flat
        assert "15 of its 120 SDK turns" in flat
        assert "Cost tracks TIME" in flat

    def test_the_turn_caps_say_they_are_only_a_runaway_stop(self, runner):
        flat = " ".join(runner.replace("#:", " ").split())
        assert "kept only as a runaway stop" in flat

    def test_a_stage_with_no_entry_is_not_wall_capped(self, runner):
        """`notes` edits one file. A cap it cannot plausibly hit is noise."""
        assert "WALL_NOTES" not in runner
        flat = " ".join(runner.replace("#:", " ").split())
        assert "not wall-capped" in flat


class TestTheWatchdogItself:
    @pytest.fixture(scope="class")
    def claude_stage(self) -> str:
        body = RUNNER.read_text()
        return body[body.index("claude_stage() {"):
                    body.index("# ── WALL_CLOCK DECISION")]

    def test_there_is_no_timeout_binary_to_rely_on(self):
        """The reason the watchdog exists at all."""
        found = subprocess.run("command -v timeout || command -v gtimeout",
                               shell=True, capture_output=True, text=True,
                               executable="/bin/bash")
        assert found.returncode != 0, (
            "this machine HAS timeout(1) now — the hand-rolled watchdog "
            "could be replaced by it, which would be simpler")

    def test_it_backgrounds_claude_and_watches_it(self, claude_stage):
        assert "claude \"${args[@]}\" > \"$base.json\" 2> \"$base.err\" &" in \
            claude_stage
        assert "sleep \"$wall_s\"" in claude_stage

    def test_it_terms_before_it_kills(self, claude_stage):
        """A TERM'd claude can flush its JSON; a KILL'd one cannot."""
        assert claude_stage.index("kill -TERM") < claude_stage.index("kill -KILL")

    def test_it_marks_the_timeout_so_it_can_be_told_apart(self, claude_stage):
        """A TERM'd claude and one that failed on its own both exit
        non-zero. Without the marker the runner cannot distinguish them."""
        assert ': > "$marker"' in claude_stage

    def test_it_clears_a_stale_marker_before_each_attempt(self, claude_stage):
        assert 'rm -f "$marker"' in claude_stage

    def test_it_stops_watching_once_claude_is_done(self, claude_stage):
        """An orphan watchdog would TERM whatever took that pid later."""
        assert 'kill "$wpid"' in claude_stage

    def test_an_uncapped_stage_runs_in_the_foreground(self, claude_stage):
        assert "(( wall_s > 0 ))" in claude_stage

    def test_the_cap_is_looked_up_per_stage(self, claude_stage):
        assert 'wall_var="WALL_$(printf' in claude_stage
        assert '${!wall_var:-0}' in claude_stage

    def test_a_hyphenated_stage_name_maps_to_its_variable(self):
        """scene_plan is already underscored, but a `-` in a stage name
        would silently look up nothing and uncap the stage."""
        got = subprocess.run(
            ["bash", "-c",
             'name="scene-plan"; printf "%s" "WALL_$(printf \'%s\' "$name" '
             '| tr "[:lower:]-" "[:upper:]_")"'],
            capture_output=True, text=True)
        assert got.stdout == "WALL_SCENE_PLAN"

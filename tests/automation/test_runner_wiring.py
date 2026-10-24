"""The weekly runner's shape, read from the file.

Three things here were wrong on disk and silent: the launchd agent pointed at
a path with a stray "22:" in it and would never have run, its schedule said
Friday in a comment and Sunday in the keys, and every `claude -p` call was a
bare invocation that died on a usage limit with no way back in.
"""
from __future__ import annotations

import plistlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_weekly.sh"
PLIST = ROOT / "launchd" / "com.wak3up.docs.weekly.plist"


class TestTheAgentCanActuallyFire:
    def test_the_program_it_runs_exists(self):
        """A path with a stray "22:" in it is a Friday that never happens."""
        d = plistlib.loads(PLIST.read_bytes())
        program = Path(d["ProgramArguments"][-1])
        assert program.exists(), f"launchd points at {program}, which is not there"

    def test_it_fires_friday_at_nineteen_hundred(self):
        """Weekday 5 is Friday. It said Weekday 0 — Sunday — under a comment
        claiming Friday, which is not the same day or the same hour."""
        d = plistlib.loads(PLIST.read_bytes())
        when = d["StartCalendarInterval"]
        assert when["Weekday"] == 5, when
        assert when["Hour"] == 19, when

    def test_the_comment_and_the_keys_agree(self):
        text = PLIST.read_text()
        assert "Friday 19:00" in text


class TestEveryClaudeStageIsResumable:
    def test_claude_is_invoked_in_exactly_one_place(self):
        """The wrapper, and nowhere else.

        A second bare `claude -p` would be a stage that cannot be slept on
        and re-entered — which is the whole defect. Comments and the strings
        `say` prints are not invocations, so they are stripped first.
        """
        body = RUNNER.read_text()
        lines = [l for l in body.splitlines() if not l.lstrip().startswith("#")]
        # strip double-quoted strings, so `say "writing the script (claude -p)"`
        # is not read as running it
        stripped = [re.sub(r'"[^"]*"', '""', l) for l in lines]
        calls = [i for i, l in enumerate(stripped)
                 if re.search(r"(^|\s|\|)claude\s+-p\b", l)]
        assert len(calls) == 1, (
            f"{len(calls)} places run `claude -p`; only claude_stage() may")

        # and that one call is inside claude_stage()
        start = next(i for i, l in enumerate(lines) if l.startswith("claude_stage()"))
        end = next(i for i, l in enumerate(lines[start:], start) if l == "}")
        assert start < calls[0] < end, (
            "the one `claude -p` is outside claude_stage(), so it is not wrapped")

    def test_the_wrapper_sleeps_only_on_a_usage_limit(self):
        body = RUNNER.read_text()
        assert "usage_limit.py" in body
        assert "MAX_RESUMES" in body

    def test_it_gives_up_loudly_rather_than_waiting_out_a_week(self):
        body = RUNNER.read_text()
        assert "giving up" in body

    def test_it_says_when_it_will_be_back(self):
        """The owner asked for 'paused: usage limit, resuming at <time>'."""
        body = RUNNER.read_text()
        assert "paused: usage limit, resuming at" in body

    def test_both_long_stages_are_told_to_resume(self):
        """A stage that re-enters without this starts at research again."""
        body = RUNNER.read_text()
        assert body.count("resume_state.py") >= 2, (
            "the script stage and the render stage both have to be told what "
            "is already finished")


class TestWhatAFilmCostIsRecorded:
    def test_usage_is_written_per_stage(self):
        body = RUNNER.read_text()
        assert "stage_usage.py" in body
        assert "usage.jsonl" in body

    def test_the_run_ends_with_a_total(self):
        body = RUNNER.read_text()
        assert "what this film cost" in body
        assert "TOTAL" in body

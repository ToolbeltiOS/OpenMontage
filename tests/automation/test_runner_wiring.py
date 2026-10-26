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
        # Comments too, not just quoted strings: this file now DISCUSSES
        # `claude -p` in its header, and a sentence about a call is not one.
        stripped = [re.sub(r'"[^"]*"', '""', l) for l in lines]
        stripped = ["" if l.lstrip().startswith("#") else l for l in stripped]
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

    def test_the_resume_cap_is_actually_SET(self):
        """A name the script only MENTIONS is not a cap.

        This assertion used to be `"MAX_RESUMES" in body`, which passed while
        the variable was used four times and assigned nowhere. Measured, under
        `set -u` an unbound name in `(( ))` ABORTS THE SHELL — neither branch
        runs, nothing after runs, and the exit status is 0. The first usage
        limit would have killed the weekly run silently, looking to launchd
        like a clean finish.
        """
        import re

        body = RUNNER.read_text()
        assert re.search(r"^MAX_RESUMES=", body, re.M), (
            "MAX_RESUMES is used but never assigned")

    def test_the_cap_holds_when_the_script_is_actually_run(self):
        """INJECTED: run the arithmetic under the shell's own options.

        Reading the file cannot tell you what `set -u` does to an unbound
        name in `(( ))`. Running it can.
        """
        import re
        import subprocess

        body = RUNNER.read_text()
        assign = re.search(r"^(MAX_RESUMES=\S+)", body, re.M)
        assert assign, "MAX_RESUMES is not assigned"
        # `bash <file>`, which is how launchd invokes it — not `bash -c`,
        # which aborts with a different status.
        import tempfile

        probe = f"""set -uo pipefail
{assign.group(1)}
resumes=7
if (( resumes > MAX_RESUMES )); then echo CAPPED; else echo FELL_THROUGH; fi
"""
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
            fh.write(probe)
            path = fh.name
        out = subprocess.run(["bash", path], capture_output=True, text=True)
        assert out.stdout.strip() == "CAPPED", (
            f"stdout={out.stdout!r} stderr={out.stderr!r} — the cap does not "
            f"hold under the options the runner sets")

    def test_an_unset_cap_kills_the_run_silently_which_is_the_defect(self):
        """The same probe without the assignment, to prove the test can fail.

        And to pin what actually happens, because it is not what it looks
        like: the shell aborts, so NEITHER branch runs and nothing after the
        `if` runs either — and it exits 0, so the caller cannot tell.
        """
        import subprocess

        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
            fh.write("""set -uo pipefail
resumes=7
if (( resumes > MAX_RESUMES )); then echo CAPPED; else echo FELL; fi
echo AFTER
""")
            path = fh.name
        out = subprocess.run(["bash", path], capture_output=True, text=True)
        assert out.stdout.strip() == "", (
            f"expected the shell to abort before printing anything; "
            f"got {out.stdout!r}")
        assert "unbound variable" in out.stderr
        assert out.returncode == 0, (
            f"the silent part: launchd runs `bash <file>` and that form exits "
            f"0, so a run killed this way looks like a clean finish. Got "
            f"{out.returncode}.")

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


class TestSmokeMode:
    """`--dry-run` proves the hand-offs. It does not prove the schedule.

    The thing that actually goes wrong with a scheduled job is whether launchd
    runs the script at all, with the right environment, writing where it
    should — and the agent's plist pointed at a file that did not exist for
    three days without anything noticing, because nothing had ever made
    launchd try.

    RUN_WEEKLY_SMOKE=1 runs the real path and stops at the gate.
    """

    def test_it_is_read_from_the_environment(self):
        import re

        body = RUNNER.read_text()
        assert re.search(r'^SMOKE="\$\{RUN_WEEKLY_SMOKE:-0\}"', body, re.M)

    def test_it_does_not_call_claude(self):
        body = RUNNER.read_text()
        i = body.index('if [[ "$SMOKE" == "1" ]]; then\n  say "smoke: not calling claude -p"')
        assert i > 0

    def test_it_stops_at_the_gate_and_exits_zero(self):
        body = RUNNER.read_text()
        block = body[body.index("# ── 3. the human"):]
        block = block[:block.index("# ── 4. the render")]
        assert "smoke run reached the gate" in block
        assert "exit 0" in block

    def test_it_stops_before_the_render_and_the_publish(self):
        body = RUNNER.read_text()
        smoke_exit = body.index('say "done (smoke)"')
        assert smoke_exit < body.index("# ── 4. the render")
        assert smoke_exit < body.index("# ── 5. publish")

    def test_it_still_takes_the_lock_and_rotates_the_logs(self):
        """The point is to exercise those, not to skip them."""
        body = RUNNER.read_text()
        smoke_exit = body.index('say "done (smoke)"')
        assert body.index("rotate_logs.sh") < smoke_exit
        assert body.index('mkdir "$LOCK"') < smoke_exit
        assert body.index("pick_topic.py") < smoke_exit

    def test_the_telegram_line_is_the_one_asked_for(self):
        body = RUNNER.read_text()
        assert "<b>smoke run reached the gate</b>" in body

    def test_the_plist_carries_no_smoke_variable(self):
        """Friday must run for real. This fails if the env is left behind."""
        from pathlib import Path

        for plist in (Path("launchd/com.wak3up.docs.weekly.plist"),
                      Path.home() / "Library" / "LaunchAgents"
                      / "com.wak3up.docs.weekly.plist"):
            if plist.exists():
                assert "RUN_WEEKLY_SMOKE" not in plist.read_text(), (
                    f"{plist} still carries the smoke flag — Friday would "
                    f"pick a topic, post to Telegram and stop")

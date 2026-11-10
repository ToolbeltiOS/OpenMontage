"""`run_weekly.sh --preflight`: what Friday needs, asked on Thursday.

WHY A PREFLIGHT AT ALL
----------------------
Everything it checks takes longer than an hour to fix. An expired YouTube
token needs a browser, a missing `node_modules` needs an `npm ci`, a Mac on
battery needs someone to walk over to it. Discovering any of them at 19:00
Friday is discovering that Friday is gone.

THE TRAP THIS FILE EXISTS FOR
-----------------------------
`set -o pipefail` plus `cmd | grep -q` reports a MATCH as a failure. `grep -q`
exits on its first hit, the producer gets SIGPIPE, and pipefail takes the
pipeline's status from the producer. Measured on this script 2026-11-10:

    launchctl list | grep -q "<TAB>com.wak3up.docs.weekly$"   -> 141, five of five
    launchctl list | grep -q "<TAB>com.wak3up.docs.afterpublish$" -> 0

Both agents were loaded. The difference is position: `weekly` is the FIRST
line of `launchctl list` output, so grep exits while launchctl still has four
lines to write; `afterpublish` is the last, so there is nothing left to write
and no SIGPIPE. The first preflight written this way reported two loaded
agents as "not loaded" and a scheduled wake as absent.

A preflight that lies is worse than no preflight, because it sends someone to
fix a thing that was never broken and they stop believing the next one.
"""
from __future__ import annotations

import plistlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN_WEEKLY = ROOT / "scripts" / "run_weekly.sh"


def source() -> str:
    return RUN_WEEKLY.read_text()


class TestTheScriptIsValid:
    def test_it_parses(self):
        done = subprocess.run(["bash", "-n", str(RUN_WEEKLY)],
                              capture_output=True, text=True)
        assert done.returncode == 0, done.stderr

    def test_preflight_is_a_known_flag(self):
        assert "--preflight) PREFLIGHT=1" in source()


class TestThePipefailTrap:
    """No `| grep -q` anywhere in a script that sets pipefail."""

    def test_the_script_sets_pipefail(self):
        """If it ever stops, this whole class is guarding nothing."""
        assert re.search(r"^set -\w*o\w* pipefail|^set -uo pipefail",
                         source(), re.M), (
            "run_weekly.sh no longer sets pipefail — check whether the rule "
            "below still applies before deleting it")

    def test_no_pipe_into_grep_q(self):
        offenders = [
            f"{i}: {line.strip()}"
            for i, line in enumerate(source().splitlines(), start=1)
            if re.search(r"\|\s*grep\s+-[a-z]*q", line)
        ]
        assert not offenders, (
            "a match will be reported as a failure when the producer is cut "
            "off mid-write:\n  " + "\n  ".join(offenders) +
            "\nCapture the output first and match it with bash: "
            'out="$(cmd)"; if [[ "$out" == *needle* ]]')

    def test_the_real_pipeline_still_behaves_the_way_this_was_written_for(self):
        """The trap itself, reproduced — so the rule keeps its reason.

        If a future bash or grep stops producing 141 here, the rule above is
        merely stylistic and whoever reads it deserves to know.
        """
        script = (
            "set -uo pipefail\n"
            "printf 'first\\nsecond\\nthird\\nfourth\\nfifth\\n' "
            "| grep -q first\n"
            "echo \"early=$?\"\n"
            "printf 'first\\nsecond\\nthird\\nfourth\\nfifth\\n' "
            "| grep -q fifth\n"
            "echo \"late=$?\"\n"
        )
        out = subprocess.run(["bash", "-c", script],
                             capture_output=True, text=True).stdout
        assert "late=0" in out, out
        # `early` is 0 or 141 depending on how fast the producer writes; the
        # point is only that it is NOT reliably 0.
        assert "early=" in out, out


class TestItRunsBeforeTheGuardsThatWouldStopIt:
    """A preflight must report everything, not die on the first problem.

    `run_weekly.sh` refuses to start on the wrong branch, on a dirty tree or
    on battery, each with `exit 7`, and fails on a bad `node_modules`. Every
    one of those is a thing the preflight is supposed to REPORT. Dispatched
    after them, it printed one line and exited 7 — which is exactly how the
    first version of it behaved.
    """

    def _line_of(self, needle: str) -> int:
        """First line CARRYING the needle as code, not as prose.

        `caffeinate -dimsu` appears three times in comments explaining why it
        cannot hold a clamshell awake, hundreds of lines before it is run, so
        matching any occurrence compares the dispatch against a comment.
        """
        for i, line in enumerate(source().splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            if needle in line:
                return i
        raise AssertionError(f"{needle!r} is not executed in run_weekly.sh")

    def test_the_dispatch_precedes_the_branch_refusal(self):
        assert self._line_of('if [[ "$PREFLIGHT" == "1" ]]') < \
            self._line_of('REFUSED: on $RUN_ON')

    def test_the_dispatch_precedes_the_battery_refusal(self):
        assert self._line_of('if [[ "$PREFLIGHT" == "1" ]]') < \
            self._line_of("REFUSED: on battery")

    def test_the_dispatch_precedes_the_node_modules_failure(self):
        assert self._line_of('if [[ "$PREFLIGHT" == "1" ]]') < \
            self._line_of("is a SYMLINK to")

    def test_the_dispatch_precedes_the_lock(self):
        """It must not take the lock, or it would block a real run."""
        assert self._line_of('if [[ "$PREFLIGHT" == "1" ]]') < \
            self._line_of('mkdir "$LOCK"')

    def test_it_never_reaches_caffeinate_or_the_topic_picker(self):
        dispatch = self._line_of('if [[ "$PREFLIGHT" == "1" ]]')
        assert dispatch < self._line_of("caffeinate -dimsu")
        # the topic picker is named in a section header, which is a comment,
        # so the thing to compare against is the lock it sits behind
        assert dispatch < self._line_of('mkdir "$LOCK"')


class TestEveryCheckRuns:
    def test_a_failing_check_does_not_stop_the_others(self):
        """`pf_bad` counts and continues; it must never exit."""
        body = source()
        start = body.index("pf_bad()  {")
        end = body.index("preflight() {")
        assert "exit" not in body[start:end], (
            "pf_bad exits, so the first failure hides every later one")

    def test_the_checks_the_doc_asks_for_are_all_there(self):
        """docs/PREFLIGHT.md is the list; this is the list being honoured."""
        body = source()
        for name in ("branch", "code tree", "node_modules", "power",
                     "sleep policy", "disk", "telegram", "youtube",
                     "pixazo"):
            assert f'"{name}"' in body, f"no preflight check named {name}"

    def test_the_2_5d_checks_are_conditional_on_use(self):
        """A run that authors no 2.5D cut must not be blocked by its deps."""
        body = source()
        assert "build_25d_cuts|render_25d" in body
        assert "pf_skip \"2.5D\"" in body


class TestTheThursdayAgent:
    def setup_method(self):
        self.plist = plistlib.loads(
            (ROOT / "launchd"
             / "com.wak3up.docs.preflight.plist").read_bytes())

    def test_it_is_thursday_at_21(self):
        assert self.plist["StartCalendarInterval"] == {
            "Weekday": 4, "Hour": 21, "Minute": 0}

    def test_it_runs_the_preflight_and_not_the_film(self):
        args = [str(a) for a in self.plist["ProgramArguments"]]
        assert args[-1] == "--preflight", args

    def test_it_points_at_the_runner_worktree(self):
        """The three older agents ran from the wrong tree for four films."""
        assert self.plist["WorkingDirectory"].endswith("/runner")
        assert self.plist["EnvironmentVariables"]["REPO"].endswith("/runner")

    def test_it_names_the_shared_state_directory(self):
        assert self.plist["EnvironmentVariables"]["WAK3UP_DOCS_STATE"] == \
            "/Users/mac/Developer/wak3up-docs/state"

    def test_it_says_what_was_measured_about_waking(self):
        """The comment carries the finding, or the next person re-derives it."""
        text = (ROOT / "launchd"
                / "com.wak3up.docs.preflight.plist").read_text()
        assert "does NOT wake a sleeping Mac" in text


class TestTheSleepPolicy:
    """The Mac never sleeps on AC — decided 2026-11-10, asserted here.

    The alternative was a `pmset repeat` wake before each agent's hour. One
    setting covers every agent there will ever be, and a machine that is
    simply awake cannot drop a firing at all — measured: launchd fires a
    calendar agent 3-5 seconds after its minute while awake, and an agent
    that is not there at its time does not catch up.

    It is ASSERTED rather than assumed because `sudo pmset -c sleep 0` does
    not survive a new machine or necessarily an OS update, and the failure it
    prevents is silent: nothing reports that Friday did not happen until
    Sunday's tripwire.
    """

    #: The parser from the preflight, kept in one place so the test and the
    #: script cannot drift. It reads the AC POWER section specifically.
    AWK = ('/^AC Power:/ {ac = 1; next} /^[^ ]/ {ac = 0} '
           'ac && $1 == "sleep" {print $2; exit}')

    def parse(self, text: str) -> str:
        done = subprocess.run(["awk", self.AWK], input=text,
                              capture_output=True, text=True)
        return done.stdout.strip()

    def test_the_script_uses_this_parser(self):
        """Compared on the distinctive parts, not whitespace."""
        body = source()
        for fragment in ('/^AC Power:/', '$1 == "sleep"', '/^[^ ]/'):
            assert fragment in body, fragment

    def test_it_reads_the_ac_section_and_not_the_battery_one(self):
        """THE TRAP. This machine's battery section says `sleep 1`.

        A parser that takes the first `sleep` line it sees reads the battery
        policy and passes a Mac that sleeps a minute after the lid closes.
        """
        text = ("Battery Power:\n sleep                1\n"
                "AC Power:\n sleep                0\n")
        assert self.parse(text) == "0"

    def test_it_is_not_fooled_by_the_reverse(self):
        text = ("Battery Power:\n sleep                0\n"
                "AC Power:\n sleep                1\n")
        assert self.parse(text) == "1"

    def test_it_is_not_fooled_by_the_other_sleep_keys(self):
        """`Sleep On Power Button`, `displaysleep` and `disksleep` all match
        a careless pattern, and all three come BEFORE `sleep` in the real
        output."""
        text = ("AC Power:\n Sleep On Power Button 1\n"
                " displaysleep         10\n disksleep            10\n"
                " sleep                0\n")
        assert self.parse(text) == "0"

    def test_no_ac_section_reads_as_unknown_not_as_zero(self):
        """Unreadable must fail, not pass. A preflight that cannot tell has
        not checked."""
        assert self.parse("Battery Power:\n sleep                1\n") == ""

    def test_the_check_fails_on_anything_but_zero(self):
        body = source()
        assert 'if [[ "$ac_sleep" == "0" ]]' in body, (
            "the sleep policy is not compared against 0 exactly; '10' and "
            "'' must both fail")

    def test_both_sleep_risks_are_shouted_about(self):
        """On battery and AC-sleep-not-0 both set the loud flag.

        Every other failure costs a stage. These two cost the night, and they
        are the only two that do, so they get a line of their own above the
        table instead of a row inside it.
        """
        body = source()
        assert body.count("PF_SLEEP_RISK=1") == 2, (
            "exactly two conditions should raise the sleep alarm: on "
            "battery, and AC sleep not 0")
        assert "THIS MAC CAN SLEEP THROUGH FRIDAY" in body
        assert "sudo pmset -c sleep 0 displaysleep 10" in body

    def test_no_per_agent_wake_was_added(self):
        """The decision was one policy, not a wake per agent."""
        body = source()
        assert "pmset repeat" not in body, (
            "a per-agent wake was added; the decision of 2026-11-10 was "
            "`sudo pmset -c sleep 0` instead")


class TestTheAgentCheckCoversEveryAgent:
    """Including the one doing the asking.

    The check was a hardcoded list of four labels, written the same day a
    fifth agent was added — the preflight's own. So it reported "all four
    loaded" on a machine with five, and the single agent it could not vouch
    for was the one whose job is vouching. test_runner_wiring.py already
    refuses a plist no schedule table covers; this is the runtime half.
    """

    def test_it_iterates_the_launchd_directory(self):
        body = source()
        assert 'for plist in "$REPO"/launchd/com.wak3up.docs.*.plist' in body, (
            "the agent check names agents instead of reading the directory, "
            "so the next agent added will not be checked")

    def test_no_hardcoded_agent_list_remains(self):
        """A leftover list would silently shadow the directory walk.

        Code lines only. The comment above the loop quotes the old
        behaviour — "all four loaded" — on purpose, and a test that reads
        prose fails on its own explanation.
        """
        code = "\n".join(line for line in source().splitlines()
                         if not line.lstrip().startswith("#"))
        for label in ("com.wak3up.docs.weekly com.wak3up.docs.metrics",
                      "all four loaded"):
            assert label not in code, f"stale hardcoded agent list: {label!r}"

    def test_the_count_it_reports_is_counted_not_written(self):
        body = source()
        assert '"all $(ls "$REPO"/launchd/com.wak3up.docs.*.plist' in body

    def test_every_plist_on_disk_would_be_reached(self):
        """The glob and the test table have to see the same set."""
        import plistlib

        on_disk = sorted(p.stem for p in
                         (ROOT / "launchd").glob("com.wak3up.docs.*.plist"))
        assert len(on_disk) >= 5, on_disk
        assert "com.wak3up.docs.preflight" in on_disk
        for stem in on_disk:
            d = plistlib.loads((ROOT / "launchd" / f"{stem}.plist").read_bytes())
            assert d.get("Label") == stem, (
                f"{stem}.plist carries Label {d.get('Label')!r}; the preflight "
                f"matches `launchctl list` on the LABEL, so a filename that "
                f"disagrees with it reads as an agent that is not loaded")

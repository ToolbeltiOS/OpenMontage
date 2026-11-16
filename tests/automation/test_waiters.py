"""How a waiter waits, and the one way of writing it that hangs forever.

2026-11-15, twice in one session, and 2026-11-14 once before that.

Three background shells were started to wait for the same test suite:

    until ! pgrep -f "pytest tests/" >/dev/null; do sleep 20; done; ...

The suite finished green and not one of them ever said so. The night before,
two shells waiting for `repatch_plate.py` hung the same way while the
repatch had been finished for forty minutes.

THE CAUSE, WHICH IS NOT THE OBVIOUS ONE
---------------------------------------
The first explanation given was that each waiter matched ITSELF — its own
command line contains the pattern it greps for. That is wrong, and the
control below falsifies it: `pgrep` excludes its own process, and a lone
waiter reports `clear` exactly as intended.

What actually happens needs TWO of them. A waiter's command line is a
perfectly ordinary process to everybody else's `pgrep`, so when two waiters
carry the same pattern, each one sees THE OTHER, neither ever sees an empty
result, and both wait for ever — with the thing they were waiting for long
since finished. One waiter is fine. Two are a deadlock, and the second one
usually exists because the first appeared to be stuck.

THE FIX IS TO WAIT ON SOMETHING THAT IS NOT A NAME
--------------------------------------------------
A pid (`kill -0 "$pid"`) is a specific process and cannot be confused with
a description of one. A file — a sentinel, a pidfile the exit trap removes,
a result's mtime — is not a process at all. Everything in this repo already
does one of those; this file keeps it that way.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Deliberately unlike anything real, so a match can only be a waiter.
PATTERN = "wak3up_waiter_control_pattern"

#: A capped waiter: reports what it saw instead of hanging, so the control
#: can be a test rather than a story about one.
WAITER = (
    f'for i in 1 2; do '
    f'if pgrep -f "{PATTERN}" >/dev/null; then echo MATCHED; '
    f'else echo clear; fi; sleep 1; done'
)


def no_target_is_running() -> bool:
    """Nothing but waiters can match. Asserted, not assumed."""
    out = subprocess.run(["ps", "-ax", "-o", "command"],
                         capture_output=True, text=True).stdout
    hits = [line for line in out.splitlines()
            if PATTERN in line and "pgrep" not in line]
    return len(hits) == 0


class TestAProcessNameWaiterDeadlocks:
    def test_one_waiter_alone_reports_clear(self):
        """Which is why the defect hid: written once, it works.

        This is also the test that falsifies "it matched itself".
        """
        done = subprocess.run(["/bin/sh", "-c", WAITER],
                              capture_output=True, text=True, timeout=30)
        assert done.stdout.split() == ["clear", "clear"], done.stdout

    def test_two_concurrent_waiters_match_EACH_OTHER(self):
        """THE CONTROL THAT REPRODUCES THE HANG.

        Neither waiter would ever have exited. They are capped at two ticks
        so that the hang is measured rather than suffered.
        """
        a = subprocess.Popen(["/bin/sh", "-c", WAITER],
                             stdout=subprocess.PIPE, text=True)
        b = subprocess.Popen(["/bin/sh", "-c", WAITER],
                             stdout=subprocess.PIPE, text=True)
        try:
            out_a, _ = a.communicate(timeout=30)
            out_b, _ = b.communicate(timeout=30)
        finally:
            for proc in (a, b):
                if proc.poll() is None:              # pragma: no cover
                    proc.kill()
        assert "MATCHED" in out_a and "MATCHED" in out_b, (out_a, out_b)

    def test_and_nothing_they_were_waiting_for_was_ever_running(self):
        """The whole defect in one assertion: they matched each other while
        the job had already finished."""
        assert no_target_is_running()

    def test_waiting_on_a_pid_is_immune(self):
        """The same wait, written the way the repo writes it."""
        script = (
            '/bin/sh -c "sleep 1" & pid=$!; '
            'ticks=0; '
            'while kill -0 "$pid" 2>/dev/null; do '
            '  ticks=$((ticks+1)); sleep 1; '
            '  if [ "$ticks" -gt 10 ]; then echo STUCK; exit 1; fi; '
            'done; echo RELEASED'
        )
        done = subprocess.run(["/bin/sh", "-c", script],
                              capture_output=True, text=True, timeout=40)
        assert done.stdout.strip() == "RELEASED", done.stdout


class TestTheRepoNeverWaitsOnAProcessName:
    """The repo was already clean when this was written — every waiter in it
    uses `kill -0` on a captured pid. That is the state being held."""

    SEARCHED = ("scripts", "lib", "launchd", "docs")

    def tree(self):
        for folder in self.SEARCHED:
            for path in sorted((ROOT / folder).rglob("*")):
                if (path.is_file() and path.suffix in (".sh", ".py", ".plist")
                        and "__pycache__" not in str(path)):
                    yield path

    def test_nothing_polls_for_a_process_by_name(self):
        offenders = []
        for path in self.tree():
            text = path.read_text(encoding="utf-8", errors="replace")
            for n, line in enumerate(text.splitlines(), start=1):
                bare = line.strip()
                if bare.startswith("#") or bare.startswith("//"):
                    continue
                if "pgrep" in bare or "pkill" in bare:
                    offenders.append(f"{path.relative_to(ROOT)}:{n}: {bare}")
        assert offenders == [], (
            "a waiter that greps for a process NAME deadlocks against "
            "another copy of itself — wait on a pid or a file:\n"
            + "\n".join(offenders))

    def test_the_contract_tells_a_stage_how_to_wait(self):
        contract = (ROOT / "docs" / "STAGE_CONTRACT.md").read_text()
        assert "pgrep" in contract, (
            "the rule is not written down anywhere a stage will read it")

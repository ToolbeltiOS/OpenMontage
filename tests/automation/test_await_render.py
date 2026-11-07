"""The waiter answers from what exists while the render runs.

WHY THIS TEST EXISTS
--------------------
The first version of await_render.py read `render_status.json` for both
progress and completion. That file is written by `render_detached.sh`'s EXIT
trap, so it DOES NOT EXIST until the render is over. Observed on the live
king-tut render, 2026-11-07: 40 minutes in, Remotion at 11,842/36,803, and
`find -name 'render_status*'` empty across the whole runner — correctly, and
with nothing in the waiter able to say how far along the render was except
the one `tail -1` of render.log it printed every ten minutes.

Two things were wrong with resting on that file:

  * it is useless as a progress signal, because it only appears at the end;
  * it is fragile as a completion signal, because a render killed with
    SIGKILL, or one whose trap cannot write, finishes without ever producing
    it — and the waiter then reads "the process is gone and wrote no status"
    as "it was killed" for a render that may have delivered.

So every answer comes from evidence that exists DURING the render, each with
a fallback, and the authority order is asserted here: render_film.py's own
`FILM DELIVERY: PASS|FAIL` verdict outranks the wrapper's status file, which
outranks what is on disk.

THE CONTROL is `test_a_growing_log_with_no_status_file_reports_progress`: a
project with no status file, a live pid whose process burns no CPU, and a
render.log being appended to. Everything the old version relied on is
absent. It must report frames, and it must not say STALLED.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WAITER = ROOT / "scripts" / "await_render.py"

FAST = {
    "AWAIT_POLL_SECONDS": "0.3",
    "AWAIT_SPEAK_SECONDS": "0.3",
    "AWAIT_STALL_SECONDS": "2",
    "AWAIT_START_GRACE_SECONDS": "2",
}


@pytest.fixture
def film(tmp_path):
    """A project laid out as the runner's, under a root of its own.

    Returns a helper that writes the pieces a render leaves behind, so each
    test says exactly which signals exist and which do not.
    """
    class Film:
        slug = "a-film"
        root = tmp_path
        project = tmp_path / "projects" / "a-film"
        log = project / "render.log"
        pidfile = project / "render.pid"
        status = project / "render_status.json"
        delivered = project / "renders" / "final.mp4"

        def __init__(self):
            (self.project / "renders").mkdir(parents=True)
            (tmp_path / "scripts").mkdir(exist_ok=True)
            (tmp_path / "reports").mkdir(exist_ok=True)
            self.helpers: list[subprocess.Popen] = []

        def log_lines(self, *rows: str) -> None:
            with self.log.open("a") as fh:
                for row in rows:
                    fh.write(row + "\n")

        def frames(self, done: int, total: int = 36803) -> None:
            self.log_lines(f"Rendered {done}/{total}, time remaining: 1h 0m")

        def live_pid(self) -> int:
            """A real, live process that burns no CPU.

            start_new_session so its process-group id equals its pid, which
            is what group_cpu() sums — and a sleeping process contributes
            nothing, so a test cannot pass on the CPU signal by accident.
            """
            proc = subprocess.Popen([sys.executable, "-c",
                                     "import time; time.sleep(120)"],
                                    start_new_session=True)
            self.helpers.append(proc)
            self.pidfile.write_text(str(proc.pid))
            return proc.pid

        def dead_pid(self) -> int:
            proc = subprocess.Popen([sys.executable, "-c", "pass"])
            proc.wait()
            self.pidfile.write_text(str(proc.pid))
            return proc.pid

        def kill_after(self, seconds: float) -> None:
            """Kill the render AND REAP IT after `seconds`.

            The reap is the point. A killed child whose parent has not
            waited on it stays a ZOMBIE, and `os.kill(pid, 0)` — which is
            how the waiter asks whether the render is alive — SUCCEEDS on a
            zombie. Without the wait() this test watches a corpse that
            still answers, and the waiter correctly keeps waiting.

            Production does not have the problem: render_detached.sh
            re-execs itself into its own session, so its parent is PID 1,
            which reaps it at once (measured on the live render: `ps` gave
            PPID 1 for pid 73329).
            """
            proc = self.helpers[-1]

            def go():
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except (OSError, subprocess.SubprocessError):
                    pass

            threading.Timer(seconds, go).start()

        def status_after(self, seconds: float, blob: dict) -> None:
            """Write render_status.json LATER, the way the wrapper does.

            render_detached.sh writes it from its EXIT trap, so it appears
            when the render ends and not before. A test that pre-writes it
            beside a live pid is asserting a state production cannot reach —
            and that is the state the 14:30:56 defect lived in.
            """
            def go():
                self.status.write_text(json.dumps(blob))

            threading.Timer(seconds, go).start()

        def run(self, *extra: str, timeout_hours: float = 0.0015,
                wait: float = 25):
            env = {**os.environ, **FAST, "AWAIT_ROOT": str(tmp_path)}
            return subprocess.run(
                [sys.executable, str(WAITER), "--project", self.slug,
                 "--no-start", "--timeout-hours", str(timeout_hours), *extra],
                capture_output=True, text=True, timeout=wait, env=env)

        def cleanup(self):
            for proc in self.helpers:
                try:
                    proc.kill()
                except OSError:
                    pass

    made = Film()
    yield made
    made.cleanup()


class TestProgressComesFromWhatExists:
    def test_a_growing_log_with_no_status_file_reports_progress(self, film):
        """THE CONTROL. Everything the old waiter needed is missing.

        No render_status.json, a live pid that burns no CPU, and a log being
        appended to while the waiter watches. The frames must come through
        and the word STALLED must not appear.
        """
        film.live_pid()
        film.log_lines("king-tut: 161 cuts, 36803 frames", "1. plate")
        film.frames(100)

        stop = threading.Event()

        def keep_rendering():
            frame = 100
            while not stop.is_set():
                frame += 250
                film.frames(frame)
                time.sleep(0.25)

        writer = threading.Thread(target=keep_rendering, daemon=True)
        writer.start()
        try:
            done = film.run()
        finally:
            stop.set()
            writer.join(timeout=2)

        out = done.stdout
        assert not film.status.exists(), "the control requires no status file"
        assert "STALLED" not in out, (
            f"a render advancing a frame every 250ms was called stalled:\n{out}")
        assert re.search(r"frame [\d,]+/36,803", out), out
        assert "1. plate" in out, "the pass label must reach the log line"
        assert done.returncode == 2, (
            "it should have run to its timeout still watching, not decided "
            f"anything:\n{out}")

    def test_the_pass_label_survives_a_megabyte_of_frame_lines(self, film):
        """The regression that made `pass` come back None on the real render.

        `1. plate` is printed once at the top of a pass. By frame 12,764 it
        was megabytes behind, and a 64 KB tail could not see it.
        """
        sys.path.insert(0, str(ROOT / "scripts"))
        import await_render as A

        film.log_lines("1. plate")
        with film.log.open("a") as fh:
            for frame in range(1, 20_001):
                fh.write(f"Rendered {frame}/36803, time remaining: 1h 0m\n")
        assert film.log.stat().st_size > 800_000, "need a big log to prove it"

        state = A.log_state(film.log)
        assert state["pass"] == "1. plate"
        assert state["frames"] == 20_000

    def test_a_new_pass_resets_the_frame_count(self, film):
        """The look pass starts again at zero; carrying 36,803 forward would
        read as progress that is not happening."""
        sys.path.insert(0, str(ROOT / "scripts"))
        import await_render as A

        film.log_lines("1. plate")
        film.frames(36803)
        film.log_lines("3. look pass")
        state = A.log_state(film.log)
        assert state["pass"] == "3. look pass"
        assert state["frames"] is None, state

        film.frames(12)
        state = A.log_state(film.log)
        assert state["frames"] == 12


class TestAStallIsReportedAndNotActedOn:
    def test_a_silent_render_is_called_stalled(self, film):
        pid = film.live_pid()
        film.log_lines("1. plate")
        film.frames(5000)
        done = film.run(timeout_hours=0.0025)
        assert "STALLED" in done.stdout, done.stdout
        assert "NOT killing it" in done.stdout

    def test_and_the_render_is_left_alive(self, film):
        pid = film.live_pid()
        film.log_lines("1. plate")
        film.frames(5000)
        film.run(timeout_hours=0.0025)
        os.kill(pid, 0)   # raises if the waiter killed it

    def test_it_says_so_when_it_starts_moving_again(self, film):
        film.live_pid()
        film.log_lines("1. plate")
        film.frames(5000)

        def nudge():
            time.sleep(3.5)
            film.frames(5250)

        thread = threading.Thread(target=nudge, daemon=True)
        thread.start()
        done = film.run(timeout_hours=0.0028)
        thread.join(timeout=2)
        assert "STALLED" in done.stdout
        assert "moving again" in done.stdout, done.stdout


class TestCompletionComesFromRenderFilm:
    def test_the_verdict_alone_finishes_it_with_no_status_file(self, film):
        film.live_pid()
        film.log_lines("1. plate", "5. deliver", "6. gates",
                       "FILM DELIVERY: PASS")
        film.delivered.write_bytes(b"x" * 2_000_000)
        done = film.run()
        assert done.returncode == 0, done.stdout
        assert "FILM DELIVERY: PASS" in done.stdout
        assert not film.status.exists()

    def test_a_failed_verdict_fails_the_stage(self, film):
        film.live_pid()
        film.log_lines("6. gates", "   FAIL: frame motion: 41% duplicate pairs",
                       "FILM DELIVERY: FAIL")
        film.delivered.write_bytes(b"x" * 2_000_000)
        done = film.run()
        assert done.returncode == 1, done.stdout
        assert "the gates rejected it" in done.stdout

    def test_the_verdict_outranks_a_status_file_that_disagrees(self, film):
        """The gates decided; the trap only recorded a shell exit code.

        The realistic disagreement is this way round: render_film.py passed
        its gates and said so, and the wrapper's trap then recorded a
        non-zero exit — a `tee` in the pipeline failing, a signal arriving
        during cleanup. The film is delivered and the waiter must say so.

        (The opposite pairing — status `delivered` with a FAIL verdict — is
        not a state one attempt can produce, and it is the shape the resume
        short-circuit is for: a previously delivered film is not re-judged.)
        """
        film.live_pid()
        film.log_lines("6. gates", "FILM DELIVERY: PASS")
        film.status.write_text(json.dumps(
            {"outcome": "failed", "exit_code": 1}))
        film.delivered.write_bytes(b"x" * 2_000_000)
        done = film.run()
        assert done.returncode == 0, done.stdout
        assert "FILM DELIVERY: PASS" in done.stdout

    def test_a_render_that_vanishes_with_a_film_on_disk_is_delivered(self, film):
        """A SIGKILLed wrapper: no verdict, no status, but a film.

        The render has to be ALIVE first and then die, because that is the
        only way this state arises — and because a pidfile that was already
        dead when the waiter started means there is nothing to wait for, and
        is refused before the loop.
        """
        film.live_pid()
        film.log_lines("1. plate", "5. deliver")
        film.delivered.write_bytes(b"x" * 2_000_000)
        film.kill_after(1.5)
        done = film.run(timeout_hours=0.003)
        assert done.returncode == 0, done.stdout
        assert "no verdict and no status file" in done.stdout

    def test_a_render_that_vanishes_with_nothing_on_disk_fails_loudly(self, film):
        film.live_pid()
        film.log_lines("1. plate", "Traceback (most recent call last):",
                       "MemoryError")
        film.kill_after(1.5)
        done = film.run(timeout_hours=0.003)
        assert done.returncode == 1, done.stdout
        assert "no verdict, no status file and no" in done.stdout
        assert "MemoryError" in done.stdout, "the log tail must be shown"

    def test_a_status_file_is_still_honoured_when_there_is_no_verdict(self, film):
        """And the waiter's own exit stays 0/1/2.

        It reports the render's exit code in the message rather than
        returning it: 2 is already taken, and means "still going, left
        running" to run_weekly.sh.
        """
        film.live_pid()
        film.log_lines("=== attempt 20261107T142641  (pid 1, automation@x) ===",
                       "1. plate")
        # The render ends and ITS trap writes the status, in that order. A
        # status file sitting there while the pid is alive is a previous
        # attempt's and is shelved — see
        # TestEvidenceBelongsToOneAttempt.
        film.kill_after(0.6)
        film.status_after(0.9, {"outcome": "failed", "exit_code": 3,
                                "started": "20261107T142641"})
        done = film.run()
        assert done.returncode == 1, done.stdout
        assert "render_status.json: exit 3" in done.stdout


class TestTheFreeCases:
    def test_an_already_delivered_film_returns_at_once(self, film):
        film.status.write_text(json.dumps(
            {"outcome": "delivered", "exit_code": 0}))
        film.delivered.write_bytes(b"x" * 2_000_000)
        started = time.monotonic()
        done = film.run()
        assert done.returncode == 0
        assert "nothing to render" in done.stdout
        assert time.monotonic() - started < 10, "it should not have polled"

    def test_no_render_and_no_start_is_an_error_not_a_wait(self, film):
        done = film.run()
        assert done.returncode == 1
        assert "no render running" in done.stdout

    def test_a_missing_project_is_refused(self, film):
        env = {**os.environ, **FAST, "AWAIT_ROOT": str(film.root)}
        done = subprocess.run(
            [sys.executable, str(WAITER), "--project", "nope", "--no-start"],
            capture_output=True, text=True, env=env, timeout=20)
        assert done.returncode == 1
        assert "no project at" in done.stderr


class TestEvidenceBelongsToOneAttempt:
    """The 14:30:56 defect, and the worse one standing behind it.

    2026-11-07. The render was restarted by hand and was 6,000 frames into
    its look pass. The weekly run re-fired, skipped every finished stage
    correctly, reached the compose stage, and printed:

        a render is already going (pid 10914) — waiting on it rather than
        starting a second
        render finished after 0 min: failed — render_status.json: exit 1

    `render_status.json` had been written at 13:49 by the EXIT trap of a
    render that no longer existed. The waiter moved the old status aside only
    in the branch where IT started the render; the attach branch skipped that
    line, so the first poll judged a live render on a dead one's exit code.

    Behind it, the same mistake with a worse outcome: `render.log` is
    CUMULATIVE — render_detached.sh tees every attempt onto it — and
    `log_state` scanned the whole file, so a previous attempt's
    `FILM DELIVERY: PASS` would have been read as this attempt's verdict and
    an undelivered film would have gone to publish.

    One rule fixes both: this attempt begins at the last `=== attempt`
    header, and nothing above it is evidence.
    """

    @staticmethod
    def _mod():
        import importlib
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        return importlib.import_module("await_render")

    def test_a_live_render_is_never_judged_by_a_status_file(self):
        """A live render CANNOT have written one: the trap runs on exit."""
        mod = self._mod()
        dead = {"outcome": "failed", "exit_code": 1, "started": "20261107T110155"}
        assert mod.status_for(dead, "20261107T142641", 10914) == {}
        assert mod.status_for(dead, None, 10914) == {}

    def test_a_status_from_another_attempt_is_not_this_attempt_s(self):
        mod = self._mod()
        dead = {"outcome": "failed", "exit_code": 1, "started": "20261107T110155"}
        assert mod.status_for(dead, "20261107T142641", None) == {}
        mine = dict(dead, started="20261107T142641")
        assert mod.status_for(mine, "20261107T142641", None) == mine

    def test_an_unstamped_status_is_still_read_when_nothing_is_running(self):
        """Older wrappers wrote no `started`. Absence is not contradiction."""
        mod = self._mod()
        blob = {"outcome": "delivered", "exit_code": 0}
        assert mod.status_for(blob, "20261107T142641", None) == blob

    def test_the_previous_attempt_s_verdict_is_not_read_as_this_one_s(self, tmp_path):
        """The control: a PASS above the header, nothing below it."""
        mod = self._mod()
        log = tmp_path / "render.log"
        log.write_text(
            "=== attempt 20261107T110155  (pid 73329, automation@689b77c) ===\n"
            "1. plate\n"
            "Rendered 36803/36803\n"
            "FILM DELIVERY: PASS\n"
            "=== attempt 20261107T142641  (pid 10914, automation@69bfc95) ===\n"
            "3. look pass\n"
            "Rendered 6377/36803, time remaining: 19m 45s\n")
        state = mod.log_state(log)
        assert state["attempt"] == "20261107T142641"
        assert state["verdict"] is None, (
            "the previous attempt's PASS was read as this attempt's — an "
            "undelivered film would have gone to publish")
        assert (state["frames"], state["total"]) == (6377, 36803)
        assert state["pass"] == "3. look pass"

    def test_this_attempt_s_verdict_is_still_read(self):
        """And the fix must not make the waiter blind."""
        import tempfile
        mod = self._mod()
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "render.log"
            log.write_text(
                "=== attempt 20261107T110155  (pid 73329) ===\n"
                "FILM DELIVERY: FAIL\n"
                "=== attempt 20261107T142641  (pid 10914) ===\n"
                "6. gates\n"
                "FILM DELIVERY: PASS\n")
            state = mod.log_state(log)
            assert state["verdict"] == "PASS"
            assert state["attempt"] == "20261107T142641"

    def test_a_frame_count_does_not_carry_across_an_attempt(self, tmp_path):
        """36,803 of 36,803 above the header is not progress below it."""
        mod = self._mod()
        log = tmp_path / "render.log"
        log.write_text(
            "=== attempt 20261107T110155  (pid 73329) ===\n"
            "Rendered 36803/36803\n"
            "=== attempt 20261107T142641  (pid 10914) ===\n"
            "1. plate\n")
        state = mod.log_state(log)
        assert state["frames"] is None and state["total"] is None


class TestTheCpuSignalSeesTheWholeTree:
    """A liveness signal that reads zero on a healthy render is not a signal.

    `group_cpu` summed one process GROUP, and went inert the same day it was
    written: `run_watched` started launching Remotion with
    `start_new_session=True` — so a stalled pass could be reaped with killpg
    without the signal reaching the run — and that put the renderer in a group
    of its own. Measured on the live king-tut look pass, 82% in and burning
    five cores:

        group_cpu(10914)  ->   0.4 %
        tree under 10914  -> 304.5 % over 15 procs
        process groups:      [10914, 11184, 11209]

    The stall rule needs all four signals flat, so nothing broke. It was the
    fourth inert guard this project has shipped, which is three more than the
    budget.
    """

    @staticmethod
    def _mod():
        import importlib
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        return importlib.import_module("await_render")

    def test_work_in_a_child_process_group_is_counted(self):
        """The control: the burner is deliberately NOT in the parent's group.

        `start_new_session=True` on the grandchild is the thing that made the
        old signal read zero, so the test puts it there on purpose.
        """
        mod = self._mod()
        parent = subprocess.Popen(
            [sys.executable, "-c",
             "import subprocess, sys, time\n"
             "kid = subprocess.Popen([sys.executable, '-c',\n"
             "    'import time\\nend = time.time() + 20\\n"
             "while time.time() < end: pass'], start_new_session=True)\n"
             "print(kid.pid, flush=True)\n"
             "time.sleep(20)\n"
             "kid.kill()"],
            stdout=subprocess.PIPE, text=True)
        try:
            burner = int(parent.stdout.readline().strip())
            # ps %cpu is a decaying average; give the burner a moment to earn
            # one rather than asserting on its first scheduling quantum.
            time.sleep(2.5)

            groups = subprocess.run(
                ["ps", "-o", "pgid=", "-p", f"{parent.pid},{burner}"],
                capture_output=True, text=True).stdout.split()
            assert len({g for g in groups if g}) == 2, (
                f"the burner shares the parent's process group ({groups}), so "
                f"this test cannot tell a tree walk from a group sum")

            seen = mod.tree_cpu(parent.pid)
            assert seen > 20, (
                f"tree_cpu saw {seen}% of a process tree with a busy loop in "
                f"it — the CPU signal is inert again")
            assert mod.group_cpu is mod.tree_cpu, (
                "group_cpu must be the tree walk: the stall rule and the "
                "10-minute log line both read that name")
        finally:
            try:
                parent.kill()
                parent.wait(timeout=5)
            except (OSError, subprocess.SubprocessError):
                pass
            subprocess.run(["kill", "-9", str(burner)], capture_output=True)

    def test_an_idle_tree_reads_about_zero(self):
        """And it must not report busy for a sleeping render, or a stall can
        never be detected at all."""
        mod = self._mod()
        proc = subprocess.Popen([sys.executable, "-c",
                                 "import time; time.sleep(20)"],
                                start_new_session=True)
        try:
            time.sleep(1.5)
            assert mod.tree_cpu(proc.pid) < 5
        finally:
            proc.kill()
            proc.wait(timeout=5)

    def test_no_pid_is_no_cpu(self):
        assert self._mod().tree_cpu(None) == 0.0
        assert self._mod().tree_cpu(0) == 0.0

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
        film.log_lines("1. plate")
        film.status.write_text(json.dumps(
            {"outcome": "failed", "exit_code": 3}))
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

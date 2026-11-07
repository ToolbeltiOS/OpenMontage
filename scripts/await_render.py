#!/usr/bin/env python3
"""Start the film's render and wait for it WITH NO MODEL OPEN.

WHY THIS EXISTS
---------------
The 2026-11-06 render stage was a `claude -p` agent told to start the render
detached and then poll for it. It did start it detached. Then it polled —
for 2 hours 45 minutes, across 1,222 turns, 29 Monitor calls and 458 Bash
calls, re-reading a context that grew to 842,269 tokens, until it hit the
five-hour usage window. 388 million cache-read tokens, $194 of the $212
stage, to move 745 KB of tool output. Nothing it did in those turns required
a language model: it ran `ls -lt renders/`, tailed a log, and waited.

Polling is not a judgement. It is a loop with a sleep in it, and a loop with
a sleep in it costs nothing. So the model's job now ends when the artifacts
are on disk, and THIS runs the render — no agent, no context, no cost, and
it cannot hit a usage limit because it makes no API calls.

It is also the whole of the compose stage. `scripts/render_film.py` renders
the plate, the look pass and the type pass, delivers, AND RUNS THE GATES,
writing reports/film_delivery_<name>.md. There was never a decision in the
compose stage for an agent to make.

    scripts/await_render.py --project king-tut
    scripts/await_render.py --project king-tut --timeout-hours 10

Exit 0 the film is delivered and the gates passed. Exit 1 the render failed
or the gates did. Exit 2 it is still going after the timeout — and the
render is LEFT RUNNING, because a render killed at 33,055 of 35,561 frames
is how three attempts and six hours were lost once already.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: How often to look. The render takes hours; a tighter loop buys nothing
#: and a looser one delays the report of a failure.
POLL_SECONDS = 30

#: How often to say something, so a long render leaves a trail in the log
#: rather than three hours of silence that reads like a hang.
SPEAK_SECONDS = 10 * 60

#: How long to wait for the render to even announce itself — a pid file and
#: a log. Past this, render_detached.sh did not start, which is a failure to
#: report rather than something to keep waiting for.
START_GRACE_SECONDS = 180


def now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def say(message: str) -> None:
    print(f"  [{now()}] {message}", flush=True)


def read_json(path: Path) -> dict:
    try:
        blob = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return blob if isinstance(blob, dict) else {}


def alive(pidfile: Path) -> int | None:
    """The live render's pid, or None. A stale pid file is not a render."""
    try:
        pid = int(pidfile.read_text().strip())
    except (OSError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return pid


def on_battery() -> bool:
    try:
        out = subprocess.run(["pmset", "-g", "batt"], capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "'Battery Power'" in out


def tail(path: Path, lines: int = 1) -> str:
    try:
        with path.open(errors="replace") as fh:
            kept = fh.readlines()[-lines:]
    except OSError:
        return ""
    return " / ".join(line.strip() for line in kept if line.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--timeout-hours", type=float, default=8.0)
    ap.add_argument("--no-start", action="store_true",
                    help="wait for a render somebody else started; do not "
                         "start one")
    ap.add_argument("--force", action="store_true",
                    help="pass --force to render_film.py, which otherwise "
                         "refuses to overwrite a delivered film")
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    status_path = project / "render_status.json"
    pidfile = project / "render.pid"
    log = project / "render.log"
    delivered = project / "renders" / "final.mp4"

    if not project.is_dir():
        print(f"no project at {project}", file=sys.stderr)
        return 1

    # Already done? This is the resume case and must be free. The gates live
    # in render_film.py and their verdict is in the status file, so a status
    # that says delivered is the whole answer.
    previous = read_json(status_path)
    if previous.get("outcome") == "delivered" and delivered.exists():
        say(f"already delivered: {delivered.relative_to(ROOT)} "
            f"({delivered.stat().st_size / 1e6:.0f} MB) — nothing to render")
        return 0

    running = alive(pidfile)
    if running:
        say(f"a render is already going (pid {running}) — waiting on it "
            f"rather than starting a second")
    elif args.no_start:
        say("no render running and --no-start was given")
        return 1
    else:
        # The old status belongs to the old attempt. Keep it — a previous
        # failure is evidence — but out of the way, so this wait cannot
        # finish on it.
        if status_path.exists():
            status_path.replace(project / "render_status.prev.json")
            say("kept the previous attempt's status as render_status.prev.json")
        cmd = [str(ROOT / "scripts" / "render_detached.sh"), args.project]
        if args.force:
            cmd.append("--force")
        say(f"starting: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            say(f"render_detached.sh exited {result.returncode}: "
                f"{(result.stderr or result.stdout).strip()[:300]}")
            return 1

    started = time.monotonic()
    limit = args.timeout_hours * 3600
    spoke = 0.0
    announced = False
    warned_battery = False

    while True:
        waited = time.monotonic() - started

        status = read_json(status_path)
        if status:
            outcome = status.get("outcome")
            code = status.get("exit_code")
            say(f"render finished: outcome={outcome} exit={code} "
                f"after {waited / 60:.0f} min")
            extra = Path(str(status_path) + ".tail")
            if extra.exists():
                for row in (extra.read_text(errors="replace")
                            .strip().splitlines()[-12:]):
                    print(f"    | {row}", flush=True)
            if outcome == "delivered" and code == 0:
                if delivered.exists():
                    say(f"delivered {delivered.relative_to(ROOT)} "
                        f"({delivered.stat().st_size / 1e6:.0f} MB)")
                report = ROOT / "reports" / f"film_delivery_{args.project}.md"
                for guess in (report, ROOT / "reports" / "film_delivery_final.md"):
                    if guess.exists():
                        say(f"gates: {guess.relative_to(ROOT)}")
                        break
                return 0
            return 1

        pid = alive(pidfile)
        if not announced:
            if pid or log.exists():
                announced = True
            elif waited > START_GRACE_SECONDS:
                say(f"no render.pid and no render.log after "
                    f"{START_GRACE_SECONDS}s — the render never started")
                return 1
        elif not pid:
            # The pid is gone and no status was written. render_detached.sh
            # writes the status from an EXIT trap, so this is a kill -9 or a
            # machine that went down mid-render, not a normal failure.
            time.sleep(POLL_SECONDS)
            if not read_json(status_path):
                say("the render process is gone and wrote no status — it was "
                    "killed, or the machine stopped. Nothing to wait for.")
                return 1
            continue

        if waited - spoke >= SPEAK_SECONDS:
            spoke = waited
            progress = tail(log, 1) or "(no output yet)"
            say(f"{waited / 60:.0f} min, pid {pid or '?'}: {progress[:160]}")
            if on_battery() and not warned_battery:
                warned_battery = True
                say("ON BATTERY — a clamshell Mac sleeps through a render and "
                    "caffeinate cannot hold it awake. Plug in.")

        if waited > limit:
            say(f"still rendering after {args.timeout_hours}h. LEAVING IT "
                f"RUNNING (pid {pid or '?'}): a render killed near the end "
                f"leaves no file and no error. Watch {log.relative_to(ROOT)} "
                f"and re-run this to pick it up.")
            return 2

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())

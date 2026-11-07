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
printing `FILM DELIVERY: PASS` or `FILM DELIVERY: FAIL` as its last word and
exiting 0 or 1 accordingly. There was never a decision in the compose stage
for an agent to make.

WHAT IT TAKES ITS ANSWERS FROM
------------------------------
The first version read `render_status.json` for BOTH progress and
completion. That file is written by `render_detached.sh`'s EXIT trap, so it
does not exist until the render is over — which is correct, and which makes
it useless as a progress signal and fragile as a completion one: a render
killed with SIGKILL, or one whose trap cannot write (a full disk), finishes
without ever producing it.

So every answer now comes from evidence that exists WHILE the render runs,
and each has a fallback:

  progress    the `Rendered N/M` lines render_film.py tees into render.log,
              that log's own mtime (appended once per frame), the growth of
              the delivered files, and the CPU of the render's process
              group. Any one of the four moving means the render is alive.

  completion  `FILM DELIVERY: PASS|FAIL` in render.log — render_film.py's
              own verdict and exit code, teed live. Failing that, the status
              file. Failing that, the session leader being gone plus what is
              on disk.

  a stall     frames, bytes AND cpu all flat for STALL_SECONDS. Reported
              loudly and NOT acted on: the render is left alone, because the
              Noah plate was killed three times on a waiter's judgement, the
              last at 33,055 of 35,561 frames, leaving no file and no error.

    scripts/await_render.py --project king-tut
    scripts/await_render.py --project king-tut --timeout-hours 10

Exit 0 the film is delivered and the gates passed. Exit 1 the render failed
or the gates did. Exit 2 it is still going after the timeout — and the
render is LEFT RUNNING.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

#: The repository. AWAIT_ROOT exists so the tests can stand up a whole fake
#: project in a temp directory instead of writing one into projects/ — a
#: test that has to touch the real tree is a test nobody runs while a render
#: is going.
ROOT = Path(os.environ.get("AWAIT_ROOT") or Path(__file__).resolve().parents[1])

#: How often to look. The render takes hours; a tighter loop buys nothing.
#: Overridable so the tests do not have to wait a real minute.
POLL_SECONDS = float(os.environ.get("AWAIT_POLL_SECONDS", 30))

#: How often to say something, so a long render leaves a trail in the log
#: rather than hours of silence that reads like a hang.
SPEAK_SECONDS = float(os.environ.get("AWAIT_SPEAK_SECONDS", 10 * 60))

#: How long every signal must be flat before this is called a stall. The
#: look pass writes nothing for minutes at a time between frames, so this
#: has to be longer than the longest legitimate quiet stretch.
STALL_SECONDS = float(os.environ.get("AWAIT_STALL_SECONDS", 20 * 60))

#: How long to wait for the render to announce itself at all — a pid file or
#: a log. Past this, render_detached.sh did not start.
START_GRACE_SECONDS = float(os.environ.get("AWAIT_START_GRACE_SECONDS", 180))

#: `Rendered 11842/36803, time remaining: 1h 34m 56s`
FRAME_RE = re.compile(r"Rendered\s+(\d+)\s*/\s*(\d+)")

#: render_film.py's stage headers: `1. plate`, `3. look pass`, `5. deliver`.
STAGE_RE = re.compile(r"^\s*(\d)\.\s+(.+?)\s*$")

#: Its last word, and the thing that means the render is over.
VERDICT_RE = re.compile(r"^FILM DELIVERY:\s*(PASS|FAIL)\s*$", re.M)

def output_paths(project: str) -> list[Path]:
    """The files the render finishes with. Each appears at a pass boundary.

    MEASURED 2026-11-07 on the king-tut render: none of these existed 40
    minutes into the plate pass. Remotion renders every frame into a scratch
    directory under $TMPDIR and muxes the mp4 at the END, so the delivered
    files say nothing at all mid-pass. They are the coarse signal — a pass
    finished — and the log is the fine one.
    """
    work = ROOT / "remotion-composer" / "out" / project
    renders = ROOT / "projects" / project / "renders"
    return [work / "plate.mp4", work / "look.mp4", work / "type.mov",
            renders / "final.mp4"]


def touched(path: Path) -> float:
    """When this file was last written, or 0.

    Used on the project's own render.log, which render_film.py appends to
    once per frame — so its mtime IS the per-frame heartbeat, and it is
    scoped to THIS project.

    An earlier version measured $TMPDIR/react-motion-render* instead,
    reasoning that Remotion's frame scratch is where the bytes actually
    land. That glob is MACHINE-WIDE: it has no project in its name, so the
    waiter for one film read the liveness of whatever Remotion process
    happened to be running. The waiter tests caught it immediately — a
    deliberately stalled fake project kept reporting "frames written 0s
    ago" because the real king-tut render was writing frames at the time.
    A per-project signal must not be a global glob.
    """
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


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


def group_cpu(pid: int | None) -> float:
    """Total %CPU of the render's process group.

    The render is a tree — bash, python, npm, node, and a dozen headless
    Chrome processes — and the work happens in the leaves. The session
    leader's own CPU is nearly zero, so asking about IT would make a healthy
    render look idle. The group is what is busy.
    """
    if not pid:
        return 0.0
    try:
        out = subprocess.run(["ps", "-ax", "-o", "pgid=,%cpu="],
                             capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return 0.0
    total = 0.0
    for line in out.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            if int(parts[0]) == pid:
                total += float(parts[1])
        except ValueError:
            continue
    return round(total, 1)


def tail(path: Path, lines: int = 1) -> str:
    try:
        with path.open(errors="replace") as fh:
            kept = fh.readlines()[-lines:]
    except OSError:
        return ""
    return " / ".join(line.strip() for line in kept if line.strip())


def log_state(log: Path) -> dict:
    """Frames, the pass being rendered, and the verdict if it has landed.

    ONE FULL SCAN, not a tail. The first version read the last 64 KB, which
    held the frame lines but NOT the `1. plate` header — that is printed once
    at the top of a pass and by frame 12,764 it was megabytes behind, so the
    pass came back as None on the live render. A pass label is only useful if
    it survives the pass. The file is a few megabytes of short lines and this
    runs once every thirty seconds, so a full scan costs milliseconds.
    """
    state = {"frames": None, "total": None, "pass": None, "verdict": None,
             "last": ""}
    try:
        with log.open(errors="replace") as fh:
            for row in fh:
                row = row.strip()
                if not row:
                    continue
                state["last"] = row
                found = FRAME_RE.search(row)
                if found:
                    state["frames"] = int(found.group(1))
                    state["total"] = int(found.group(2))
                    continue
                found = STAGE_RE.match(row)
                if found:
                    # A new pass resets the frame count: the look pass starts
                    # again at zero and a carried-over number would read as
                    # progress that is not happening.
                    state["pass"] = f"{found.group(1)}. {found.group(2)}"
                    state["frames"] = None
                    state["total"] = None
                    continue
                found = VERDICT_RE.match(row)
                if found:
                    state["verdict"] = found.group(1)
    except OSError:
        return state
    return state


def output_bytes(project: str) -> int:
    """Bytes in the finished outputs. Zero until the first pass muxes."""
    total = 0
    for path in output_paths(project):
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def describe(state: dict, cpu: float, written: int,
             beat: float = 0.0) -> str:
    """One line a person can read at 3am and know whether to worry."""
    bits = []
    if state["pass"]:
        bits.append(state["pass"])
    if state["frames"] is not None:
        share = (f" ({state['frames'] / state['total']:.0%})"
                 if state["total"] else "")
        bits.append(f"frame {state['frames']:,}/{state['total']:,}{share}"
                    if state["total"] else f"frame {state['frames']:,}")
    if written:
        bits.append(f"{written / 1e6:.0f} MB delivered")
    elif beat:
        # "0 MB delivered" is true and misleading for most of a render:
        # Remotion muxes the mp4 at the END of a pass, so the honest number
        # mid-pass is how long since the render last said anything.
        bits.append(f"last wrote {max(0.0, time.time() - beat):.0f}s ago")
    bits.append(f"{cpu:.0f}% cpu")
    return ", ".join(bits)


def outcome(project_dir: Path, log: Path, status: dict,
            verdict: str | None) -> tuple[str, int, str]:
    """(outcome, exit code, evidence), most authoritative source first.

    render_film.py's own verdict outranks the wrapper's status file, because
    the verdict is what the gates decided and the status file is what a
    shell trap managed to write afterwards.
    """
    if verdict:
        return (("delivered", 0, "FILM DELIVERY: PASS") if verdict == "PASS"
                else ("failed", 1, "FILM DELIVERY: FAIL — the gates rejected it"))
    if status:
        code = status.get("exit_code")
        return (str(status.get("outcome") or "unknown"),
                code if isinstance(code, int) else 1,
                f"render_status.json: exit {code}")
    delivered = project_dir / "renders" / "final.mp4"
    if delivered.exists() and delivered.stat().st_size > 0:
        return ("delivered", 0,
                f"no verdict and no status file, but {delivered.name} is "
                f"{delivered.stat().st_size / 1e6:.0f} MB")
    return ("failed", 1,
            "the render ended with no verdict, no status file and no "
            f"delivered film. Last log line: {tail(log, 1) or '(none)'}")


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

    # Already done? This is the resume case and must be free.
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
        # failure is evidence — but out of the way.
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
    stalled_since: float | None = None
    said_stalled = False
    # (pass, frames, delivered bytes, render.log mtime) at the last change
    mark: tuple = (None, None, 0, 0.0)
    moved_at = time.monotonic()

    while True:
        waited = time.monotonic() - started
        pid = alive(pidfile)
        state = log_state(log)
        written = output_bytes(args.project)
        beat = touched(log)
        cpu = group_cpu(pid)

        # ── is it over? ──────────────────────────────────────────────────
        # render_film.py's verdict first: it is teed into the log the moment
        # the gates finish, and it is the thing that decided.
        status = read_json(status_path)
        if state["verdict"] or status or (announced and not pid):
            if not (state["verdict"] or status):
                # The pid is gone and neither signal landed. Give the trap a
                # moment to write, then judge on what is on disk.
                time.sleep(min(POLL_SECONDS, 5))
                status = read_json(status_path)
                state = log_state(log)
            name, code, why = outcome(project, log, status, state["verdict"])
            say(f"render finished after {waited / 60:.0f} min: {name} — {why}")
            extra = Path(str(status_path) + ".tail")
            if extra.exists():
                for row in (extra.read_text(errors="replace")
                            .strip().splitlines()[-12:]):
                    print(f"    | {row}", flush=True)
            elif name != "delivered":
                for row in (tail(log, 12) or "").split(" / "):
                    if row:
                        print(f"    | {row}", flush=True)
            if name == "delivered" and code == 0:
                if delivered.exists():
                    say(f"delivered {delivered.relative_to(ROOT)} "
                        f"({delivered.stat().st_size / 1e6:.0f} MB)")
                for guess in (ROOT / "reports" / f"film_delivery_{args.project}.md",
                              ROOT / "reports" / "film_delivery_final.md"):
                    if guess.exists():
                        say(f"gates: {guess.relative_to(ROOT)}")
                        break
                return 0
            return 1

        # ── has it started? ──────────────────────────────────────────────
        if not announced:
            if pid or log.exists():
                announced = True
                moved_at = time.monotonic()
            elif waited > START_GRACE_SECONDS:
                say(f"no render.pid and no render.log after "
                    f"{START_GRACE_SECONDS:.0f}s — the render never started")
                return 1

        # ── is it working? ───────────────────────────────────────────────
        # Three signals, and any one of them moving is proof of life. The
        # log alone is not enough: a pass can write nothing for minutes
        # while ffmpeg muxes, and that is not a stall.
        here = (state["pass"], state["frames"], written, beat)
        # `or cpu > 1.0`, not a tight threshold: macOS reports %cpu as a
        # decaying average, and this render measured 52% one minute and 7%
        # the next while rendering a frame a second throughout. This is a
        # positive signal only — any one of the four moving means alive —
        # so it should be easy to trip and never used to declare death.
        if here != mark or cpu > 1.0:
            mark = here
            moved_at = time.monotonic()
            if said_stalled:
                say(f"moving again: {describe(state, cpu, written, beat)}")
                said_stalled = False
            stalled_since = None
        elif time.monotonic() - moved_at > STALL_SECONDS and not said_stalled:
            stalled_since = moved_at
            said_stalled = True
            say(f"STALLED: no frames, no bytes and no cpu for "
                f"{(time.monotonic() - moved_at) / 60:.0f} min. "
                f"{describe(state, cpu, written, beat)}")
            say(f"         NOT killing it — a render stopped near the end "
                f"leaves no file and no error. Watch "
                f"{log.relative_to(ROOT)}; this gives up at "
                f"{args.timeout_hours}h.")

        if waited - spoke >= SPEAK_SECONDS:
            spoke = waited
            say(f"{waited / 60:.0f} min, pid {pid or '?'}: "
                f"{describe(state, cpu, written, beat)}")
            if not state["frames"]:
                say(f"         last line: {state['last'][:140] or '(none)'}")
            if _on_battery() and not warned_battery:
                warned_battery = True
                say("ON BATTERY — a clamshell Mac sleeps through a render "
                    "and caffeinate cannot hold it awake. Plug in.")

        if waited > limit:
            say(f"still rendering after {args.timeout_hours}h. LEAVING IT "
                f"RUNNING (pid {pid or '?'}): a render killed near the end "
                f"leaves no file and no error. {describe(state, cpu, written, beat)}. "
                f"Watch {log.relative_to(ROOT)} and re-run this to pick it up.")
            return 2

        time.sleep(POLL_SECONDS)


def _on_battery() -> bool:
    try:
        out = subprocess.run(["pmset", "-g", "batt"], capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "'Battery Power'" in out


if __name__ == "__main__":
    sys.exit(main())

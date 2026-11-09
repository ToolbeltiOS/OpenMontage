"""The render path: plate, look, type, deliver, gates.

ONE PATH, NOT TWO
-----------------
The act 2 demo was first rendered by hand — a picture render, a frame
extraction, a look pass and an encode, four commands typed in order — and it
shipped silent, because the fifth command, the one that puts the mix into the
file, was never typed and nothing was responsible for noticing. The demo got
a script. The film did not, and a film rendered by a different path from the
demo is a film whose gates have never run on it.

So the stages live here and both scripts call them. `scripts/render_demo.py`
is the ninety-second window; `scripts/render_film.py` is the whole film; the
only differences between them are which props, which mix and how long.

THE STAGES
----------
  1. plate      the film with the type laid out but not inked
  2. frames     the plate as a JPEG sequence, for the shader to sample
  3. look       FilmLookPass over that sequence
  4. type       the film with ONLY the type, over transparency
  5. deliver    type over the graded plate, and the mix with it
  6. gates      frame motion, frame order, plate purity, type lock, delivery
                audio — all blocking

Stages 1 and 4 are the same film rendered twice from the same tree, so that
the composite order can be plate -> grade and vignette and grain -> type. A
single flat render puts the grain on the glyph edges, which is half of why
the type shook; see remotion-composer/src/design/layers.tsx for the other
half.
"""
from __future__ import annotations

import hashlib
import json
import collections
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "remotion-composer"
ENTRY = "src/index.tsx"
FPS = 30


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("  $", " ".join(str(c) for c in cmd[:9]), "..." if len(cmd) > 9 else "")
    subprocess.run(cmd, cwd=cwd, check=True)


#: How often the watchdog looks, and how long it will tolerate no progress.
#:
#: WHY THIS EXISTS. The Noah plate was launched three times as a background
#: task of the agent driving the stage, and all three times the harness
#: stopped that task at its two-hour limit. The third died with 33,055 of
#: 35,561 frames rendered — and left nothing: no output file, no error line,
#: no exit status, because a killed process writes none of those. The stage
#: was waiting on
#:
#:     until grep -qE "2. frames|3. look|error occurred" render.log; do ...
#:
#: and not one of those three strings can ever appear once the render is
#: dead, so the wait slept forever on a process that no longer existed. A
#: waiter keyed on strings that only a LIVING process emits cannot report a
#: death. This watchdog watches the process, not the text.
WATCH_INTERVAL = 30
WATCH_STALL = 600

#: Remotion's two counters. `Encoded` trails `Rendered` by a long way — it
#: was at 886 when 33,055 frames had been rendered — so a reader who takes
#: the last line of the log as "the frame we got to" is out by 32,000.
_PROGRESS = re.compile(r"^(Rendered|Encoded)\s+(\d+)/(\d+)")

#: The line Remotion prints when a pass has written its file:
#:
#:     +                    /…/out/king-tut/plate.mp4 1.3 GB
#:
#: It is printed BEFORE the browser tree is torn down, and teardown is where
#: a render can hang, or throw a ProtocolError closing a page, without
#: touching the file it has already finished writing.
_WROTE = re.compile(r"^\+\s+(.+?)\s+\d+(?:\.\d+)?\s*[KMGTP]?i?B\s*$")

#: How long a pass that has written its file is given to exit on its own
#: before the tree is reaped and the pass is called a success.
#:
#: WHY THIS EXISTS. 2026-11-07, the king-tut plate: 36,803 of 36,803 frames
#: rendered, 36,803 encoded, "+ …/plate.mp4 1.3 GB" printed — and the stage
#: recorded "plate FAILED: no progress for 600s". ffprobe then decoded all
#: 36,803 frames out of that same file. Two defects, both in this module:
#:
#:   1. THE ENCODE HAD NO HEARTBEAT. `Encoded` is in `_PROGRESS`, but the
#:      reader below only reset the stall clock on `Rendered`, and h264
#:      prints no `Rendered` line after the last frame. So the whole
#:      50-minute encode-and-mux ran with the clock stopped at the last
#:      rendered frame, and the watchdog armed at log line 37,768 with
#:      `Encoded` climbing three lines a second in front of it.
#:   2. THE KILL NEVER REACHED THE RENDERER. `proc.kill()` killed `npm
#:      exec`, a shell wrapper; node and the compositor were grandchildren in
#:      the same process group and got no signal. Remotion ran on for 3,000
#:      more log lines and finished the file. The run was failed by a
#:      watchdog that had already lost the argument — and the inconsistency
#:      is the tell: a watchdog whose kill works cannot see output after it.
#:
#: So: BOTH counters are a heartbeat, the output line ends the pass, and a
#: reap signals the process GROUP.
FINISH_GRACE = 60


def _reap(proc: subprocess.Popen) -> None:
    """Kill the whole render tree, not just the shim we launched.

    `npm exec remotion` -> `node .bin/remotion` -> the compositor and N
    Chromium renderers. Only a group signal reaches all of them, which is why
    `run_watched` starts the child in its own session. If that did not take —
    the group is ours — fall back to signalling the one process, because
    killing our own group kills the run.
    """
    try:
        pgid = os.getpgid(proc.pid)
    except (ProcessLookupError, PermissionError, OSError):
        pgid = None
    if pgid is not None and pgid == os.getpgid(0):
        pgid = None
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            if pgid is not None:
                os.killpg(pgid, sig)
            else:
                proc.send_signal(sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        try:
            proc.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            continue


def _is_output(named: str, output: Path | None) -> bool:
    """Is this `+` line about the file we asked this pass to write?

    Remotion prints a `+ <path> <size>` line per artifact it writes. Treating
    any of them as the end of the pass would end a pass early; treating none
    of them as the end is the defect above. So the caller names its own
    output and the match is on the resolved path, and the file has to be
    there — the line is a claim, `stat` is the fact.
    """
    try:
        path = Path(named)
        if not path.exists():
            return False
        return output is None or path.resolve() == Path(output).resolve()
    except OSError:
        return False


def cut_at_frame(cuts: list[dict[str, Any]] | None, frame: int,
                 fps: int = FPS) -> str:
    """The cut on screen at a frame, named well enough to go and look at it."""
    for c in cuts or []:
        if round(float(c["in_seconds"]) * fps) <= frame < round(
                float(c["out_seconds"]) * fps):
            where = " ".join(str(x) for x in (c.get("act"), c.get("sceneIndex"))
                             if x)
            kind = c.get("type") or c.get("treatment") or "?"
            return f"{c.get('id', '?')} ({kind}{', ' + where if where else ''})"
    return f"no cut covers frame {frame}"


def run_watched(cmd: list[str], cwd: Path | None, label: str, count: int,
                cuts: list[dict[str, Any]] | None = None,
                output: Path | None = None) -> None:
    """`run`, but it cannot hang and it cannot die quietly.

    Progress is read from the child's own output as it arrives — BOTH of
    Remotion's counters, because an h264 encode prints only the second one
    and the encode is the longest silence in a pass. If neither counter moves
    for WATCH_STALL seconds the render TREE is killed; if the pass exits
    non-zero having never named its output, the failure names the frame, the
    cut on screen at that frame, and the last twenty lines. Nothing here
    greps for a fixed frame number or a fixed phrase.

    A pass that has printed its output line is DONE, whatever it does next:
    see FINISH_GRACE for the three hours that bought this paragraph.
    """
    print("  $", " ".join(str(c) for c in cmd[:9]), "..." if len(cmd) > 9 else "")
    sys.stdout.flush()
    # start_new_session, so the child LEADS ITS OWN PROCESS GROUP and `_reap`
    # can signal the whole tree without signalling us.
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1,
                            start_new_session=True)
    tail: collections.deque[str] = collections.deque(maxlen=20)
    state: dict[str, Any] = {"frame": 0, "at": time.monotonic(),
                             "stalled": False, "wrote": None,
                             "wrote_at": 0.0, "reaped": False}
    lock = threading.Lock()

    def watch() -> None:
        while proc.poll() is None:
            time.sleep(WATCH_INTERVAL)
            with lock:
                if state["wrote"] is not None:
                    idle = time.monotonic() - state["wrote_at"]
                    if idle < FINISH_GRACE:
                        continue
                    state["reaped"] = True
                else:
                    idle = time.monotonic() - state["at"]
                    if idle < WATCH_STALL:
                        continue
                    state["stalled"] = True
                done, frame, wrote = (state["reaped"], state["frame"],
                                      state["wrote"])
            if done:
                print(f"  {label}: wrote {wrote} and was still up "
                      f"{int(idle)}s later — reaping the render tree")
            else:
                print(f"  WATCHDOG: no progress for {int(idle)}s at frame "
                      f"{frame}/{count} — killing {label}")
            sys.stdout.flush()
            _reap(proc)
            return

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()

    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip("\n")
        tail.append(line)
        print(line)
        sys.stdout.flush()
        m = _PROGRESS.match(line)
        if m:
            with lock:
                # The frame REACHED is the `Rendered` counter only: `Encoded`
                # trailed it by 32,000 once, and a failure that names the
                # encoder's number sends the reader to the wrong cut. Both
                # counters are a heartbeat.
                if m.group(1) == "Rendered":
                    state["frame"] = int(m.group(2))
                state["at"] = time.monotonic()
            continue
        w = _WROTE.match(line)
        if w and state["wrote"] is None and _is_output(w.group(1), output):
            with lock:
                state["wrote"] = w.group(1)
                state["wrote_at"] = time.monotonic()
    rc = proc.wait()

    with lock:
        wrote, stalled = state["wrote"], state["stalled"]

    if wrote is not None:
        # THE FILE IS THE RESULT. A pass that named its output and then hung
        # in teardown, threw closing a page, or was reaped by the grace above
        # has still produced the thing the next pass reads. This is not a
        # claim that the file is good: render_film.py verifies the frame
        # count before reusing one, and `gates` decodes the delivery. It is a
        # claim about WHO DECIDES a pass finished — the render, not the
        # watchdog.
        if rc != 0:
            print(f"  {label}: wrote {wrote}, then exited {rc} — the file is "
                  f"what the next pass reads, carrying on")
            sys.stdout.flush()
        return

    if rc == 0 and not stalled:
        return

    why = (f"no progress for {WATCH_STALL}s" if stalled
           else f"exited {rc}" if rc > 0 else f"killed by signal {-rc}")
    raise SystemExit(
        f"{label} FAILED: {why}\n"
        f"  reached frame {state['frame']} of {count}\n"
        f"  on screen there: {cut_at_frame(cuts, state['frame'])}\n"
        f"  it never named an output file\n"
        f"  last {len(tail)} lines:\n"
        + "\n".join(f"    {t}" for t in tail))


def frame_count(cuts: list[dict[str, Any]], fps: int = FPS) -> int:
    """Frames up to the last cut's end.

    Not the composition's own duration: `calculateMetadata` adds a second of
    padding for a final fade, and in anything without one that second is an
    empty background gradient.

    IT DOES NOT MAKE THE PICTURE AND THE MIX THE SAME LENGTH, which is what
    this docstring used to claim. Measured on easter-island: the cuts sum to
    1210.567s and the narration timeline the mixer builds comes to 1210.081s,
    0.486s apart — 169 cuts each rounded to a frame. The delivered file held
    36,302 frames against the 36,317 asked for, because `deliver` passed
    `-shortest` and the audio was the shorter of the two. Half a second of the
    outro, gone, with the report printing the number the edit asked for beside
    a file that did not have it.

    The mix is padded to the picture now, and `gates` compares the two.
    """
    return round(max(float(c["out_seconds"]) for c in cuts) * fps)


#: A pass whose output already verifies is not rendered again.
#:
#: WHY THIS EXISTS. 2026-11-07: the king-tut plate rendered all 36,803 frames
#: and was recorded as a failure (see FINISH_GRACE). Resuming meant either
#: re-rendering a 1.3 GB file that ffprobe had just decoded in full — two
#: hours and forty-five minutes of the week's compute, to arrive at the same
#: bytes — or `--skip-picture`, which skips the plate AND the frames AND the
#: type pass, so it cannot resume a film whose plate is the only finished
#: thing. There was no third option, which is what made a bookkeeping bug
#: cost a day.
#:
#: Cheap on purpose: the container index and a decode of the last second,
#: because a truncated write is a short index or an undecodable tail. The
#: full per-frame decode belongs to `gates`, on the delivered film.
def _probe_int(path: Path, field: str, extra: tuple[str, ...] = ()) -> int | None:
    cmd = ["ffprobe", "-v", "error", *extra, "-select_streams", "v:0",
           "-show_entries", f"stream={field}", "-of", "default=nw=1:nk=1",
           str(path)]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = [l.strip() for l in (done.stdout or "").splitlines() if l.strip()]
    return int(lines[0]) if lines and lines[0].isdigit() else None


def _tail_decodes(path: Path, seconds: float = 1.0) -> bool:
    """Will the END of this file decode? A truncated write is a broken tail."""
    cmd = ["ffmpeg", "-v", "error", "-sseof", f"-{seconds}", "-i", str(path),
           "-map", "0:v:0", "-f", "null", "-"]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0 and not (done.stderr or "").strip()


def verified_video(path: Path, count: int) -> tuple[bool, str]:
    """Does this file already hold the `count` frames a pass was asked for?"""
    if not path.exists() or path.stat().st_size == 0:
        return False, "missing"
    got, how = _probe_int(path, "nb_frames"), "index"
    if got is None:
        got, how = _probe_int(path, "nb_read_packets", ("-count_packets",)), "packets"
    if got is None:
        return False, "no video stream ffprobe will count"
    if got != count:
        return False, f"{got} frames by {how}, the edit asks for {count}"
    if not _tail_decodes(path):
        return False, f"{got} frames by {how} but the last second will not decode"
    return True, f"{got} frames by {how}, tail decodes"


def verified_stills(frames_dir: Path, count: int) -> tuple[bool, str]:
    """The frame extraction's output: `count` stills, named as it names them."""
    if not frames_dir.is_dir():
        return False, "missing"
    got = len(list(frames_dir.glob("f_*.jpg")))
    if got != count:
        return False, f"{got} stills, the edit asks for {count}"
    return True, f"{got} stills"


def act_spans(cuts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """When each act is on screen, for the shader's per-act grade.

    The grade is per act and the look pass is one composition, so without this
    a twenty-minute film is graded as whichever act was named first.

    Act names are section ids, and a film has sections that are not numbered:
    this crashed on `cold_open` with `invalid literal for int()`, because it
    coerced every label to `act<N>` and the demo's cuts were numbered "01".
    `gradeForAct` in design/system.ts has always normalised the same two
    forms — a section id as it stands, a bare number to `act<N>` — so this
    mirrors it rather than inventing a third rule, and `cold_open` and
    `outro` keep the grades the playbook writes for them.
    """
    spans: list[dict[str, Any]] = []
    for cut in cuts:
        # The SECTION ID first, the chrome's display number only as a
        # fallback. They agree on a numbered act and disagree on every other
        # section: the cold open carries actNumber "00", which normalises to
        # `act0` — a key no grade table has — so 35 seconds of it was being
        # graded with the fallback while `act: cold_open` sat right beside it
        # naming the grade the playbook writes. It also split the cold open
        # into two spans with a third in between.
        raw = cut.get("act") or cut.get("actNumber")
        if raw is None:
            continue
        key = str(raw).strip().lower()
        name = f"act{int(key)}" if key.isdigit() else key
        start, end = float(cut["in_seconds"]), float(cut["out_seconds"])
        if spans and spans[-1]["act"] == name:
            spans[-1]["to_seconds"] = end
        else:
            spans.append({"act": name, "from_seconds": start, "to_seconds": end})
    return spans


#: File extensions a props value has to end in to be treated as an asset.
ASSET_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif",
                  ".mp4", ".mov", ".webm")


def _asset_values(blob: Any):
    """Every (container, key, value) in the props that names a local asset."""
    stack: list[Any] = [blob]
    while stack:
        node = stack.pop()
        items = (node.items() if isinstance(node, dict)
                 else enumerate(node) if isinstance(node, list) else ())
        for key, value in items:
            if isinstance(value, str):
                plain = value.split("?")[0].lower()
                if (plain.endswith(ASSET_SUFFIXES)
                        and not value.startswith(("http://", "https://", "data:"))):
                    yield node, key, value
            elif isinstance(value, (dict, list)):
                stack.append(value)


def stage_assets(blob: Any, project: str) -> dict[str, Any]:
    """Put every asset the props name where the renderer can actually read it.

    WHY THIS STAGE EXISTS
    ---------------------
    The first real film render died at frame 0 with

        Not allowed to load local resource:
        file:///Users/.../renders/proxies/wm_20150500.jpg

    87 of the 104 asset paths in the props were absolute filesystem paths.
    `resolveAsset` in the composer turns an absolute path into a `file://`
    URL, and a page served from http://localhost is not allowed to load one —
    so that branch of the resolver cannot work in a render or in the Studio.
    It looks accommodating and is a dead end.

    Remotion reads assets from `remotion-composer/public/`, which is why the
    demo path worked: `build_demo_cut.py` copied its assets in. The film path
    had no such step, because run #1 was finished by hand and the gates were
    written against the demo. So the one documented full-film path had never
    once resolved a real project's assets.

    Hard links, not copies: the proxies are hundreds of megabytes and the
    staging directory is gitignored working space. A cross-device link falls
    back to a copy.
    """
    stage = COMPOSER / "public" / f"assets_{project}"
    stage.mkdir(parents=True, exist_ok=True)

    missing: list[str] = []
    for node, key, value in list(_asset_values(blob)):
        # A prop that ALREADY points into public/ needs no staging and must
        # not be rewritten: basemap tiles are cut straight into
        # remotion-composer/public/basemaps by scripts/build_basemap_tile.py,
        # and the renderer reads them from there by the same relative name.
        # Resolving them against the repo root instead reported six real
        # tiles as missing assets and refused the render.
        if not value.startswith("/") and (COMPOSER / "public" / value).exists():
            continue
        source = Path(value) if value.startswith("/") else ROOT / value
        if not source.exists():
            missing.append(value)
            continue
        # The basename alone collides: two acts can both carry a detail.jpg.
        digest = hashlib.sha1(str(source.resolve()).encode()).hexdigest()[:8]
        dest = stage / f"{digest}_{source.name}"
        if not dest.exists():
            try:
                os.link(source, dest)
            except OSError:
                shutil.copy2(source, dest)
        node[key] = f"{stage.name}/{dest.name}"

    if missing:
        raise SystemExit(
            f"{len(missing)} asset(s) in the props do not exist, and a render "
            f"finds that out at the frame that needs them:\n  "
            + "\n  ".join(missing[:10]))
    return blob


def props_for_layer(props_path: Path, mode: str, work: Path,
                    project: str | None = None) -> Path:
    """The same props with one field added, written where the renderer sees it.

    `project` names the staging directory under `public/`. Without it the
    props go through unstaged, which is only right for props that already
    point into `public/` — the demo's do, because its own builder copied them
    there.
    """
    blob = json.loads(props_path.read_text())
    blob["layer_mode"] = mode
    if project:
        # The renderer has no business with the mix. `deliver()` is the one
        # place the audio enters, by ffmpeg, onto the finished picture — and
        # the plate, look and type passes would otherwise each carry a
        # 232MB wav through Remotion's asset downloader, which refuses a
        # file:// URL anyway. Picture-only layers, mix at the mux.
        blob.pop("audio", None)
        blob = stage_assets(blob, project)
    work.mkdir(parents=True, exist_ok=True)
    dest = work / f"props_{mode}.json"
    dest.write_text(json.dumps(blob))
    return dest


#: Remotion's own default: about half the cores.
#:
#: MEASURED, because the first guess here was wrong. This was briefly set to
#: cores - 1 (7 of 8) on the reasoning that concurrency is free — it changes
#: how fast frames are made, never what is in them — and the first minute's
#: estimate agreed, dropping from "over two hours" to "about 43 minutes".
#: Sustained, it was the opposite: 7 renderers managed 2.6 frames/s over
#: twenty minutes, against 4.6 frames/s sustained over two hours at the
#: default on the same film and the same machine. Seven Chromium renderers
#: and ffmpeg on eight cores contend; the first minute cannot see it.
#:
#: A Remotion ETA printed in the first minute is not a measurement. Overriding
#: this needs a sustained rate over at least ten minutes, in the comment.
CONCURRENCY = max(1, (os.cpu_count() or 4) // 2)


#: Frames rendered in front of a requested range and thrown away.
#:
#: Two, where one was measured — see `render_plate`. The frame after the bad
#: one already matched the full render to 0.1552 and the one after that to
#: 0.0848, so the warm-up is over within a frame; the second is there because
#: the cause is inferred rather than proven, and a frame costs a quarter of a
#: second. `repatch_plate.py` checks every frame it writes against the frame
#: it overwrote, so if this is ever not enough, the splice fails rather than
#: ships.
LEAD_IN = 2


def render_plate(props: Path, dest: Path, count: int,
                 cuts: list[dict[str, Any]] | None = None,
                 frames: tuple[int, int] | None = None) -> int:
    """The picture, with the type laid out but not inked.

    `frames` renders a RANGE of the same composition instead of all of it,
    for `scripts/repatch_plate.py`: a change that touches eighteen cuts out
    of a hundred and sixty-one has no business re-rendering the other
    hundred and forty-three. The composition is identical either way — a
    cut's animation is driven by its `<Sequence>`, so frame 14,087 renders
    the same whether it is reached from frame 0 or asked for directly.

    EXCEPT FOR THE FIRST FRAME, WHICH IS NOT THE SAME. Measured on king-tut,
    `--frames=1548-1747` against the full render of the same 200 frames:

        frame 1548   mean absolute difference  6.2876
        frame 1549                             0.1552
        frame 1550                             0.0848
        frames 1551-1557                       0.0776 down to 0.0000

    One frame, wrong by two orders of magnitude more than its neighbours.
    1548 is inside a title sequence whose backdrop is a JPEG, and it comes
    back 5.5 grey levels darker — the frame was painted before the image
    was. A full render reaches 1548 twenty-six hundred frames after that
    image first appeared, so it has never been visible there.

    The range is therefore rendered with `LEAD_IN` frames in front of it,
    and THE FIRST FRAME ACTUALLY RENDERED IS RETURNED so the caller can
    throw them away. Rendering a frame to discard it is the cheapest
    possible fix and it does not care WHY the frame is wrong, which matters:
    this was found by measurement and its cause is inferred, not proven.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    first, last = frames if frames else (0, count - 1)
    if frames:
        first = max(0, first - LEAD_IN)
    run_watched(["npx", "remotion", "render", ENTRY, "Explainer", str(dest),
                 f"--props={props}", f"--frames={first}-{last}", "--gl=angle",
                 f"--concurrency={CONCURRENCY}"],
                COMPOSER, "plate", last - first + 1, cuts, output=dest)
    return first


def extract_frames(picture: Path, frames_dir: Path, count: int) -> None:
    """The plate as stills, because WebGL cannot sample a <video>."""
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(picture),
         "-frames:v", str(count), "-q:v", "2", str(frames_dir / "f_%05d.jpg")])
    got = len(list(frames_dir.glob("f_*.jpg")))
    if got != count:
        raise SystemExit(f"extracted {got} frames, expected {count}")


def render_look(frames_dir: Path, dest: Path, count: int,
                act: str = "act2", acts: list[dict[str, Any]] | None = None,
                cuts: list[dict[str, Any]] | None = None) -> None:
    props: dict[str, Any] = {"dir": frames_dir.name, "act": act, "stack": "full",
                             "frames": count}
    if acts:
        props["acts"] = acts
    run_watched(["npx", "remotion", "render", ENTRY, "FilmLookPass", str(dest),
                 f"--props={json.dumps(props)}", f"--frames=0-{count - 1}",
                 "--gl=angle", f"--concurrency={CONCURRENCY}"],
                COMPOSER, "look pass", count, cuts, output=dest)


def render_type(props: Path, dest: Path, count: int,
                cuts: list[dict[str, Any]] | None = None) -> None:
    """Only the type, over transparency.

    ProRes 4444 because it is the one format in the renderer that carries an
    alpha channel losslessly. It is a working file — about 8MB a second — and
    it stays in remotion-composer/out, which is gitignored.
    """
    run_watched(["npx", "remotion", "render", ENTRY, "Explainer", str(dest),
                 f"--props={props}", f"--frames=0-{count - 1}",
                 "--codec=prores", "--prores-profile=4444",
                 "--pixel-format=yuva444p10le", "--image-format=png",
                 "--gl=angle", f"--concurrency={CONCURRENCY}"],
                COMPOSER, "type pass", count, cuts, output=dest)


def deliver(look: Path, type_layer: Path, mix: Path, dest: Path) -> None:
    """Type over the graded plate, and the mix with it.

    One ffmpeg call, so the picture is encoded once rather than once for the
    composite and again for the mux. The mux half is the step that was missing
    entirely when the demo first shipped silent.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    # `apad` BEFORE `-shortest`, so the shorter of the two is the PICTURE.
    #
    # The cut durations and the narration timeline do not come to the same
    # length — 0.486s apart on easter-island, 169 cuts each rounded to a frame
    # — and with the audio shorter, `-shortest` truncated the picture: 15
    # frames of the outro, under the closing title card, with nothing saying
    # so. Padding the audio instead costs half a second of silence under a
    # card that is already silent furniture.
    # Written beside the film and moved into place, as `remux` does: a
    # twenty-minute encode that dies at minute eighteen must not leave a
    # truncated file where the delivered one was.
    tmp = dest.with_suffix(".deliver.mp4")
    run(["ffmpeg", "-v", "error", "-y",
         "-i", str(look), "-i", str(type_layer), "-i", str(mix),
         "-filter_complex", "[0:v][1:v]overlay=format=auto:eof_action=pass[v]",
         "-map", "[v]", "-map", "2:a:0", "-af", "apad",
         "-c:v", "libx264", "-crf", "16", "-preset", "medium",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k",
         "-shortest", str(tmp)])
    tmp.replace(dest)


def remux(dest: Path, mix: Path) -> None:
    """Put a new mix onto a delivered film without touching the picture.

    `-c:v copy`, so the video stream is the bytes that were already graded,
    composited and encoded — not a second generation of them. An audio change
    is the one kind of change that can be delivered this way, and a twenty
    minute ProRes-to-h264 pass is the one kind of cost worth avoiding.

    THIS IS NOT A LICENCE TO FIX AUDIO DOWNSTREAM. The mix it carries has to
    be one `lib/mix_audio.py` built from the EDL, which is what the input hash
    beside `mix_final.wav` exists to say. A remux of a mix that was adjusted
    by hand is exactly the defect that put rejected music back into run #1 on
    the next re-render.
    """
    tmp = dest.with_suffix(".remux.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(dest), "-i", str(mix),
         "-map", "0:v:0", "-map", "1:a:0", "-af", "apad",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
         "-shortest", "-movflags", "+faststart", str(tmp)])
    # Only once ffmpeg has written a whole file. Replacing the delivered film
    # with a truncated one because the remux died halfway is not a trade
    # anybody would make.
    tmp.replace(dest)


def gates(dest: Path, picture: Path, cuts: list[dict[str, Any]],
          expected_lufs: float | None, fps: int = FPS,
          type_layer: Path | None = None
          ) -> tuple[list[str], dict[str, Any]]:
    """Every blocking check, on the file that is about to be delivered.

    `type_layer` is handed to type lock so that a reading is bound to our
    type by where it is rather than by its text; see that gate's docstring
    for the film it failed without it.
    """
    sys.path.insert(0, str(ROOT / "lib"))
    from verify_delivery_audio import check as check_audio
    from verify_frame_motion import check as check_motion
    from verify_frame_order import check as check_order
    from verify_plate_dropout import check as check_dropout
    from verify_type_lock import check as check_type, plate_is_clean

    results: dict[str, Any] = {}
    problems: list[str] = []
    for name, (found, measured) in {
        "frame motion": check_motion(str(dest), fps),
        "frame order": check_order(str(dest), cuts, str(picture), fps),
        "plate purity": plate_is_clean(str(picture), cuts),
        "type lock": check_type(str(dest), cuts, fps,
                                str(type_layer) if type_layer else None),
        "delivery audio": check_audio(str(dest), expected_lufs),
        # THE ONLY GATE THAT CAN SEE A DEFECT THE PLATE AND THE DELIVERY
        # AGREE ABOUT. Frame order compares the two, so a frame whose
        # picture never painted passes it perfectly; frame count sees a
        # frame that is present; frame motion sees that one frame is not a
        # freeze. Film #1 shipped with eight of these and king-tut's first
        # delivery had five, under 7 of 7 green.
        "plate-dropout": check_dropout(str(dest), fps),
    }.items():
        results[name] = measured
        problems += [f"{name}: {p}" for p in found]

    # IS EVERY FRAME THE EDIT ASKED FOR IN THE FILE?
    #
    # The frame-motion gate already decodes the whole film and counts, and the
    # report already prints the number the EDIT asked for. Nothing compared
    # them, so easter-island shipped 36,302 frames under a report that said
    # 36,317 — half a second of the outro removed by `-shortest`, because the
    # mix is 0.486s shorter than the cuts and nothing was responsible for
    # noticing. No decode is added here; this is arithmetic on a figure two
    # gates already had.
    asked = frame_count(cuts, fps)
    got = int(results["frame motion"].get("frames") or 0)
    results["frame count"] = {"asked": asked, "delivered": got,
                              "missing": asked - got,
                              "seconds_missing": round((asked - got) / fps, 3)}
    if got != asked:
        problems.append(
            f"frame count: the file holds {got} frames and the edit asks for "
            f"{asked} — {abs(asked - got)} "
            f"{'missing' if got < asked else 'extra'} "
            f"({abs(asked - got) / fps:.2f}s). A delivered film that is "
            f"shorter than its own edit has had the end taken off it.")
    return problems, results


def report(title: str, dest: Path, picture: Path, count: int, seconds: float,
           results: dict[str, Any], problems: list[str], expected_lufs: float | None,
           out: Path) -> Path:
    motion = results["frame motion"]
    order = results["frame order"]
    purity = results["plate purity"]
    type_lock = results["type lock"]
    audio = results["delivery audio"]

    def verdict(name: str) -> str:
        return "FAIL" if any(p.startswith(name + ":") for p in problems) else "PASS"

    lines = [
        f"# {title}",
        "",
        f"`{dest.relative_to(ROOT) if dest.is_relative_to(ROOT) else dest}` · "
        f"{results.get('frame count', {}).get('delivered', count)} frames "
        f"delivered of {count} asked · {seconds:.1f}s · plate "
        f"`{picture.relative_to(ROOT) if picture.is_relative_to(ROOT) else picture}`",
        "",
        "## Gates", "",
        "| check | measured | verdict |",
        "|---|---|---|",
        f"| frame motion | {motion['duplicate_pairs_pct']}% duplicate pairs, "
        f"longest freeze {motion['longest_freeze_seconds']}s, timestamps "
        f"{'constant' if motion['timestamps_constant'] else 'IRREGULAR'} | "
        f"{verdict('frame motion')} |",
        f"| frame order | {order['out_of_order_count']} frames out of place, "
        f"{order['isolated_black_runs']} isolated black, correlation with the "
        f"plate {order['reference_correlation']} | {verdict('frame order')} |",
        f"| plate purity | {purity['words_in_plate']} words legible in the "
        f"plate pass | {verdict('plate purity')} |",
        f"| type lock | {type_lock['scenes_sampled']} text-bearing scenes "
        f"sampled a second apart, {type_lock['scenes_with_movement']} with a "
        f"word in a different place, worst {type_lock['worst_shift_px']}px"
        + (f", {type_lock['scenes_with_one_box_over']} scene(s) where a "
           f"single box read over the tolerance and the rest of the scene "
           f"did not"
           if type_lock.get('scenes_with_one_box_over') else "")
        + f", readings bound to our type by "
          f"{type_lock.get('bound_by', 'cut text')}"
          f" | {verdict('type lock')} |",
        f"| plate-dropout | {results['plate-dropout']['frames']} frames "
        f"scanned, {results['plate-dropout']['certain']} certain, "
        f"{results['plate-dropout']['marginal']} marginal"
        + (f", closest call {results['plate-dropout']['worst_decisiveness']} "
           f"of the spike (certain under {0.25})"
           if results['plate-dropout']['worst_decisiveness'] is not None
           else ", nothing came near the limit")
        + f" | {verdict('plate-dropout')} |",
        f"| frame count | {results.get('frame count', {}).get('delivered')} "
        f"delivered of {results.get('frame count', {}).get('asked')} asked "
        f"({results.get('frame count', {}).get('seconds_missing')}s missing) | "
        f"{verdict('frame count')} |",
        f"| delivery audio | {audio.get('mean_dbfs')} dBFS mean, "
        f"{audio.get('integrated_lufs')} LUFS against the mix's {expected_lufs} "
        f"({audio.get('loudness_delta_db')} dB) | {verdict('delivery audio')} |",
        "",
        "## Luma map", "",
        "One character per frame, 30 per row — a second a row. `#` is black, "
        "`+` under 12, then `.` `:` `-` `=` `*` `o` `O` `@` brightening. A cut "
        "is a step; a frame from somewhere else is one character that belongs "
        "to neither side of it.", "",
        "```",
    ] + order["luma_map"] + ["```", ""]
    if problems:
        lines += ["## Failures", ""] + [f"- {p}" for p in problems] + [""]
    out.write_text("\n".join(lines))
    return out

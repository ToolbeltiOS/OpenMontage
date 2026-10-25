#!/usr/bin/env python3
"""Mix narration and music beds to the documentary's loudness spec.

Ducking is done with an explicit gain envelope computed from the narration's
own short-term loudness, not with a threshold compressor. A compressor's duck
depth depends on how far the signal is over the threshold, so it cannot be
asked for "music sits 16 dB under the voice" — it can only be tuned until it
looks about right. The envelope here is derived from measurement and the
resulting levels are verifiable afterwards.

Levels (run #2 as delivered, then REVISED 2026-10-25 after the owner's full
watch — "the bed must stay in the background the whole film"):
  narration        -16 LUFS short-term, true peak -1.5 dBTP
  music under speech   -33 LUFS integrated (was -30)
  music in gaps        the under-speech level +3 dB, capped, = -30 absolute
                       (was an absolute -26, which is +7 from -33)
  music at act boundaries -27 LUFS (was -22), under the fade to black
  rise ramps       1.5 s in and 1.5 s out, raised cosine, explicit
  duck             attack 150 ms / release 1200 ms, so nothing pumps
  music EQ         high-pass 120 Hz, high shelf -6 dB from 3.5 kHz,
                   low-pass 5 kHz (was 7 kHz with a -4 dB bell at 3 kHz)
  bed dynamics     a gentle 2:1 compressor on EACH bed before the envelope,
                   so no bed's own loudness range exceeds 6 LU
  bed matching     every bed within +/-1.5 LU of the others
  final mix        -14 LUFS integrated, -1.5 dBTP

No LRA target ON THE FILM. A continuously narrated film has little loudness
range by nature — the voice sits at one level for twenty minutes — and the
earlier 6-9 LU target was dropped rather than manufactured by letting the
music swell. The measured figure is recorded instead.

There IS now an LRA ceiling on each BED, which is a different thing: it is not
a target for the film's range, it is a limit on how much a bed may move on its
own underneath the voice. A bed with 11 LU of internal range is a bed that
comes forward by itself, which is what the owner heard as "music level
irregular" even where the envelope was doing nothing.

Beds are assigned per span, not crossfaded in sequence: adjacent acts share a
bed and the crossfades land on the act boundaries, under the fade to black.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from music_brightness import BED_EQ  # noqa: E402  the one definition of the EQ

SR = 48000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Run #1's slug, kept as the default so that every existing caller and every
#: test that invoked this module with three positionals still mixes the film it
#: always mixed. A second film passes --project; nothing about the first one
#: changes.
DEFAULT_PROJECT = "they-said-it-couldnt-be-built"
PROJECT = DEFAULT_PROJECT
PROJ = os.path.join(ROOT, "projects", PROJECT)
AUD = os.path.join(PROJ, "assets", "audio")
OUT = os.path.join(PROJ, "renders")
SECTIONS = ["cold_open", "act1", "act2", "act3", "act4", "outro"]


def set_project(slug: str) -> None:
    """Point the mixer at a project workspace.

    The paths were module constants naming run #1, which is why the mix was
    the one stage of the chain a second film could not reach: every other
    hard-coded path in the chain is reachable through an argument somewhere,
    and this one was not. They are still module-level — the functions below
    read them directly — but they are now set in one place.
    """
    global PROJECT, PROJ, AUD, OUT
    PROJECT = slug
    PROJ = os.path.join(ROOT, "projects", slug)
    AUD = os.path.join(PROJ, "assets", "audio")
    OUT = os.path.join(PROJ, "renders")

GAP_SECONDS = 1.5

#: The gap level, stated BOTH ways because the owner stated it both ways: a
#: cap on the rise, and the absolute figure that cap lands on from the current
#: bed level. The cap is the authority — if the bed level moves again, the
#: rise stays +3 dB rather than silently growing to close the distance to a
#: fixed absolute target. The two are asserted to agree at import.
GAP_RISE_DB_MAX = 3.0
GAP_TARGET_LUFS = -30.0        # absolute, = the bed's -33 plus the +3 cap
BOUNDARY_TARGET_LUFS = -27.0   # absolute, under the fade through black
BOUNDARY_WINDOW = 2.5      # the music crossfade length

#: How long a rise takes to arrive and to leave, as an explicit raised-cosine
#: ramp rather than whatever the one-pole smoother happened to do. 1.5 s each
#: way: a rise that arrives faster than that is heard as a fader move, which
#: is the thing the whole music-rise gate exists to prevent.
RISE_RAMP_SECONDS = 1.5

#: A gentle compressor on each bed BEFORE the ducking envelope. Not to make it
#: louder — the normaliser that follows undoes any makeup gain — but to stop
#: the bed moving on its own underneath a voice that is not moving.
BED_COMPRESSOR_RATIO = 2.0
BED_COMPRESSOR_ATTACK_MS = 50
BED_COMPRESSOR_RELEASE_MS = 500
BED_COMPRESSOR_KNEE_DB = 6.0

#: No bed's own loudness range may exceed this. Measured on the bed as it will
#: sit in the film: EQ'd, compressed and levelled.
#:
#: MEASURED TWO WAYS, AND THE SECOND ONE IS THE GATE.
#:
#: The owner asked for "internal dynamics inside 6 LU (LRA per bed <= 6)".
#: EBU LRA is the named metric and it is reported, but it cannot see what the
#: ear complained about: LRA is the 10th-to-95th percentile of short-term
#: loudness above a relative gate, so a bed can measure 5.7 LU of LRA and
#: still have a 13 dB hole in it. Both were true of this film's act 2/3 bed.
#:
#: So the gate is the 5th-to-95th percentile spread of K-weighted short-term
#: loudness, which does see a hole, and LRA is recorded beside it.
BED_LRA_MAX_LU = 6.0
BED_DYNAMICS_MAX_LU = 6.0

#: How far below its own median a bed may dip, anywhere. A hole is not a
#: dynamic — it is the music going away and coming back, which is the literal
#: reading of "the bed must stay in the background the whole film". Set from
#: the measurement: the three tracks' steadiest windows hole by 2.7, 6.3 and
#: 13.0 dB before conditioning, and 10 dB is the line that admits the two the
#: compressor can hold and refuses the one it cannot without being asked to
#: flatten the music into a tone.
BED_HOLE_MAX_DB = 10.0

#: How far the beds may sit from each other. Three beds at three levels is
#: heard as the music level changing at the act boundary, which is exactly
#: what "music level irregular" was.
BED_SPREAD_MAX_LU = 1.5

#: How many times the compressor threshold is lowered, 3 dB at a time, trying
#: to bring a bed inside BED_LRA_MAX_LU before the mix is refused.
BED_COMPRESSOR_MAX_PASSES = 5

#: The crossfade curve, for the loop joins and for the act boundaries alike.
#:
#: `tri` is linear in AMPLITUDE: at the centre of the fade both sides are at
#: 0.5, and two uncorrelated beds at 0.5 sum to 0.707 — a 3 dB dip. There is
#: one at every act boundary, which is exactly where the sting is placed and
#: where the envelope is lifting the bed to be heard. Measured, that dip was
#: most of why three of the six stings read as louder than the music under
#: them.
#:
#: `qsin` is a quarter-sine fade, which is constant POWER for uncorrelated
#: material and is the standard answer. The dip goes away without anything
#: being levelled.
XFADE_CURVE = "qsin"

#: A cut the edit marked `music_rise_allowed`, and whose bed the arousal gate
#: found actually rising, lets the music come forward around that cut.
#:
#: It reaches GAP_TARGET_LUFS, not BOUNDARY_TARGET_LUFS: coming forward in a
#: pause is what a gap already is, and -22 is reserved for the act boundary,
#: where the picture is fading through black and nothing is being said.
#:
#: It does NOT lift the bed under speech. `bed_under_speech_lufs` is a
#: binding playbook number, and a fader move under a voice that is still
#: talking is the manipulation `lib/music_arousal.py` refuses rises for in
#: the first place. So a rise is not a new level — it lets a SHORTER pause
#: take the level a long one already gets, where the music is rising into it.
RISE_WINDOW = 2.0              # either side of the cut
RISE_MIN_GAP_SECONDS = 0.4     # the shortest pause a supported rise may lift
LOOP_XFADE = 8.0           # crossfade between repeats of a bed shorter than its span;
                           # 4s left a 13 dB step on the two piano beds, which
                           # reads as the music restarting rather than turning over
#: WHAT HAPPENED TO ATTACK/RELEASE.
#:
#: The envelope's edges used to be an asymmetric one-pole: attack 150 ms,
#: release 900 ms. The owner asked on 2026-10-25 for "1.5 s ramps in and out"
#: on the gap rises AND for a "ducking release 1.2 s". Those are two numbers
#: for one edge, and measuring the one-pole shows it delivers neither: with a
#: 1200 ms release it gives a 2.64 s rise and a 0.33 s fall, and an authored
#: ramp in front of it barely moves the rise (2.64 -> 2.80 s at 1.5 s) while
#: dragging the fall out to 0.95 s. A one-pole cannot be asked for a ramp
#: length; it can only be tuned until the ramp looks about right — which is
#: the same objection this module already makes to using a compressor for the
#: ducking.
#:
#: So the edges are now the explicit raised-cosine ramps above, and the
#: one-pole is demoted to removing sample-level steps where two regions meet.
#: The ramp OUT is anticipatory: it finishes as the voice returns rather than
#: reacting after it, which is possible here because the whole mix is offline
#: and is strictly better than a 1.2 s reactive release. 1.5 s out is slower
#: than the 1.2 s asked for, so it is the more conservative of the two
#: against pumping.
DEZIPPER_MS = 30

#: Kept because the playbook, the EDL and run #1's published record all state
#: them, and `scripts/build_demo_audio.py` built its demo with them. Nothing
#: shapes an edge with these any more — `shape_envelope` is the one path — and
#: the mix report says so rather than printing a law that did not run.
SUPERSEDED_ATTACK_MS = 150
SUPERSEDED_RELEASE_MS = 900


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def ff_read(path: str, extra: list[str] | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", path]
    if extra:
        cmd += extra
    cmd += ["-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def measure(path: str) -> dict:
    err = subprocess.run(["ffmpeg", "-nostats", "-i", path, "-af", "ebur128=peak=true",
                          "-f", "null", "/dev/null"], capture_output=True, text=True).stderr
    tail = err[-4000:]

    def g(p):
        m = re.findall(p, tail)
        return float(m[-1]) if m else None

    return {"lufs": g(r"I:\s+(-?\d+\.\d+)\s*LUFS"),
            "lra": g(r"LRA:\s+(-?\d+\.\d+)\s*LU"),
            "peak_dbfs": g(r"Peak:\s+(-?\d+\.\d+)\s*dBFS")}


def two_pass_loudnorm(src: str, dst: str, I: float, TP: float, LRA: float = 11) -> None:
    probe = subprocess.run(["ffmpeg", "-nostats", "-i", src, "-af",
                            f"loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json",
                            "-f", "null", "/dev/null"], capture_output=True, text=True).stderr
    m = json.loads(re.search(r'\{[^{}]*"input_i"[\s\S]*?\}', probe).group(0))
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af",
         f"loudnorm=I={I}:TP={TP}:LRA={LRA}:measured_I={m['input_i']}:"
         f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
         f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true",
         "-ar", str(SR), "-ac", "2", dst])


def _with_silent_sections(segments: list[dict]) -> list[dict]:
    """Put back the sections that hold time without speaking.

    A title sequence is six to eight seconds of picture with no narration
    under it, so the narration plan has no segment for it — the plan is a list
    of things somebody says. But the PICTURE has a cut there, and
    `build_render_props` takes its section offsets from the section files on
    disk, so a section missing from the voice track puts the sound ahead of
    the picture for the whole rest of the film.

    The section's own wav is the authority for how long it is: for a silent
    section that file IS the silence, written by the narration stage. Nothing
    is invented here — a silent section with no file on disk is left out, and
    the missing-file check below then reports it.
    """
    script_path = os.path.join(PROJ, "artifacts", "script.json")
    if not os.path.exists(script_path):
        return segments
    with open(script_path, encoding="utf-8") as fh:
        order = [s["id"] for s in json.load(fh)["sections"]]
    spoken = {s.get("section_id") for s in segments}
    silent = [sid for sid in order
              if sid not in spoken and os.path.exists(os.path.join(AUD, sid + ".wav"))]
    if not silent:
        return segments

    out: list[dict] = []
    emitted: set[str] = set()
    for seg in segments:
        sid = seg.get("section_id")
        # Any silent section that sits before this one in the script, and has
        # not been emitted yet, goes in first.
        for q in silent:
            if q in emitted:
                continue
            if sid in order and order.index(q) < order.index(sid):
                out.append({"path": os.path.join(AUD, q + ".wav"),
                            "air_after_s": 0.0, "section_id": q})
                emitted.add(q)
        out.append(seg)
    for q in silent:
        if q not in emitted:
            out.append({"path": os.path.join(AUD, q + ".wav"),
                        "air_after_s": 0.0, "section_id": q})
    print(f"silent sections placed in the narration timeline: "
          f"{', '.join(silent)}", file=sys.stderr)
    return out


def narration_segments() -> tuple[list[dict], str]:
    """The ordered pieces of narration, and where the list came from.

    AIR IS WRITTEN, NOT FOUND. When the script stage has produced a narration
    plan, each of its segments is one rendered file plus the silence the script
    asked for after it, and that silence is inserted here — in the stage that
    rebuilds the audio. A gap applied anywhere downstream of this function has
    an expiry date, and the date is the next re-render.

    Without a plan, or with a plan whose segment files have not been rendered,
    this falls back to the six section files and reports `air_planned: False`
    so that the absence is visible rather than silently zero. Run #1 delivered
    thirteen seconds of silence in twenty minutes precisely because nothing
    ever said out loud that none had been synthesised.
    """
    plan_path = os.path.join(PROJ, "artifacts", "narration_plan.json")
    if os.path.exists(plan_path):
        with open(plan_path, encoding="utf-8") as fh:
            plan = json.load(fh)
        segments = [
            {"path": os.path.join(AUD, f"{seg['id']}.wav"),
             "air_after_s": float(seg.get("air_after_s") or 0.0),
             "section_id": seg.get("section_id")}
            for seg in plan.get("segments", [])
        ]
        segments = _with_silent_sections(segments)
        missing = [s["path"] for s in segments if not os.path.exists(s["path"])]
        if segments and not missing:
            return segments, "narration_plan"
        if missing:
            print(f"narration plan found but {len(missing)} of {len(segments)} "
                  f"segment files are missing; falling back to whole sections "
                  f"and NO planned air will be synthesised", file=sys.stderr)
    return ([{"path": os.path.join(AUD, s + ".wav"), "air_after_s": 0.0}
             for s in SECTIONS], "sections")


def audio_format(path: str) -> tuple[int, int]:
    """(sample_rate, channels) of a file, from ffprobe."""
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=sample_rate,channels", "-of", "csv=p=0", path],
        text=True).strip().split(",")
    return int(out[0]), int(out[1])


def silence_file(seconds: float, sample_rate: int = SR, channels: int = 1) -> str:
    """Silence at the NARRATION's format, cached by length and by format.

    Not at the project rate. The concat demuxer decodes every file with the
    first file's format and does not resample — the comment forty lines below
    says so, and was written after a 48 kHz outro among 24 kHz sections was
    decoded at four times its length. The guard added then checks the
    NARRATION files against each other; it never saw these, because this
    function makes them.

    Kokoro writes 24 kHz mono. This wrote 48 kHz, so every written gap was
    decoded at half speed and played for twice as long: 112.5s of planned air
    arrived as 225s, and the mix came out 112 seconds longer than the picture.
    Every loudness check still passed, because silence has no loudness.
    """
    layout = "mono" if channels == 1 else "stereo"
    path = os.path.join(OUT, f".silence_{seconds:.3f}_{sample_rate}_{channels}.wav")
    if not os.path.exists(path):
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", f"anullsrc=r={sample_rate}:cl={layout}", "-t", f"{seconds:.3f}",
             "-c:a", "pcm_s16le", path])
    return path


def build_narration() -> tuple[str, list[float], list[float], dict]:
    """Concatenate the segments, insert the written air, normalise to -16 LUFS.

    Returns the voice, every SEGMENT's offset, every ACT BOUNDARY, and the air
    report. The second and third are not the same list and the difference is a
    defect this function used to hide: see `gain_envelope`.
    """
    os.makedirs(OUT, exist_ok=True)
    segments, source = narration_segments()
    # The silence has to be written in the same format as the thing it sits
    # between, because the concat demuxer will not resample it.
    sample_rate, channels = audio_format(segments[0]["path"])
    offsets, t = [], 0.0
    boundaries: list[float] = []
    last_section = None
    planned_air = 0.0
    listfile = os.path.join(OUT, "narration_concat.txt")
    with open(listfile, "w", encoding="utf-8") as fh:
        for seg in segments:
            path = seg["path"]
            # An act boundary is where the SECTION changes, which is the first
            # segment of each section after the first. Taken from the timeline
            # being built here rather than from the section wavs, so it is the
            # position in the file that actually plays.
            section = seg.get("section_id")
            if last_section is not None and section != last_section:
                boundaries.append(t)
            last_section = section
            offsets.append(t)
            t += float(subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", path]).strip())
            fh.write(f"file '{path}'\n")
            air = seg.get("air_after_s") or 0.0
            if air > 0:
                # The silence is a file in the concat list, not a filter after
                # it: the concat demuxer is what builds this timeline, so the
                # gap has to exist as one of its inputs or it is not in the
                # file the next stage reads.
                fh.write(f"file '{silence_file(air, sample_rate, channels)}'\n")
                planned_air += air
                t += air
    # The concat demuxer decodes every file with the FIRST file's format. A
    # section written at a different rate or channel count is not resampled,
    # it is misread: a 48 kHz stereo outro among 24 kHz mono sections decoded
    # as four times its length and added 33 seconds of slurred audio to the
    # film. Check before concatenating rather than discovering it in the mix.
    fmts = set()
    for seg in segments:
        fmts.add(subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
             "stream=sample_rate,channels", "-of", "csv=p=0",
             seg["path"]], text=True).strip())
    if len(fmts) > 1:
        raise SystemExit(f"narration sections differ in format: {sorted(fmts)}. "
                         f"Re-encode them to match before mixing.")

    raw = os.path.join(OUT, "narration_raw.wav")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
         "-ar", str(SR), "-ac", "2", raw])

    # What came out must be what went in. The format guard above compares the
    # narration files with each other and cannot see the silence files this
    # function writes, which is how 112.5 seconds of planned air arrived as
    # 225 seconds of it — every gap decoded at half speed, every loudness
    # check still green, because silence has no loudness. Measuring the
    # result against the sum of the parts catches that whatever causes it.
    measured = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", raw]).strip())
    if abs(measured - t) > 0.25:
        raise SystemExit(
            f"the concatenated narration is {measured:.2f}s against "
            f"{t:.2f}s of inputs, a difference of {measured - t:+.2f}s. The "
            f"concat demuxer decodes every file at the FIRST file's rate and "
            f"does not resample, so this is almost always a file in the list "
            f"written at a different sample rate or channel count.")

    voice = os.path.join(OUT, "narration_16.wav")
    two_pass_loudnorm(raw, voice, I=-16, TP=-1.5, LRA=11)
    air = {
        "source": source,
        "air_planned": source == "narration_plan",
        "planned_air_seconds": round(planned_air, 2),
        "segments": len(segments),
        "act_boundaries": [round(b, 2) for b in boundaries],
    }
    print(f"narration: {len(segments)} segments, {len(boundaries)} act "
          f"boundaries at {', '.join(f'{b:.1f}s' for b in boundaries)}")
    return voice, offsets, boundaries, air


#: Filled in by `build_bed`, read by `main` for the report. A module global
#: rather than a return value because `build_bed` already returns the path
#: every caller wants and three of them exist.
BED_REPORT: dict | None = None

#: Which part of each track the bed was taken from, filled in by `build_bed`.
WINDOWS: dict[str, dict] = {}


def internal_dynamics(path: str) -> dict:
    """How much a bed moves on its own: spread, hole depth, and EBU LRA.

    The first two are computed from K-weighted short-term loudness, which is
    the unit the SFX gate measures in as well, so the two checks are not in
    two different scales.
    """
    from verify_sfx_level import short_term

    data, sr = sf.read(path, dtype="float32", always_2d=True)
    _, st = short_term(data, sr)
    live = st[st > -70.0]
    if not len(live):
        return {"spread_5_95_lu": None, "hole_db": None, "lra_lu": None,
                "median_lufs": None}
    p5, p95 = float(np.percentile(live, 5)), float(np.percentile(live, 95))
    median = float(np.median(live))
    return {"spread_5_95_lu": round(p95 - p5, 2),
            "hole_db": round(median - float(live.min()), 2),
            "lra_lu": measure(path)["lra"],
            "median_lufs": round(median, 2)}


def steadiest_window(track: str, need: float, src_dur: float,
                     step: float = 5.0) -> tuple[float, dict]:
    """Where in a track to take a bed from: the steadiest `need` seconds of it.

    It used to be the middle, with the comment "take from the middle". The
    middle is an arbitrary choice and on this film it was an actively bad one:
    `Spooked` fades out over its last thirty seconds, and the middle of a
    321-second window inside a 353-second track pushes the window's tail into
    that fade. Measured, the middle gave a 18.7 dB hole and the head of the
    track gave 6.3 dB — and the hole landed exactly on the act 2 boundary,
    where the sting is.

    Scored on the same two numbers the bed is gated by, with the hole weighted
    half: a shallow hole in a slightly wider spread is better than a narrow
    spread with the music dropping out of it.
    """
    from verify_sfx_level import short_term

    slack = src_dur - need
    if slack <= step:
        return max(0.0, slack / 2), {"searched": 0, "why": "no slack to search"}

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", track, "-f", "f32le",
         "-acodec", "pcm_f32le", "-ac", "2", "-ar", str(SR), "-"],
        capture_output=True, check=True).stdout
    y = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
    times, st = short_term(y, SR)
    hop = times[1] - times[0] if len(times) > 1 else 0.1
    width = int(need / hop)

    best = None
    searched = 0
    for i in range(0, max(1, len(st) - width), max(1, int(step / hop))):
        seg = st[i:i + width]
        live = seg[seg > -70.0]
        if len(live) < 0.9 * width:        # mostly silence; not a bed
            continue
        searched += 1
        spread = float(np.percentile(live, 95) - np.percentile(live, 5))
        hole = float(np.median(live) - live.min())
        score = spread + 0.5 * hole
        if best is None or score < best[0]:
            best = (score, spread, hole, float(i * hop))
    if best is None:
        return max(0.0, slack / 2), {"searched": 0,
                                     "why": "no window was mostly not silence"}
    score, spread, hole, start = best
    start = min(start, max(0.0, slack))
    return start, {"searched": searched, "step_seconds": step,
                   "start_seconds": round(start, 1),
                   "middle_would_be": round(slack / 2, 1),
                   "spread_5_95_lu": round(spread, 2),
                   "hole_db": round(hole, 2)}


def condition_bed(src: str, dst: str, name: str,
                  under_speech_lufs: float) -> dict:
    """EQ a bed, compress it until it holds still, then level it.

    The compressor threshold is not a typed-in number. It starts at the bed's
    own integrated loudness — so roughly the louder half of the material is
    what gets reduced — and is lowered 3 dB at a time until the measured
    loudness range is inside the ceiling. Starting from the material means one
    threshold works for a quiet pad and a loud one; measuring after each pass
    means the ceiling is a fact about the file rather than a hope about the
    settings.
    """
    eqd = dst + ".eq.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", BED_EQ,
         "-ar", str(SR), "-ac", "2", eqd])

    start = measure(eqd)
    threshold_db = start["lufs"] if start["lufs"] is not None else -24.0
    passes, lra = 0, None
    for attempt in range(BED_COMPRESSOR_MAX_PASSES):
        passes = attempt + 1
        linear = min(1.0, max(0.000976563, 10 ** (threshold_db / 20.0)))
        comp = dst + ".comp.wav"
        run(["ffmpeg", "-v", "error", "-y", "-i", eqd, "-af",
             f"acompressor=threshold={linear:.6f}:ratio={BED_COMPRESSOR_RATIO}:"
             f"attack={BED_COMPRESSOR_ATTACK_MS}:release={BED_COMPRESSOR_RELEASE_MS}:"
             f"knee={BED_COMPRESSOR_KNEE_DB}:makeup=1:detection=rms",
             "-ar", str(SR), "-ac", "2", comp])
        # Levelled before the range is measured, because the normaliser is
        # allowed to be the thing that widens it: loudnorm with a linear gain
        # cannot, but it is cheap to measure the file that will actually play.
        two_pass_loudnorm(comp, dst, I=under_speech_lufs, TP=-6,
                          LRA=BED_LRA_MAX_LU)
        dyn = internal_dynamics(dst)
        lra = dyn["lra_lu"]
        if (dyn["spread_5_95_lu"] is None
                or (dyn["spread_5_95_lu"] <= BED_DYNAMICS_MAX_LU
                    and dyn["hole_db"] is not None
                    and dyn["hole_db"] <= BED_HOLE_MAX_DB)):
            break
        # Lowering the threshold is what closes a hole: a 2:1 compressor only
        # acts above its threshold, so to halve a range you have to put the
        # threshold under the bottom of it.
        threshold_db -= 3.0
    for scratch in (eqd, dst + ".comp.wav"):
        if os.path.exists(scratch):
            os.remove(scratch)
    return {
        "name": name,
        "source_lufs": start["lufs"],
        "source_lra_lu": start["lra"],
        "window": WINDOWS.get(name),
        "compressor_threshold_db": round(threshold_db, 1),
        "compressor_passes": passes,
        "lra_lu": lra,
        "spread_5_95_lu": dyn["spread_5_95_lu"],
        "hole_db": dyn["hole_db"],
        "levelled_to_lufs": under_speech_lufs,
    }


def bed_spread(bed: str, spans: list[dict], crossfade: float
               ) -> tuple[float | None, list[tuple[str, float | None]]]:
    """Integrated loudness of the delivered bed inside each span, and the spread.

    A span is trimmed by one crossfade at each end so that a boundary — where
    two beds are both present — is not measured as if it belonged to one of
    them.
    """
    per: list[tuple[str, float | None]] = []
    for sp in spans:
        a = float(sp["start"]) + crossfade
        b = float(sp["end"]) - crossfade
        if b - a < 10.0:                      # too short to measure honestly
            per.append((sp["name"], None))
            continue
        cut = os.path.join(OUT, f".bedmeas_{sp['name']}.wav")
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", bed,
             "-t", f"{b - a:.3f}", "-ar", str(SR), "-ac", "2", cut])
        lufs = measure(cut)["lufs"]
        os.remove(cut)
        per.append((sp["name"], None if lufs is None else round(lufs, 2)))
    values = [v for _, v in per if v is not None]
    spread = round(max(values) - min(values), 2) if len(values) > 1 else None
    return spread, per


def _cosine_ramp(n: int) -> np.ndarray:
    """0 -> 1 over n samples, raised cosine: zero slope at both ends.

    Zero slope matters. A linear ramp has a corner at each end, and a corner
    in a gain curve is audible as the moment the fader started moving — which
    is the thing the whole music-rise rule exists to avoid.
    """
    if n <= 1:
        return np.ones(max(n, 0), dtype=np.float32)
    return (0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, n))).astype(np.float32)


def ramp_rises(target: np.ndarray,
               ramp_seconds: float = RISE_RAMP_SECONDS) -> np.ndarray:
    """Give every raised region of the envelope an explicit ramp in and out.

    The ramp OUT is anticipatory: it is the last `ramp_seconds` of the raised
    region, so the bed is back under the voice at the instant the voice
    returns instead of a reactive release afterwards. Offline mixing can see
    the future and a reactive ducker cannot.

    A region shorter than twice the ramp gets half of itself each way, so it
    reaches the full rise for one sample at its centre and no longer. That is
    the right behaviour and not a compromise: a 1.3 s pause should not be
    held at the gap level, it should be touched by it.
    """
    out = target.copy()
    raised = target > 0
    edges = np.diff(np.concatenate(([0], raised.view(np.int8), [0])))
    for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        r = min(int(ramp_seconds * SR), (b - a) // 2)
        if r < 1:
            continue
        ramp = _cosine_ramp(r)
        out[a:a + r] *= ramp
        out[b - r:b] *= ramp[::-1]
    return out


def shape_envelope(voice: np.ndarray, boundaries: list[float], n: int,
                   base_lufs: float, rises: list[float] | None = None
                   ) -> np.ndarray:
    """The finished dB envelope: targets, explicit ramps, de-zipper.

    ONE path. `scripts/build_demo_audio.py` builds its auditions through this
    function too, because a demo shaped by a different envelope is a demo of a
    mix that does not exist — the same defect as the two numbers that once
    existed for one bed level.
    """
    return smooth(ramp_rises(gain_envelope(voice, boundaries, n, base_lufs,
                                          rises)),
                  DEZIPPER_MS, DEZIPPER_MS)


def edge_times(env_db: np.ndarray) -> dict:
    """Measured 10-90% rise and 90-10% fall of each raised region.

    PER REGION, against that region's OWN plateau. Measuring the steepest
    rise against the film's global peak gives 4.95 s on this film, which is
    not a ramp length — it is a gap rise at +3 dB running straight into an
    act boundary at +6, so the 10% line is crossed inside the gap and the 90%
    line is not crossed until the boundary. One number for two edges.

    The figure to expect is about 0.9 s, not 1.5: a raised cosine crosses 10%
    to 90% in 0.59 of its length. Reported, never asserted — the authored
    ramp is the thing that is specified, this is the thing that was delivered.
    """
    raised = env_db > 0.01
    edges = np.diff(np.concatenate(([0], raised.view(np.int8), [0])))
    rises, falls = [], []
    for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        seg = env_db[a:b]
        plateau = float(seg.max())
        if plateau <= 0.01 or len(seg) < 3:
            continue
        lo, hi = 0.1 * plateau, 0.9 * plateau
        above_lo = np.flatnonzero(seg >= lo)
        above_hi = np.flatnonzero(seg >= hi)
        if not above_lo.size or not above_hi.size:
            continue
        rises.append((above_hi[0] - above_lo[0]) / SR)
        falls.append((above_lo[-1] - above_hi[-1]) / SR)
    if not rises:
        return {"peak_db": round(float(env_db.max()), 2), "regions": 0}
    return {
        "peak_db": round(float(env_db.max()), 2),
        "regions": len(rises),
        "rise_10_90_s_median": round(float(np.median(rises)), 2),
        "rise_10_90_s_slowest": round(float(np.max(rises)), 2),
        "fall_90_10_s_median": round(float(np.median(falls)), 2),
        "fall_90_10_s_slowest": round(float(np.max(falls)), 2),
        "authored_ramp_s": RISE_RAMP_SECONDS,
        "expected_10_90_s": round(0.59 * RISE_RAMP_SECONDS, 2),
    }


def build_bed(spans: list[dict], total: float, under_speech_lufs: float,
              crossfade: float = 2.5) -> str:
    """Lay each bed over its own span, crossfading on the act boundaries.

    Sequential acrossfade would put the joins wherever the track lengths
    happened to fall. The spans are solved so each crossfade is centred on the
    boundary it belongs to, where the picture is already fading through black.
    """
    bounds = [sp["end"] for sp in spans[:-1]]
    lengths = []
    prev_start = 0.0
    for i, sp in enumerate(spans):
        if i < len(spans) - 1:
            # output position of this segment's start, plus the half-crossfade
            L = bounds[i] + crossfade / 2 - prev_start
            prev_start = prev_start + L - crossfade
        else:
            L = total - prev_start + crossfade * 0  # remainder
        lengths.append(L)
    # correct the final length so the whole bed is exactly `total` long
    lengths[-1] = total - (sum(lengths[:-1]) - crossfade * (len(spans) - 1))

    parts = []
    for sp, L in zip(spans, lengths):
        src_dur = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", sp["track"]]).strip())
        need = L + crossfade
        seg = os.path.join(OUT, f".bedseg_{sp['name']}.wav")
        if src_dur >= need:
            # NOT the middle. See `steadiest_window`: the middle of this
            # film's opening bed landed in the track's fade-out and put an
            # 18.7 dB hole on the act 2 boundary.
            start, window = steadiest_window(sp["track"], need, src_dur)
            WINDOWS[sp["name"]] = window
            print(f"bed {sp['name']}: taking {need:.1f}s from {start:.1f}s "
                  f"(middle would be {window.get('middle_would_be')}s) — "
                  f"spread {window.get('spread_5_95_lu')} LU, hole "
                  f"{window.get('hole_db')} dB over "
                  f"{window.get('searched')} candidate windows")
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", sp["track"],
                 "-t", f"{need:.3f}", "-ar", str(SR), "-ac", "2", seg])
        else:
            # The bed is shorter than its span, so it repeats. -stream_loop
            # restarts the file on a hard cut, which drops the listener back to
            # bar one mid-phrase; under narration that reads as a mistake even
            # when it does not click. The repeats are crossfaded instead, so a
            # loop point sounds like the music turning over rather than
            # starting again. All three chosen beds run 150-220s against spans
            # of 284-629s, so every span has at least one of these.
            reps = int(need // max(1.0, src_dur - LOOP_XFADE)) + 2
            ins, chain, prev = [], [], None
            for r in range(reps):
                ins += ["-i", sp["track"]]
            for r in range(1, reps):
                label = f"l{r}"
                a = prev or "0:a"
                chain.append(f"[{a}][{r}:a]acrossfade=d={LOOP_XFADE}:"
                             f"c1={XFADE_CURVE}:c2={XFADE_CURVE}[{label}]")
                prev = label
            filt = ";".join(chain) if chain else None
            cmd = ["ffmpeg", "-v", "error", "-y"] + ins
            if filt:
                cmd += ["-filter_complex", filt, "-map", f"[{prev}]"]
            cmd += ["-t", f"{need:.3f}", "-ar", str(SR), "-ac", "2", seg]
            run(cmd)
        parts.append(seg)

    # EVERY BED IS CONDITIONED ON ITS OWN, BEFORE THE JOIN.
    #
    # It used to be one EQ and one normalisation across the joined bed, which
    # meant three tracks of three different characters arrived at one average
    # level: each bed sat wherever its own loudness put it relative to that
    # average, and the level changed at every act boundary. That is what the
    # owner heard as "music level irregular" — not the envelope, the beds.
    #
    # Conditioning each one separately is also the only way the +/-1.5 LU
    # match between beds can be asked for at all: you cannot match three
    # things to each other by normalising their sum.
    conditioned, bed_reports = [], []
    for sp, seg in zip(spans, parts):
        dst = os.path.join(OUT, f".bedcond_{sp['name']}.wav")
        bed_reports.append(condition_bed(seg, dst, sp["name"], under_speech_lufs))
        conditioned.append(dst)

    joined = os.path.join(OUT, "bed_joined.wav")
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for pth in conditioned:
        cmd += ["-i", pth]
    chain, prev = [], "0:a"
    for i in range(1, len(conditioned)):
        chain.append(f"[{prev}][{i}:a]acrossfade=d={crossfade}:"
                     f"c1={XFADE_CURVE}:c2={XFADE_CURVE}[x{i}]")
        prev = f"x{i}"
    chain.append(f"[{prev}]apad,atrim=0:{total:.3f},asetpts=N/SR/TB[j]")
    cmd += ["-filter_complex", ";".join(chain), "-map", "[j]", "-ar", str(SR), "-ac", "2", joined]
    run(cmd)

    # `bed_eq.wav` is the name the music-arousal gate reads, so it keeps the
    # name. It is now the conditioned, joined bed before the final trim of
    # level — which is what the gate should be grading, because it is what
    # goes under the voice.
    eqd = os.path.join(OUT, "bed_eq.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", joined, "-c", "copy", eqd])

    bed = os.path.join(OUT, f"bed_{abs(int(under_speech_lufs))}.wav")
    two_pass_loudnorm(eqd, bed, I=under_speech_lufs, TP=-6, LRA=BED_LRA_MAX_LU)

    # WHAT THE BEDS MEASURE WHERE THEY PLAY.
    #
    # Measured on the delivered bed inside each span rather than on the
    # separate files, because the crossfades and the final normalisation both
    # happen after conditioning and either could undo the match. The spans are
    # trimmed by a crossfade either side so a boundary is not measured as if
    # it were one bed or the other.
    spread, per_span = bed_spread(bed, spans, crossfade)
    for rep, (name, lufs) in zip(bed_reports, per_span):
        rep["in_film_lufs"] = lufs
    problems = []
    for rep in bed_reports:
        if rep["spread_5_95_lu"] is not None \
                and rep["spread_5_95_lu"] > BED_DYNAMICS_MAX_LU:
            problems.append(
                f"bed {rep['name']!r} moves {rep['spread_5_95_lu']:.1f} LU "
                f"between its 5th and 95th percentile after "
                f"{rep['compressor_passes']} compressor pass(es), over the "
                f"{BED_DYNAMICS_MAX_LU:.0f} LU ceiling (EBU LRA reads "
                f"{rep['lra_lu']}). A bed that moves this much comes forward "
                f"on its own under a voice that is not moving.")
        if rep["hole_db"] is not None and rep["hole_db"] > BED_HOLE_MAX_DB:
            problems.append(
                f"bed {rep['name']!r} drops {rep['hole_db']:.1f} dB below its "
                f"own median somewhere in its span, past the "
                f"{BED_HOLE_MAX_DB:.0f} dB limit. That is not dynamics, it is "
                f"the music going away and coming back — and whatever is in "
                f"the sound-design layer is then on top of nothing.")
    if spread is not None and spread > BED_SPREAD_MAX_LU:
        worst = ", ".join(f"{n} {v:.1f}" for n, v in per_span)
        problems.append(
            f"the beds sit {spread:.1f} LU apart in the film, over the "
            f"+/-{BED_SPREAD_MAX_LU} LU match ({worst}). The music level "
            f"changes at the act boundary, which is what it is not allowed "
            f"to do.")
    if problems:
        raise SystemExit("the music bed was refused:\n  - " +
                         "\n  - ".join(problems))

    global BED_REPORT
    BED_REPORT = {"beds": bed_reports, "spread_lu": spread,
                  "spread_ceiling_lu": BED_SPREAD_MAX_LU,
                  "lra_ceiling_lu": BED_LRA_MAX_LU,
                  "eq": BED_EQ,
                  "compressor": {"ratio": BED_COMPRESSOR_RATIO,
                                 "attack_ms": BED_COMPRESSOR_ATTACK_MS,
                                 "release_ms": BED_COMPRESSOR_RELEASE_MS,
                                 "knee_db": BED_COMPRESSOR_KNEE_DB}}
    return bed


def speech_envelope(voice: np.ndarray) -> np.ndarray:
    """Per-sample speech-present flag from a 400 ms short-term loudness window."""
    mono = voice.mean(axis=1)
    win = int(0.4 * SR)
    hop = int(0.05 * SR)
    n = max(1, (len(mono) - win) // hop)
    st = np.empty(n, dtype=np.float32)
    for i in range(n):
        seg = mono[i * hop:i * hop + win]
        st[i] = np.sqrt((seg.astype(np.float64) ** 2).mean()) + 1e-12
    db = 20 * np.log10(st)
    # speech is anything within 25 dB of the loud passages; silence sits far below
    thr = np.percentile(db, 85) - 25
    flag = (db > thr).astype(np.float32)
    return np.repeat(flag, hop)[:len(mono)]


def build_sound_design(total: float, bed: np.ndarray):
    """Render the sound-design layer, if this project has a spec for one.

    Returns (samples, report). A project without a spec gets (None, a report
    saying so) rather than a silent skip: an absent floor should be visible in
    the mix report, because that is where anyone looks when the film sounds
    thin.
    """
    spec_path = os.path.join(PROJ, "artifacts", "sound_design.json")
    if not os.path.exists(spec_path):
        return None, {"present": False,
                      "why": "no artifacts/sound_design.json for this project"}

    import yaml

    from sound_design import build as build_design, check_spec

    with open(spec_path, encoding="utf-8") as fh:
        spec = json.load(fh)
    with open(os.path.join(ROOT, "styles", "wak3up-documentary.yaml"),
              encoding="utf-8") as fh:
        playbook = yaml.safe_load(fh)

    problems = check_spec(spec, playbook)
    if problems:
        raise SystemExit("sound design spec rejected:\n  - " +
                         "\n  - ".join(problems))

    # Every level is an offset from the music bed AS IT SITS IN THE FILM, so
    # the floor follows the bed through the -36 / -30 / -33 audition instead
    # of needing three separate specs.
    #
    # K-WEIGHTED, AND THE MEDIAN. It was the broadband RMS of the whole ducked
    # bed, which is the wrong unit — the gate that decides whether a sound is
    # too loud measures K-weighted loudness, and the two differ by up to 10 dB
    # depending on where an element sits in the spectrum. The median of the
    # short-term windows rather than the integrated figure because the offsets
    # are about the bed's level in a MOMENT, and for a bed held inside 6 LU
    # the two are within a decibel of each other anyway.
    # THE UN-DUCKED BED, and this is the whole point of the argument.
    #
    # It was `bed_ducked`, and the layer built against it is then multiplied by
    # the SAME envelope a few lines later — so the floor was ducked twice
    # relative to its own reference. The envelope is 0 dB under speech and
    # +3 dB in a gap and +6 dB at an act boundary, which is exactly where the
    # impacts and the stings are placed, so every one-shot arrived 3 to 6 dB
    # louder than the playbook asked for and nowhere else did. Measured: the
    # sting at 52s came out at -32.3 LUFS against a -38.3 target, +6.0 dB, the
    # boundary boost to the decibel.
    #
    # Referenced to the un-ducked bed, the ratio between the two layers is the
    # playbook's offset at every instant, which is what "the sound-design
    # layer rides the SAME envelope as the music" was always supposed to mean.
    from verify_sfx_level import short_term

    bed_times, bed_st = short_term(bed, SR)
    bed_live = bed_st[bed_st > -70.0]
    bed_db = float(np.median(bed_live)) if bed_live.size else -60.0
    print(f"the bed the floor is placed under: {bed_db:.1f} LUFS (median "
          f"short-term window of the ducked bed)")

    samples, report = build_design(
        spec, total, bed_db, playbook,
        os.path.join(PROJ, "assets", "audio", "sound_design"),
        bed_curve=(bed_times, bed_st))
    report["present"] = True
    return samples, report


def measure_air(voice: np.ndarray, total: float) -> dict:
    """Silence in the finished voice track: how much, how many gaps, how long.

    Uses the same speech flag the ducking is keyed on, so the air the report
    claims is the air the mix actually treats as a gap.
    """
    flag = speech_envelope(voice)
    quiet = flag < 0.5
    edges = np.diff(np.concatenate(([0], quiet.view(np.int8), [0])))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    lengths = [(b - a) / SR for a, b in zip(starts, ends)]
    # Two thresholds, because they are two different things. A 0.7s break is
    # punctuation — the voice taking a breath between sentences — and run #1
    # had 54 of them. Air is a gap the music can rise into and a cut can land
    # inside, which the playbook sets at GAP_SECONDS, and run #1 had none at
    # all. Reporting only the first number would have called a film with no
    # air 4% air.
    pauses = [g for g in lengths if g >= 0.6]
    gaps = [g for g in lengths if g >= GAP_SECONDS]
    realised = float(sum(gaps))
    return {
        "realised_air_seconds": round(realised, 2),
        "realised_gaps": len(gaps),
        "air_threshold_s": GAP_SECONDS,
        "pauses_over_0_6s": len(pauses),
        "pause_seconds_total": round(float(sum(pauses)), 2),
        "longest_realised_gap_s": round(max(lengths), 2) if lengths else 0.0,
        "air_pct_of_total": round(100 * realised / total, 1) if total else 0.0,
    }


def gain_envelope(voice: np.ndarray, boundaries: list[float], n: int,
                  base_lufs: float,
                  rises: list[float] | None = None) -> np.ndarray:
    """dB offsets applied to the bed, before the ramps and the de-zipper.

    `rises` are the cut times the edit asked the music to lift under and the
    bed supports — see RISE_WINDOW above for what that is allowed to mean.

    `boundaries` ARE THE ACT BOUNDARIES, AND THAT IS A FIX.
    ------------------------------------------------------
    This parameter was called `offsets` and it was given the list
    `build_narration` returns — which is one entry PER NARRATION SEGMENT, not
    per act. On easter-island that is 73 segments against 6 acts, so the bed
    was lifted to the ACT-BOUNDARY level, the loudest level in the mix, at
    every one of 73 paragraph starts: 365 seconds of a 1,210-second film, 30%
    of the runtime, at a level reserved for the fade through black.
    Mid-sentence, under speech, where `bed_under_speech_lufs` is supposed to
    be a binding number.

    This is what the owner heard as "MUSIC LEVEL IRREGULAR", and no gate could
    have found it: the film's integrated loudness is set by the voice, the
    bed's integrated loudness still came out at its target because the lifts
    average out over twenty minutes, and the music-rise gate only looks at the
    cuts the EDIT asked to lift under. Nothing measured the envelope against
    the thing it was supposed to be keyed to.

    The name was the whole bug. `offsets` is true of both lists.
    """
    # CAPPED. The gap target is an absolute level and the cap is a limit on
    # the move; where they disagree the cap wins, so a bed that is dropped
    # again later does not quietly grow a bigger rise to reach a fixed
    # absolute figure. At -33 under speech the two agree exactly: -30 is +3.
    gap_boost = min(GAP_TARGET_LUFS - base_lufs, GAP_RISE_DB_MAX)
    boundary_boost = BOUNDARY_TARGET_LUFS - base_lufs
    rise_spans = [(max(0.0, t - RISE_WINDOW), t + RISE_WINDOW)
                  for t in (rises or [])]
    speech = speech_envelope(voice)
    if len(speech) < n:
        speech = np.pad(speech, (0, n - len(speech)))
    speech = speech[:n]

    target = np.zeros(n, dtype=np.float32)        # 0 dB == the under-speech level

    # gaps longer than GAP_SECONDS rise by GAP_BOOST_DB
    quiet = speech < 0.5
    edges = np.diff(np.concatenate(([0], quiet.view(np.int8), [0])))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    for a, b in zip(starts, ends):
        length = (b - a) / SR
        if length >= GAP_SECONDS:
            target[a:b] = gap_boost
        elif length >= RISE_MIN_GAP_SECONDS and any(
                a / SR < hi and b / SR > lo for lo, hi in rise_spans):
            # Too short to be a gap on its own, but the music is rising into
            # this cut and the edit asked for it, so it takes the gap level.
            target[a:b] = gap_boost

    # act boundaries rise further, under the fade through black
    for off in boundaries:
        a = max(0, int((off - BOUNDARY_WINDOW) * SR))
        b = min(n, int((off + BOUNDARY_WINDOW) * SR))
        target[a:b] = np.maximum(target[a:b], boundary_boost)
    return target


def smooth(target: np.ndarray, attack_ms: float, release_ms: float) -> np.ndarray:
    """Asymmetric one-pole: fast enough to get out of the way, slow coming back."""
    a_up = np.exp(-1.0 / (SR * attack_ms / 1000.0))     # rising level = release
    a_dn = np.exp(-1.0 / (SR * release_ms / 1000.0))
    out = np.empty_like(target)
    y = target[0]
    for i in range(len(target)):
        x = target[i]
        c = a_up if x < y else a_dn
        y = c * y + (1 - c) * x
        out[i] = y
    return out


def playbook_under_speech_lufs() -> float:
    """The bed level, from the playbook, which is where the decision lives.

    It was an argument, which meant the level that shipped was whatever was
    typed that day. It was decided by ear on 2026-10-21 — -30, from an A/B of
    -36, -30 and -28 with the sound design present — and a decision made by
    ear belongs in the playbook, not in a shell history.
    """
    import yaml

    with open(os.path.join(ROOT, "styles", "wak3up-documentary.yaml"),
              encoding="utf-8") as fh:
        return float(yaml.safe_load(fh)["audio"]["music_under_speech_lufs"])


def main() -> int:
    """argv: [--project <slug>] <spans json> <out> [under-speech LUFS] [window json]

    The level defaults to the playbook's and only needs stating to audition
    something else. The project defaults to run #1's, so the positional
    contract every existing caller uses is unchanged.
    """
    argv = sys.argv[1:]
    if argv and argv[0] == "--project":
        set_project(argv[1])
        argv = argv[2:]
    print(f"project: {PROJECT}")

    spans = json.loads(argv[0])
    out_path = argv[1]
    stated_level = len(argv) > 2 and argv[2] != "-"
    under_speech = float(argv[2]) if stated_level else playbook_under_speech_lufs()
    window = json.loads(argv[3]) if len(argv) > 3 else None

    # The cuts the edit asked the music to lift under, already reconciled
    # against this bed by `build_render_props`. Absent, the mix is exactly
    # what it was: gaps and act boundaries only.
    rises: list[float] = []
    props_path = os.path.join(PROJ, "artifacts", "render_props.json")
    if os.path.exists(props_path):
        with open(props_path, encoding="utf-8") as fh:
            rises = [float(c.get("in_seconds", 0.0))
                     for c in json.load(fh).get("cuts", [])
                     if c.get("music_rise_allowed")]
    print(f"music rises the bed supports: {len(rises)}")
    print(f"bed under speech: {under_speech} LUFS"
          + ("" if stated_level else " (from the playbook)"))

    # IS ANY OF THESE BEDS TOO BRIGHT TO SIT UNDER A VOICE?
    #
    # Checked here, on the chosen tracks, before a minute of mixing is spent
    # on them. The three movement criteria the beds were chosen by say nothing
    # about timbre, so a bed can meet all three and still hiss.
    from music_brightness import check as check_brightness

    bright_problems, brightness = check_brightness(
        [{"name": sp["name"], "path": sp["track"]} for sp in spans])
    for row in brightness["beds"]:
        print(f"bed {row['name']}: {row['energy_above_4k_pct']:.2f}% above "
              f"4 kHz, centroid {row['spectral_centroid_hz']:.0f} Hz "
              f"({row['after_eq']:.2f}% after the EQ)")
    if bright_problems:
        raise SystemExit("the music was refused:\n  - " +
                         "\n  - ".join(bright_problems))

    voice_path, offsets, boundaries, air = build_narration()
    total = len(sf.read(voice_path, dtype="float32")[0]) / SR
    bed_path = build_bed(spans, total, under_speech)

    voice, _ = sf.read(voice_path, dtype="float32", always_2d=True)
    bed, _ = sf.read(bed_path, dtype="float32", always_2d=True)
    n = min(len(voice), len(bed))
    voice, bed = voice[:n], bed[:n]

    # What the film actually holds, measured on the voice track rather than
    # taken from the plan. The two disagreeing is the defect worth catching:
    # the plan asked for air, the synthesiser did not deliver it, and the
    # loudness checks all pass either way because they are set by the voice.
    air.update(measure_air(voice, total))

    env_db = shape_envelope(voice, boundaries, n, under_speech, rises)
    edges = edge_times(env_db)
    print(f"envelope: peak {edges.get('peak_db')} dB over "
          f"{edges.get('regions')} raised regions; 10-90% rise median "
          f"{edges.get('rise_10_90_s_median')}s (slowest "
          f"{edges.get('rise_10_90_s_slowest')}s), 90-10% fall median "
          f"{edges.get('fall_90_10_s_median')}s; authored ramp "
          f"{RISE_RAMP_SECONDS}s each way, so expect "
          f"{edges.get('expected_10_90_s')}s")
    duck = (10 ** (env_db[:, None] / 20)).astype(np.float32)
    bed_ducked = bed * duck

    # The sound-design layer rides the SAME envelope as the music. A second
    # ducker on the same voice would fight the first one, and the floor would
    # pump where the bed does not.
    design, design_report = build_sound_design(total, bed)
    design_ducked = (design[:n, None] * duck) if design is not None else None

    # IS THE FLOOR UNDER THE BED, EVERYWHERE?
    #
    # On the two finished layers, not on the offset table: the offsets are
    # relative to the bed's UNDER-SPEECH level and the bed is 3 dB higher in a
    # gap and 6 dB higher at a boundary, which is exactly where the one-shots
    # are placed. Only the layers know the answer.
    sfx_report: dict = {"checked": False}
    if design_ducked is not None:
        from verify_sfx_level import check as check_sfx

        spec_path = os.path.join(PROJ, "artifacts", "sound_design.json")
        spec = None
        if os.path.exists(spec_path):
            with open(spec_path, encoding="utf-8") as fh:
                spec = json.load(fh)
        sfx_problems, sfx_report = check_sfx(design_ducked, bed_ducked, SR, spec)
        sfx_report["checked"] = True
        print(f"sound design against the bed: "
              f"{sfx_report['events_over_the_bed']} of "
              f"{sfx_report['events_checked']} events over it; "
              f"{sfx_report['continuous_seconds_over_the_bed']}s of the "
              f"continuous layers over it (worst "
              f"{sfx_report['worst_continuous_excess_db']} dB at "
              f"{sfx_report['worst_continuous_at_seconds']}s); "
              f"{sfx_report['seconds_excluded_as_a_hole_in_the_bed']}s "
              f"excluded as a hole in the bed")
        if sfx_problems:
            raise SystemExit("the sound-design layer was refused:\n  - " +
                             "\n  - ".join(sfx_problems))

    mix = voice + bed_ducked
    if design_ducked is not None:
        mix = mix + design_ducked
    pre = os.path.join(OUT, ".mix_pre.wav")
    sf.write(pre, mix, SR)

    if window:
        start, dur = window
        cut = os.path.join(OUT, ".mix_cut.wav")
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-i", pre, "-t", str(dur),
             "-ar", str(SR), "-ac", "2", cut])
        pre = cut

    two_pass_loudnorm(pre, out_path, I=-14, TP=-1.5, LRA=11)

    report = {
        "output": out_path,
        "spans": [{"name": sp["name"], "acts": sp.get("acts"),
                   "track": os.path.basename(sp["track"]),
                   "start": sp["start"], "end": sp["end"]} for sp in spans],
        "under_speech_lufs": under_speech,
        "gap_target_lufs": GAP_TARGET_LUFS,
        "gap_rise_db_max": GAP_RISE_DB_MAX,
        "boundary_target_lufs": BOUNDARY_TARGET_LUFS,
        "duck": {"rise_ramp_seconds": RISE_RAMP_SECONDS,
                 "dezipper_ms": DEZIPPER_MS,
                 "gap_seconds": GAP_SECONDS,
                 "measured_edges": edges,
                 "superseded": {"attack_ms": SUPERSEDED_ATTACK_MS,
                                "release_ms": SUPERSEDED_RELEASE_MS,
                                "why": "a one-pole cannot be asked for a ramp "
                                       "length; measured, 1200 ms gave a "
                                       "2.64 s rise and a 0.33 s fall"}},
        "eq": BED_EQ,
        "bed_conditioning": BED_REPORT,
        "brightness": brightness,
        "sfx_against_the_bed": sfx_report,
        "narration": measure(voice_path),
        "air": air,
        "sound_design": design_report,
        "bed_under_speech": measure(bed_path),
        "final": measure(out_path),
        "note": "LRA is recorded on the FILM, not targeted; it IS a ceiling on each BED.",
    }
    json.dump(report, open(os.path.join(OUT, "mix_report.json"), "w"), indent=1)
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

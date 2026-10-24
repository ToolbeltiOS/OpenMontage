#!/usr/bin/env python3
"""Mix narration and music beds to the documentary's loudness spec.

Ducking is done with an explicit gain envelope computed from the narration's
own short-term loudness, not with a threshold compressor. A compressor's duck
depth depends on how far the signal is over the threshold, so it cannot be
asked for "music sits 16 dB under the voice" — it can only be tuned until it
looks about right. The envelope here is derived from measurement and the
resulting levels are verifiable afterwards.

Levels (run #2, approved):
  narration        -16 LUFS short-term, true peak -1.5 dBTP
  music under speech   -36 LUFS integrated (the bed is normalised to it)
  music in gaps > 1.5s -26 LUFS  (absolute target, so +10 dB here)
  music at act boundaries -22 LUFS (absolute, +14 dB), under the fade to black
  attack 150 ms / release 900 ms, so it never pumps
  music EQ: high-pass 120 Hz, low-pass 7 kHz, -4 dB around 3 kHz
  final mix        -14 LUFS integrated, -1.5 dBTP

No LRA target. A continuously narrated film has little loudness range by
nature — the voice sits at one level for twenty minutes — and the earlier
6-9 LU target was dropped rather than manufactured by letting the music swell.
The measured figure is recorded instead.

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
GAP_TARGET_LUFS = -26.0        # absolute, not an offset
BOUNDARY_TARGET_LUFS = -22.0
BOUNDARY_WINDOW = 2.5      # the music crossfade length

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
ATTACK_MS = 150
RELEASE_MS = 900


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


def build_narration() -> tuple[str, list[float], dict]:
    """Concatenate the segments, insert the written air, normalise to -16 LUFS."""
    os.makedirs(OUT, exist_ok=True)
    segments, source = narration_segments()
    # The silence has to be written in the same format as the thing it sits
    # between, because the concat demuxer will not resample it.
    sample_rate, channels = audio_format(segments[0]["path"])
    offsets, t = [], 0.0
    planned_air = 0.0
    listfile = os.path.join(OUT, "narration_concat.txt")
    with open(listfile, "w", encoding="utf-8") as fh:
        for seg in segments:
            path = seg["path"]
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
    }
    return voice, offsets, air


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
            start = max(0.0, (src_dur - need) / 2)   # take from the middle
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
                chain.append(f"[{a}][{r}:a]acrossfade=d={LOOP_XFADE}:c1=tri:c2=tri[{label}]")
                prev = label
            filt = ";".join(chain) if chain else None
            cmd = ["ffmpeg", "-v", "error", "-y"] + ins
            if filt:
                cmd += ["-filter_complex", filt, "-map", f"[{prev}]"]
            cmd += ["-t", f"{need:.3f}", "-ar", str(SR), "-ac", "2", seg]
            run(cmd)
        parts.append(seg)

    joined = os.path.join(OUT, "bed_joined.wav")
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for pth in parts:
        cmd += ["-i", pth]
    chain, prev = [], "0:a"
    for i in range(1, len(parts)):
        chain.append(f"[{prev}][{i}:a]acrossfade=d={crossfade}:c1=tri:c2=tri[x{i}]")
        prev = f"x{i}"
    chain.append(f"[{prev}]apad,atrim=0:{total:.3f},asetpts=N/SR/TB[j]")
    cmd += ["-filter_complex", ";".join(chain), "-map", "[j]", "-ar", str(SR), "-ac", "2", joined]
    run(cmd)

    eqd = os.path.join(OUT, "bed_eq.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", joined, "-af",
         # out of the voice's way: no low rumble, no air, and a dip through the
         # consonant band where intelligibility lives
         "highpass=f=120,highpass=f=120,lowpass=f=7000,lowpass=f=7000,"
         "equalizer=f=3000:width_type=o:width=1.4:g=-4",
         "-ar", str(SR), "-ac", "2", eqd])

    bed = os.path.join(OUT, f"bed_{abs(int(under_speech_lufs))}.wav")
    two_pass_loudnorm(eqd, bed, I=under_speech_lufs, TP=-6, LRA=7)
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


def build_sound_design(total: float, bed_ducked: np.ndarray):
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

    # Every level is an offset from the music bed AS IT SITS UNDER SPEECH, so
    # the floor follows the bed through the -36 / -30 / -28 audition instead of
    # needing three separate specs.
    mono = bed_ducked.mean(axis=1) if bed_ducked.ndim > 1 else bed_ducked
    loud = mono[np.abs(mono) > 0]
    bed_db = float(20 * np.log10(np.sqrt(np.mean(loud.astype(np.float64) ** 2)) + 1e-12)) \
        if loud.size else -60.0

    samples, report = build_design(
        spec, total, bed_db, playbook,
        os.path.join(PROJ, "assets", "audio", "sound_design"))
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


def gain_envelope(voice: np.ndarray, offsets: list[float], n: int,
                  base_lufs: float,
                  rises: list[float] | None = None) -> np.ndarray:
    """dB offsets applied to the bed, before attack/release smoothing.

    `rises` are the cut times the edit asked the music to lift under and the
    bed supports — see RISE_WINDOW above for what that is allowed to mean.
    """
    gap_boost = GAP_TARGET_LUFS - base_lufs
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
    for off in offsets[1:]:
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

    voice_path, offsets, air = build_narration()
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

    env_db = smooth(gain_envelope(voice, offsets, n, under_speech, rises),
                    ATTACK_MS, RELEASE_MS)
    duck = (10 ** (env_db[:, None] / 20)).astype(np.float32)
    bed_ducked = bed * duck

    # The sound-design layer rides the SAME envelope as the music. A second
    # ducker on the same voice would fight the first one, and the floor would
    # pump where the bed does not.
    design, design_report = build_sound_design(total, bed_ducked)
    design_ducked = (design[:n, None] * duck) if design is not None else None

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
        "boundary_target_lufs": BOUNDARY_TARGET_LUFS,
        "duck": {"attack_ms": ATTACK_MS, "release_ms": RELEASE_MS,
                 "gap_seconds": GAP_SECONDS},
        "eq": "highpass 120 Hz x2, lowpass 7 kHz x2, -4 dB at 3 kHz (Q~1.4)",
        "narration": measure(voice_path),
        "air": air,
        "sound_design": design_report,
        "bed_under_speech": measure(bed_path),
        "final": measure(out_path),
        "note": "LRA is recorded, not targeted: narration-led material has little range.",
    }
    json.dump(report, open(os.path.join(OUT, "mix_report.json"), "w"), indent=1)
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
PROJ = os.path.join(ROOT, "projects", "they-said-it-couldnt-be-built")
AUD = os.path.join(PROJ, "assets", "audio")
OUT = os.path.join(PROJ, "renders")
SECTIONS = ["cold_open", "act1", "act2", "act3", "act4", "outro"]

GAP_SECONDS = 1.5
GAP_TARGET_LUFS = -26.0        # absolute, not an offset
BOUNDARY_TARGET_LUFS = -22.0
BOUNDARY_WINDOW = 2.5      # the music crossfade length
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


def build_narration() -> tuple[str, list[float]]:
    """Concatenate the sections and normalise the voice to -16 LUFS / -1.5 dBTP."""
    os.makedirs(OUT, exist_ok=True)
    offsets, t = [], 0.0
    listfile = os.path.join(OUT, "narration_concat.txt")
    with open(listfile, "w", encoding="utf-8") as fh:
        for s in SECTIONS:
            path = os.path.join(AUD, s + ".wav")
            offsets.append(t)
            t += float(subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", path]).strip())
            fh.write(f"file '{path}'\n")
    # The concat demuxer decodes every file with the FIRST file's format. A
    # section written at a different rate or channel count is not resampled,
    # it is misread: a 48 kHz stereo outro among 24 kHz mono sections decoded
    # as four times its length and added 33 seconds of slurred audio to the
    # film. Check before concatenating rather than discovering it in the mix.
    fmts = set()
    for s in SECTIONS:
        fmts.add(subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
             "stream=sample_rate,channels", "-of", "csv=p=0",
             os.path.join(AUD, s + ".wav")], text=True).strip())
    if len(fmts) > 1:
        raise SystemExit(f"narration sections differ in format: {sorted(fmts)}. "
                         f"Re-encode them to match before mixing.")

    raw = os.path.join(OUT, "narration_raw.wav")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
         "-ar", str(SR), "-ac", "2", raw])
    voice = os.path.join(OUT, "narration_16.wav")
    two_pass_loudnorm(raw, voice, I=-16, TP=-1.5, LRA=11)
    return voice, offsets


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


def gain_envelope(voice: np.ndarray, offsets: list[float], n: int,
                  base_lufs: float) -> np.ndarray:
    """dB offsets applied to the bed, before attack/release smoothing."""
    gap_boost = GAP_TARGET_LUFS - base_lufs
    boundary_boost = BOUNDARY_TARGET_LUFS - base_lufs
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
        if (b - a) / SR >= GAP_SECONDS:
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


def main() -> int:
    """argv: <spans json> <under-speech LUFS> <out> [window json]"""
    spans = json.loads(sys.argv[1])
    under_speech = float(sys.argv[2])
    out_path = sys.argv[3]
    window = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None

    voice_path, offsets = build_narration()
    total = len(sf.read(voice_path, dtype="float32")[0]) / SR
    bed_path = build_bed(spans, total, under_speech)

    voice, _ = sf.read(voice_path, dtype="float32", always_2d=True)
    bed, _ = sf.read(bed_path, dtype="float32", always_2d=True)
    n = min(len(voice), len(bed))
    voice, bed = voice[:n], bed[:n]

    env_db = smooth(gain_envelope(voice, offsets, n, under_speech), ATTACK_MS, RELEASE_MS)
    bed_ducked = bed * (10 ** (env_db[:, None] / 20)).astype(np.float32)

    mix = voice + bed_ducked
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
        "bed_under_speech": measure(bed_path),
        "final": measure(out_path),
        "note": "LRA is recorded, not targeted: narration-led material has little range.",
    }
    json.dump(report, open(os.path.join(OUT, "mix_report.json"), "w"), indent=1)
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Synthesise the narration, one segment per beat, and bake the written air.

WHY A SEGMENT AT A TIME
-----------------------
Run #1 synthesised one file per section and delivered thirteen seconds of
silence in a twenty-minute film, because a section is a wall of prose and a
synthesiser does not invent a four-second gap in the middle of one. The air is
written in the script, `lib/script_beats.py --plan` turns each marker into a
number, and this stage is where those numbers become real silence.

So the unit is the beat, not the section: 73 segments for this film, each
rendered on its own and each followed by exactly the silence the script asked
for. `lib/mix_audio.py` reads `narration_plan.json` and expects one wav per
segment id at `assets/audio/<segment_id>.wav`; this writes them.

WHY THE SECTION FILES TOO
-------------------------
Two downstream stages read whole sections rather than segments:
`scripts/align_narration.py` aligns a section's audio against the section's
text, and `lib/build_render_props.py` takes the picture timeline's section
offsets from the section files' durations. Both must see the SAME audio the
mix will carry, so each section file is its segments concatenated with the air
already in it. A section file without the air would put the picture 112
seconds short of the sound.

SPEED COMES FROM THE BEAT
-------------------------
The script's voice_performance asks for 150 wpm baseline and about 130 on a
reveal and on every attributed claim. Kokoro's speed is a multiplier on its
own natural rate, not a wpm figure, so the baseline is calibrated by measuring
one segment and the beat offsets are applied to whatever that measurement says
(see --calibrate). The ratios are the playbook's: a landing reads at about
0.85 of the body rate and a reveal at about 0.9.

    .venv/bin/python scripts/synthesize_narration.py --project easter-island --calibrate
    .venv/bin/python scripts/synthesize_narration.py --project easter-island
    .venv/bin/python scripts/synthesize_narration.py --project easter-island --sections act2
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VOICE = "bm_george"

#: Multipliers on the body rate, from the script's voice_performance:
#: "150 wpm baseline. Drop to roughly 130 on a reveal and on every attributed
#: claim." 130/150 = 0.867, and the playbook's outro measured a landing line at
#: 0.76 against a body rate of 0.87, which is 0.874 — the same ratio from the
#: other direction.
BEAT_RATE = {
    "exposition": 1.00,
    "transition": 1.00,
    "reveal": 0.90,
    "landing": 0.87,
}

#: The hyperframes CLI shells out to python for Kokoro and the interpreter it
#: finds by default has no kokoro-onnx. The project venv does.
HF_PYTHON = str(ROOT / ".venv" / "bin" / "python")


def probe(path: Path) -> float:
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], text=True).strip())


def fmt(path: Path) -> str:
    return subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=sample_rate,channels", "-of", "csv=p=0", str(path)],
        text=True).strip()


def tts(text: str, dest: Path, speed: float) -> None:
    """One segment through the hyperframes CLI (Kokoro-82M, local, offline)."""
    env = dict(os.environ, HYPERFRAMES_PYTHON=HF_PYTHON)
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["npx", "hyperframes", "tts", text,
         "--voice", VOICE, "--speed", f"{speed:.3f}",
         "--output", str(dest), "--json"],
        cwd=ROOT, env=env, capture_output=True, text=True)
    tail = (proc.stdout or "").strip().splitlines()
    payload = None
    for line in reversed(tail):
        if line.startswith("{"):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            break
    if payload is not None and not payload.get("ok", True):
        raise SystemExit(f"tts failed for {dest.name}: {payload.get('error')}")
    if proc.returncode != 0 or not dest.exists():
        raise SystemExit(f"tts failed for {dest.name}: rc={proc.returncode}\n"
                         f"{proc.stdout[-800:]}\n{proc.stderr[-800:]}")


def silence(seconds: float, out_dir: Path, sample_rate: int, channels: int) -> Path:
    """Silence at the narration's own format, so concat never resamples."""
    path = out_dir / f"_air_{seconds:.3f}_{sample_rate}_{channels}.wav"
    if not path.exists():
        layout = "mono" if channels == 1 else "stereo"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", f"anullsrc=r={sample_rate}:cl={layout}",
             "-t", f"{seconds:.3f}", "-c:a", "pcm_s16le", str(path)], check=True)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--sections", nargs="*",
                    help="only these section ids (default: all in the plan)")
    ap.add_argument("--body-speed", type=float, default=0.89,
                    help="Kokoro speed for the body rate; beat offsets apply to it")
    ap.add_argument("--calibrate", action="store_true",
                    help="synthesise three segments, report measured wpm, write nothing else")
    ap.add_argument("--force", action="store_true",
                    help="re-synthesise segments that already exist")
    ap.add_argument("--sections-only", action="store_true",
                    help="skip synthesis; rebuild the per-section files from existing segments")
    ap.add_argument("--silent-section", action="append", default=[],
                    metavar="ID=SECONDS",
                    help="a script section with no narration that still holds "
                         "picture time, e.g. title_sequence=7.0")
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    audio = project / "assets" / "audio"
    plan = json.loads((project / "artifacts" / "narration_plan.json").read_text())
    segments = plan["segments"]
    if args.sections:
        segments = [s for s in segments if s["section_id"] in args.sections]
    if not segments:
        raise SystemExit("no segments selected")

    if args.calibrate:
        sample = [s for s in segments if s["beat"] == "exposition"][:3]
        words = secs = 0
        for seg in sample:
            dest = audio / f"_calib_{seg['id']}.wav"
            tts(seg["text"], dest, args.body_speed)
            d = probe(dest)
            n = len(seg["text"].split())
            words += n
            secs += d
            print(f"  {seg['id']}: {n} words, {d:.2f}s, "
                  f"{60 * n / d:.1f} wpm, format {fmt(dest)}")
        print(f"\nbody speed {args.body_speed}: {60 * words / secs:.1f} wpm "
              f"over {words} words")
        print(f"target 150 wpm -> body speed "
              f"{args.body_speed * 150 / (60 * words / secs):.3f}")
        return 0

    # ── segments ────────────────────────────────────────────────────────
    if not args.sections_only:
        for i, seg in enumerate(segments, 1):
            dest = audio / f"{seg['id']}.wav"
            if dest.exists() and not args.force:
                continue
            speed = args.body_speed * BEAT_RATE.get(seg["beat"], 1.0)
            tts(seg["text"], dest, speed)
            print(f"  [{i}/{len(segments)}] {seg['id']} "
                  f"({seg['beat']}, speed {speed:.3f}) -> {probe(dest):.2f}s",
                  flush=True)

    # ── per-section files, with the air baked in ────────────────────────
    sections: list[str] = []
    for seg in plan["segments"]:
        if seg["section_id"] not in sections:
            sections.append(seg["section_id"])
    if args.sections:
        sections = [s for s in sections if s in args.sections]

    first = audio / f"{plan['segments'][0]['id']}.wav"
    sr, ch = fmt(first).split(",")
    sample_rate, channels = int(sr), int(ch)

    report = []
    for section in sections:
        segs = [s for s in plan["segments"] if s["section_id"] == section]
        missing = [s["id"] for s in segs if not (audio / f"{s['id']}.wav").exists()]
        if missing:
            print(f"{section}: {len(missing)} segment(s) missing, skipped",
                  file=sys.stderr)
            continue
        listfile = audio / f"_concat_{section}.txt"
        speech = air_total = 0.0
        with listfile.open("w", encoding="utf-8") as fh:
            for seg in segs:
                wav = audio / f"{seg['id']}.wav"
                fh.write(f"file '{wav.resolve()}'\n")
                speech += probe(wav)
                air = float(seg.get("air_after_s") or 0.0)
                if air > 0:
                    fh.write(f"file '{silence(air, audio, sample_rate, channels).resolve()}'\n")
                    air_total += air
        dest = audio / f"{section}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(listfile), "-c", "copy", str(dest)], check=True)
        measured = probe(dest)
        report.append({"section": section, "segments": len(segs),
                       "speech_seconds": round(speech, 2),
                       "air_seconds": round(air_total, 2),
                       "measured_seconds": round(measured, 2)})
        print(f"{section}: {len(segs)} segments, speech {speech:.1f}s + "
              f"air {air_total:.1f}s -> {measured:.1f}s")

    # ── sections that hold time without speaking ────────────────────────
    #
    # A title sequence is six to eight seconds of picture with nobody talking
    # over it. The narration plan has no segment for it, because the plan is a
    # list of things somebody says — but the audio timeline still has to
    # reserve the time, or the sound runs ahead of the picture from the next
    # act to the end of the film. The file is written here, in the narration
    # stage, so that it exists on disk for both the mixer and the props
    # builder to measure rather than being inferred twice.
    for spec in args.silent_section:
        sid, _, secs = spec.partition("=")
        seconds = float(secs)
        dest = audio / f"{sid}.wav"
        src = silence(seconds, audio, sample_rate, channels)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src),
                        "-c:a", "pcm_s16le", str(dest)], check=True)
        report.append({"section": sid, "segments": 0, "speech_seconds": 0.0,
                       "air_seconds": 0.0,
                       "measured_seconds": round(probe(dest), 2),
                       "silent": True})
        print(f"{sid}: silent section, {probe(dest):.1f}s")

    total = sum(r["measured_seconds"] for r in report)
    speech = sum(r["speech_seconds"] for r in report)
    air = sum(r["air_seconds"] for r in report)
    print(f"\nNARRATION: {len(report)} sections, speech {speech:.1f}s, "
          f"air {air:.1f}s ({100 * air / total:.1f}%), total {total:.1f}s")
    out = project / "artifacts" / "narration_measured.json"
    out.write_text(json.dumps(
        {"voice": VOICE, "route": "hyperframes CLI / Kokoro-82M, local",
         "body_speed": args.body_speed, "beat_rate": BEAT_RATE,
         "sections": report,
         "total_speech_seconds": round(speech, 2),
         "total_air_seconds": round(air, 2),
         "total_seconds": round(total, 2)}, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

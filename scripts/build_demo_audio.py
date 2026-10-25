#!/usr/bin/env python3
"""Three mixes of the demo window, for the bed-level audition.

The owner's A/B: −36 (the approved level), −30 and −28 LUFS under speech, with
the sound design present. The floor is part of the question — the references
run their beds nearer the voice than we do, and some of what fills that
distance on their films is wind and room tone rather than music, so a bed
auditioned without a floor under it is the wrong test.

Everything is built with the film's own mixer: the same ducking envelope
(lib/mix_audio), the same sound-design layer (lib/sound_design), the same
offsets from the bed. Only the bed's target level changes between the three.

    python scripts/build_demo_audio.py --project <id> --start 306.67 --seconds 89.8
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import numpy as np                                            # noqa: E402
import soundfile as sf                                        # noqa: E402

SR = 48000
LEVELS = (-36.0, -30.0, -28.0)


def slice_wav(src: Path, start: float, seconds: float, dest: Path) -> Path:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(src),
         "-t", f"{seconds:.3f}", "-ar", str(SR), "-ac", "2", str(dest)],
        check=True)
    return dest


def loudnorm(src: Path, dest: Path, target_lufs: float) -> Path:
    """Two-pass loudnorm to an absolute target, as the film's mixer does."""
    probe = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(src), "-af",
         f"loudnorm=I={target_lufs}:TP=-2:LRA=11:print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True)
    blob = probe.stderr[probe.stderr.rfind("{"):probe.stderr.rfind("}") + 1]
    m = json.loads(blob)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af",
         f"loudnorm=I={target_lufs}:TP=-2:LRA=11:"
         f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
         f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
         f"offset={m['target_offset']}:linear=true:print_format=summary",
         "-ar", str(SR), "-ac", "2", str(dest)],
        check=True)
    return dest


def measure_lufs(path: Path) -> float:
    out = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-af",
         "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    return float(json.loads(out[out.rfind("{"):out.rfind("}") + 1])["input_i"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--seconds", type=float, required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    renders = project / "renders"
    out_dir = Path(args.out) if args.out else renders / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / ".tmp"
    tmp.mkdir(exist_ok=True)

    import yaml

    from mix_audio import shape_envelope
    from sound_design import build as build_design

    playbook = yaml.safe_load(
        (ROOT / "styles" / "wak3up-documentary.yaml").read_text())

    voice_path = slice_wav(renders / "narration_16.wav", args.start,
                           args.seconds, tmp / "voice.wav")
    bed_raw = slice_wav(renders / "bed_eq.wav", args.start, args.seconds,
                        tmp / "bed_raw.wav")

    voice, _ = sf.read(voice_path, dtype="float32", always_2d=True)
    n = len(voice)
    total = n / SR

    # The sound design for this window, offset so each element lands where it
    # does in the film. Levels are offsets from the bed, so the layer is built
    # once per bed level rather than once overall.
    spec = json.loads((project / "artifacts" / "sound_design.json").read_text())
    window = {
        "room_tone": spec["room_tone"],
        "ambience": [
            {**a,
             "start_seconds": max(a["start_seconds"] - args.start, 0.0),
             "end_seconds": min(a["end_seconds"] - args.start, total)}
            for a in spec.get("ambience", [])
            if a["end_seconds"] > args.start and a["start_seconds"] < args.start + total
        ],
        "risers": [{**r, "at_seconds": r["at_seconds"] - args.start}
                   for r in spec.get("risers", [])
                   if args.start <= r["at_seconds"] <= args.start + total],
        "impacts": [{**i, "at_seconds": i["at_seconds"] - args.start}
                    for i in spec.get("impacts", [])
                    if args.start <= i["at_seconds"] <= args.start + total],
        "stings": [{**s, "at_seconds": s["at_seconds"] - args.start}
                   for s in spec.get("stings", [])
                   if args.start <= s["at_seconds"] <= args.start + total],
    }

    report = {"window": [args.start, args.start + total], "mixes": []}

    for target in LEVELS:
        bed_path = loudnorm(bed_raw, tmp / f"bed_{abs(target):.0f}.wav", target)
        bed, _ = sf.read(bed_path, dtype="float32", always_2d=True)
        bed = bed[:n] if len(bed) >= n else np.pad(bed, ((0, n - len(bed)), (0, 0)))

        # ONE envelope path with the film. A demo shaped by a different
        # envelope is a demo of a mix that does not exist.
        env_db = shape_envelope(voice, [0.0], n, target)
        duck = (10 ** (env_db[:, None] / 20)).astype(np.float32)
        bed_ducked = bed * duck

        mono = bed_ducked.mean(axis=1)
        loud = mono[np.abs(mono) > 0]
        bed_db = float(20 * np.log10(
            np.sqrt(np.mean(loud.astype(np.float64) ** 2)) + 1e-12)) if loud.size else -60.0

        design, design_report = build_design(
            window, total, bed_db, playbook,
            str(project / "assets" / "audio" / "sound_design"))
        design_ducked = design[:n, None] * duck

        mix = voice + bed_ducked + design_ducked
        peak = float(np.max(np.abs(mix)))
        if peak > 0.99:
            mix = mix * (0.99 / peak)

        dest = out_dir / f"act2_demo_bed{abs(target):.0f}.wav"
        sf.write(dest, mix, SR)
        report["mixes"].append({
            "file": dest.name,
            "bed_target_lufs": target,
            "bed_measured_lufs": round(measure_lufs(bed_path), 2),
            "mix_measured_lufs": round(measure_lufs(dest), 2),
            "sound_design_db": design_report["measured_db"],
            "sound_design_elements": len(design_report["elements"]),
            "peak_before_limit": round(peak, 4),
        })
        print(f"bed {target:+.0f} LUFS -> {dest.name}  "
              f"mix {report['mixes'][-1]['mix_measured_lufs']} LUFS  "
              f"floor {design_report['measured_db']} dB")

    (out_dir / "demo_audio_report.json").write_text(json.dumps(report, indent=1) + "\n")
    print(f"wrote {out_dir / 'demo_audio_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

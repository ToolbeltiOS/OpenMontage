"""Is the music already rising where the edit wants it to rise?

WHY
---
The mood table lets certain rows lift the bed — a reveal in an awe register
may rise, an exposition in doubt may not. That is a decision about the EDIT.
The music is a separate fact: a bed that is sitting flat, or falling, does not
become a rise because an edit asked for one. It becomes a fader move, and a
fader move under a shot that is not changing is the thing an audience hears as
manipulation.

So a rise is allowed only where the bed is already going up, and this is what
measures that.

NOT ESSENTIA, AND SAYING SO
---------------------------
The brief named Essentia's arousal model. Essentia does not install on this
machine and the budget is zero, so this is built from librosa, which does,
and it is NOT the same thing: Essentia's arousal is a regressor trained on
human ratings, and this is three signals combined by hand.

That matters less than it sounds for the question actually being asked. "Is
this passage more arousing than that one" wants a trained model. "Is the music
rising HERE" wants a slope, and a slope is visible in loudness, brightness and
event density — which is what the three signals are:

    loudness     RMS in dB          music getting louder
    brightness   spectral centroid  music opening up, more high content
    density      onset strength     more happening per second

Each is z-scored over the piece before they are combined, because they are in
different units and the question is relative anyway. The name of the module is
arousal; the docstring is the disclaimer.

    python3 lib/music_arousal.py <bed.wav> [--at 120.5]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: How often the curve is sampled, in seconds.
HOP_S = 0.5

#: The half-width of the window a slope is taken over. Four seconds either
#: side: shorter and the slope is a phrase, longer and it is the whole act.
SLOPE_WINDOW_S = 4.0

#: Slope, in standard deviations per second, above which the music counts as
#: rising. Not zero: a flat bed wanders, and a rise that only exists in the
#: third decimal place is not one.
RISING_THRESHOLD = 0.02

#: What each signal contributes. Loudness leads because it is what a rise
#: mostly is; the other two keep a bed that opens up without getting louder
#: from reading as flat.
WEIGHTS = {"loudness": 0.5, "brightness": 0.25, "density": 0.25}


def curve(path: str, hop_s: float = HOP_S) -> dict[str, Any]:
    """Loudness, brightness and event density over the piece, combined."""
    import librosa
    import numpy as np

    y, sr = librosa.load(path, sr=22050, mono=True)
    hop = max(1, int(sr * hop_s))

    rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
    loudness = 20 * np.log10(rms + 1e-9)
    brightness = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]
    density = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)

    n = min(len(loudness), len(brightness), len(density))
    parts = {"loudness": loudness[:n], "brightness": brightness[:n],
             "density": density[:n]}

    def z(a):
        sd = float(a.std())
        return (a - a.mean()) / sd if sd > 1e-9 else np.zeros_like(a)

    combined = sum(WEIGHTS[k] * z(v) for k, v in parts.items())
    times = np.arange(n) * hop / sr
    return {
        "times": times,
        "arousal": combined,
        "hop_seconds": hop / sr,
        "duration": float(len(y) / sr),
    }


def slope_at(data: dict[str, Any], seconds: float,
             window_s: float = SLOPE_WINDOW_S) -> float:
    """Standard deviations of arousal per second, around this moment."""
    import numpy as np

    times, arousal = data["times"], data["arousal"]
    lo, hi = seconds - window_s, seconds + window_s
    mask = (times >= lo) & (times <= hi)
    if mask.sum() < 3:
        return 0.0
    return float(np.polyfit(times[mask], arousal[mask], 1)[0])


def check(cuts: list[dict[str, Any]], bed_path: str,
          window_s: float = SLOPE_WINDOW_S) -> tuple[list[str], dict[str, Any]]:
    """Every cut that asks for a rise, against what the bed is doing there."""
    data = curve(bed_path)
    problems: list[str] = []
    asked = 0
    rows = []

    for cut in cuts:
        if not cut.get("music_rise_allowed"):
            continue
        asked += 1
        at = float(cut.get("in_seconds", 0.0))
        slope = slope_at(data, at, window_s)
        rising = slope >= RISING_THRESHOLD
        rows.append({"cut": cut.get("id"), "seconds": round(at, 2),
                     "slope": round(slope, 4), "rising": rising})
        if not rising:
            problems.append(
                f"{cut.get('id')} at {at:.1f}s asks the bed to rise, and the "
                f"bed is {'falling' if slope < 0 else 'flat'} there "
                f"({slope:+.3f} sd/s against a floor of "
                f"{RISING_THRESHOLD}) — a fader move under a shot that is not "
                f"changing is what an audience hears as manipulation")

    measured = {
        "bed": bed_path,
        "bed_seconds": round(data["duration"], 1),
        "rises_asked_for": asked,
        "rises_the_music_supports": sum(1 for r in rows if r["rising"]),
        "rises": rows[:40],
    }
    return problems, measured


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bed")
    ap.add_argument("--at", type=float, default=None)
    ap.add_argument("--cuts", default=None)
    args = ap.parse_args()

    if args.cuts:
        blob = json.loads(Path(args.cuts).read_text())
        cuts = blob["cuts"] if isinstance(blob, dict) else blob
        problems, measured = check(cuts, args.bed)
        print(f"{measured['rises_asked_for']} rises asked for, "
              f"{measured['rises_the_music_supports']} the music supports")
        for p in problems[:20]:
            print("  -", p)
        print("MUSIC RISE:", "PASS" if not problems else "FAIL")
        return 0 if not problems else 1

    data = curve(args.bed)
    if args.at is not None:
        slope = slope_at(data, args.at)
        print(f"{args.at:.1f}s: slope {slope:+.4f} sd/s — "
              f"{'rising' if slope >= RISING_THRESHOLD else 'not rising'}")
        return 0

    import numpy as np

    print(f"{data['duration']:.1f}s, {len(data['times'])} samples")
    step = max(1, len(data["times"]) // 40)
    for i in range(0, len(data["times"]), step):
        t = float(data["times"][i])
        bar = int((float(data["arousal"][i]) + 2) * 8)
        print(f"  {t:7.1f}s {'#' * max(0, min(40, bar))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

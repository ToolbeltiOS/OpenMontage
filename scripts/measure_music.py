#!/usr/bin/env python3
"""Measure a music library against the playbook's bed criteria.

The playbook stopped choosing beds by mood word after run #1 put tunes under
the narration. It states three properties a track either has or does not, and
all three are measurable before anyone listens:

  melodic_movement        frame-to-frame pitch-class distance. A held chord
                          barely moves; a tune does. Prefer < 0.11.
  build_db                p95 - p25 of the loudness envelope across the track.
                          Prefer < 5 dB.
  rhythmic_periodicity    autocorrelation peak of the onset envelope over
                          50-200 BPM. Lower is better.

What this CANNOT do is certify "no melody" — the playbook says so itself, and
asks for a 20-second audition of the shortlist, EQ'd and levelled as it will
sit in the mix, before committing. This ranks candidates for that audition; it
does not replace it.

    .venv/bin/python scripts/measure_music.py --dir "$MUSIC_LIBRARY_DIR" \
        --out projects/<id>/artifacts/music_candidates.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path

import librosa
import numpy as np

SR = 22050


def measure(path: str) -> dict:
    y, sr = librosa.load(path, sr=SR, mono=True)
    seconds = len(y) / sr

    # ── melodic movement ────────────────────────────────────────────────
    # Mean L1 distance between consecutive normalised chroma frames. A
    # sustained pad holds its pitch classes; a melody moves them.
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    norm = chroma / (np.linalg.norm(chroma, ord=1, axis=0, keepdims=True) + 1e-9)
    movement = float(np.mean(np.abs(np.diff(norm, axis=1)).sum(axis=0)) / 2.0)

    # ── build ───────────────────────────────────────────────────────────
    # Spread of the short-term loudness envelope. A track that swells has a
    # wide spread; elevator-quiet has a narrow one.
    rms = librosa.feature.rms(y=y, frame_length=4096, hop_length=2048)[0]
    db = librosa.amplitude_to_db(rms + 1e-9)
    build_db = float(np.percentile(db, 95) - np.percentile(db, 25))

    # ── rhythm ──────────────────────────────────────────────────────────
    # Peak of the onset envelope's autocorrelation inside 50-200 BPM. A pad
    # has no periodic onsets; a percussion loop has a sharp one.
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    hop = 512
    ac = librosa.autocorrelate(onset - onset.mean(), max_size=len(onset))
    ac = ac / (ac[0] + 1e-9)
    frames_per_s = sr / hop
    lo = int(frames_per_s * 60 / 200)      # 200 BPM
    hi = int(frames_per_s * 60 / 50)       # 50 BPM
    window = ac[max(lo, 1):max(hi, 2)]
    periodicity = float(window.max()) if len(window) else 0.0

    return {
        "track": os.path.basename(path),
        "path": path,
        "seconds": round(seconds, 1),
        "melodic_movement": round(movement, 4),
        "build_db": round(build_db, 2),
        "rhythmic_periodicity": round(periodicity, 4),
    }


def verdict(m: dict) -> dict:
    """The playbook's preferences, applied as a score rather than a gate.

    They are stated as "prefer", not as thresholds, and a library that fails
    all three still has a least-bad track in it — so this ranks and records
    which preferences each candidate misses.
    """
    misses = []
    if m["melodic_movement"] >= 0.11:
        misses.append(f"melodic_movement {m['melodic_movement']} >= 0.11")
    if m["build_db"] >= 5.0:
        misses.append(f"build_db {m['build_db']} >= 5")
    if m["rhythmic_periodicity"] >= 0.25:
        misses.append(f"rhythmic_periodicity {m['rhythmic_periodicity']} >= 0.25")
    # Normalised so the three criteria carry comparable weight.
    score = (m["melodic_movement"] / 0.11
             + m["build_db"] / 5.0
             + m["rhythmic_periodicity"] / 0.25)
    return {**m, "misses": misses, "score": round(score, 3),
            "meets_all": not misses}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-seconds", type=float, default=60.0,
                    help="a bed shorter than this loops too often to be a span")
    args = ap.parse_args()

    files = sorted(
        p for ext in ("mp3", "wav", "m4a", "flac", "ogg")
        for p in glob.glob(os.path.join(args.dir, f"*.{ext}"))
    )
    print(f"{len(files)} tracks in {args.dir}", flush=True)

    rows = []
    for i, path in enumerate(files, 1):
        try:
            m = measure(path)
        except Exception as exc:                      # a bad file is a fact
            print(f"  [{i}/{len(files)}] {os.path.basename(path)}: "
                  f"FAILED {type(exc).__name__}: {exc}", flush=True)
            continue
        if m["seconds"] < args.min_seconds:
            print(f"  [{i}/{len(files)}] {m['track']}: {m['seconds']}s, "
                  f"too short for a bed span", flush=True)
            continue
        row = verdict(m)
        rows.append(row)
        print(f"  [{i}/{len(files)}] {row['score']:6.3f}  "
              f"mov {row['melodic_movement']:.3f}  build {row['build_db']:5.2f}  "
              f"per {row['rhythmic_periodicity']:.3f}  {row['track']}", flush=True)

    rows.sort(key=lambda r: r["score"])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "library": args.dir,
        "measured": len(rows),
        "criteria": {
            "melodic_movement": "< 0.11 preferred",
            "build_db": "< 5 dB preferred",
            "rhythmic_periodicity": "lower is better; 0.25 used as the miss line",
        },
        "note": "Ranking for an audition, not a substitute for one. The "
                "playbook requires the shortlist to be heard as 20-second "
                "previews, EQ'd and levelled as it will sit in the mix.",
        "candidates": rows,
    }, indent=2) + "\n")

    print(f"\nmeets all three: {sum(1 for r in rows if r['meets_all'])} of {len(rows)}")
    print("top 12 by score:")
    for r in rows[:12]:
        print(f"  {r['score']:6.3f}  {r['seconds']:7.1f}s  {r['track']}"
              + ("" if r["meets_all"] else f"   misses: {'; '.join(r['misses'])}"))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

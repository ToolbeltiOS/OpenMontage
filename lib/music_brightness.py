#!/usr/bin/env python3
"""How bright a music bed is, and whether it is too bright to sit under a voice.

WHY THIS EXISTS
---------------
The three bed criteria already in the playbook — melodic movement, build, and
rhythmic periodicity — are all about MOVEMENT. None of them is about timbre, so
a track can meet all three and still be wrong: a sustained, unmoving, quiet
pad made of high content hisses under the narration. The owner heard exactly
that at the head of easter-island ("high pitch at the start") on a bed that
scored 0.0486 / 3.61 dB / 0.166 and missed nothing.

The ear's complaint is about the top of the spectrum, so that is what gets
measured:

  spectral_centroid_hz    the energy-weighted centre of the spectrum. Where the
                          track "sits". A low pad is a few hundred Hz; something
                          with air in it is thousands.
  energy_above_4k_pct     share of the track's total power above 4 kHz. This is
                          the one that is gated, because 4 kHz and up is where
                          hiss, breath and cymbal wash live, and it is also
                          exactly the band the voice needs for consonants.

WHERE THE GATE IS MEASURED, AND WHY IT IS NOT MEASURED AFTER THE EQ
-------------------------------------------------------------------
On the SOURCE track, before the bed EQ.

Measured, the EQ divides the high-band ratio by about eight: a pad with
moderate hiss over it reads 65% above 4 kHz before the EQ and 8% after, which
is across the ceiling in the forgiving direction. That is the bed somebody
would actually choose, and after the EQ the gate would certify it as clean.

It is NOT true that the EQ makes anything pass — pink noise high-passed at
5 kHz still reads 38% after it, because this figure is a ratio and what
survives a 5 kHz low-pass sits just under it. The first version of this
comment claimed otherwise and the test suite disproved it. The EQ's limit is
that it cannot rescue a bed with no body; it can only make one quiet.

The EQ'd figure is still reported — it is closer to what the viewer hears —
but it is reported, not gated.

    python3 lib/music_brightness.py <track> [<track> ...]
    python3 lib/music_brightness.py --beds <edit_decisions.json>
    python3 lib/music_brightness.py --dir <library> --out <candidates.json>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from typing import Any

#: Analysis rate. Nyquist 11 kHz, which is well clear of the 4 kHz and 8 kHz
#: lines below and halves the decode cost against 48 kHz.
SR = 22050

#: The band that is gated. Above this is where hiss and cymbal wash live, and
#: it is the band the voice needs for consonants.
HIGH_HZ = 4000.0

#: A second, informational line further up, so the report can say whether the
#: high content is "air" or genuinely top-octave.
VERY_HIGH_HZ = 8000.0

#: The ceiling, as a share of the track's total power above HIGH_HZ.
#:
#: 10% is the owner's number (2026-10-25, after the first full watch). It is
#: not arbitrary in the library it was set against: of the 67 tracks measured,
#: the chosen beds ran 1.3% to 14.8% and the library's worst ran over 40%, so
#: the line sits inside the distribution rather than above it. A gate no track
#: can fail is not a gate.
MAX_ENERGY_ABOVE_4K_PCT = 10.0

#: The bed EQ, as the mixer applies it. Kept here as well as in `mix_audio` so
#: that the "after the EQ" column of a report is the EQ that actually ran, and
#: so this module can be used to audition a candidate the way it will sit.
#: 2026-10-25: a high SHELF, not the bell that was here before. "-6 dB from
#: 3.5 kHz" is a shelf — everything above the corner comes down and stays
#: down — whereas a bell at 3.5 kHz dips one band and leaves 5 kHz where it
#: was. The low-pass moved 7 kHz -> 5 kHz in the same change, so the shelf and
#: the low-pass now overlap on purpose: the shelf takes the top octave of what
#: survives, the low-pass ends it.
BED_EQ = ("highpass=f=120,highpass=f=120,"
          "highshelf=f=3500:g=-6:width_type=q:width=0.7,"
          "lowpass=f=5000,lowpass=f=5000")


def _load(path: str, eq: str | None = None):
    """Mono float32 at SR, optionally through a filter chain, via ffmpeg.

    ffmpeg rather than librosa.load so the EQ'd measurement runs through the
    same filters the mix does, instead of a reimplementation of them.
    """
    import numpy as np

    cmd = ["ffmpeg", "-v", "error", "-i", path]
    if eq:
        cmd += ["-af", eq]
    cmd += ["-f", "f32le", "-acodec", "pcm_f32le", "-ac", "1", "-ar", str(SR), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def spectrum(y, sr: int = SR):
    """Mean power spectrum of a whole track, and the bin frequencies.

    Averaged over frames rather than taken from one, so the answer is about
    the track and not about whichever second was sampled.
    """
    import numpy as np

    n_fft, hop = 4096, 2048
    if len(y) < n_fft:
        y = np.pad(y, (0, n_fft - len(y)))
    win = np.hanning(n_fft).astype(np.float32)
    frames = 1 + (len(y) - n_fft) // hop
    acc = np.zeros(n_fft // 2 + 1, dtype=np.float64)
    for i in range(frames):
        seg = y[i * hop:i * hop + n_fft] * win
        acc += np.abs(np.fft.rfft(seg)) ** 2
    acc /= max(frames, 1)
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    return acc, freqs


def brightness(path: str, eq: str | None = None) -> dict[str, Any]:
    """Centroid and high-band share of one track."""
    import numpy as np

    y = _load(path, eq)
    seconds = len(y) / SR
    power, freqs = spectrum(y)
    total = float(power.sum()) + 1e-20
    above_4k = float(power[freqs >= HIGH_HZ].sum())
    above_8k = float(power[freqs >= VERY_HIGH_HZ].sum())
    centroid = float((freqs * power).sum() / total)
    return {
        "track": os.path.basename(path),
        "path": path,
        "seconds": round(seconds, 1),
        "spectral_centroid_hz": round(centroid, 1),
        "energy_above_4k_pct": round(100.0 * above_4k / total, 2),
        "energy_above_8k_pct": round(100.0 * above_8k / total, 3),
        "measured_after_eq": bool(eq),
    }


def softest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rows, darkest first.

    Ordered by the gated quantity, with the centroid as the tie-break: two
    tracks can share a high-band share and still not sit in the same place.
    """
    return sorted(rows, key=lambda r: (r["energy_above_4k_pct"],
                                       r["spectral_centroid_hz"]))


def check(beds: list[dict[str, Any]]) -> tuple[list[str], dict[str, Any]]:
    """Gate: no bed carries more than MAX_ENERGY_ABOVE_4K_PCT above 4 kHz.

    `beds` are the EDL's bed entries — anything with a `path` (or `track`) and
    optionally a `name`.
    """
    problems: list[str] = []
    rows: list[dict[str, Any]] = []
    for bed in beds:
        path = bed.get("path") or bed.get("track")
        row = brightness(path)
        row["name"] = bed.get("name")
        row["after_eq"] = brightness(path, BED_EQ)["energy_above_4k_pct"]
        rows.append(row)
        if row["energy_above_4k_pct"] > MAX_ENERGY_ABOVE_4K_PCT:
            problems.append(
                f"bed {row.get('name') or row['track']!r} carries "
                f"{row['energy_above_4k_pct']:.1f}% of its energy above "
                f"{HIGH_HZ / 1000:.0f} kHz, over the "
                f"{MAX_ENERGY_ABOVE_4K_PCT:.0f}% ceiling (centroid "
                f"{row['spectral_centroid_hz']:.0f} Hz) — it will be audible "
                f"as hiss under the narration and it sits in the consonant "
                f"band. Choose a darker bed; the EQ cannot rescue it, it can "
                f"only make it quiet and dull.")
    return problems, {
        "ceiling_pct": MAX_ENERGY_ABOVE_4K_PCT,
        "high_hz": HIGH_HZ,
        "beds": rows,
        "worst_pct": max((r["energy_above_4k_pct"] for r in rows), default=0.0),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tracks", nargs="*")
    ap.add_argument("--beds", help="an edit_decisions.json; gate its beds")
    ap.add_argument("--dir", help="measure a whole library")
    ap.add_argument("--out", help="write the library measurement as JSON")
    ap.add_argument("--eq", action="store_true",
                    help="also report the figure after the bed EQ")
    args = ap.parse_args()

    if args.beds:
        with open(args.beds, encoding="utf-8") as fh:
            beds = (json.load(fh).get("music") or {}).get("beds") or []
        problems, measured = check(beds)
        for row in measured["beds"]:
            print(f"  {row['energy_above_4k_pct']:6.2f}% >4k  "
                  f"{row['spectral_centroid_hz']:7.1f} Hz centroid  "
                  f"({row['after_eq']:.2f}% after the EQ)  "
                  f"{row.get('name')}: {row['track']}")
        for p in problems:
            print("  -", p)
        print("MUSIC BRIGHTNESS:", "PASS" if not problems else "FAIL")
        return 0 if not problems else 1

    paths = list(args.tracks)
    if args.dir:
        paths += sorted(p for ext in ("mp3", "wav", "m4a", "flac", "ogg")
                        for p in glob.glob(os.path.join(args.dir, f"*.{ext}")))
    if not paths:
        print("nothing to measure", file=sys.stderr)
        return 2

    rows = []
    for i, path in enumerate(paths, 1):
        try:
            row = brightness(path)
        except Exception as exc:
            print(f"  [{i}/{len(paths)}] {os.path.basename(path)}: "
                  f"FAILED {type(exc).__name__}: {exc}", flush=True)
            continue
        if args.eq:
            row["after_eq"] = brightness(path, BED_EQ)["energy_above_4k_pct"]
        rows.append(row)
        print(f"  [{i}/{len(paths)}] {row['energy_above_4k_pct']:6.2f}% >4k  "
              f"{row['spectral_centroid_hz']:7.1f} Hz  {row['seconds']:7.1f}s  "
              f"{row['track']}", flush=True)

    ranked = softest(rows)
    print(f"\ndarkest 12 of {len(ranked)}:")
    for row in ranked[:12]:
        over = "" if row["energy_above_4k_pct"] <= MAX_ENERGY_ABOVE_4K_PCT else "  OVER"
        print(f"  {row['energy_above_4k_pct']:6.2f}%  "
              f"{row['spectral_centroid_hz']:7.1f} Hz  {row['seconds']:7.1f}s  "
              f"{row['track']}{over}")
    over = [r for r in ranked if r["energy_above_4k_pct"] > MAX_ENERGY_ABOVE_4K_PCT]
    print(f"\nover the {MAX_ENERGY_ABOVE_4K_PCT:.0f}% ceiling: "
          f"{len(over)} of {len(ranked)}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"high_hz": HIGH_HZ,
                       "ceiling_pct": MAX_ENERGY_ABOVE_4K_PCT,
                       "bed_eq": BED_EQ,
                       "measured": len(ranked),
                       "over_ceiling": len(over),
                       "tracks": ranked}, fh, indent=2)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

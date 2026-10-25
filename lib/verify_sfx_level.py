#!/usr/bin/env python3
"""Is the sound-design layer under the music bed, everywhere, measured?

THE RULE
--------
"Everything below the bed's level in its moment" — the owner, 2026-10-25,
after the first full watch, where the floor was loud enough to be heard as
its own layer rather than as the room the film is in. A riser that draws
attention is too loud; so is an impact that lands as a drum hit.

The playbook states each element as an offset from the bed's UNDER-SPEECH
level, which is not the same thing as the bed's level at the moment the
element plays: the bed rises +3 dB in a gap and +6 dB at an act boundary, and
it is ducked nowhere else. So an offset table cannot answer this question on
its own, and this measures it on the two finished layers instead.

WHY K-WEIGHTED AND NOT RMS
--------------------------
Because the question is "is it louder", and louder is a property of hearing,
not of a sum of squares. The elements here are deliberately spread across the
spectrum: this film's sting has a 59 Hz centroid, its impact 75 Hz, and its
sea ambience 1,647 Hz.

Measured, at equal RMS the curve puts 30 Hz 9.0 dB down on 1 kHz, 75 Hz
2.7 dB down, and 1.6 kHz 1.6 dB up — so a low impact and a bright hiss at the
same RMS differ by about 4 dB of loudness, in the direction the ear agrees
with. Four decibels, not the "far above" an earlier version of this comment
claimed; it is enough to change a verdict near the line and it is not enough
to rescue a one-shot that is 8 dB too loud.

The real reason to use it is narrower and stronger than the size of the
correction: it is the scale every other level in this film is already set in,
so the offset table and this ceiling are in one unit and can be reconciled.
Before they were in two and could not.

Both layers are measured the same way over the same windows. The absolute
figures are therefore comparable to each other, which is all the rule needs;
they are not a claim about BS.1770 compliance for a mono sum.

    python3 lib/verify_sfx_level.py <design.wav> <bed.wav> [--spec sound_design.json]
"""
from __future__ import annotations

import argparse
import json
from typing import Any

import numpy as np

#: Short-term window and hop, in seconds. 400 ms is BS.1770's momentary
#: window, which is the right length for a transient: a 3 s window would
#: average an impact away into the bed around it.
WINDOW_S = 0.400
HOP_S = 0.100

#: How far over the bed a window may measure before it is a failure. Zero:
#: the rule is "below the bed", and a tolerance here would be the gate
#: deciding how much louder than the bed is acceptable, which is not its call.
TOLERANCE_DB = 0.0

#: Windows quieter than this carry nothing to compare — both layers are
#: effectively absent and the ratio between two silences is not a finding.
FLOOR_LUFS = -70.0

#: How far below the bed's own median counts as a HOLE in the bed rather than
#: as the floor being too loud.
#:
#: 6 dB, because `lib/mix_audio.py` gates each bed at 6 LU of 5th-to-95th
#: spread: a window more than 6 dB under the bed's median is a window where
#: the bed is outside the allowance the bed gate enforces, and that is the
#: bed's defect to answer for.
#:
#: IT WAS THE BED'S 5TH PERCENTILE, which does not work: a hole big enough to
#: occupy 5% of the film defines its own floor, so the deeper and longer the
#: drop-out the less of it was recognised as one. Measured on a fixture with a
#: hole across 20% of the runtime, the percentile version excluded 0.1 s of it.
HOLE_BELOW_MEDIAN_DB = 6.0

#: BS.1770 K-weighting at 48 kHz: a high-shelf for the head, then an RLB
#: high-pass. The coefficients are the ones in the recommendation.
_SHELF_B = (1.53512485958697, -2.69169618940638, 1.19839281085285)
_SHELF_A = (1.0, -1.69065929318241, 0.73248077421585)
_HPF_B = (1.0, -2.0, 1.0)
_HPF_A = (1.0, -1.99004745483398, 0.99007225036621)


def k_weight(x: np.ndarray, sr: int = 48000) -> np.ndarray:
    """K-weighted copy of a mono signal.

    The coefficients above are defined at 48 kHz. A different rate is not
    resampled silently — it raises, because a weighting curve applied at the
    wrong rate is a measurement that looks right and is not.
    """
    if sr != 48000:
        raise ValueError(
            f"K-weighting coefficients are 48 kHz; got {sr}. Resample before "
            f"measuring rather than applying the curve at the wrong rate.")
    from scipy.signal import lfilter

    y = lfilter(_SHELF_B, _SHELF_A, x.astype(np.float64))
    return lfilter(_HPF_B, _HPF_A, y)


def short_term(x: np.ndarray, sr: int = 48000,
               window_s: float = WINDOW_S, hop_s: float = HOP_S
               ) -> tuple[np.ndarray, np.ndarray]:
    """(window centre times, loudness in LUFS) of a mono signal."""
    mono = x.mean(axis=1) if x.ndim > 1 else x
    k = k_weight(mono, sr)
    win, hop = int(window_s * sr), int(hop_s * sr)
    if len(k) < win:
        k = np.pad(k, (0, win - len(k)))
    n = 1 + (len(k) - win) // hop
    power = np.empty(n)
    for i in range(n):
        seg = k[i * hop:i * hop + win]
        power[i] = float(np.mean(seg * seg))
    lufs = -0.691 + 10.0 * np.log10(power + 1e-20)
    times = (np.arange(n) * hop + win / 2) / sr
    return times, lufs


#: Where to look for a one-shot's own loudness, relative to the time the spec
#: gives it. A riser ENDS on its time (it leads to the first word of a line),
#: so its window sits before it; everything else starts on its time.
EVENT_WINDOWS = {"risers": (-2.4, 0.3), "impacts": (-0.2, 2.0),
                 "stings": (-0.2, 3.0)}


def events(spec: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The one-shots the owner's rule is about, with the window each occupies.

    Ambience and room tone are not events. They are beds in their own right,
    they run for whole acts, and the playbook governs them with an offset. An
    "event" here is a riser, an impact or a sting — the three things that are
    MEANT to be noticed, and so the three whose level is a decision rather
    than a floor.
    """
    out: list[dict[str, Any]] = []
    for kind, (lo, hi) in EVENT_WINDOWS.items():
        for one in (spec or {}).get(kind, []):
            at = float(one.get("at_seconds", -1))
            if at < 0:
                continue
            out.append({"kind": kind[:-1], "at_seconds": at,
                        "from": at + lo, "to": at + hi,
                        "path": one.get("path")})
    return sorted(out, key=lambda e: e["at_seconds"])


def _layers_at(spec: dict[str, Any] | None, t: float) -> str:
    """Which CONTINUOUS layer is playing at t — ambience, and room tone."""
    if not spec:
        return "sound design"
    names = [f"{amb.get('palette')} ambience (act {amb.get('act')})"
             for amb in spec.get("ambience", [])
             if float(amb["start_seconds"]) <= t <= float(amb["end_seconds"])]
    if not names and spec.get("room_tone"):
        names = ["room tone"]
    return ", ".join(names) if names else "sound design"


def check(design: np.ndarray, bed: np.ndarray, sr: int = 48000,
          spec: dict[str, Any] | None = None
          ) -> tuple[list[str], dict[str, Any]]:
    """Problems and measurements for the two finished layers.

    `design` and `bed` are the layers as they will be summed into the mix —
    ducked, levelled, the real thing. Measuring the sources instead would
    measure a balance nobody hears.

    TWO CHECKS, BECAUSE THERE ARE TWO KINDS OF SOUND IN THE LAYER.
    --------------------------------------------------------------
    1. EVENTS — risers, impacts, stings. The owner's rule is written about
       these ("no SFX event louder than the bed at that instant"), and it is
       applied strictly: the loudest 400 ms of the design layer inside the
       event's own window, against the bed in that same window.

    2. CONTINUOUS LAYERS — ambience and room tone. These are not events, they
       run for whole acts, and the playbook governs them with an offset from
       the bed. They are still checked window by window, but only where the
       BED IS ACTUALLY THERE: a window in which the music has dropped more
       than HOLE_BELOW_MEDIAN_DB under its own median is not evidence that
       the floor is too loud, it is evidence that the bed has a hole, and a
       hole is what the bed's own dynamics gate exists to refuse. Counting it
       twice would mean the only way to pass this check was to duck the room
       tone into every dip in the music, which is audible as the room
       breathing.

       The excluded windows are counted and reported, so a bed full of holes
       cannot hide behind the exclusion.
    """
    n = min(len(design), len(bed))
    t, d = short_term(design[:n], sr)
    _, b = short_term(bed[:n], sr)
    m = min(len(d), len(b))
    t, d, b = t[:m], d[:m], b[:m]

    live_bed = b[b > FLOOR_LUFS]
    bed_median = float(np.median(live_bed)) if len(live_bed) else FLOOR_LUFS
    bed_floor = bed_median - HOLE_BELOW_MEDIAN_DB

    problems: list[str] = []
    event_rows: list[dict[str, Any]] = []
    for ev in events(spec):
        sel = (t >= ev["from"]) & (t <= ev["to"])
        if not sel.any():
            continue
        idx = np.flatnonzero(sel)
        i = idx[int(np.argmax(d[sel]))]
        excess = float(d[i] - b[i])
        row = {**ev, "at_measured_seconds": round(float(t[i]), 2),
               "design_lufs": round(float(d[i]), 1),
               "bed_lufs": round(float(b[i]), 1),
               "excess_db": round(excess, 1)}
        event_rows.append(row)
        if excess > TOLERANCE_DB:
            problems.append(
                f"the {ev['kind']} at {ev['at_seconds']:.2f}s measures "
                f"{d[i]:.1f} LUFS against the bed's {b[i]:.1f} at "
                f"{t[i]:.2f}s — {excess:+.1f} dB over it. An event louder "
                f"than the bed is an event the viewer notices as a sound "
                f"effect rather than as the film.")

    event_span = np.zeros(m, dtype=bool)
    for ev in events(spec):
        event_span |= (t >= ev["from"]) & (t <= ev["to"])

    here = (b >= bed_floor) & ((d > FLOOR_LUFS) | (b > FLOOR_LUFS))
    in_a_hole = (b < bed_floor) & (d > b + TOLERANCE_DB)
    over = here & ~event_span & (d > b + TOLERANCE_DB)
    excess = np.where(over, d - b, -np.inf)

    seen: list[float] = []
    for i in np.argsort(-excess):
        if not np.isfinite(excess[i]) or len(seen) >= 8:
            break
        if any(abs(t[i] - x) < 5.0 for x in seen):
            continue
        seen.append(float(t[i]))
        problems.append(
            f"at {t[i]:.2f}s the sound design measures {d[i]:.1f} LUFS "
            f"against the bed's {b[i]:.1f} — {excess[i]:+.1f} dB over it "
            f"({_layers_at(spec, float(t[i]))}). The floor is the room the "
            f"film is in; above the bed it is a layer of its own.")

    finite = excess[np.isfinite(excess)]
    measured = {
        "windows": int(m),
        "window_seconds": WINDOW_S,
        "bed_median_lufs_for_the_hole_test": round(bed_median, 2),
        "hole_threshold_lufs": round(bed_floor, 2),
        "hole_below_median_db": HOLE_BELOW_MEDIAN_DB,
        "events_checked": len(event_rows),
        "events_over_the_bed": sum(1 for r in event_rows
                                   if r["excess_db"] > TOLERANCE_DB),
        "worst_event": (max(event_rows, key=lambda r: r["excess_db"])
                        if event_rows else None),
        "events": event_rows,
        "continuous_windows_over_the_bed": int(over.sum()),
        "continuous_seconds_over_the_bed": round(float(over.sum()) * HOP_S, 1),
        "worst_continuous_excess_db": (round(float(finite.max()), 2)
                                       if finite.size else None),
        "worst_continuous_at_seconds": (round(float(t[int(np.argmax(excess))]), 2)
                                        if finite.size else None),
        "windows_excluded_as_a_hole_in_the_bed": int(in_a_hole.sum()),
        "seconds_excluded_as_a_hole_in_the_bed": round(float(in_a_hole.sum()) * HOP_S, 1),
        "design_median_lufs": (round(float(np.median(d[d > FLOOR_LUFS])), 2)
                               if (d > FLOOR_LUFS).any() else None),
        "bed_median_lufs": (round(float(np.median(live_bed)), 2)
                            if len(live_bed) else None),
        "tolerance_db": TOLERANCE_DB,
    }
    return problems, measured


def main() -> int:
    import soundfile as sf

    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("bed")
    ap.add_argument("--spec", default=None)
    args = ap.parse_args()

    design, sr = sf.read(args.design, dtype="float32", always_2d=True)
    bed, sr2 = sf.read(args.bed, dtype="float32", always_2d=True)
    if sr != sr2:
        raise SystemExit(f"the two layers are at different rates: {sr} and {sr2}")
    spec = None
    if args.spec:
        with open(args.spec, encoding="utf-8") as fh:
            spec = json.load(fh)

    problems, measured = check(design, bed, sr, spec)
    print(f"{measured['windows']} windows of {measured['window_seconds']}s; "
          f"sound design median {measured['design_median_lufs']} LUFS, bed "
          f"{measured['bed_median_lufs']} LUFS")
    print(f"events: {measured['events_over_the_bed']} of "
          f"{measured['events_checked']} over the bed"
          + (f", worst {measured['worst_event']['kind']} at "
             f"{measured['worst_event']['at_seconds']}s "
             f"{measured['worst_event']['excess_db']:+} dB"
             if measured["worst_event"] else ""))
    print(f"continuous layers: {measured['continuous_windows_over_the_bed']} "
          f"windows over the bed "
          f"({measured['continuous_seconds_over_the_bed']}s), worst "
          f"{measured['worst_continuous_excess_db']} dB at "
          f"{measured['worst_continuous_at_seconds']}s; "
          f"{measured['seconds_excluded_as_a_hole_in_the_bed']}s excluded as "
          f"a hole in the bed")
    for p in problems:
        print("  -", p)
    print("SFX LEVEL:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

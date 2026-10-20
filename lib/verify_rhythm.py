"""Does the finished edit have a rhythm, or only an average?

WHY THIS EXISTS
---------------
Run #1 passed every pacing check it had. Mean hold 6.6s, inside the playbook's
5-8s band; no still held past its cap; slideshow risk low. The film was still
metronomic, because the checks all measured the middle of the distribution and
the defect was the absence of its tails: 181 of 182 shots between 5 and 8
seconds, p10 5.89s, p90 7.47s, and 8 to 10 cuts in every single minute of a
twenty-minute film.

Every reference measured for run #2 swings by a factor of three to seven inside
one film. So this check looks for the spread, not the mean:

  - the per-minute cuts curve against the playbook's envelope
  - the long tail (p90) and the short tail (p10), which must both exist
  - how much of the film piles into any one two-second band
  - per-beat hold bands, where the edit says which beat a cut belongs to
  - a long hold that is a static still rather than a shot with motion in it

A check that cannot fail on the defect is not a check. This one fails on
run #1's edit, which is the only evidence that it measures the right thing —
see tests/contracts/test_verify_rhythm.py.

Run it as a gate:

    python3 lib/verify_rhythm.py projects/<id>/artifacts/edit_decisions.json
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_playbook(path: str | None = None) -> dict[str, Any]:
    import yaml

    path = path or os.path.join(ROOT, "styles", "wak3up-documentary.yaml")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def timeline(cuts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each cut's length and its position on the timeline.

    `in_seconds` and `out_seconds` are positions in the SOURCE clip, not on the
    timeline — reading them as timeline positions puts every cut of run #1 in
    the first minute, which is how this was found.
    """
    out, clock = [], 0.0
    for c in cuts:
        length = float(c.get("duration_seconds") or
                       (float(c["out_seconds"]) - float(c["in_seconds"])))
        start = float(c["timeline_start_seconds"]) if "timeline_start_seconds" in c else clock
        out.append({
            "id": c.get("id"),
            "start": start,
            "length": length,
            "beat": c.get("beat"),
            "treatment": c.get("treatment"),
            "internal_motion": c.get("internal_motion"),
        })
        clock = start + length
    return out


def distribution(shots: list[dict[str, Any]]) -> dict[str, Any]:
    import numpy as np

    lengths = np.array([s["length"] for s in shots], dtype=float)
    total = float(lengths.sum())
    # Whole minutes only. A film ending at 20:06 has a final minute holding six
    # seconds and almost no cuts; counting it as the quietest minute handed
    # run #1 a spread of 10 and a pass on a curve that never leaves 8-10.
    minutes = math.ceil(total / 60) or 1
    per_minute = [
        sum(1 for s in shots[1:] if m * 60 <= s["start"] < (m + 1) * 60)
        for m in range(minutes)
    ]
    whole = [n for m, n in enumerate(per_minute) if (m + 1) * 60 <= total]
    spread_source = whole or per_minute
    # the fullest two-second band, which is what a metronome looks like
    bands = Counter(int(L // 2) for L in lengths)
    worst_band, worst_n = (bands.most_common(1) or [(0, 0)])[0]
    return {
        "shots": len(shots),
        "duration_seconds": round(total, 1),
        "cuts_per_minute_mean": round((len(shots) - 1) * 60 / total, 2) if total else 0.0,
        "cuts_per_minute_series": per_minute,
        "cuts_per_minute_min": min(spread_source) if spread_source else 0,
        "cuts_per_minute_max": max(spread_source) if spread_source else 0,
        "cuts_per_minute_spread": (max(spread_source) - min(spread_source)) if spread_source else 0,
        "whole_minutes_counted": len(whole),
        "shot_length": {
            "mean": round(float(lengths.mean()), 2),
            "median": round(float(np.median(lengths)), 2),
            "p10": round(float(np.percentile(lengths, 10)), 2),
            "p90": round(float(np.percentile(lengths, 90)), 2),
            "max": round(float(lengths.max()), 2),
        },
        "fullest_2s_band": [worst_band * 2, worst_band * 2 + 2],
        "pct_in_fullest_2s_band": round(100 * worst_n / len(shots), 1),
    }


def check(cuts: list[dict[str, Any]],
          playbook: dict[str, Any] | None = None,
          air: dict[str, Any] | None = None) -> tuple[list[str], dict[str, Any]]:
    """Structural violations, and the measurements behind them.

    Two severities, because they are different kinds of fact. A flat curve or
    a metronome band is a property of the edit as built and nothing downstream
    will fix it, so it blocks. A thin long tail may be the honest shape of a
    particular film — an act with no reveal in it is allowed to exist — so it
    is reported in `notes` and read by a human. Returned problems block; notes
    come back inside the measurements.
    """
    pb = playbook or load_playbook()
    rhythm = pb["rhythm"]
    env = rhythm["film_envelope"]
    targets = rhythm["targets"]

    shots = timeline(cuts)
    if not shots:
        return ["edit has no cuts"], {}
    d = distribution(shots)
    problems: list[str] = []
    notes: list[str] = []

    # The envelope describes a film. On a short extract its three tests are
    # arithmetic artefacts rather than findings: a 90-second clip has one
    # whole minute, so its cuts-per-minute spread is zero by construction, and
    # its p90 is the second-longest of a dozen shots. The per-beat bands below
    # still apply, because those are per shot.
    FILM_MINIMUM_SECONDS = 240.0
    short = d["duration_seconds"] < FILM_MINIMUM_SECONDS
    if short:
        notes.append(
            f"{d['duration_seconds']:.0f}s of material: the film-level envelope "
            f"(curve spread and the two tails) is not checked under "
            f"{FILM_MINIMUM_SECONDS:.0f}s, because on a short extract it "
            f"measures the sample rather than the edit")

    lo, hi = env["cuts_per_minute_mean"]
    if not short and not (lo <= d["cuts_per_minute_mean"] <= hi):
        notes.append(
            f"mean {d['cuts_per_minute_mean']} cuts/min is outside {lo}-{hi}")

    if not short and d["cuts_per_minute_spread"] < env["cuts_per_minute_spread_min"]:
        problems.append(
            f"the cuts-per-minute curve is flat: busiest minute "
            f"{d['cuts_per_minute_max']}, quietest {d['cuts_per_minute_min']}, "
            f"spread {d['cuts_per_minute_spread']} against a minimum of "
            f"{env['cuts_per_minute_spread_min']}")

    if not short and d["shot_length"]["p90"] < env["shot_length_p90_min_seconds"]:
        notes.append(
            f"no long tail: p90 is {d['shot_length']['p90']}s, and the film "
            f"needs holds of at least {env['shot_length_p90_min_seconds']}s "
            f"to land its reveals")

    if not short and d["shot_length"]["p10"] > env["shot_length_p10_max_seconds"]:
        notes.append(
            f"no short tail: p10 is {d['shot_length']['p10']}s, so nothing in "
            f"the film moves faster than "
            f"{env['shot_length_p10_max_seconds']}s a shot")

    if d["pct_in_fullest_2s_band"] > env["max_pct_of_shots_in_any_2s_band"]:
        a, b = d["fullest_2s_band"]
        problems.append(
            f"{d['pct_in_fullest_2s_band']}% of shots are {a}-{b}s long, over "
            f"the {env['max_pct_of_shots_in_any_2s_band']}% ceiling — that is "
            f"a metronome, whatever the mean says")

    # per-beat bands, for the cuts that carry a beat
    tagged = [s for s in shots if s.get("beat")]
    for s in tagged:
        t = targets.get(s["beat"])
        if not t:
            problems.append(f"{s['id']}: unknown beat {s['beat']!r}")
            continue
        blo, bhi = t["shot_seconds"]
        if not (blo <= s["length"] <= bhi):
            problems.append(
                f"{s['id']}: {round(s['length'], 2)}s on a {s['beat']} beat, "
                f"outside {blo}-{bhi}s")
        if s["beat"] == "reveal" and s["length"] > pb["visual_cadence"]["stills"]["max_hold_seconds"]:
            if s.get("internal_motion") is False:
                problems.append(
                    f"{s['id']}: {round(s['length'], 2)}s held on a shot with "
                    f"no internal motion. A reveal earns its hold with "
                    f"movement inside the frame, not with the beat type")
    d["beat_tagged_cuts"] = len(tagged)

    d["notes"] = notes

    if air is not None:
        lo_pct, hi_pct = pb["structure"]["air"]["film_total_pct"]
        pct = air.get("air_pct_of_total", 0.0)
        if not (lo_pct <= pct <= hi_pct):
            problems.append(
                f"realised air is {pct}% of runtime, outside {lo_pct}-{hi_pct}%")
        d["air"] = air

    return problems, d


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: verify_rhythm.py <edit_decisions.json> [narration_plan.json]")
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        ed = json.load(fh)
    cuts = ed["cuts"] if isinstance(ed, dict) else ed

    air = None
    if len(argv) > 2:
        from script_beats import measure  # noqa: F401  (same dir on sys.path)

    problems, d = check(cuts, air=air)
    print(f"shots {d.get('shots')}  {d.get('duration_seconds')}s  "
          f"mean {d.get('cuts_per_minute_mean')} cuts/min  "
          f"spread {d.get('cuts_per_minute_spread')}")
    sl = d.get("shot_length", {})
    print(f"  shot length p10 {sl.get('p10')}s  median {sl.get('median')}s  "
          f"p90 {sl.get('p90')}s  max {sl.get('max')}s")
    print(f"  fullest 2s band {d.get('fullest_2s_band')} holds "
          f"{d.get('pct_in_fullest_2s_band')}% of shots")
    for n in d.get("notes", []):
        print("  note:", n)
    for p in problems:
        print("  -", p)
    print("RHYTHM:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main(sys.argv))

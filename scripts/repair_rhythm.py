#!/usr/bin/env python3
"""Spread an edit's holds across its beat bands, by moving boundaries.

WHY THIS IS A SCRIPT AND NOT SOMETHING A STAGE WRITES
-----------------------------------------------------
`lib/verify_rhythm.py` fails an edit that is a metronome. It is a good gate
and it says nothing about what to do next, so each edit stage that tripped
it wrote its own repair — in the project directory, by hand, differently
every time. docs/STAGE_CONTRACT.md allows that once and says what it means
when it happens twice: "forty-eight edits to one is a program being
developed, and a stage is not the place to develop a program. Promote it to
scripts/ in a commit, later, with a human looking." This is that promotion.

THE ONE INVARIANT: A BOUNDARY MOVES, A FILM DOES NOT GET LONGER
---------------------------------------------------------------
Every move here is PAIRWISE with a neighbour — one cut takes frames the
next one gives up — which is the same rule `lib/build_render_props.py`
applies to audio leads, and for the same reason: the film's length is the
narration's length, and a repair that changed it would desynchronise every
cut after the one it fixed. Total duration is invariant by construction,
not by a correction afterwards, and the script asserts it before writing.

A boundary is also an editorial decision — the cut was placed on a meaning
change — so no boundary may move more than `--max-shift` (default 2.0s)
from where the edit put it, and every move is printed.

WHAT IT REPAIRS, IN ORDER
-------------------------
1. BEAT BANDS. A cut tagged `transition` that runs 9s is outside its band;
   it is pruned back into it, and the frames go to its neighbour.
2. THE LONG TAIL. The playbook wants p90 >= 12s, and no film #1-#6 has ever
   had one: p90 was 9.7 to 10.0 on all six. Holds are grown on the cuts
   that can carry them — a reveal or a landing with movement inside the
   frame — because a long hold on a static still is the defect the gate
   calls out separately.
3. THE SHORT TAIL. p10 <= 4s, grown out of `transition` beats, which are
   the shots that are allowed to be quick.
4. THE FULLEST BAND. Over 45% of shots inside one two-second band is a
   metronome whatever the mean says, so cuts are nudged out of it into the
   bands either side.

It REFUSES to lengthen a cut whose picture is a video clip: a still can be
held for as long as you like and a clip runs out. Those cuts can still be
shortened.

    .venv/bin/python scripts/repair_rhythm.py --project <slug>
    .venv/bin/python scripts/repair_rhythm.py --project <slug> --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import verify_rhythm as VR                                      # noqa: E402

#: No shot goes below this, whatever a band says. Under a second and a half
#: the viewer registers a flash, not a shot.
MIN_SHOT_SECONDS = 1.5

#: How far a boundary may travel from where the edit put it. The cut was
#: placed on a meaning change; this is the most it can drift from the line
#: it was cut to and still be that cut.
MAX_SHIFT_SECONDS = 2.0

#: The step a nudge takes. A frame at 30fps is 0.0333s; a tenth of a second
#: is three frames and the smallest move worth printing.
STEP = 0.1

#: Beats whose shots are allowed to carry a long hold.
HOLDING_BEATS = ("reveal", "landing")

#: Beats whose shots are allowed to be quick.
QUICK_BEATS = ("transition",)

VIDEO_SUFFIXES = (".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi")


def primary(cuts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The spine. Overlays sit on top of it and have no hold of their own."""
    return [c for c in cuts if (c.get("layer") or "primary") == "primary"]


def length_of(cut: dict[str, Any]) -> float:
    if "duration_seconds" in cut:
        return float(cut["duration_seconds"])
    return float(cut["out_seconds"]) - float(cut["in_seconds"])


def set_length(cut: dict[str, Any], seconds: float) -> None:
    """Write a new hold back in the shape the cut was authored in."""
    seconds = round(seconds, 3)
    if "duration_seconds" in cut:
        cut["duration_seconds"] = seconds
    cut["out_seconds"] = round(float(cut["in_seconds"]) + seconds, 3)


def extensible(cut: dict[str, Any]) -> bool:
    """Can this cut be held longer than the edit asked?

    A still can. A video clip cannot be stretched past its own end, and
    this script has no way to measure the file, so it does not try: a cut
    whose source is a video may only be shortened.
    """
    source = str(cut.get("source") or "")
    return not source.lower().endswith(VIDEO_SUFFIXES)


def band_of(cut: dict[str, Any], targets: dict[str, Any]
            ) -> tuple[float, float] | None:
    beat = cut.get("beat")
    target = targets.get(beat) if beat else None
    if not target or "shot_seconds" not in target:
        return None
    lo, hi = target["shot_seconds"]
    return float(lo), float(hi)


def legal(cut: dict[str, Any], seconds: float, targets: dict[str, Any]
          ) -> bool:
    if seconds < MIN_SHOT_SECONDS:
        return False
    band = band_of(cut, targets)
    if band and not (band[0] <= seconds <= band[1]):
        return False
    return True


def move(cuts: list[dict[str, Any]], i: int, delta: float,
         shifted: dict[int, float], targets: dict[str, Any],
         max_shift: float) -> bool:
    """Give `delta` seconds to cut i, taken from the next cut. Pairwise.

    Returns False and changes nothing when the move would break a band, a
    floor, the shift cap, or the no-stretching-a-clip rule.
    """
    if i + 1 >= len(cuts) or delta == 0:
        return False
    a, b = cuts[i], cuts[i + 1]
    new_a, new_b = length_of(a) + delta, length_of(b) - delta
    if delta > 0 and not extensible(a):
        return False
    if delta < 0 and not extensible(b):
        return False
    if not legal(a, new_a, targets) or not legal(b, new_b, targets):
        return False
    if abs(shifted.get(i, 0.0) + delta) > max_shift + 1e-9:
        return False
    set_length(a, new_a)
    set_length(b, new_b)
    shifted[i] = shifted.get(i, 0.0) + delta
    return True


def grow(cuts: list[dict[str, Any]], index: int, wanted: float,
         shifted: dict[int, float], targets: dict[str, Any],
         max_shift: float) -> float:
    """Lengthen cut `index` by up to `wanted`, from either neighbour."""
    got = 0.0
    for boundary, sign in ((index, 1.0), (index - 1, -1.0)):
        if boundary < 0:
            continue
        while got < wanted - 1e-9:
            step = min(STEP, wanted - got)
            if not move(cuts, boundary, step * sign if sign > 0 else -step,
                        shifted, targets, max_shift):
                break
            got += step
    return got


def shrink(cuts: list[dict[str, Any]], index: int, wanted: float,
           shifted: dict[int, float], targets: dict[str, Any],
           max_shift: float) -> float:
    gave = 0.0
    for boundary, sign in ((index, -1.0), (index - 1, 1.0)):
        if boundary < 0:
            continue
        while gave < wanted - 1e-9:
            step = min(STEP, wanted - gave)
            if not move(cuts, boundary, -step if sign < 0 else step,
                        shifted, targets, max_shift):
                break
            gave += step
    return gave


def repair(cuts: list[dict[str, Any]], playbook: dict[str, Any],
           max_shift: float = MAX_SHIFT_SECONDS) -> list[str]:
    """Spread the holds. Mutates `cuts`. Returns one line per move made."""
    # The same two blocks `verify_rhythm.check` reads, from the same
    # playbook: a repair aimed at different numbers than the gate is a
    # repair that argues with it.
    rhythm = playbook["rhythm"]
    targets = rhythm["targets"]
    env = rhythm["film_envelope"]
    spine = primary(cuts)
    before = {id(c): length_of(c) for c in spine}
    shifted: dict[int, float] = {}
    notes: list[str] = []

    # 1. BEAT BANDS -------------------------------------------------------
    for i, cut in enumerate(spine):
        band = band_of(cut, targets)
        if not band:
            continue
        have = length_of(cut)
        if have > band[1]:
            shrink(spine, i, have - band[1], shifted, targets, max_shift)
        elif have < band[0]:
            grow(spine, i, band[0] - have, shifted, targets, max_shift)

    # 2. THE LONG TAIL ----------------------------------------------------
    want_p90 = float(env.get("shot_length_p90_min_seconds", 12))
    holders = [i for i, c in enumerate(spine)
               if c.get("beat") in HOLDING_BEATS
               and c.get("internal_motion") is not False
               and extensible(c)]
    if not holders:
        # An edit with no beat tags at all — film #1 is one. The gate still
        # wants a long tail, so the holds go on the shots that are already
        # longest and can be extended: the nearest thing to an editorial
        # choice available without one.
        holders = [i for i, c in enumerate(spine)
                   if extensible(c) and c.get("internal_motion") is not False]
    holders.sort(key=lambda i: -length_of(spine[i]))
    need = max(0, int(round(0.1 * len(spine))) + 1)
    for i in holders[:need]:
        if length_of(spine[i]) < want_p90:
            grow(spine, i, want_p90 - length_of(spine[i]), shifted, targets,
                 max_shift)

    # 3. THE SHORT TAIL ---------------------------------------------------
    want_p10 = float(env.get("shot_length_p10_max_seconds", 4))
    quick = [i for i, c in enumerate(spine) if c.get("beat") in QUICK_BEATS]
    quick.sort(key=lambda i: length_of(spine[i]))
    for i in quick[:need]:
        if length_of(spine[i]) > want_p10:
            shrink(spine, i, length_of(spine[i]) - want_p10, shifted,
                   targets, max_shift)

    # 4. THE FULLEST BAND -------------------------------------------------
    ceiling = float(env.get("max_pct_of_shots_in_any_2s_band", 45))
    for _ in range(40):
        d = VR.distribution(VR.timeline(spine))
        if d["pct_in_fullest_2s_band"] <= ceiling:
            break
        lo, hi = d["fullest_2s_band"]
        inside = [i for i, c in enumerate(spine)
                  if lo <= length_of(c) < hi]
        moved = False
        for n, i in enumerate(inside):
            want = (hi - length_of(spine[i]) + STEP) if n % 2 == 0 \
                else (length_of(spine[i]) - lo + STEP)
            ok = (grow(spine, i, want, shifted, targets, max_shift) if n % 2 == 0
                  else shrink(spine, i, want, shifted, targets, max_shift))
            if ok > 0:
                moved = True
            if len(inside) - (n + 1) <= 0:
                break
        if not moved:
            break

    # 5. WHAT A BOUNDARY NUDGE CANNOT DO ----------------------------------
    #
    # The cuts-per-minute curve is not reachable from here, and saying so is
    # more useful than trying. Flow across any one boundary is capped, so a
    # minute cannot gain cuts from its neighbours: a busy minute is a minute
    # that was PLANNED busy. Film #1 reads spread 2 against a minimum of 4
    # before and after, and the honest answer is that its edit has no
    # dynamics to recover, not that the repair failed.
    d = VR.distribution(VR.timeline(spine))
    floor = float(env.get("cuts_per_minute_spread_min", 4))
    if d["cuts_per_minute_spread"] < floor:
        notes.append(
            f"NOT REPAIRABLE HERE: cuts-per-minute spread is "
            f"{d['cuts_per_minute_spread']} against a minimum of "
            f"{floor:g}. Moving boundaries cannot move a cut from one "
            f"minute into another — the flow across each boundary is "
            f"capped at {max_shift}s — so this is a planning result and "
            f"has to come from the scene plan.")

    for cut in spine:
        was, now = before[id(cut)], length_of(cut)
        if abs(now - was) >= STEP / 2:
            notes.append(f"{cut.get('id')}: {was:.2f}s -> {now:.2f}s "
                         f"({now - was:+.2f}s, {cut.get('beat')})")
    return notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--artifacts", default=None)
    ap.add_argument("--apply", action="store_true",
                    help="write the repaired edit back")
    ap.add_argument("--max-shift", type=float, default=MAX_SHIFT_SECONDS)
    args = ap.parse_args(argv)

    art = (Path(args.artifacts) if args.artifacts
           else ROOT / "projects" / args.project / "artifacts")
    path = art / "edit_decisions.json"
    if not path.exists():
        print(f"no edit at {path}")
        return 1
    ed = json.loads(path.read_text(encoding="utf-8"))
    cuts = ed.get("cuts") or []
    playbook = VR.load_playbook()

    was_problems, was_d = VR.check(cuts, playbook)
    total_before = sum(length_of(c) for c in primary(cuts))

    notes = repair(cuts, playbook, args.max_shift)

    total_after = sum(length_of(c) for c in primary(cuts))
    drift = abs(total_after - total_before)
    now_problems, now_d = VR.check(cuts, playbook)

    print(f"{args.project}: {len([n for n in notes if not n.startswith('NOT')])} cut(s) moved. Each BOUNDARY moves "
          f"at most {args.max_shift}s; a cut lies between two, so its hold "
          f"can change by up to {2 * args.max_shift}s.")
    moves = [n for n in notes if not n.startswith("NOT REPAIRABLE")]
    blocked = [n for n in notes if n.startswith("NOT REPAIRABLE")]
    for note in moves[:60]:
        print(f"  {note}")
    if len(moves) > 60:
        print(f"  ... and {len(moves) - 60} more")
    wl, nl = was_d["shot_length"], now_d["shot_length"]
    print(f"  p10 {wl['p10']}s -> {nl['p10']}s"
          f"   p90 {wl['p90']}s -> {nl['p90']}s"
          f"   max {wl['max']}s -> {nl['max']}s")
    print(f"  fullest band {was_d['pct_in_fullest_2s_band']}% -> "
          f"{now_d['pct_in_fullest_2s_band']}%"
          f"   cuts/min spread {was_d['cuts_per_minute_spread']} -> "
          f"{now_d['cuts_per_minute_spread']}")
    for note in blocked:
        print(f"  {note}")
    print(f"  problems {len(was_problems)} -> {len(now_problems)}")
    for problem in now_problems[:10]:
        print(f"    still: {problem}")

    # THE INVARIANT, checked before anything is written. A rhythm repair
    # that changed the running time would move every cut after it off the
    # narration it was cut to.
    if drift > 0.002:
        print(f"REFUSED: the film's length moved by {drift:.3f}s. Every "
              f"move here is pairwise, so this is a bug in the repair and "
              f"not something to write out.")
        return 2

    if not args.apply:
        print("  (nothing written — pass --apply)")
        return 0
    path.write_text(json.dumps(ed, indent=1, ensure_ascii=True) + "\n")
    print(f"written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Which way the camera moves, and why.

Run #1 gave every still the same push. The playbook's own treatment list has
three entries — parallax, slow push, drift across an oversized frame — and one
of them was used for 182 shots, so the film's only camera idea was "in", at one
speed, for twenty minutes.

The rule set here is small and comes from what the beat is doing:

  reveal      PUSH   — the frame closes on the thing being revealed
  exposition  PULL   — context arrives as the frame opens
  landing     LOCK   — the picture stops with the voice; the air is held, not travelled
  transition  DRIFT  — lateral movement carries the eye between subjects

Two rules are about consecutive shots rather than single ones:

  - **Direction is consistent across a run of stills.** Two stills in a row
    that drift opposite ways read as a mistake; the eye is thrown back where
    it came from. A run keeps its direction until the beat changes.
  - **One speed ramp per act, into a hard cut.** A ramp is the only place the
    move's speed changes inside a shot, and spending more than one per act
    turns a documentary into a trailer.

`assign` writes the choice and its reason onto each cut; `to_props` turns it
into the numbers AnnotatedStill actually animates; `check` is the gate.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MOVES = ("push", "pull", "drift", "lock")

#: Beat -> move. The whole table, deliberately four rows long.
BY_BEAT = {
    "reveal": "push",
    "exposition": "pull",
    "landing": "lock",
    "transition": "drift",
}

#: Scale or offset applied per second of shot, as a fraction. The playbook caps
#: a push at 4% of scale per second; a drift is slower still because lateral
#: movement reads faster than a push at the same number.
SPEED_PCT_PER_SECOND = {"push": 2.4, "pull": 2.0, "drift": 1.2, "lock": 0.0}


def load_playbook(path: str | None = None) -> dict[str, Any]:
    import yaml

    path = path or os.path.join(ROOT, "styles", "wak3up-documentary.yaml")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def mood_choice(beat: str, register: str | None, asset_class: str | None,
                playbook: dict[str, Any]) -> dict[str, Any] | None:
    """The (beat x register) row, with the asset's own veto applied.

    The beat says what the paragraph is doing; the register says how it
    sounds. Two reveals in one film can be awe and dread, and giving both the
    same push at the same speed is how run #1 ended up with one gesture for
    182 shots.

    The asset overrules the table in exactly one direction: a push into a
    DENSE frame becomes a lock, because the frame is already full and the move
    reads as a zoom on a photograph rather than an approach to a subject.
    """
    mood = (playbook.get("motion", {}) or {}).get("mood") or {}
    table = mood.get("table") or {}
    if not register:
        return None
    row = table.get(f"{beat}.{register}")
    if not row:
        return None
    row = dict(row)
    row["vetoed_by_asset"] = False
    if (row["move"] == "push"
            and asset_class in set(mood.get("never_push_into") or [])):
        row["move"] = "lock"
        row["speed"] = 0.0
        row["vetoed_by_asset"] = True
    return row


def assign(cuts: list[dict[str, Any]], playbook: dict[str, Any] | None = None
           ) -> list[dict[str, Any]]:
    """Give every cut a camera move and the reason for it.

    Returns the same list, with `camera` filled in where it was absent. An
    existing `camera` is left alone — a move chosen by hand outranks the table.

    A cut carrying a `register` is read from the mood table; one without falls
    back to the beat alone, which is what run #1's material has.
    """
    pb = playbook or load_playbook()
    cap = float(pb["motion"].get("max_push_pct_per_second", 4.0))

    run_direction = "left"
    prev_move: str | None = None
    ramp_used_in_act: set[Any] = set()

    for i, cut in enumerate(cuts):
        if cut.get("camera"):
            prev_move = cut["camera"].get("move")
            continue
        beat = cut.get("beat") or "exposition"

        row = mood_choice(beat, cut.get("register"), cut.get("asset_class"), pb)
        if row:
            camera = {
                "move": row["move"],
                "speed_pct_per_second": round(min(float(row["speed"]), cap), 2),
                "direction": "none",
                "reason": (f"{beat} in a {cut['register']} register"
                           + (f"; the asset is {cut.get('asset_class')}, so the "
                              f"push became a lock — a push into a full frame "
                              f"reads as a zoom"
                              if row["vetoed_by_asset"] else "")),
            }
            if row["move"] == "drift":
                if prev_move != "drift":
                    run_direction = "left" if run_direction == "right" else "right"
                camera["direction"] = run_direction
                camera["reason"] += f" ({run_direction}, held across the run)"
            cut["camera"] = camera
            cut.setdefault("hold_multiplier", row["hold"])
            cut.setdefault("music_rise_allowed", row["rise"])
            cut.setdefault("transition_family", row["transition"])
            prev_move = row["move"]
            continue

        move = BY_BEAT.get(beat, "pull")
        speed = min(SPEED_PCT_PER_SECOND[move], cap)

        reason = {
            "push": "reveal: the frame closes on what is being revealed",
            "pull": "exposition: context arrives as the frame opens",
            "lock": "landing: the picture stops with the voice and holds the air",
            "drift": "transition: lateral movement carries the eye to the next subject",
        }[move]

        direction = "none"
        if move == "drift":
            # A run of drifts keeps its direction; the eye is not thrown back.
            if prev_move != "drift":
                run_direction = "left" if run_direction == "right" else "right"
            direction = run_direction
            reason += f" ({direction}, held across the run)"

        camera = {"move": move, "speed_pct_per_second": round(speed, 2),
                  "direction": direction, "reason": reason}

        # One ramp per act, and only into a hard cut.
        act = cut.get("act") or cut.get("actNumber")
        nxt = cuts[i + 1] if i + 1 < len(cuts) else None
        hard_cut_next = not (nxt or {}).get("transition_in") or \
            (nxt or {}).get("transition_in") == "cut"
        if (act is not None and act not in ramp_used_in_act
                and beat == "reveal" and hard_cut_next):
            camera["ramp"] = True
            camera["reason"] += "; the act's one speed ramp, into a hard cut"
            ramp_used_in_act.add(act)

        cut["camera"] = camera
        prev_move = move
    return cuts


def to_props(cut: dict[str, Any]) -> dict[str, Any]:
    """The numbers AnnotatedStill animates, from the camera intent.

    A push and a pull are the same interpolation with its ends swapped, which
    is why they share a speed table. A lock still carries parallax=false
    rather than from == to, so the renderer does no work for a shot that does
    not move.
    """
    cam = cut.get("camera") or {}
    move = cam.get("move", "pull")
    length = float(cut.get("out_seconds", 0)) - float(cut.get("in_seconds", 0))
    travel = (cam.get("speed_pct_per_second", 0.0) / 100.0) * max(length, 0.0)

    if move == "lock":
        return {"parallax": False}
    if move == "push":
        return {"parallax": True, "parallaxFrom": 1.0,
                "parallaxTo": round(1.0 + travel, 4)}
    if move == "pull":
        return {"parallax": True, "parallaxFrom": round(1.0 + travel, 4),
                "parallaxTo": 1.0}
    sign = -1.0 if cam.get("direction") == "left" else 1.0
    half = round(travel / 2, 4)
    return {"parallax": True, "parallaxFrom": 1.0, "parallaxTo": 1.0,
            "driftFrom": -sign * half, "driftTo": sign * half}


def check(cuts: list[dict[str, Any]], playbook: dict[str, Any] | None = None
          ) -> list[str]:
    """Problems with the camera intent across a whole edit."""
    pb = playbook or load_playbook()
    cap = float(pb["motion"].get("max_push_pct_per_second", 4.0))
    problems: list[str] = []

    untagged = [c.get("id") for c in cuts if not c.get("camera")]
    if untagged:
        problems.append(
            f"{len(untagged)} cuts carry no camera intent "
            f"(first: {untagged[0]}) — run #1 gave every still the same push "
            f"because nothing recorded a choice")

    ramps_per_act: dict[Any, int] = {}
    prev_drift_dir: str | None = None
    prev_move: str | None = None

    for cut in cuts:
        cam = cut.get("camera")
        if not cam:
            continue
        cid = cut.get("id")
        if cam.get("move") not in MOVES:
            problems.append(f"{cid}: unknown move {cam.get('move')!r}")
        if not cam.get("reason"):
            problems.append(f"{cid}: a move with no reason")
        if float(cam.get("speed_pct_per_second", 0)) > cap:
            problems.append(
                f"{cid}: {cam['speed_pct_per_second']}%/s is over the "
                f"playbook's {cap}%/s ceiling")
        if cam.get("ramp"):
            act = cut.get("act") or cut.get("actNumber")
            ramps_per_act[act] = ramps_per_act.get(act, 0) + 1
        if cam.get("move") == "drift":
            if prev_move == "drift" and cam.get("direction") != prev_drift_dir:
                problems.append(
                    f"{cid}: drifts {cam.get('direction')} straight after a "
                    f"drift {prev_drift_dir} — a run of stills keeps one "
                    f"direction or the eye is thrown back")
            prev_drift_dir = cam.get("direction")
        prev_move = cam.get("move")

    for act, n in ramps_per_act.items():
        if n > 1:
            problems.append(
                f"act {act}: {n} speed ramps — one per act, or it is a trailer")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: camera_intent.py <edit_decisions.json>")
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        ed = json.load(fh)
    cuts = ed["cuts"] if isinstance(ed, dict) else ed
    problems = check(cuts)
    moves: dict[str, int] = {}
    for c in cuts:
        m = (c.get("camera") or {}).get("move", "none")
        moves[m] = moves.get(m, 0) + 1
    print("camera:", ", ".join(f"{k} {v}" for k, v in sorted(moves.items())))
    for p in problems[:20]:
        print("  -", p)
    print("CAMERA INTENT:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

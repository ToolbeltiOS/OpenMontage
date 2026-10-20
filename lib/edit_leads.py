"""J-cuts and L-cuts: letting sound and picture change at different moments.

Run #1 cut picture and sound together 182 times. Every boundary was square,
which is what makes an edit feel like a slideshow even when the holds vary —
the viewer is told twice, at the same instant, that something has changed.

In this pipeline the narration is one continuous track and the picture is cut
against it, so a lead is not two timelines drifting: it is the picture
boundary moving relative to the narration boundary it was placed on.

    audio_lead_frames > 0   the next scene's AUDIO leads its picture.
                            The picture cut happens LATER, so the previous
                            image is still up while the new section is already
                            speaking. This is a J-cut, and it is what carries
                            a viewer over an act boundary.

    audio_lead_frames < 0   the PICTURE leads the narration. The cut happens
                            EARLIER, so the new image is up before the
                            sentence that explains it. This is an L-cut, and
                            it is how an exposition cut stops announcing
                            itself.

The budget comes from the brief: 12-18 frames at act boundaries and reveals,
and no more than 10 frames of picture lead at exposition cuts. Both are small —
at 30fps, 12 frames is 0.4s. The effect is meant to be felt and not seen.

A lead moves a boundary; it never changes the film's length. The frames one
cut gains, its neighbour loses.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

J_CUT_FRAMES = (12, 18)      # audio leads picture, at act boundaries and reveals
L_CUT_MAX_FRAMES = 10        # picture leads narration, at exposition cuts


def load_playbook(path: str | None = None) -> dict[str, Any]:
    import yaml

    path = path or os.path.join(ROOT, "styles", "wak3up-documentary.yaml")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def assign(cuts: list[dict[str, Any]], fps: int = 30) -> list[dict[str, Any]]:
    """Choose a lead for every boundary that earns one.

    Boundaries that get a J-cut: an act boundary, and the cut into a reveal.
    Boundaries that may get an L-cut: an ordinary exposition cut, and only
    every third one — a lead on every cut is a style, and this is punctuation.

    A landing never gets either. The picture is holding through written air;
    moving its boundary is exactly the cut the air was written to avoid.
    """
    lo, hi = J_CUT_FRAMES
    mid = (lo + hi) // 2
    exposition_seen = 0

    for i, cut in enumerate(cuts):
        if i == 0 or cut.get("audio_lead_frames") is not None:
            continue
        beat = cut.get("beat") or "exposition"
        prev_act = (cuts[i - 1].get("act") or cuts[i - 1].get("actNumber"))
        act = cut.get("act") or cut.get("actNumber")
        at_boundary = act is not None and prev_act is not None and act != prev_act

        if at_boundary:
            cut["audio_lead_frames"] = hi
            cut["lead_reason"] = (
                "act boundary: the next act is already speaking while the last "
                "image of the previous one is still up")
        elif beat == "reveal":
            cut["audio_lead_frames"] = mid
            cut["lead_reason"] = (
                "reveal: the sentence that turns the act starts before the "
                "picture does, so the image lands on a line already running")
        elif beat == "landing":
            cut["audio_lead_frames"] = 0
            cut["lead_reason"] = (
                "landing: the picture holds through the written air, so its "
                "boundary does not move")
        elif beat == "exposition":
            exposition_seen += 1
            if exposition_seen % 3 == 0:
                cut["audio_lead_frames"] = -6
                cut["lead_reason"] = (
                    "exposition: the picture arrives before the sentence that "
                    "explains it, so the cut stops announcing itself")
            else:
                cut["audio_lead_frames"] = 0
                cut["lead_reason"] = "straight cut"
        else:
            cut["audio_lead_frames"] = 0
            cut["lead_reason"] = "straight cut"
    return cuts


def apply_leads(cuts: list[dict[str, Any]], fps: int = 30) -> dict[str, Any]:
    """Move each boundary by its lead, in place, preserving total length.

    Expects cuts already laid out back to back with absolute `in_seconds` and
    `out_seconds`. The frames a cut gains are taken from its predecessor, so
    the film does not grow — a lead that lengthened the timeline would push
    every later cut off the narration it was placed against.
    """
    applied, skipped = 0, 0
    for i in range(1, len(cuts)):
        lead = int(cuts[i].get("audio_lead_frames") or 0)
        if lead == 0:
            continue
        shift = lead / fps
        prev, cur = cuts[i - 1], cuts[i]
        prev_len = float(prev["out_seconds"]) - float(prev["in_seconds"])
        cur_len = float(cur["out_seconds"]) - float(cur["in_seconds"])
        # Never shrink a neighbour below a second; a lead is punctuation and
        # must not eat a shot.
        if prev_len + shift < 1.0 or cur_len - shift < 1.0:
            cuts[i]["lead_skipped"] = (
                f"would leave a shot under 1s ({prev_len:.2f}s / {cur_len:.2f}s)")
            skipped += 1
            continue
        boundary = round(float(cur["in_seconds"]) + shift, 3)
        prev["out_seconds"] = boundary
        cur["in_seconds"] = boundary
        applied += 1
    return {"applied": applied, "skipped": skipped, "fps": fps}


def check(cuts: list[dict[str, Any]], fps: int = 30) -> list[str]:
    """Problems with the leads across an edit."""
    lo, hi = J_CUT_FRAMES
    problems: list[str] = []
    for cut in cuts:
        lead = cut.get("audio_lead_frames")
        if lead is None:
            continue
        cid = cut.get("id")
        if lead != 0 and not cut.get("lead_reason"):
            problems.append(f"{cid}: a lead of {lead} frames with no reason")
        if lead > 0 and not (lo <= lead <= hi):
            problems.append(
                f"{cid}: audio leads by {lead} frames, outside the {lo}-{hi} "
                f"budget for a J-cut")
        if lead < 0 and abs(lead) > L_CUT_MAX_FRAMES:
            problems.append(
                f"{cid}: picture leads by {abs(lead)} frames, over the "
                f"{L_CUT_MAX_FRAMES}-frame ceiling for an exposition cut")
        if lead != 0 and (cut.get("beat") == "landing"):
            problems.append(
                f"{cid}: a landing holds through its air — its boundary does "
                f"not move")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: edit_leads.py <edit_decisions.json>")
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        ed = json.load(fh)
    cuts = ed["cuts"] if isinstance(ed, dict) else ed
    j = sum(1 for c in cuts if (c.get("audio_lead_frames") or 0) > 0)
    l = sum(1 for c in cuts if (c.get("audio_lead_frames") or 0) < 0)
    print(f"leads: {j} J-cuts, {l} L-cuts, {len(cuts) - j - l} square")
    problems = check(cuts)
    for p in problems[:20]:
        print("  -", p)
    print("EDIT LEADS:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

#!/usr/bin/env python3
"""Assemble the 90-second act 2 demo through run #2's rules.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
It is a demonstration cut, not a re-edit of run #1. It takes the same shots,
in the same order, from the same assets, and re-times them under the new
rules so the difference IS the rules:

  - the hold comes from the beat, not from one cadence;
  - the camera move comes from the beat;
  - boundaries lead or lag by the J/L budget;
  - the grade is act 2's;
  - captions are off, because this is a demo.

The beat assignment below is the one editorial judgement in the file. Run #2's
script will carry its own `[beat: ...]` markers and the planner will read
those; here they are written out, because run #1's script has none and
inventing markers in a published artifact would be worse than stating the
call in the place that uses it.

    python scripts/build_demo_cut.py --project they-said-it-couldnt-be-built
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

FPS = 30
MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm"}

#: The window: the moai-walking passage, from the quarry to the objection.
WINDOW = (306.67, 397.25)

#: scene index -> (beat, seconds). One reveal, the gait experiment, which is
#: the paragraph that turns the act; a landing held through the silence after
#: it; a burst of transitions opening the passage; exposition for the rest.
PLAN = [
    ("S 049", "transition", 2.6),
    ("S 050", "transition", 2.4),
    ("S 051", "transition", 2.8),
    ("S 052", "exposition", 8.0),
    ("S 053", "exposition", 7.0),
    ("S 054", "reveal", 16.0),     # the gait: a schematic with timed reveals
    ("S 055", "landing", 6.0),
    ("S 056", "exposition", 7.5),
    ("S 057", "exposition", 9.0),
    ("S 058", "exposition", 6.5),
    ("S 059", "exposition", 8.5),
    ("S 060", "exposition", 6.5),
    ("S 061", "exposition", 7.0),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    props = json.loads((project / "artifacts" / "render_props.json").read_text())

    by_index = {}
    for cut in props["cuts"]:
        idx = str(cut.get("sceneIndex") or "").strip()
        if idx:
            by_index.setdefault(idx.split("/")[0].strip(), cut)

    cuts = []
    for scene, beat, seconds in PLAN:
        src = by_index.get(scene)
        if src is None:
            print(f"{scene}: not in render_props, skipped", file=sys.stderr)
            continue
        cut = dict(src)
        cut["beat"] = beat
        # A reveal may hold past the stills cap only with motion inside the
        # frame. The gait schematic draws itself, so it qualifies; nothing
        # else here is asked to hold that long.
        cut["internal_motion"] = cut.get("type") in {
            "schematic", "map_route", "timeline", "document_reveal",
            "scale_comparison", "texture_field",
        } or str(cut.get("source", "")).endswith(".mp4")
        cut["act"] = 2
        cut["in_seconds"] = 0.0
        cut["out_seconds"] = seconds
        cuts.append(cut)

    from camera_intent import assign as assign_camera, check as check_camera, to_props
    from edit_leads import apply_leads, assign as assign_leads, check as check_leads
    from verify_rhythm import check as check_rhythm

    assign_camera(cuts)
    assign_leads(cuts, fps=FPS)

    # Lay out back to back, then move the boundaries, exactly as
    # build_render_props does for a full film.
    t = 0.0
    for cut in cuts:
        length = cut["out_seconds"] - cut["in_seconds"]
        cut["in_seconds"] = round(t, 3)
        cut["out_seconds"] = round(t + length, 3)
        t += length
    lead_report = apply_leads(cuts, fps=FPS)

    for cut in cuts:
        for key, value in to_props(cut).items():
            cut[key] = value

    # Chrome refuses a file:// URL outside the bundle's public directory, so
    # the demo stages the shots it uses. The full film's props carry absolute
    # paths and are rendered with those files already copied in; a demo built
    # from a slice has to bring its own.
    staged = ROOT / "remotion-composer" / "public" / "demo"
    staged.mkdir(parents=True, exist_ok=True)
    copied = 0
    for cut in cuts:
        for key in ("source", "backgroundImage", "image", "before", "after"):
            src = cut.get(key)
            if not isinstance(src, str) or not src:
                continue
            # `source` on an authored scene is a citation, not a file — "Ledger
            # c06" is not a path and must not be staged as one. Only strings
            # that resolve to a real media file on disk are copied.
            if Path(src).suffix.lower() not in MEDIA_SUFFIXES:
                continue
            source_path = Path(src) if src.startswith("/") else ROOT / src
            if not source_path.exists():
                print(f"{cut.get('id')}: missing {src}", file=sys.stderr)
                continue
            dest = staged / f"{cut['id']}__{source_path.name}"
            if not dest.exists():
                dest.write_bytes(source_path.read_bytes())
                copied += 1
            cut[key] = f"demo/{dest.name}"

    out = {
        "cuts": cuts,
        "overlays": [],
        # No caption track: this is a demo and the film ships closed captions.
        "captions": [],
        "burn_in_captions": False,
        "caption_style": "documentary",
        "playbook": props.get("playbook"),
    }
    dest = Path(args.out) if args.out else project / "artifacts" / "demo_act2_props.json"
    dest.write_text(json.dumps(out, indent=1) + "\n")

    problems = check_camera(cuts) + check_leads(cuts, fps=FPS)
    rhythm_problems, measured = check_rhythm(cuts)

    print(f"{len(cuts)} cuts over {t:.2f}s -> {dest}")
    print(f"  staged {copied} assets into remotion-composer/public/demo/")
    print(f"  leads: {lead_report['applied']} applied, {lead_report['skipped']} skipped")
    print(f"  shot length p10 {measured['shot_length']['p10']}s  "
          f"median {measured['shot_length']['median']}s  "
          f"p90 {measured['shot_length']['p90']}s")
    print(f"  fullest 2s band holds {measured['pct_in_fullest_2s_band']}% of shots")
    for p in problems + rhythm_problems:
        print("  -", p)
    for n in measured.get("notes", []):
        print("  note:", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

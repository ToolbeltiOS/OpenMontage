#!/usr/bin/env python3
"""Run the parallax gate on every 2.5D cut, and demote the ones that fail.

WHY THIS IS A SEPARATE STEP FROM BUILDING THEM
----------------------------------------------
Eligibility cannot be predicted from the photograph. The obvious test —
how much relief the depth model found — was measured on 2026-11-09 and is
ANTI-CORRELATED with what it is meant to detect: Tutankhamun's burial
chamber, a room with a foreground railing and two receding walls, scored
LOWEST of 24 stills, while a photograph of a flat lantern slide on a mount
scored HIGHEST. Depth Anything V2 is a RELATIVE depth model: it normalises
per image, so the spread of its output says how much contrast it put into
its own map, not how deep the scene was.

So the design is try-then-judge rather than predict. The budget picks
candidates cheaply, this runs the gate the branch already wrote on the
RENDERED clip, and a cut that does not earn its depth plate loses it and
renders flat. A wrong guess costs one clip render — about six seconds —
and produces the cut we would have had anyway.

A DEMOTION IS NOT A FAILURE. This exits 0 unless it cannot run at all.

    scripts/verify_25d_cuts.py --project king-tut
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))


def camera_of(cut: dict):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_25d_cuts", ROOT / "scripts" / "build_25d_cuts.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder.camera_of(cut)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--props", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    props_path = Path(args.props) if args.props else (
        ROOT / "projects" / args.project / "artifacts" / "render_props.json")
    props = json.loads(props_path.read_text())
    cuts = props["cuts"]

    with_depth = [c for c in cuts if c.get("depth_clip")]
    if not with_depth:
        print(f"{args.project}: no 2.5D cuts to check")
        return 0
    print(f"{args.project}: checking {len(with_depth)} 2.5D cut(s)")
    if args.dry_run:
        return 0

    import depth_cache
    import verify_depth_parallax as gate

    kept, demoted = 0, []
    for cut in with_depth:
        image = cut.get("backgroundImage") or cut.get("source")
        path = Path(image)
        if not path.is_absolute():
            path = ROOT / path
        try:
            depth = depth_cache.ensure(path)["path"]
            move, amount, pan = camera_of(cut)
            seconds = float(cut["out_seconds"]) - float(cut["in_seconds"])
            problems, measured = gate.check(
                str(path), depth, move=move, amount=amount, pan=pan,
                seconds=seconds)
        except Exception as error:          # noqa: BLE001
            problems = [f"the gate could not run: {type(error).__name__}: {error}"]
            measured = {}
        if problems:
            # DEMOTED, not failed. The cut keeps everything else it has and
            # renders as it does today.
            cut.pop("depth_clip", None)
            cut.pop("anchor_track", None)
            demoted.append((cut["id"], problems[0]))
        else:
            kept += 1

    props_path.write_text(json.dumps(props, indent=1) + "\n")
    print(f"  {kept} kept, {len(demoted)} demoted to a flat drift")
    for cid, why in demoted:
        print(f"  {cid}: DEMOTED — {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Give a cut a 2.5D plate and the measured track its annotations need.

WHAT THIS STAGE PRODUCES, AND WHY BOTH HALVES
---------------------------------------------
For one still cut:

  1. a 2.5D clip, rendered by `scripts/render_25d.py` with the cut's
     AUTHORED camera move baked into the pixels, and
  2. an anchor track, measured by `scripts/anchor_track.py` through the same
     shader with the same state, giving every annotation anchor's position
     per frame.

The second is not optional for an annotated still. The 2D plate is moved by
a CSS transform that `AnnotatedStill` inverts in three lines to put a dot
back on its feature; DepthFlow's shader raymarches a displaced surface and
has no inverse, so the only way to know where a point of the photograph went
is to measure it. A clip without a track gives annotations that sit
somewhere plausible and wrong, which is the failure mode this whole branch
exists to remove — see `lib/depthTrack.ts`.

THE AUTHORED CAMERA IS THE INPUT, NOT A DEFAULT
-----------------------------------------------
The edit stage writes `parallaxFrom/To` and `driftFrom/To` per cut, and this
reads them. It matters more than it sounds: on easter-island 19 of 20
annotated stills carry an authored camera, including pulls and
lock-with-drift, and `AnnotatedStill`'s call site passed none of them, so
every one rendered as the default 1.0 -> 1.08 push. A cut authored as a pull
ran as a push. The clip has to carry the move the edit asked for, or the
depth plate and the 2D fallback describe different films.

    python scripts/build_25d_cuts.py --project easter-island --cuts c003
    python scripts/build_25d_cuts.py --project easter-island --all --dry-run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: The interpreter that can run DepthFlow. See `scripts/render_25d.py`.
DEPTH_PY = ROOT / ".venv-depth" / "bin" / "python"

#: ShaderFlow opens a GLFW window unless told not to, and as a subprocess
#: that segfaults with rc -11 and no message.
HEADLESS = {"WINDOW_BACKEND": "headless"}

#: A still whose content is TEXT is never given a 2.5D treatment. A depth
#: model reads a page as a surface at one distance with noise on it, and the
#: displacement turns straight lines of type into waves. The same rule keeps
#: Real-ESRGAN off these.
NEVER = ("text_bearing",)

FPS = 30
WIDTH, HEIGHT = 1920, 1080


def _env() -> dict:
    import os

    return {**os.environ, **HEADLESS}


#: The parallax offset a 2.5D drift lays over its pan.
#:
#: The pan is not a choice -- it is the distance the edit authored, and the
#: frame-travel gate holds it to 10%. This is the depth laid over it, and it
#: is a look decision of the same kind as `ISOMETRIC_TRAVEL = 0.35` was for
#: the push: chosen by watching the six candidates in
#: ~/Downloads/visual-quality/drift2, not computed.
#:
#: 0.08, the middle candidate. Measured on it, frozen-twin parallax reads
#: 3.551 on c003 and 4.160 on c027, which sits inside the band the approved
#: pushes occupy (3.54 moai row, 4.46 Tiryns wall, 5.32 Sacsayhuaman joint)
#: -- so a drift and a push carry comparable depth, which is what keeps the
#: two from reading as different films.
DRIFT_PARALLAX: float | None = 0.08


def camera_of(cut: dict) -> tuple[str, float, float]:
    """The cut's authored move, as `render_25d.py`'s move and amount.

    `parallaxFrom/To` are CSS scales and `driftFrom/To` are fractions of the
    frame width, both as the edit stage writes them.

      1.00 -> 1.08   push 0.08      a slow move in
      1.13 -> 1.00   pull 0.13      a move out, and it is authored this way
      1.00 -> 1.00   drift or lock  the zoom is doing nothing

    A drift returns BOTH: the pan is the total travel the edit authored, as
    a signed fraction of frame width, and the amount is the parallax laid
    over it. They are different quantities and the first attempt conflated
    them -- feeding the authored fraction straight into DepthFlow's `offset`
    moved c003's frame 2.0px where the 2D treatment moved it 196.
    """
    pf = cut.get("parallaxFrom")
    pt = cut.get("parallaxTo")
    df = cut.get("driftFrom") or 0.0
    dt = cut.get("driftTo") or 0.0
    zoom = (pf is not None and pt is not None and abs(pt - pf) > 1e-6)
    drift = abs(dt - df) > 1e-6

    # REFUSE RATHER THAN DROP ONE. No cut in either film authors both, so
    # there is no tested behaviour to fall back on, and silently rendering
    # half of an authored move is the class of defect this branch is about.
    if zoom and drift:
        raise SystemExit(
            f"{cut.get('id')} authors BOTH a zoom ({pf} -> {pt}) and a drift "
            f"({df} -> {dt}). render_25d.py has no combined move and this "
            f"stage will not render half of one. Add the combined move to "
            f"render_25d.py deliberately, with a parallax measurement, "
            f"before giving this cut a depth plate.")
    if zoom:
        return (("push", pt - pf, 0.0) if pt > pf
                else ("pull", pf - pt, 0.0))
    if drift:
        return ("drift", DRIFT_PARALLAX or 0.0, dt - df)
    return ("lock", 0.0, 0.0)


def eligible(cut: dict) -> str | None:
    """Why this cut cannot have a depth plate, or None if it can."""
    if cut.get("type") not in ("annotated_still", "image", None):
        return f"type {cut.get('type')}"
    if cut.get("asset_class") in NEVER:
        return f"asset_class {cut.get('asset_class')}"
    image = cut.get("backgroundImage") or cut.get("source")
    if not image:
        return "no image"
    if Path(image).suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
        return f"not a still ({Path(image).suffix})"

    # A LOCK GETS NO DEPTH PLATE. 2.5D is a camera moving through a scene,
    # and a lock has no camera move for it to move through: the clip would be
    # a static frame that cost a render, and `lib/verify_depth_parallax.py`
    # would fail it correctly, because nothing in it has any parallax.
    move, amount, pan = camera_of(cut)
    if move == "lock":
        return "authored as a lock (no move to carry parallax)"
    if move == "drift" and DRIFT_PARALLAX is None:
        return ("drift, and DRIFT_PARALLAX is not chosen yet — see "
                "~/Downloads/visual-quality/drift2")
    return None


def build_cut(cut: dict, project: str, out_dir: Path,
              dry_run: bool = False) -> dict[str, Any]:
    import lib.depth_cache as depth_cache

    cid = cut["id"]
    image = Path(cut.get("backgroundImage") or cut["source"])
    if not image.is_absolute():
        image = ROOT / image
    seconds = round(float(cut["out_seconds"]) - float(cut["in_seconds"]), 3)
    move, amount, pan = camera_of(cut)
    anchors = [(a["x"], a["y"]) for a in (cut.get("annotations") or [])]

    row: dict[str, Any] = {"cut": cid, "image": str(image), "move": move,
                           "amount": round(amount, 4), "pan": round(pan, 4),
                           "seconds": seconds, "anchors": len(anchors)}
    if dry_run:
        return row

    # The depth map is cached beside the asset and keyed by content, so this
    # is a no-op after the first call for a given photograph.
    info = depth_cache.ensure(image)
    depth = Path(info["path"])
    row["depth"] = str(depth)

    out_dir.mkdir(parents=True, exist_ok=True)
    clip = out_dir / f"{cid}.mp4"
    cmd = [str(DEPTH_PY), str(ROOT / "scripts" / "render_25d.py"),
           "--image", str(image), "--depth", str(depth), "--out", str(clip),
           "--move", move, "--amount", str(amount), "--pan", str(pan),
           "--seconds", str(seconds),
           "--fps", str(FPS), "--width", str(WIDTH), "--height", str(HEIGHT)]
    run = subprocess.run(cmd, capture_output=True, text=True, env=_env())
    if run.returncode != 0:
        row["error"] = f"render failed: {run.stderr.strip()[-300:]}"
        return row
    row["clip"] = str(clip.relative_to(ROOT))

    if anchors:
        track_out = out_dir / f"{cid}.track.json"
        cmd = [str(DEPTH_PY), str(ROOT / "scripts" / "anchor_track.py"),
               "--image", str(image), "--depth", str(depth),
               "--out", str(track_out), "--move", move,
               "--amount", str(amount), "--pan", str(pan),
               "--seconds", str(seconds),
               "--fps", str(FPS), "--width", str(WIDTH), "--height", str(HEIGHT),
               "--anchors"] + [f"{x:.4f},{y:.4f}" for x, y in anchors]
        run = subprocess.run(cmd, capture_output=True, text=True, env=_env())
        if run.returncode != 0:
            row["error"] = f"track failed: {run.stderr.strip()[-300:]}"
            return row
        row["track"] = str(track_out.relative_to(ROOT))
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--cuts", nargs="*", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--props", default=None)
    args = ap.parse_args()

    props_path = Path(args.props) if args.props else (
        ROOT / "projects" / args.project / "artifacts" / "render_props.json")
    props = json.loads(props_path.read_text())
    cuts = props["cuts"]

    wanted = set(args.cuts or [])
    rows, skipped = [], []
    for cut in cuts:
        if wanted and cut["id"] not in wanted:
            continue
        if not wanted and not args.all:
            continue
        why = eligible(cut)
        if why:
            skipped.append((cut["id"], why))
            continue
        rows.append(build_cut(cut, args.project,
                              ROOT / "projects" / args.project / "renders" / "depth",
                              args.dry_run))

    for r in rows:
        bits = (f"  {r['cut']}  {r['move']:<5} off {r['amount']:+.4f} "
                f"pan {r['pan']:+.4f}  "
                f"{r['seconds']:5.2f}s  {r['anchors']} anchor(s)")
        print(bits + ("  " + r["error"] if r.get("error") else
                      ("  -> " + r["clip"] if r.get("clip") else "")))
    for cid, why in skipped:
        print(f"  {cid}  skipped: {why}")

    if args.dry_run:
        return 0

    # WRITE THE PROPS LAST, and only for cuts that produced BOTH halves. A
    # clip without its track would make AnnotatedStill fall back to the 2D
    # inverse over a plate whose move is already baked in, which puts every
    # dot on a move that is not happening.
    wrote = 0
    for cut in cuts:
        r = next((x for x in rows if x["cut"] == cut["id"]), None)
        if not r or r.get("error") or not r.get("clip"):
            continue
        if r["anchors"] and not r.get("track"):
            continue
        cut["depth_clip"] = r["clip"]
        if r.get("track"):
            cut["anchor_track"] = json.loads((ROOT / r["track"]).read_text())
        wrote += 1
    if wrote:
        props_path.write_text(json.dumps(props, indent=1) + "\n")
    print(f"\n{wrote} cut(s) given a depth plate in {props_path.name}")
    failed = [r for r in rows if r.get("error")]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

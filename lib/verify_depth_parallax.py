#!/usr/bin/env python3
"""Is this 2.5D render actually 2.5D, or is it a zoom with a depth map?

WHY THIS GATE EXISTS
--------------------
Because the answer was no, twice, and nothing noticed.

First, DepthFlow was handed a 16-bit single-channel depth array.
`ShaderTexture` accepted it, the sampler came back as the zero texture, and
three rounds of renders — reviewed, compared side by side, and passed by a
tearing gate — were flat zooms. The tearing gate passed them *because* there
was no parallax to tear.

Second, with the depth map loading correctly, a push still had no parallax:
`steady` pins a depth plane and `zoom` scales about it, so zooming alone is a
2D zoom whatever the depth map says.

Neither failure looks like a failure. The render succeeds, the picture moves,
and it is plausible. The only thing that tells them apart from a real 2.5D
render is whether points at DIFFERENT DEPTHS move by DIFFERENT AMOUNTS, which
is the one thing a parallax render is for.

HOW IT IS MEASURED
------------------
Two measurements, because there are two failures and neither number catches
both of them.

1. FLAT TWIN. The same photograph and the same move rendered twice, once with
   the depth map and once with a map of constant depth. The mean difference
   IS the depth contribution. Zero means the map never reached the shader.

2. ANCHOR PARALLAX. Three anchors at the near, middle and far depths the
   picture has, tracked through the render by `scripts/anchor_track.py`
   (which measures the mapping rather than deriving it — the shader is a
   raymarch with no closed-form inverse). A plain zoom about the centre is
   then FITTED to their displacements and subtracted; what is left cannot be
   produced by scaling, so it is parallax.

Measured on the three approved renders and on two deliberately broken ones:

    case                      flat twin   anchor parallax   caught by
    moai row                     19.639              3.54   — pass
    tiryns wall                   6.166              4.46   — pass
    sacsayhuaman joint           16.012              5.32   — pass
    INJECT no-relief map          0.000              2.03   both
    INJECT zoom-only move        21.660              1.50   anchors only

Note the last row: a zoom-only move differs from its flat twin MORE than any
working render does. Scaling a static relief changes the picture a great deal
without near and far ever separating, so check 1 cannot see that failure and
check 2 has to.

Reproduce the second injection with OPENMONTAGE_ISOMETRIC_TRAVEL=0.0, the
test hook in `scripts/render_25d.py`. The first needs a constant depth map.

    python3 lib/verify_depth_parallax.py --image a.jpg --depth a.jpg.depth.png
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: ShaderFlow opens a GLFW window unless told not to. Run from a shell that
#: is fine; run as a SUBPROCESS it segfaults — rc -11, no message — because
#: there is no window system to attach to. Every call out to the renderer
#: carries this, or the gate reports "the renders could not be made" and the
#: reason is invisible.
HEADLESS = {"WINDOW_BACKEND": "headless"}


def _env() -> dict:
    import os

    return {**os.environ, **HEADLESS}

#: The interpreter that can run DepthFlow. See `scripts/render_25d.py`.
DEPTH_PY = ROOT / ".venv-depth" / "bin" / "python"

#: Minimum anchor parallax, in pixels, AFTER a plain zoom is fitted and
#: subtracted. Raw travel is not the measurement — see `parallax_residual`.
#:
#: TWO CHECKS, BECAUSE THERE ARE TWO FAILURES AND NEITHER MEASURE CATCHES
#: BOTH.
#:
#:   failure              flat-twin present   anchor parallax
#:   no-relief depth map             0.000              2.03
#:   zoom-only move                 21.660              1.50   <- anchors only
#:   working renders          6.2 to 19.6        3.54 to 5.32
#:
#: The flat-twin number is blind to the second failure — it reads HIGHER
#: there than on any working render. The anchors catch both. Both run.
#:
#: 2.5 px, not the 4.0 first proposed. 4.0 came from two hand-picked anchors
#: at the depth extremes under isometric 0.5; the shipping setting is 0.35
#: with anchors chosen automatically, and at 4.0 a GOOD render measures 3.54
#: and fails. 2.5 is the only floor that separates the measured bands, and it
#: separates them by 1.42x above and 1.23x below. That is THIN, and it is the
#: honest number: the gate will not survive a photograph with less depth in
#: it than these three. Widening the margin means more parallax, which is a
#: look decision at isometric 0.35 and not the gate's to make.
MIN_SPREAD_PX = 2.5

#: THE VERDICT: how much the depth map changes the picture, as a mean
#: absolute difference in 8-bit levels between the render and a twin of it
#: made with a FLAT depth map and the identical move.
#:
#: This asks the question the failures actually posed — does the depth map
#: reach the shader and change anything — rather than inferring it from three
#: points. Measured, the broken render and its flat twin differed by 0.000;
#: a working one differs by about 20. There is no band to overlap.
MIN_FLAT_DIFF = 2.0

#: How much that contribution must CHANGE between the first frame and the
#: last. Reported; it does NOT separate the two failures on its own.
#:
#: Measured, a zoom-only push reads 32.1 here — HIGHER than the good render's
#: 28.7 — because zooming a static relief changes the depth contribution
#: without near and far ever separating. The whole-frame measures cannot tell
#: "the camera moved through the scene" from "the relief got bigger".
MIN_FLAT_MOTION = 1.0

#: Anchors are kept away from the frame edge, where the measurement is
#: noisiest and where a point can leave the frame mid-hold.
EDGE_MARGIN = 0.12


def pick_anchors(depth_png: str, count: int = 3) -> list[tuple[float, float]]:
    """A near, a middle and a far point AT THE SAME DISTANCE FROM CENTRE.

    The radius is the control. A zoom moves every point in proportion to how
    far it sits from the centre of the frame, so three anchors scattered
    around the picture separate by tens of pixels with no depth involved —
    and the zoom-fit that removes it also eats part of the signal. On the
    first attempt that left a good 2.5D render measuring 4.67 px against a
    4 px floor, and two others failing at 1.82 and 3.93.

    Held at one radius, the pure-zoom prediction is IDENTICAL for all three,
    so every pixel of difference between them is depth and the measurement
    stops depending on where the anchors happened to land.

    Each is the pixel closest to its depth percentile within a thin annulus,
    preferring somewhere the depth is locally smooth — a point on a depth
    edge is ambiguous by construction and tracks badly.
    """
    import numpy as np
    from PIL import Image

    d = np.asarray(Image.open(depth_png)).astype(np.float32)
    if d.ndim == 3:
        d = d[:, :, 0]
    h, w = d.shape
    gy, gx = np.gradient(d)
    rough = np.abs(gy) + np.abs(gx)
    smooth = rough < np.percentile(rough, 40)

    # THE DEPTH EXTREMES, not a ring. Holding the anchors at one radius
    # removes the zoom confound but a thin annulus rarely contains three
    # distinct depths, and widening it brings the confound back: measured,
    # that version read 2.36, 2.55 and 0.94 px on three good renders.
    #
    # So the anchors go to the nearest and the furthest trackable points the
    # picture has, which is what makes the depth difference as large as the
    # photograph allows, and the zoom is removed by the fit instead.
    m0, m1 = int(h * EDGE_MARGIN), int(w * EDGE_MARGIN)
    inside = np.zeros_like(d, dtype=bool)
    inside[m0:h - m0, m1:w - m1] = True
    band = inside & smooth
    if band.sum() < 100:
        band = inside

    values = d[band]
    taken = np.zeros_like(d, dtype=bool)
    keep = max(int(min(h, w) * 0.05), 8)          # no two anchors adjacent
    out: list[tuple[float, float]] = []
    for pct in np.linspace(2, 98, count):
        target = np.percentile(values, pct)
        cost = np.where(band & ~taken, np.abs(d - target), 1e9)
        flat_i = int(np.argmin(cost))
        if cost.flat[flat_i] >= 1e9:
            break                                  # nowhere left to put one
        y, x = np.unravel_index(flat_i, d.shape)
        taken[max(0, y - keep):y + keep, max(0, x - keep):x + keep] = True
        out.append((x / w, y / h))
    return out


def displacement(track: dict, key: str) -> tuple[float, float]:
    """How one anchor moved, in pixels, from the first frame to the last."""
    pts = track["anchors"][key]
    if len(pts) < 2:
        return (0.0, 0.0)
    return ((pts[-1][0] - pts[0][0]) * track["width"],
            (pts[-1][1] - pts[0][1]) * track["height"])


def parallax_residual(anchors: list[tuple[float, float]],
                      moves: list[tuple[float, float]],
                      width: int, height: int) -> dict[str, Any]:
    """What is left of each anchor's travel once a plain zoom is accounted for.

    RAW TRAVEL IS NOT THE MEASUREMENT, and assuming it was let a flat render
    through. Under a zoom about the centre every point travels in proportion
    to its distance FROM that centre, so three anchors in different parts of
    the frame separate by tens of pixels with no depth involved at all.
    Measured on the zoom-only push the owner's note is about: travels of
    35.6, 49.6 and 53.7 px, a spread of 18 — on a render with no parallax.

    So the best pure-zoom-about-centre model is fitted to the three
    displacements and subtracted. A zoom moves a point along the line from
    the centre through it; parallax does not, and it is what is left over.

    The scale is fitted rather than taken from the move's own `amount`,
    because the fit does not have to be told what the move was and cannot be
    fooled by a move that is not quite the one on the label.
    """
    cx, cy = width / 2.0, height / 2.0
    radii = [((u * width) - cx, (v * height) - cy) for u, v in anchors]
    num = sum(dx * rx + dy * ry for (dx, dy), (rx, ry) in zip(moves, radii))
    den = sum(rx * rx + ry * ry for rx, ry in radii) or 1.0
    scale = num / den

    rows = []
    for (u, v), (dx, dy), (rx, ry) in zip(anchors, moves, radii):
        ex, ey = dx - scale * rx, dy - scale * ry
        rows.append({
            "anchor": f"{u:.4f},{v:.4f}",
            "travel_px": round((dx * dx + dy * dy) ** 0.5, 2),
            "residual_px": round((ex * ex + ey * ey) ** 0.5, 2),
        })
    return {"fitted_zoom": round(scale, 5), "rows": rows,
            "parallax_px": round(max(r["residual_px"] for r in rows), 2),
            "raw_travel_spread_px": round(
                max(r["travel_px"] for r in rows)
                - min(r["travel_px"] for r in rows), 2)}


def flat_twin_difference(image: str, depth: str, move: str, amount: float,
                         seconds: float, fps: int, width: int,
                         height: int) -> tuple[float, float]:
    """How much the depth map changes the render, in 8-bit levels.

    The same photograph and the same move, rendered twice: once with the
    depth map and once with a map of constant depth. Everything else is
    identical, so the difference between the two IS the depth contribution.

    It is the direct form of the question. A depth map the shader never
    loaded, a dtype it silently dropped, a move that scales instead of
    translating — all three produce a render indistinguishable from its flat
    twin, and all three produced plausible video that passed a tearing gate.
    """
    import numpy as np

    with tempfile.TemporaryDirectory() as tmp:
        real = str(Path(tmp) / "real.mp4")
        flat = str(Path(tmp) / "flat.mp4")
        base = [str(DEPTH_PY), str(ROOT / "scripts" / "render_25d.py"),
                "--image", image, "--move", move, "--amount", str(amount),
                "--seconds", str(seconds), "--fps", str(fps),
                "--width", str(width), "--height", str(height)]
        if subprocess.run(base + ["--depth", depth, "--out", real],
                          capture_output=True,
                          env=_env()).returncode != 0:
            return (-1.0, -1.0)
        if subprocess.run(base + ["--depth", depth, "--out", flat,
                                  "--flat-depth"],
                          capture_output=True,
                          env=_env()).returncode != 0:
            return (-1.0, -1.0)

        def luma(path):
            raw = subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-i", path,
                 "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                capture_output=True, check=True).stdout
            return np.frombuffer(raw, dtype="u1").reshape(
                -1, height, width).astype("float32")

        a, b = luma(real), luma(flat)
        n = min(len(a), len(b))
        contribution = a[:n] - b[:n]      # what the depth map is doing, per frame

        # TWO NUMBERS, BECAUSE THERE ARE TWO WAYS TO BE FLAT.
        #
        # `present` is how much the depth map changes the picture at all. It
        # is zero when the map never reaches the shader — the dtype case,
        # which measured exactly 0.000.
        #
        # `motion` is how much that contribution CHANGES across the hold, and
        # it is the one that catches a move which does not parallax. With
        # `isometric` held constant the depth map still displaces pixels, so
        # a zoom-only render differs from its flat twin by a large and
        # CONSTANT amount: present is high, motion is not. Only a camera
        # actually moving through the scene makes the contribution evolve.
        present = float(np.abs(contribution).mean())
        motion = float(np.abs(contribution[-1] - contribution[0]).mean())
        return present, motion


def check(image: str, depth: str, move: str = "push", amount: float = 0.08,
          seconds: float = 8.0, fps: int = 30, width: int = 1920,
          height: int = 1080) -> tuple[list[str], dict[str, Any]]:
    # THE VERDICT FIRST, because it does not depend on anchors. A depth map
    # with no relief has no three distinct depths to track, and a gate that
    # fell over trying to find them would report a subprocess error instead
    # of the plain fact that the map is flat.
    diff, motion = flat_twin_difference(image, depth, move, amount, seconds,
                                        fps, width, height)
    problems: list[str] = []
    if diff < 0:
        return (["the flat-twin renders could not be made"], {"ok": False})
    if diff < MIN_FLAT_DIFF:
        problems.append(
            f"this render and a twin of it made with a FLAT depth map differ "
            f"by {diff:.3f} levels, under the {MIN_FLAT_DIFF} floor. The "
            f"depth map is changing NOTHING: it is not reaching the shader, "
            f"or its dtype was dropped. The render will look entirely "
            f"plausible and it is a 2D zoom.")


    anchors = pick_anchors(depth)
    if len(anchors) < 3:
        problems.append(
            f"only {len(anchors)} distinct anchor(s) could be placed: the "
            f"depth map has no relief to pick them from. Every percentile of "
            f"a flat map is the same place.")
        return problems, {"ok": True, "flat_twin_diff": round(diff, 3),
                          "flat_twin_motion": round(motion, 3),
                          "flat_twin_floor": MIN_FLAT_DIFF,
                          "flat_motion_floor": MIN_FLAT_MOTION,
                          "rows": [], "parallax_px": 0.0,
                          "raw_travel_spread_px": 0.0, "fitted_zoom": 0.0,
                          "floor_px": MIN_SPREAD_PX, "move": move,
                          "amount": amount, "seconds": seconds}

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        out = fh.name
    cmd = [str(DEPTH_PY), str(ROOT / "scripts" / "anchor_track.py"),
           "--image", image, "--depth", depth, "--out", out,
           "--move", move, "--amount", str(amount), "--seconds", str(seconds),
           "--fps", str(fps), "--width", str(width), "--height", str(height),
           "--anchors"] + [f"{u:.4f},{v:.4f}" for u, v in anchors]
    run = subprocess.run(cmd, capture_output=True, text=True, env=_env())
    if run.returncode != 0:
        # A diagnostic that could not be taken does not overturn a verdict
        # that was.
        problems.append(f"the anchor track could not be made (diagnostic "
                        f"only): {run.stderr.strip()[-200:]}")
        return problems, {"ok": True, "flat_twin_diff": round(diff, 3),
                          "flat_twin_motion": round(motion, 3),
                          "flat_twin_floor": MIN_FLAT_DIFF,
                          "flat_motion_floor": MIN_FLAT_MOTION, "rows": [],
                          "parallax_px": 0.0, "raw_travel_spread_px": 0.0,
                          "fitted_zoom": 0.0, "floor_px": MIN_SPREAD_PX,
                          "move": move, "amount": amount, "seconds": seconds}

    track = json.loads(Path(out).read_text())
    moves = [displacement(track, f"{u:.4f},{v:.4f}") for u, v in anchors]
    fit = parallax_residual(anchors, moves, width, height)

    if fit["parallax_px"] < MIN_SPREAD_PX:
        problems.append(
            f"once a plain zoom is subtracted, the three anchors have "
            f"{', '.join(str(r['residual_px']) for r in fit['rows'])} px of "
            f"travel left — at most {fit['parallax_px']}, under the "
            f"{MIN_SPREAD_PX} px floor. Points at different depths are "
            f"moving as a flat plane would. The depth map IS reaching the "
            f"shader ({diff:.1f} levels against a flat twin), so this is the "
            f"MOVE: it scales about a pinned depth plane instead of carrying "
            f"the camera through the scene. A push needs its `isometric` to "
            f"open over the cut; a drift needs its lateral offset.")
    return problems, {
        **fit, "flat_twin_diff": round(diff, 3),
        "flat_twin_motion": round(motion, 3),
        "flat_twin_floor": MIN_FLAT_DIFF,
        "flat_motion_floor": MIN_FLAT_MOTION,
        "floor_px": MIN_SPREAD_PX, "move": move, "amount": amount,
        "seconds": seconds, "frames": track.get("frames"), "ok": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--depth", required=True)
    ap.add_argument("--move", default="push")
    ap.add_argument("--amount", type=float, default=0.08)
    ap.add_argument("--seconds", type=float, default=8.0)
    args = ap.parse_args()
    problems, measured = check(args.image, args.depth, args.move,
                               args.amount, args.seconds)
    if measured.get("ok"):
        for r in measured["rows"]:
            print(f"  {r['anchor']}  travel {r['travel_px']:7.2f}px  "
                  f"parallax {r['residual_px']:6.2f}px")
        print(f"  fitted zoom {measured['fitted_zoom']}, anchor parallax "
              f"{measured['parallax_px']}px, raw travel spread "
              f"{measured['raw_travel_spread_px']}px")
        print(f"  depth changes the render by "
              f"{measured['flat_twin_diff']} levels against a flat twin "
              f"(floor {measured['flat_twin_floor']}); that contribution "
              f"moves {measured.get('flat_twin_motion')} across the hold "
              f"(reported, not a floor — a zoom moves it too)")
    for p in problems:
        print("  -", p)
    print("DEPTH PARALLAX:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

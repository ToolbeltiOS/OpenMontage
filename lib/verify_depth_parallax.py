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


#: THE VERDICT: how much the depth map changes the picture, as a mean
#: absolute difference in 8-bit levels between the render and a twin of it
#: made with a FLAT depth map and the identical move.
#:
#: This asks the question the failures actually posed — does the depth map
#: reach the shader and change anything — rather than inferring it from three
#: points. Measured, the broken render and its flat twin differed by 0.000;
#: a working one differs by about 20. There is no band to overlap.
MIN_FLAT_DIFF = 1.0

#: THE SECOND PER-CUT CHECK: how much the move's parallax-carrying parameter
#: contributes, against a twin with that one parameter frozen. See
#: `parallax_twin_difference`.
#:
#: Also 1.0, and for the same reason: the two failures read EXACTLY 0.000 on
#: the check that sees them, and the worst working render measured 3.326.
#: There is no band to overlap, so the floor only has to be above zero and
#: below 3.3 — unlike the absolute px floor below, which had to thread a gap
#: between 2.03 and 3.54 and could not be made to work per cut.
#:
#:   case                     flat twin   frozen twin
#:   moai row      approved      19.639         9.550
#:   tiryns wall   approved       6.166         3.952
#:   sacsayhuaman  approved      16.012        11.840
#:   c053 push 0.2427             6.334         3.326
#:   c154 push 0.0600             7.498         8.011
#:   c094 pull 0.1542             6.908         7.223
#:   INJECT no-relief map         0.000        15.251
#:   INJECT zoom-only move       21.660         0.000
MIN_FROZEN_DIFF = 1.0

#: How far the frame's own travel may differ from the distance the 2D
#: treatment authored, as a fraction.
#:
#: A 2.5D drift has to carry BOTH halves of the move: the pan the edit wrote
#: and the parallax on top. Only the second was implemented at first, and
#: six candidate renders travelled 2 to 6 px in 8 seconds where the authored
#: drift travelled 196 -- every parallax check passed them and they read as
#: still photographs. Nothing measured the distance, so nothing noticed.
#:
#: Measured after calibration, against the authored target: 3.0%, 5.7%,
#: 0.2%, 0.0% at pans of 0.102, 0.05, -0.1056 and 0.20.
FRAME_TRAVEL_TOLERANCE = 0.10

#: The absolute anchor-parallax floor, and it is a REGRESSION CHECK ON THE
#: THREE REFERENCE STILLS ONLY — `check(..., reference=True)`. It is not
#: applied per cut and cannot be: see the table in
#: reports/depth_parallax.md, where one of seven authored cuts clears it
#: while the flat twin shows the depth map working on all seven.
REFERENCE_SPREAD_PX = 3.0

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


#: Depth percentiles the three anchors are taken from: the NEAREST and
#: FURTHEST trackable points the picture has, and the middle.
#:
#: 10/50/90 was asked for, and it is kept below as `DECILES` because it is
#: the natural choice, but it cannot be the default. It was asked for to feed
#: an expected-parallax model, and that model does not exist (see
#: `parallax_twin_difference`). Without it the deciles have no consumer, and
#: they are actively worse for the one check that still reads anchors:
#:
#:   reference still     extremes 2/50/98     deciles 10/50/90
#:   moai row                      3.54 px              2.61 px
#:   tiryns wall                   4.46 px              4.24 px
#:   sacsayhuaman joint            5.32 px              0.69 px
#:
#: The absolute floor is calibrated against the first column, and at 3.0 the
#: second column fails two of the three stills the floor exists to watch. The
#: Sacsayhuaman case shows why: its 10th and 50th percentile depths are BOTH
#: 0.120, so two of the three anchors land side by side and the pair
#: straddles no depth at all. The extremes are the widest depth separation
#: the photograph offers, which is what makes the number mean something.
PERCENTILES = (2.0, 50.0, 98.0)

#: The deciles, available to a caller that wants them. Nothing uses them.
DECILES = (10.0, 50.0, 90.0)


def pick_anchors(depth_png: str, count: int = 3,
                 percentiles: tuple[float, ...] = PERCENTILES
                 ) -> list[tuple[float, float]]:
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
    for pct in (percentiles[:count] if len(percentiles) >= count
                else np.linspace(2, 98, count)):
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
                         height: int, pan: float = 0.0) -> tuple[float, float]:
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
                "--pan", str(pan),
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


def parallax_twin_difference(image: str, depth: str, move: str, amount: float,
                             seconds: float, fps: int, width: int,
                             height: int, pan: float = 0.0) -> float:
    """How much of this render is the MOVE CARRYING THE DEPTH, in 8-bit levels.

    The second self-comparison, and the one the flat twin cannot make. The
    same photograph, the same depth map, the same everything — rendered once
    normally and once with the move's PARALLAX-CARRYING PARAMETER FROZEN:

      push, pull   `isometric` held at its start value instead of opening
      drift        the lateral offset held at zero

    The difference is what that parameter contributes. It is the direct form
    of the question "does this move carry the camera through the scene, or
    only scale the picture", which is the failure a flat-twin diff reads as
    LOUDER than a working render: scaling a static relief changes the picture
    a great deal, so `present` goes up while nothing parallaxes.

    WHY A SELF-COMPARISON AND NOT A MODEL. The first attempt was the obvious
    one: predict the expected parallax from the depth map and the authored
    move, and require the measured fraction of it. It does not work, because
    there is no first-order model of this shader. Fitting
    `resid = k * amount * height * |depth - steady|` over 15 tracked anchors
    gives a k that ranges 8x for drifts and 29x for pushes, with and without
    a radius term — the shader RAYMARCHES, so where a point lands depends on
    the depth field along its whole ray and not on the depth under it. The
    percentile anchors are not dependable either: on the Sacsayhuaman joint
    the 10th and 50th percentile depths are both 0.120, so two of the three
    anchors land side by side and never straddle any depth at all.

    A self-comparison needs no model. One parameter changes and everything
    else is held, so whatever comes out is that parameter's contribution.
    """
    import numpy as np

    with tempfile.TemporaryDirectory() as tmp:
        real = str(Path(tmp) / "real.mp4")
        frozen = str(Path(tmp) / "frozen.mp4")
        base = [str(DEPTH_PY), str(ROOT / "scripts" / "render_25d.py"),
                "--image", image, "--depth", depth, "--seconds", str(seconds),
                "--pan", str(pan),
                "--fps", str(fps), "--width", str(width),
                "--height", str(height)]
        if subprocess.run(base + ["--move", move, "--amount", str(amount),
                                  "--out", real],
                          capture_output=True, env=_env()).returncode != 0:
            return -1.0

        # FREEZE THE PARAMETER THAT CARRIES THE PARALLAX, and only it.
        if move in ("push", "pull"):
            env = {**_env(), "OPENMONTAGE_ISOMETRIC_TRAVEL": "0.0"}
            args = ["--move", move, "--amount", str(amount)]
        else:
            # FREEZE THE PARALLAX, KEEP THE PAN. `--amount 0` on a drift
            # zeroes `offset`, which is the depth, while `--pan` still moves
            # the frame the authored distance. That makes the drift's check
            # exactly as sharp as the push's: before the pan existed this
            # froze the whole move, so it proved only that the drift
            # happened and read 21.076 on c003, whose frame travelled 2px.
            env = _env()
            args = ["--move", move, "--amount", "0.0"]
        if subprocess.run(base + args + ["--out", frozen],
                          capture_output=True, env=env).returncode != 0:
            return -1.0

        def luma(path):
            raw = subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-i", path,
                 "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                capture_output=True, check=True).stdout
            return np.frombuffer(raw, dtype="u1").reshape(
                -1, height, width).astype("float32")

        a, b = luma(real), luma(frozen)
        n = min(len(a), len(b))
        return float(np.abs(a[:n] - b[:n]).mean())


def frame_travel(track: dict, width: int) -> float:
    """How far the FRAME itself moved, in px, from the tracked anchors.

    The median of the anchors' horizontal travel. Parallax makes them
    disagree by a few pixels; the pan moves all of them together, so the
    middle of them is the frame's own journey.
    """
    import numpy as np

    dxs = [(pts[-1][0] - pts[0][0]) * width
           for pts in track["anchors"].values() if len(pts) >= 2]
    return float(np.median(dxs)) if dxs else 0.0


def check(image: str, depth: str, move: str = "push", amount: float = 0.08,
          seconds: float = 8.0, fps: int = 30, width: int = 1920,
          height: int = 1080,
          reference: bool = False,
          pan: float = 0.0) -> tuple[list[str], dict[str, Any]]:
    """Two per-cut checks, each a self-comparison with one thing changed.

    `reference=True` additionally applies the absolute anchor-parallax floor,
    and is for the three reference stills only — the cases it is calibrated
    on. It is not a per-cut gate; see `REFERENCE_SPREAD_PX`.
    """
    # THE VERDICT FIRST, because it does not depend on anchors. A depth map
    # with no relief has no three distinct depths to track, and a gate that
    # fell over trying to find them would report a subprocess error instead
    # of the plain fact that the map is flat.
    diff, motion = flat_twin_difference(image, depth, move, amount, seconds,
                                        fps, width, height, pan)
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

    # CHECK TWO, and it is the one that catches the failure check one reads
    # as LOUDER than a working render.
    frozen = parallax_twin_difference(image, depth, move, amount, seconds,
                                      fps, width, height, pan)
    if frozen < 0:
        problems.append("the frozen-parameter twin could not be rendered")
    elif frozen < MIN_FROZEN_DIFF:
        carrier = ("`isometric`, which has to open over the cut"
                   if move in ("push", "pull")
                   else "the lateral offset")
        problems.append(
            f"freezing {carrier} changes this render by {frozen:.3f} levels, "
            f"under the {MIN_FROZEN_DIFF} floor — so that parameter is "
            f"contributing nothing and the move does not carry the camera "
            f"through the scene. The depth map may well be loaded and the "
            f"picture may well move; a zoom about a pinned depth plane does "
            f"both and has no parallax. Measured on the injected zoom-only "
            f"push: flat twin 21.660 (louder than any working render), "
            f"frozen twin 0.000.")

    anchors = pick_anchors(depth)
    if len(anchors) < 3:
        problems.append(
            f"only {len(anchors)} distinct anchor(s) could be placed: the "
            f"depth map has no relief to pick them from. Every percentile of "
            f"a flat map is the same place.")
        return problems, {"ok": True, "flat_twin_diff": round(diff, 3),
                          "flat_twin_motion": round(motion, 3),
                          "flat_twin_floor": MIN_FLAT_DIFF,
        "frozen_twin_diff": round(frozen, 3),
        "frozen_twin_floor": MIN_FROZEN_DIFF,
                          "frozen_twin_diff": round(frozen, 3),
                          "frozen_twin_floor": MIN_FROZEN_DIFF,
                          "flat_motion_floor": MIN_FLAT_MOTION,
                          "rows": [], "parallax_px": 0.0,
                          "raw_travel_spread_px": 0.0, "fitted_zoom": 0.0,
                          "floor_px": REFERENCE_SPREAD_PX, "move": move,
                          "amount": amount, "seconds": seconds}

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        out = fh.name
    cmd = [str(DEPTH_PY), str(ROOT / "scripts" / "anchor_track.py"),
           "--image", image, "--depth", depth, "--out", out,
           "--move", move, "--amount", str(amount), "--seconds", str(seconds),
           "--pan", str(pan),
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
        "frozen_twin_diff": round(frozen, 3),
        "frozen_twin_floor": MIN_FROZEN_DIFF,
                          "frozen_twin_diff": round(frozen, 3),
                          "frozen_twin_floor": MIN_FROZEN_DIFF,
                          "flat_motion_floor": MIN_FLAT_MOTION, "rows": [],
                          "parallax_px": 0.0, "raw_travel_spread_px": 0.0,
                          "fitted_zoom": 0.0, "floor_px": REFERENCE_SPREAD_PX,
                          "move": move, "amount": amount, "seconds": seconds}

    track = json.loads(Path(out).read_text())
    moves = [displacement(track, f"{u:.4f},{v:.4f}") for u, v in anchors]
    fit = parallax_residual(anchors, moves, width, height)

    # DID THE FRAME GO WHERE THE EDIT SENT IT? Only a drift authors a
    # distance; a push's travel is a consequence of its zoom, not a target.
    travelled = frame_travel(track, width)
    target_px = pan * width
    if move == "drift" and abs(target_px) > 1.0:
        off = abs(travelled - target_px) / abs(target_px)
        fit["frame_travel_px"] = round(travelled, 1)
        fit["frame_travel_target_px"] = round(target_px, 1)
        fit["frame_travel_error"] = round(off, 4)
        if off > FRAME_TRAVEL_TOLERANCE:
            problems.append(
                f"the frame travelled {travelled:.1f}px where the edit "
                f"authored {target_px:.1f}px, which is {off * 100:.1f}% out "
                f"(tolerance {FRAME_TRAVEL_TOLERANCE * 100:.0f}%). A 2.5D "
                f"drift has to carry the PAN as well as the parallax: "
                f"`offset` alone sweeps the near plane against the far one "
                f"and leaves the frame where it was, which renders as a "
                f"still photograph however much parallax it has.")

    if reference and fit["parallax_px"] < REFERENCE_SPREAD_PX:
        problems.append(
            f"once a plain zoom is subtracted, the three anchors have "
            f"{', '.join(str(r['residual_px']) for r in fit['rows'])} px of "
            f"travel left — at most {fit['parallax_px']}, under the "
            f"{REFERENCE_SPREAD_PX} px floor. Points at different depths are "
            f"moving as a flat plane would. The depth map IS reaching the "
            f"shader ({diff:.1f} levels against a flat twin), so this is the "
            f"MOVE: it scales about a pinned depth plane instead of carrying "
            f"the camera through the scene. A push needs its `isometric` to "
            f"open over the cut; a drift needs its lateral offset.")
    return problems, {
        **fit, "flat_twin_diff": round(diff, 3),
        "flat_twin_motion": round(motion, 3),
        "flat_twin_floor": MIN_FLAT_DIFF,
        "frozen_twin_diff": round(frozen, 3),
        "frozen_twin_floor": MIN_FROZEN_DIFF,
                          "frozen_twin_diff": round(frozen, 3),
                          "frozen_twin_floor": MIN_FROZEN_DIFF,
        "flat_motion_floor": MIN_FLAT_MOTION,
        "floor_px": REFERENCE_SPREAD_PX, "move": move, "amount": amount,
        "seconds": seconds, "frames": track.get("frames"), "ok": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--depth", required=True)
    ap.add_argument("--move", default="push")
    ap.add_argument("--amount", type=float, default=0.08)
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--pan", type=float, default=0.0,
                    help="the drift's authored pan, as a fraction of frame "
                         "width; the frame-travel check uses it as target")
    ap.add_argument("--reference", action="store_true",
                    help="also apply the absolute anchor-parallax floor. For "
                         "the three reference stills it is calibrated on, "
                         "not for an arbitrary cut.")
    args = ap.parse_args()
    problems, measured = check(args.image, args.depth, args.move,
                               args.amount, args.seconds,
                               reference=args.reference, pan=args.pan)
    if measured.get("ok"):
        for r in measured["rows"]:
            print(f"  {r['anchor']}  travel {r['travel_px']:7.2f}px  "
                  f"parallax {r['residual_px']:6.2f}px")
        print(f"  fitted zoom {measured['fitted_zoom']}, anchor parallax "
              f"{measured['parallax_px']}px, raw travel spread "
              f"{measured['raw_travel_spread_px']}px"
              + (f" (floor {measured['floor_px']}, reference mode)"
                 if args.reference else " (reported; not a per-cut floor)"))
        print(f"  depth changes the render by "
              f"{measured['flat_twin_diff']} levels against a flat twin "
              f"(floor {measured['flat_twin_floor']}); that contribution "
              f"moves {measured.get('flat_twin_motion')} across the hold "
              f"(reported, not a floor — a zoom moves it too)")
        print(f"  freezing the move's parallax parameter changes it by "
              f"{measured.get('frozen_twin_diff')} levels "
              f"(floor {measured.get('frozen_twin_floor')})")
    for p in problems:
        print("  -", p)
    print("DEPTH PARALLAX:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

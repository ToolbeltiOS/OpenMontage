#!/usr/bin/env python3
"""Where a point of the photograph lands, frame by frame, once depth moves it.

WHY THIS IS MEASURED AND NOT CALCULATED
---------------------------------------
DepthFlow's shader is a RAYMARCH: for every screen pixel it walks a ray until
it meets the displaced surface. There is no closed form taking a point of the
photograph to a point on the screen, so an annotation anchor cannot be placed
by inverting a formula — there is no formula.

`AnnotatedStill` already says what happens when that inversion is wrong: "a
sign or an ordering wrong here puts every anchor somewhere plausible and
wrong". Re-deriving a raymarch in TypeScript to find out where a ring goes is
exactly that risk, taken deliberately.

So the mapping is MEASURED, through the same shader, with the same depth map
and the same camera parameters. Two extra renders of the same scene replace
the photograph with a coordinate ramp:

    the u pass   luma = x / width  of the source
    the v pass   luma = y / height of the source

After the shader has moved them, the luma at screen pixel (x, y) IS the
source coordinate of whatever is showing there. Read the two together and
every screen pixel knows where it came from; find the pixels that came from
the anchor and you have the anchor.

WHY LUMA AND NOT COLOUR
-----------------------
The video is written as yuv420p, which subsamples chroma by two in each
direction. A coordinate in the colour channels would be averaged with its
neighbours and would be wrong by several pixels near exactly the places that
matter — the edges where the parallax is largest. Luma is not subsampled.

    .venv-depth/bin/python scripts/anchor_track.py \
        --image a.jpg --depth a.jpg.depth.png --anchors 0.31,0.62 0.55,0.40 \
        --move push --amount 0.08 --seconds 8 --out track.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: How close a screen pixel's decoded source coordinate has to be to the
#: anchor's, as a fraction of the image, to count as showing that point.
#:
#: WIDENED UNTIL SOMETHING IS CAUGHT, starting tight. The single value this
#: replaces was 1.5/255 -- sized for the coarse pass's quantisation, which is
#: 11px of frame, and keeping it would have thrown away all the precision the
#: fine pass adds. The first band is two fine levels, about 0.9px, and it
#: doubles until the anchor is found, so a point near a depth discontinuity
#: (where the mapping genuinely jumps) still gets located, just less
#: precisely, instead of falling through to the carried-forward position.
TOLERANCE_STEPS = tuple(2.0 ** k / (255.0 * 2 * 8) for k in range(1, 7)) \
    + (1.5 / 255.0,)

#: The widest band, kept under its old name for the record written out.
TOLERANCE = TOLERANCE_STEPS[-1]


#: How many cycles the FINE ramp carries across the frame.
#:
#: 8-BIT LUMA IS THE MEASUREMENT'S RESOLUTION, and on a slow move it is the
#: whole error. One level of a full-width ramp is 1920/255 = 7.5px, so the
#: coarse pass can only ever place an anchor to about that. Measured on the
#: c154 push (amount 0.06 over 21.6s): the track resolved its first anchor to
#: FIVE distinct positions across 649 frames, a staircase of ~4.6px steps,
#: and the anchor gate duly reported dots 5.5 to 8.9px off their features at
#: match scores of 0.97-0.99 -- a real offset, caused by the ruler.
#:
#: So a second pass carries a triangle wave of 8 cycles. The coarse pass says
#: which cycle, the fine pass says where in it, and the resolution becomes
#: 1920/(255*2*8) = 0.47px. A triangle rather than a sawtooth because a
#: sawtooth's discontinuities ring under H.264 and a triangle is continuous.
FINE_CYCLES = 8


def ramp(width: int, height: int, axis: str, cycles: int = 1):
    """A picture whose luma is the source coordinate along one axis.

    `cycles` > 1 gives a triangle wave of that many cycles instead of a
    single ramp: the same coordinate, measured finely but ambiguously.
    """
    import numpy as np

    n = width if axis == "u" else height
    t = np.linspace(0.0, 1.0, n)
    if cycles > 1:
        # 0 -> 1 -> 0 within each cycle, continuous across the joins
        t = 1.0 - np.abs(2.0 * ((t * cycles) % 1.0) - 1.0)
    line = (t * 255.0).astype("uint8")
    plane = (np.tile(line, (height, 1)) if axis == "u"
             else np.tile(line[:, None], (1, width)))
    return np.dstack([plane, plane, plane])


#: How far the decoded source coordinate may be from the anchor's, at the
#: best screen pixel, before the point counts as not visible this frame.
#: Two coarse luma levels: beyond that the nearest thing on screen is a
#: different part of the photograph and the anchor is occluded or off frame.
MISS = 2.0 / 255.0


def _solve(du, dv, gu, gv, u: float, v: float, width: int, height: int):
    """The screen position showing source point (u, v), to sub-pixel.

    WHY NOT THE MEDIAN OF A TOLERANCE MASK, which is what this replaces.
    That asks which screen pixels decode to approximately (u, v) and takes
    the middle of them, so its answer can only move when a WHOLE PIXEL
    enters or leaves the set. On the c154 push -- 0.06 over 21.6s, the
    slowest move in the film -- it resolved an anchor's 23.5px journey into
    SIX distinct positions across 649 frames, a staircase of ~4px, and the
    anchor gate reported dots 7 to 10px off their features at match scores
    of 0.97-0.99. Adding a fine ramp did not help, because the quantisation
    was never in the luma: it was in the median.

    Instead the decoded maps are treated as the smooth functions they are.
    The best pixel is the one minimising |(du,dv) - (u,v)|, and from there
    one Newton step along the local Jacobian of the mapping lands between
    pixels:

        [du_x du_y] [dx]   [u - du]
        [dv_x dv_y] [dy] = [v - dv]

    which is exact for a locally affine mapping and good to a fraction of a
    pixel for this one.
    """
    import numpy as np

    err = (du - u) ** 2 + (dv - v) ** 2
    idx = int(np.argmin(err))
    iy, ix = np.unravel_index(idx, du.shape)
    if err.flat[idx] > MISS ** 2:
        return None

    # np.gradient returns d/drow, d/dcol -- so the Jacobian's columns are
    # (d/dx, d/dy) = (gradient[1], gradient[0]). Getting this pair the wrong
    # way round moves every anchor somewhere plausible and wrong.
    J = np.array([[gu[1][iy, ix], gu[0][iy, ix]],
                  [gv[1][iy, ix], gv[0][iy, ix]]], dtype=np.float64)
    r = np.array([u - du[iy, ix], v - dv[iy, ix]], dtype=np.float64)
    try:
        if abs(np.linalg.det(J)) < 1e-12:
            raise np.linalg.LinAlgError
        d = np.linalg.solve(J, r)
    except np.linalg.LinAlgError:
        d = np.zeros(2)                   # flat mapping here; the pixel will do
    # A Newton step larger than a few pixels means the local linear model
    # does not hold -- a depth discontinuity runs through this pixel. Keep
    # the pixel rather than trusting the extrapolation.
    if not np.all(np.isfinite(d)) or np.hypot(*d) > 3.0:
        d = np.zeros(2)
    return [float(ix + d[0]) / width, float(iy + d[1]) / height]


def refine(coarse, fine, cycles: int = FINE_CYCLES):
    """The coordinate, from the coarse pass and the fine triangle together.

    A triangle value admits two positions per cycle, one on each branch. Both
    are computed and the one nearer the coarse reading wins, which is robust
    at the turning points where the branch is genuinely ambiguous -- picking
    a branch from the coarse value's sign would be wrong exactly there.
    """
    import numpy as np

    cycle = np.floor(np.clip(coarse, 0.0, 1.0 - 1e-9) * cycles)
    half = fine / 2.0
    up = (cycle + half) / cycles                    # rising branch
    down = (cycle + 1.0 - half) / cycles            # falling branch
    return np.where(np.abs(up - coarse) <= np.abs(down - coarse), up, down)


def decode(clip: str, width: int, height: int):
    """Every frame of a ramp pass, as luma in 0..1."""
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", clip, "-f", "rawvideo",
         "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return (np.frombuffer(raw, dtype="u1")
            .reshape(-1, height, width).astype("float32") / 255.0)


def track(image: str, depth: str, anchors: list[tuple[float, float]],
          move: str, amount: float, seconds: float, fps: int,
          width: int, height: int) -> dict:
    """Screen position of each anchor, for every frame."""
    import imageio.v3 as iio
    import numpy as np

    sys.path.insert(0, str(ROOT / "scripts"))
    from render_25d import build, crop_to_aspect, load_depth

    src = np.asarray(iio.imread(image))
    if src.ndim == 3 and src.shape[2] == 4:
        src = src[:, :, :3]
    src = crop_to_aspect(src, width, height)
    dep = load_depth(depth, width, height)

    # FOUR PASSES, not two: a coarse ramp and a fine triangle per axis. See
    # FINE_CYCLES for why -- two passes measure to 7.5px and a slow push
    # moves an anchor less than that per frame, so the track comes out a
    # staircase and the gate blames the render for the ruler.
    #
    # EACH IN ITS OWN PROCESS. Four long renders in one process exhaust the
    # GL resources on this machine and fail in two different places --
    # "Recursion on Missing Texture Shader Loading" from the shader compiler
    # on a 9.3s and a 21.6s cut, "Couldn't map object into a buffer" from the
    # frame pipe on a 6.9s one. Two passes never hit it, and a 2s four-pass
    # run does not either, which is what made it look like a code fault
    # rather than a resource one.
    passes = {}
    with tempfile.TemporaryDirectory() as tmp:
        for axis in ("u", "v"):
            for label, cycles in (("", 1), ("_fine", FINE_CYCLES)):
                out = str(Path(tmp) / f"{axis}{label}.mp4")
                run = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()),
                     "--render-pass", "--axis", axis,
                     "--cycles", str(cycles), "--depth", depth,
                     "--image", image, "--move", move,
                     "--amount", str(amount), "--seconds", str(seconds),
                     "--fps", str(fps), "--width", str(width),
                     "--height", str(height), "--out", out,
                     "--anchors", "0,0"],
                    capture_output=True, text=True)
                if run.returncode != 0 or not Path(out).exists():
                    raise SystemExit(
                        f"the {axis}{label} ramp pass failed:\n"
                        f"{run.stderr.strip()[-600:]}")
                passes[axis + label] = decode(out, width, height)

    frames = min(len(v) for v in passes.values())
    ys, xs = np.mgrid[0:height, 0:width]
    out: dict[str, list] = {f"{u:.4f},{v:.4f}": [] for u, v in anchors}

    for f in range(frames):
        du = refine(passes["u"][f], passes["u_fine"][f])
        dv = refine(passes["v"][f], passes["v_fine"][f])
        gu = np.gradient(du)
        gv = np.gradient(dv)
        for (u, v) in anchors:
            key = f"{u:.4f},{v:.4f}"
            found = _solve(du, dv, gu, gv, u, v, width, height)
            if found is not None:
                out[key].append(found)
            else:
                # The point is behind something, or off frame. Carry the last
                # known position and say so, rather than snapping to 0,0.
                out[key].append(out[key][-1] if out[key] else [u, v])
    return {
        "image": image, "depth": depth, "move": move, "amount": amount,
        "seconds": seconds, "fps": fps, "width": width, "height": height,
        "frames": frames, "tolerance": TOLERANCE, "anchors": out,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--depth", required=True)
    ap.add_argument("--anchors", nargs="+", required=True,
                    help="normalised x,y of each anchor on the photograph")
    ap.add_argument("--move", default="push")
    ap.add_argument("--amount", type=float, default=0.08)
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--out", required=True)
    ap.add_argument("--render-pass", action="store_true",
                    help="internal: render ONE ramp pass and exit. Each pass "
                         "runs in its own process because four in one "
                         "exhaust the GL resources here.")
    ap.add_argument("--axis", default="u")
    ap.add_argument("--cycles", type=int, default=1)
    args = ap.parse_args()

    if args.render_pass:
        sys.path.insert(0, str(ROOT / "scripts"))
        from render_25d import build, load_depth

        dep = load_depth(args.depth, args.width, args.height)
        scene = build(args.move, args.amount, args.seconds)()
        scene.input(image=ramp(args.width, args.height, args.axis,
                               args.cycles), depth=dep)
        scene.main(output=args.out, width=args.width, height=args.height,
                   fps=args.fps, time=args.seconds, ssaa=1.0, freewheel=True)
        return 0

    anchors = []
    for spec in args.anchors:
        x, y = spec.split(",")
        anchors.append((float(x), float(y)))

    result = track(args.image, args.depth, anchors, args.move, args.amount,
                   args.seconds, args.fps, args.width, args.height)
    Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    print(f"{result['frames']} frames, {len(anchors)} anchor(s) -> {args.out}")
    for key, pts in result["anchors"].items():
        if pts:
            dx = (pts[-1][0] - pts[0][0]) * args.width
            dy = (pts[-1][1] - pts[0][1]) * args.height
            print(f"  {key}: moved {dx:+.1f}, {dy:+.1f} px over the cut")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

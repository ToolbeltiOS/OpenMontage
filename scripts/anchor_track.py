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
#: 8-bit luma quantises a coordinate to 1/255, so the band has to be at
#: least that wide or it catches nothing.
TOLERANCE = 1.5 / 255.0


def ramp(width: int, height: int, axis: str):
    """A picture whose luma is the source coordinate along one axis."""
    import numpy as np

    if axis == "u":
        row = (np.linspace(0.0, 1.0, width) * 255.0).astype("uint8")
        plane = np.tile(row, (height, 1))
    else:
        col = (np.linspace(0.0, 1.0, height) * 255.0).astype("uint8")
        plane = np.tile(col[:, None], (1, width))
    return np.dstack([plane, plane, plane])


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
    from render_25d import as_depth, build, crop_to_aspect

    src = np.asarray(iio.imread(image))
    if src.ndim == 3 and src.shape[2] == 4:
        src = src[:, :, :3]
    src = crop_to_aspect(src, width, height)
    dep = as_depth(crop_to_aspect(np.asarray(iio.imread(depth)), width, height))

    passes = {}
    with tempfile.TemporaryDirectory() as tmp:
        for axis in ("u", "v"):
            out = str(Path(tmp) / f"{axis}.mp4")
            scene = build(move, amount, seconds)()
            scene.input(image=ramp(width, height, axis), depth=dep)
            scene.main(output=out, width=width, height=height, fps=fps,
                       time=seconds, ssaa=1.0, freewheel=True)
            passes[axis] = decode(out, width, height)

    frames = min(len(passes["u"]), len(passes["v"]))
    ys, xs = np.mgrid[0:height, 0:width]
    out: dict[str, list] = {f"{u:.4f},{v:.4f}": [] for u, v in anchors}

    for f in range(frames):
        du, dv = passes["u"][f], passes["v"][f]
        for (u, v) in anchors:
            hit = (np.abs(du - u) <= TOLERANCE) & (np.abs(dv - v) <= TOLERANCE)
            key = f"{u:.4f},{v:.4f}"
            if hit.any():
                # The median, not the mean: a stray pixel on the far side of
                # a depth discontinuity would drag a mean across the frame.
                out[key].append([float(np.median(xs[hit])) / width,
                                 float(np.median(ys[hit])) / height])
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
    args = ap.parse_args()

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

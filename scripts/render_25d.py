#!/usr/bin/env python3
"""A 2.5D parallax render of one still, driven by the edit's camera intent.

RUNS ON ITS OWN INTERPRETER. DepthFlow's renderer imports `typing.Self`,
which needs Python 3.11, and the pipeline's venv is 3.10. `.venv-depth` is a
3.12 environment holding depthflow and nothing else that matters; the depth
MAP is made by `lib/depth_cache.py` on the main venv and handed over as a
file, so the two never have to agree about anything but PNG.

    .venv-depth/bin/python scripts/render_25d.py \
        --image a.jpg --depth a.jpg.depth.png --out a.mp4 \
        --move push --seconds 8 --amount 0.08

THE SOURCE MUST ALREADY BE THE OUTPUT'S ASPECT RATIO.
-----------------------------------------------------
This is not a detail. DepthFlow maps the photograph onto a plane of the
PHOTOGRAPH's aspect and clamps the texture outside it, so feeding a 3:2
picture to a 16:9 render smears the edge pixel across the pillarbox — on
every row, for the whole clip. Measured with `lib/verify_depth_tearing.py`:
2,400 border smear runs across five frames before the crop, 0 after, with
interior runs falling from ~300 to 1. It looks exactly like depth tearing and
has nothing to do with depth. The crop happens here so no caller can forget.

CAMERA INTENT IS THE EDIT'S, NOT DEPTHFLOW'S.
---------------------------------------------
`push`, `pull`, `drift` and `lock` are the moves the edit already authors, at
the speeds it already authors them. The depth map changes HOW the move is
rendered — the foreground moving further than the background — and must not
change WHICH move happens or how fast.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

#: How much relief the depth map is allowed to produce. 0.08 is a gentle
#: documentary parallax: measured on the moai quarry still it yields one
#: interior smear run across five frames, against two for the flat 2D push
#: the treatment is replacing and zero for a motionless photograph.
DEFAULT_HEIGHT = 0.08

#: How much of the relief reads as parallax rather than as scale, at the
#: start of the cut.
DEFAULT_ISOMETRIC = 0.30

#: How far the isometric opens over the cut. THIS IS WHERE THE PARALLAX
#: COMES FROM, and a zoom alone has none.
#:
#: `steady` pins a depth plane and `zoom` scales about it, so a push with
#: nothing else moving is a 2D zoom that happens to own a depth map.
#: Measured on the moai quarry still, three anchors at one column — a near
#: statue, the far hillside, and the middle distance — move over an 8s push:
#:
#:     zoom only          +30.0  +28.5  +29.0   (1.5 px apart: flat)
#:     dolly   +0.6       +36.5  +28.5  +31.5
#:     isometric +0.5     +43.0  +28.5  +33.5   (14.5 px apart)
#:
#: 0.35 sits between: the foreground magnifies about a third again as much
#: as the background, which reads as a camera moving in rather than a
#: picture being scaled, and does not turn a documentary still into a
#: parallax demonstration.
ISOMETRIC_TRAVEL = 0.35

#: A TEST HOOK, and the only reason it exists is that the alternative is
#: worse. `lib/verify_depth_parallax.py` has to prove it catches a push with
#: no parallax, which means rendering one, which means ISOMETRIC_TRAVEL = 0.
#: Editing this file to do that leaves the renderer one forgotten `git
#: checkout` away from shipping flat, and that has already happened once.
#: Nothing in the pipeline sets it; the gate's own self-test does.
if os.environ.get("OPENMONTAGE_ISOMETRIC_TRAVEL"):
    ISOMETRIC_TRAVEL = float(os.environ["OPENMONTAGE_ISOMETRIC_TRAVEL"])

#: Which depth plane stays put while the rest moves around it. 0.5 pins the
#: middle distance, which is where a documentary still's subject usually is.
DEFAULT_STEADY = 0.5


def as_depth(array):
    """The depth map in a form the shader will actually load.

    A 16-bit single-channel array is SILENTLY IGNORED. ShaderTexture takes
    it without complaint, the sampler comes back as the zero texture, and the
    render proceeds as a flat 2D zoom with a depth map that was never read.
    The only sign is one line on the first frame — "texture unloadable ...
    using zero texture" — which scrolls past in a progress bar.

    Measured: with a uint16 map, a real depth map and a FLAT one produce
    byte-identical video. uint8 and float32 both work; float32 is used here
    because it keeps the 16 bits the cache stored.
    """
    import numpy as np

    a = np.asarray(array)
    if a.ndim == 3:
        a = a[:, :, 0]

    # REJECT WHAT THE SHADER WOULD SILENTLY DROP.
    #
    # Not "convert quietly": refuse, by name, with the dtype in the message.
    # The whole defect was that an unusable array was ACCEPTED — by
    # ShaderTexture, by the renderer, by a tearing gate — and produced
    # plausible video. A conversion that happens without saying so is the
    # same silence one layer further down, and the next person to pass a
    # uint16 map will get a render that looks right.
    if a.dtype not in (np.uint8, np.float32, np.float64):
        raise SystemExit(
            f"the depth map is {a.dtype}, which DepthFlow's ShaderTexture "
            f"takes without complaint and then does not load: the sampler "
            f"returns the zero texture and the render comes out a flat 2D "
            f"zoom that looks entirely plausible. Only uint8 and float32 "
            f"load. Convert it deliberately — lib/depth_cache.py writes "
            f"16-bit PNGs and this is the function that reads them.")

    a = a.astype(np.float32)
    span = float(a.max()) - float(a.min())
    if span > 0:
        a = (a - float(a.min())) / span
    else:
        # NO RELIEF AT ALL, which still has to leave here in the 0..1 the
        # rest of the function promises. Skipping the normalisation let the
        # raw value through: a constant uint8 map arrived at the shader as
        # depth 128.0, a plane a hundred times past the far limit, and the
        # render differed from a mid-grey twin by 31 levels of uniform
        # scale. Measured while testing the gate, which read that as a loud
        # depth contribution from a map that has no depth in it.
        a = np.full_like(a, 0.5)
    return a


def load_depth(path, width: int, height: int):
    """Read a cached depth PNG and give the shader what it can load.

    ONE PATH, because the conversion is the thing that was wrong. The cache
    writes 16-bit PNGs; the shader drops 16-bit arrays without a word. Every
    caller goes through here so there is no second place to get it right.
    """
    import imageio.v3 as iio
    import numpy as np

    raw = np.asarray(iio.imread(path))
    if raw.dtype == np.uint16:
        raw = raw.astype(np.float32) / 65535.0
    return as_depth(crop_to_aspect(raw, width, height))


def crop_to_aspect(array, width: int, height: int):
    """Centre-crop and resize to exactly the output frame."""
    import numpy as np
    from PIL import Image

    im = Image.fromarray(array)
    want = width / height
    w, h = im.size
    have = w / h
    if have > want:
        new_w = int(round(h * want))
        box = ((w - new_w) // 2, 0, (w - new_w) // 2 + new_w, h)
    else:
        new_h = int(round(w / want))
        box = (0, (h - new_h) // 2, w, (h - new_h) // 2 + new_h)
    resample = Image.LANCZOS if array.ndim == 3 else Image.BICUBIC
    return np.asarray(im.crop(box).resize((width, height), resample))


def build(move: str, amount: float, seconds: float):
    """A DepthScene whose update() is the edit's move."""
    from attrs import define
    from depthflow.scene import DepthScene

    move = (move or "lock").lower()

    @define
    class Move(DepthScene):
        def update(self) -> None:
            t = min(max(self.time / max(seconds, 1e-6), 0.0), 1.0)
            self.state.height = DEFAULT_HEIGHT
            self.state.isometric = DEFAULT_ISOMETRIC
            self.state.steady = DEFAULT_STEADY
            if move == "push":
                self.state.zoom = 1.0 + amount * t
                self.state.isometric = DEFAULT_ISOMETRIC + ISOMETRIC_TRAVEL * t
            elif move == "pull":
                self.state.zoom = 1.0 + amount * (1.0 - t)
                self.state.isometric = (DEFAULT_ISOMETRIC
                                        + ISOMETRIC_TRAVEL * (1.0 - t))
            elif move == "drift":
                # A lateral camera move is already parallax: the near plane
                # sweeps against the far one, and it sweeps the OTHER way,
                # which is what makes a drift read as depth rather than as a
                # pan. Measured, near and far separate by 5.5 px at 0.20.
                self.state.offset = (amount * (t - 0.5) * 2.0, 0.0)
                self.state.zoom = 1.0 + amount * 0.25
            else:                                   # lock: relief, no move
                self.state.zoom = 1.0
    return Move


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--depth", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--move", default="push",
                    choices=("push", "pull", "drift", "lock"))
    ap.add_argument("--amount", type=float, default=0.08)
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--flat-depth", action="store_true",
                    help="replace the depth map with a constant, for the "
                         "flat twin lib/verify_depth_parallax.py compares "
                         "against. Everything else is identical.")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()

    import imageio.v3 as iio
    import numpy as np

    image = np.asarray(iio.imread(args.image))
    if image.ndim == 3 and image.shape[2] == 4:
        image = image[:, :, :3]
    image = crop_to_aspect(image, args.width, args.height)
    depth = load_depth(args.depth, args.width, args.height)
    if args.flat_depth:
        # MID-GREY FOR THE DTYPE, not the literal 0.5. `full_like(depth,
        # 0.5)` on a uint8 map truncates to 0, which is not a flat twin of
        # the picture — it is a flat plane at the NEAR limit, and it differs
        # from a mid-grey constant map by 31 levels of uniform scale. That
        # made an injected no-relief map look like a loud depth
        # contribution. The twin has to be flat AT THE SAME PLACE.
        depth = np.full_like(depth, 128 if depth.dtype == np.uint8 else 0.5)

    scene = build(args.move, args.amount, args.seconds)()
    scene.input(image=image, depth=depth)
    scene.main(output=args.out, width=args.width, height=args.height,
               fps=args.fps, time=args.seconds, ssaa=1.0, freewheel=True)
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

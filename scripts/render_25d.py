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
import sys
from pathlib import Path

#: How much relief the depth map is allowed to produce. 0.08 is a gentle
#: documentary parallax: measured on the moai quarry still it yields one
#: interior smear run across five frames, against two for the flat 2D push
#: the treatment is replacing and zero for a motionless photograph.
DEFAULT_HEIGHT = 0.08

#: How much of the relief reads as parallax rather than as scale.
DEFAULT_ISOMETRIC = 0.30

#: Which depth plane stays put while the rest moves around it. 0.5 pins the
#: middle distance, which is where a documentary still's subject usually is.
DEFAULT_STEADY = 0.5


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
            elif move == "pull":
                self.state.zoom = 1.0 + amount * (1.0 - t)
            elif move == "drift":
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
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()

    import imageio.v3 as iio
    import numpy as np

    image = np.asarray(iio.imread(args.image))
    depth = np.asarray(iio.imread(args.depth))
    if image.ndim == 3 and image.shape[2] == 4:
        image = image[:, :, :3]
    image = crop_to_aspect(image, args.width, args.height)
    depth = crop_to_aspect(depth, args.width, args.height)

    scene = build(args.move, args.amount, args.seconds)()
    scene.input(image=image, depth=depth)
    scene.main(output=args.out, width=args.width, height=args.height,
               fps=args.fps, time=args.seconds, ssaa=1.0, freewheel=True)
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

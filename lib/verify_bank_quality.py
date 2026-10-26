#!/usr/bin/env python3
"""Is this picture good enough to push into on a 1080p screen?

THREE QUESTIONS, AND THE FIRST ONE IS NOT THE OBVIOUS ONE
---------------------------------------------------------
A still that will be held for eight seconds and magnified has to be sharp,
clean and large. The bank already rejected the small ones and the blank ones;
this adds focus and compression, and measures the long edge again on the FILE
rather than on what the provider's metadata claimed.

SHARPNESS IS NOT THE GLOBAL LAPLACIAN VARIANCE, and using it would have been
wrong three times over. Ranked by global variance, the three softest pictures
in the bank are a shallow-depth-of-field macro of a hand holding a stone
(21.9), a lamplit underground tunnel (50.5) and a dim museum interior (65.3).
Not one of them is out of focus. The first is sharp exactly where it is meant
to be and deliberately soft everywhere else; the other two are dark, and
darkness is not blur. A global floor condemns all three.

So the question is whether ANYTHING in the picture is sharp, which is what
matters for a still that will be pushed into: the frame is tiled, the
Laplacian variance is taken per tile, and the measure is the 95th percentile
of those. Measured against the same pictures Gaussian-blurred at sigma 3,
which is the control:

    picture                     as banked    blurred
    hand and stone (macro)           80.4        2.2
    tunnel                          131.0        5.3
    museum interior                 269.4        2.9
    Tiryns wall                    1279.0        2.8
    moai row                       3711.3        4.7
    Sacsayhuaman joint             5471.8        7.2

Real pictures 80.4 and up, blurred ones 7.2 and down. MIN_SHARPNESS sits in
that gap with an 11x margin on the nearest real picture.

Everything is measured at a NORMALISED 1024px long edge. Laplacian variance
grows with resolution, so measured on the file it ranks big pictures above
sharp ones -- which is the one thing this check must not do, the bank having
already been ordered by resolution.

BLOCKINESS NEVER FIRES ON THIS CORPUS, and that is reported rather than
hidden. Across all 325 banked images it runs 0.856 to 1.160, median 1.001:
Commons originals are not recompressed JPEGs. The threshold is set from a
control instead -- the same picture re-encoded at falling quality:

    quality 95   blockiness 0.989
    quality 50   blockiness 1.501
    quality 20   blockiness 2.063
    quality 10   blockiness 2.987
    quality  5   blockiness 5.207

MAX_BLOCKINESS catches quality 50 and worse and clears the whole bank. It is
here for the day a provider that is not Commons supplies a recompressed file,
and until then it will pass everything, which is the honest expectation.

    python3 lib/verify_bank_quality.py <image> [<image> ...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

#: 95th percentile of per-tile Laplacian variance, at a 1024px long edge.
#: Real pictures measure 80.4 and up; the same pictures blurred at sigma 3
#: measure 7.2 and down. See the module docstring.
MIN_SHARPNESS = 25.0

#: Gradient energy on JPEG block boundaries over gradient energy off them.
#: 1.0 is no blocking. The bank tops out at 1.160; quality-50 re-encoding
#: reads 1.501.
MAX_BLOCKINESS = 1.30

#: Long edge of the FILE, after any upscale. The bank rejects below 3000 at
#: fetch time from the provider's metadata; this is the floor the picture
#: has to clear as it actually sits on disk, which is the number that
#: decides whether a push into it holds up at 1080p.
MIN_LONG_EDGE = 2400

#: Size everything is measured at, so the numbers mean the same thing for a
#: 3000px picture and a 21000px one.
NORM_LONG_EDGE = 1024

#: Side of the sharpness tile at that normalised size.
TILE = 128

#: Where the per-tile variances are read off.
TILE_PERCENTILE = 95


def _normalised(path: str):
    import cv2

    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    h, w = img.shape
    s = NORM_LONG_EDGE / max(h, w)
    return cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))),
                      interpolation=cv2.INTER_AREA)


def sharpness(g) -> float:
    """95th percentile of per-tile Laplacian variance.

    THE TILE ADAPTS TO THE FRAME, because a fixed one silently returns zero
    on an extreme panorama. wm_229317340 is 2068x20064; normalised to a
    1024px long edge it is 105px tall, no 128px tile fits, the list of tile
    variances comes back empty and the picture scores 0.0 -- a sharp
    photograph failing a sharpness check because of its shape.
    """
    import cv2
    import numpy as np

    h, w = g.shape
    tile = max(16, min(TILE, h // 2, w // 2))
    lap = cv2.Laplacian(g, cv2.CV_64F)
    step = max(1, tile // 2)
    vs = [lap[y:y + tile, x:x + tile].var()
          for y in range(0, max(1, h - tile + 1), step)
          for x in range(0, max(1, w - tile + 1), step)]
    if not vs:
        vs = [lap.var()]
    return float(np.percentile(vs, TILE_PERCENTILE))


def blockiness(g) -> float:
    """Gradient energy on 8px JPEG block boundaries, over the rest."""
    import numpy as np

    d = np.abs(np.diff(g.astype("float32"), axis=1))
    c = np.arange(d.shape[1])
    on, off = d[:, (c % 8) == 7], d[:, (c % 8) != 7]
    if on.size == 0 or off.size == 0 or off.mean() == 0:
        return 1.0
    return float(on.mean() / off.mean())


def check(path: str) -> tuple[list[str], dict[str, Any]]:
    """Every quality problem with this file, and the numbers behind them."""
    import cv2

    full = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if full is None:
        return ([f"{Path(path).name}: cannot be read as an image"], {})
    g = _normalised(path)
    long_edge = max(full.shape[:2])
    m = {"long_edge": int(long_edge),
         "sharpness": round(sharpness(g), 1),
         "blockiness": round(blockiness(g), 3),
         "floors": {"long_edge": MIN_LONG_EDGE,
                    "sharpness": MIN_SHARPNESS,
                    "blockiness": MAX_BLOCKINESS}}
    problems = []
    if long_edge < MIN_LONG_EDGE:
        problems.append(
            f"long edge {long_edge}px is under {MIN_LONG_EDGE}px, so a push "
            f"into it is upscaling past the detail it has")
    if m["sharpness"] < MIN_SHARPNESS:
        problems.append(
            f"nothing in this picture is sharp: the best tile reads "
            f"{m['sharpness']} against a floor of {MIN_SHARPNESS}, where a "
            f"deliberately blurred control reads about 5 and the softest "
            f"real picture in the bank reads 80")
    if m["blockiness"] > MAX_BLOCKINESS:
        problems.append(
            f"JPEG blocking at {m['blockiness']} against a ceiling of "
            f"{MAX_BLOCKINESS}: the 8-pixel grid is visible, which a push "
            f"magnifies. Quality-50 re-encoding measures 1.5 and the whole "
            f"Commons bank measures under 1.17")
    return problems, m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    args = ap.parse_args()
    bad = 0
    for p in args.images:
        problems, m = check(p)
        flag = "FAIL" if problems else "pass"
        print(f"  {flag}  {Path(p).name:<24} long edge {m.get('long_edge', 0):>6}  "
              f"sharpness {m.get('sharpness', 0):>8}  "
              f"blockiness {m.get('blockiness', 0)}")
        for x in problems:
            print(f"        - {x}")
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

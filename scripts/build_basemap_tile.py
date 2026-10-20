#!/usr/bin/env python3
"""Cut one map shot's terrain tile out of the Natural Earth raster.

WHY A BUILD STEP AND NOT A RUNTIME ONE
--------------------------------------
The source is Natural Earth II with shaded relief at 1:10m — 21600x10800
pixels, 700 MB, public domain. Nothing in a browser is going to open that per
frame, and nothing should: a map shot covers a few degrees and the camera
drifts by one or two percent across it, so the pixels it needs are fixed
before the first frame is drawn.

So the tile is cut here, in equirectangular, which is what the source is in,
and the component does the small remaining warp into the shot's Mercator
extent. That split is deliberate: a crop in the source projection is exact and
free, and the Mercator warp is a per-row vertical stretch the browser can do
in one pass. Reprojecting 700 MB on the fly to avoid a 300 KB JPEG would be a
worse trade in every direction.

The sidecar JSON records the tile's exact bounds, because a tile whose bounds
are guessed puts the route in the sea.

    python scripts/build_basemap_tile.py --name orcadian \\
        --route 'projects/<id>/artifacts/scene_plan.json#s118' \\
        --bounds -5.2 56.0 1.2 60.4
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/basemaps/NE2_HR_LC_SR/NE2_HR_LC_SR.tif"
DEST = ROOT / "remotion-composer/public/basemaps"

#: From the source's world file: 1/60 degree per pixel, top-left at
#: (-179.991666, 89.991666). Hard-coded rather than parsed because a basemap
#: whose georeferencing silently changed should fail loudly on the assertion
#: below, not quietly draw a route into the sea.
PX_PER_DEG = 60.0
WEST_EDGE = -180.0
NORTH_EDGE = 90.0

ATTRIBUTION = {
    "name": "Natural Earth II with Shaded Relief and Water",
    "scale": "1:10m",
    "provider": "Natural Earth",
    "url": "https://www.naturalearthdata.com/downloads/10m-raster-data/10m-natural-earth-2/",
    "licence": "public domain",
}


#: Natural Earth II's ocean is flat (253,253,253) and perfectly neutral. No
#: land reaches that: the brightest is Antarctic ice at (227,231,240), which is
#: both darker and measurably blue. So the ocean can be keyed on "very bright
#: AND neutral" without touching ice — which matters, because a globe whose
#: Antarctica had been flooded with sea colour would be wrong in a way nobody
#: would notice until it was on screen.
OCEAN_MIN = 250
OCEAN_NEUTRAL = 3


def tint_ocean(im, colour: tuple[int, int, int]):
    """Replace the raster's white ocean with the film's own water."""
    import numpy as np
    from PIL import Image

    a = np.asarray(im.convert("RGB")).astype(np.int16)
    mask = (a.min(axis=2) >= OCEAN_MIN) & ((a.max(axis=2) - a.min(axis=2)) <= OCEAN_NEUTRAL)
    out = a.copy()
    out[mask] = colour
    return Image.fromarray(out.astype("uint8")), float(mask.mean())


def grade(im, saturation: float, brightness: float):
    """Pull the raster toward the film, at build time.

    The 2D map does this with a CSS filter on the canvas. The globe is a
    texture on a mesh, where a filter would have to become a shader, so it is
    baked in here instead — same numbers, one less moving part.
    """
    import numpy as np
    from PIL import Image

    a = np.asarray(im.convert("RGB")).astype(np.float32)
    luma = (a * np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)).sum(axis=2, keepdims=True)
    out = (luma + (a - luma) * saturation) * brightness
    return Image.fromarray(np.clip(out, 0, 255).astype("uint8"))


def crop(bounds: tuple[float, float, float, float], name: str,
         max_width: int = 2600, ocean: tuple[int, int, int] | None = None,
         saturation: float = 1.0, brightness: float = 1.0) -> dict:
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None          # the source is 233 megapixels
    west, south, east, north = bounds
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise SystemExit(f"bounds out of order or off the globe: {bounds}")

    with Image.open(SOURCE) as im:
        if im.size != (21600, 10800):
            raise SystemExit(
                f"source is {im.size}, not the 21600x10800 this script's "
                f"georeferencing assumes")
        left = int(round((west - WEST_EDGE) * PX_PER_DEG))
        right = int(round((east - WEST_EDGE) * PX_PER_DEG))
        top = int(round((NORTH_EDGE - north) * PX_PER_DEG))
        bottom = int(round((NORTH_EDGE - south) * PX_PER_DEG))
        tile = im.crop((left, top, right, bottom))

    # Snap the recorded bounds back to the pixel edges actually cut, so the
    # component warps from the tile that exists rather than the one asked for.
    exact = (
        WEST_EDGE + left / PX_PER_DEG,
        NORTH_EDGE - bottom / PX_PER_DEG,
        WEST_EDGE + right / PX_PER_DEG,
        NORTH_EDGE - top / PX_PER_DEG,
    )

    if tile.width > max_width:
        tile = tile.resize(
            (max_width, max(1, round(tile.height * max_width / tile.width))),
            Image.LANCZOS)

    ocean_fraction = None
    if ocean is not None:
        tile, ocean_fraction = tint_ocean(tile, ocean)
    if saturation != 1.0 or brightness != 1.0:
        tile = grade(tile, saturation, brightness)

    DEST.mkdir(parents=True, exist_ok=True)
    out = DEST / f"{name}.jpg"
    tile.convert("RGB").save(out, quality=88, optimize=True)

    meta = {
        "name": name,
        "src": f"basemaps/{name}.jpg",
        "bounds": [round(v, 6) for v in exact],
        "pixels": list(tile.size),
        "source": ATTRIBUTION,
        **({"ocean_tint": list(ocean), "ocean_fraction": round(ocean_fraction, 3)}
           if ocean is not None else {}),
        "grade": {"saturation": saturation, "brightness": brightness},
    }
    (DEST / f"{name}.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--bounds", nargs=4, type=float, required=True,
                    metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    ap.add_argument("--max-width", type=int, default=2600)
    ap.add_argument("--saturation", type=float, default=1.0)
    ap.add_argument("--brightness", type=float, default=1.0)
    ap.add_argument("--ocean", nargs=3, type=int, metavar=("R", "G", "B"),
                    help="recolour the raster's white ocean. The 2D map masks "
                         "its ocean with coastline geometry instead; this is "
                         "for the globe, which has no mask to cut with.")
    args = ap.parse_args()

    if not SOURCE.exists():
        raise SystemExit(
            f"no basemap at {SOURCE}.\n"
            f"Download it once (public domain, ~200MB zipped):\n"
            f"  curl -L -o ne2.zip {ATTRIBUTION['url']}\n"
            f"and unzip into assets/basemaps/NE2_HR_LC_SR/")

    meta = crop(tuple(args.bounds), args.name, args.max_width,
                tuple(args.ocean) if args.ocean else None,
                args.saturation, args.brightness)
    print(f"{meta['name']}: {meta['pixels'][0]}x{meta['pixels'][1]} "
          f"covering {meta['bounds']}")
    print(f"  -> {DEST / (args.name + '.jpg')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

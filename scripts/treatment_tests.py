#!/usr/bin/env python3
"""Step 10: two treatments, one slot each, for judging by eye.

WHAT A TREATMENT IS FOR
-----------------------
The film has two recurring problems a photograph cannot solve. The first is
the reconstruction: a thing that happened and was never photographed, where
run #1's answer was a schematic and a schematic says "diagram" when the beat
wants "this is how it looked". The second is the record: a claim that lives in
print rather than in stone, where the answer was a text card and a text card
says "slide".

SKETCHED RECONSTRUCTION takes a photograph of the place as it is and renders
it as a site drawing — the archaeologist's line, not the camera's. It keeps
the real geometry, which is the point: the drawing is of the actual rock.

HALFTONE COLLAGE takes the same material and prints it: a dot screen on paper
stock, in the palette's ink. The register it buys is "this is from a record",
which is what a citation beat needs.

BOTH ARE PLATE TREATMENTS. Neither touches type: they run on the picture, and
the scene's labels are drawn over them as type, in the type pass, exactly as
for an untreated still. A treatment that baked its own labels would take the
film's grain on their edges.

    python scripts/treatment_tests.py --project <id>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "step10"

#: The palette, from the playbook's design tokens.
INK = (236, 229, 214)          # bone
FIELD = (12, 12, 14)           # near-black
ACCENT = (192, 138, 62)        # ochre
PAPER = (222, 212, 192)


def sketched_reconstruction(path: Path, width: int = 1280):
    """A site drawing of the real rock: edges kept, tone thrown away.

    XDoG rather than Canny. Canny gives a wire frame — every edge the same
    weight, which reads as a machine tracing. The difference of Gaussians
    keeps edge STRENGTH, so a deep joint draws heavier than a surface crack,
    which is what a drawn line does.
    """
    import cv2
    import numpy as np

    image = cv2.imread(str(path))
    height = round(image.shape[0] * width / image.shape[1])

    # THE LINES ARE FOUND AT A FIXED SIZE AND THEN ENLARGED.
    #
    # Every parameter here is a number of pixels — the bilateral radius, the
    # two sigmas — so running the same settings at 640 and at 1280 does not
    # give the same drawing at two sizes, it gives two different drawings.
    # Measured: at 640 the hillside was suppressed and at 1280 the same
    # settings left it a field of noise, because the filter was half the
    # relative size. Extracting at one size and scaling the line map up keeps
    # the drawing the same drawing.
    work_w = 720
    work_h = max(1, round(image.shape[0] * work_w / image.shape[1]))
    small = cv2.resize(image, (work_w, work_h), interpolation=cv2.INTER_AREA)
    grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    # Flatten the texture before looking for edges, or every blade of grass
    # and every pock in the lava becomes a line. Chosen by rendering four
    # settings side by side and looking: milder and the hillside is noise,
    # stronger and the moai outlines turn into blobs.
    smooth = cv2.bilateralFilter(grey, 13, 120, 120).astype("float32") / 255.0

    sigma = 2.2
    dog = cv2.GaussianBlur(smooth, (0, 0), sigma) - cv2.GaussianBlur(
        smooth, (0, 0), sigma * 1.6)

    # Lines, and ONLY lines. The first version added a term proportional to
    # darkness "so the drawing sits on the rock's form", and it did not draw
    # the rock — it filled it: the moai came out as white silhouettes, because
    # a dark subject is a large dark region and a tone term paints all of it.
    # A drawing is edges. Tone belongs to the photograph.
    strength = np.abs(dog)
    strength = strength / (np.percentile(strength, 99.3) + 1e-6)
    ink = np.clip((strength - 0.22) / 0.55, 0.0, 1.0) ** 0.75
    ink = cv2.resize(ink, (width, height), interpolation=cv2.INTER_CUBIC)
    ink = np.clip(ink, 0.0, 1.0)

    out = np.zeros((height, width, 3), dtype="float32")
    for c in range(3):
        out[..., c] = FIELD[2 - c] / 255.0 * (1 - ink) + INK[2 - c] / 255.0 * ink
    return (out * 255).astype("uint8")


def halftone_collage(path: Path, width: int = 1280, dot: int = 6):
    """Printed, not photographed: a rotated dot screen on paper stock.

    The screen is rotated 15 degrees because an unrotated one beats against
    the pixel grid and reads as a digital artefact rather than as print.
    """
    import cv2
    import numpy as np

    image = cv2.imread(str(path))
    height = round(image.shape[0] * width / image.shape[1])
    image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype("float32") / 255.0
    grey = np.clip((grey - 0.5) * 1.25 + 0.5, 0, 1)        # print contrast

    yy, xx = np.mgrid[0:height, 0:width].astype("float32")
    angle = np.deg2rad(15.0)
    rx = xx * np.cos(angle) - yy * np.sin(angle)
    ry = xx * np.sin(angle) + yy * np.cos(angle)
    # distance from the nearest screen centre, in cell units
    cell_x = (rx % dot) - dot / 2
    cell_y = (ry % dot) - dot / 2
    distance = np.sqrt(cell_x ** 2 + cell_y ** 2) / (dot / 2)
    # a darker patch prints a bigger dot
    radius = np.sqrt(np.clip(1.0 - grey, 0, 1))
    coverage = np.clip((radius - distance) * 2.2 + 0.5, 0.0, 1.0)

    out = np.zeros((height, width, 3), dtype="float32")
    for c in range(3):
        out[..., c] = (PAPER[2 - c] / 255.0 * (1 - coverage)
                       + FIELD[2 - c] / 255.0 * coverage)

    # paper: a faint fibre, and the stock warmed towards the accent
    rng = np.random.default_rng(4)
    fibre = cv2.GaussianBlur(rng.normal(0, 0.035, (height, width)), (0, 0), 1.2)
    out = np.clip(out + fibre[..., None], 0, 1)
    warm = np.array([ACCENT[2] / 255.0, ACCENT[1] / 255.0, ACCENT[0] / 255.0])
    out = np.clip(out * (1 - 0.08) + warm * 0.08, 0, 1)
    return (out * 255).astype("uint8")


TREATMENTS = {
    "sketched_reconstruction": sketched_reconstruction,
    "halftone_collage": halftone_collage,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--sketch-cut", default="c049")
    ap.add_argument("--halftone-cut", default="c044")
    args = ap.parse_args()

    import cv2

    props = json.loads(
        (ROOT / "projects" / args.project / "artifacts" / "render_props.json").read_text())
    by_id = {c["id"]: c for c in props["cuts"]}
    OUT.mkdir(parents=True, exist_ok=True)

    rows = []
    for name, cut_id in (("sketched_reconstruction", args.sketch_cut),
                         ("halftone_collage", args.halftone_cut)):
        cut = by_id[cut_id]
        source = cut["source"]
        path = Path(source) if source.startswith("/") else ROOT / source
        original = cv2.imread(str(path))
        height = round(original.shape[0] * 1280 / original.shape[1])
        cv2.imwrite(str(OUT / f"{cut_id}_original.jpg"),
                    cv2.resize(original, (1280, height), interpolation=cv2.INTER_AREA),
                    [cv2.IMWRITE_JPEG_QUALITY, 92])
        treated = TREATMENTS[name](path)
        cv2.imwrite(str(OUT / f"{cut_id}_{name}.jpg"), treated,
                    [cv2.IMWRITE_JPEG_QUALITY, 92])
        rows.append((name, cut_id, cut.get("sceneIndex"), path.name))
        print(f"{name}: {cut_id} {cut.get('sceneIndex')} <- {path.name}")

    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

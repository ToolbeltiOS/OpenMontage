#!/usr/bin/env python3
"""Does the 2.5D render tear at a depth discontinuity?

WHAT TEARING IS
---------------
A parallax render displaces each pixel by its depth. Where depth changes
abruptly — the edge of a statue against the hillside behind it — the
foreground moves and the background does not, and the renderer has to put
SOMETHING in the gap that opens between them. What it puts there is the last
column of pixels it had, smeared: a run of identical or near-identical pixels
along the direction of travel.

That run is the measurement. A clean render fills the gap by inpainting or
never opens one; a torn render leaves a streak, and a streak is a row of
pixels whose horizontal gradient is ~0 for many pixels in a row, sitting
beside a large depth step.

TWO PLACES IT HAPPENS, AND ONLY ONE OF THEM IS INTERESTING
----------------------------------------------------------
At the FRAME BORDER, where the parallax pulls in pixels from outside the
photograph, every renderer of this kind smears unless the move is kept inside
a margin. That is not a depth artefact, it is the move being too big for the
frame, and it is reported separately so that fixing it is not confused with
fixing the other one.

INSIDE THE FRAME, at a depth discontinuity, is the one the owner asked about.

    python3 lib/verify_depth_tearing.py <render.mp4> [--depth map.png]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any

#: How many frames to sample. The owner's number.
SAMPLES = 5

#: A run of this many consecutive pixels with almost no horizontal change is
#: a smear rather than a flat surface.
#:
#: CALIBRATED AGAINST A CONTROL, which is the only way to set it. The first
#: value tried was 12 px, and at 12 a STATIC photograph — one that cannot be
#: torn, because nothing moves — reported ninety runs. The detector was
#: measuring the grass and the sky.
#:
#: Swept against three clips of the same photograph: no motion at all, the
#: current 2D push, and the untuned 2.5D render.
#:
#:     run px   static   2D push   2.5D
#:         12       90       153   1720
#:         20       19        30    807
#:         32       10        10    472
#:         48        0         2    289
#:
#: 48 px is 2.5% of a 1920-wide frame: longer than any gradient in a
#: photograph and far shorter than a parallax smear. At 48 the control reads
#: zero, which is what makes a non-zero reading mean something.
RUN_PIXELS = 48

#: "Almost no change", in 8-bit levels per pixel step.
FLAT_LEVEL = 1.5

#: A smear only counts where the picture is not genuinely flat. A run inside
#: a clear sky is a sky. This is the local standard deviation, over the run's
#: neighbourhood, below which the region is called featureless and skipped.
FEATURELESS_STD = 3.0

#: How much of the frame's width counts as "the border", where a parallax
#: render smears for a different reason.
BORDER_PCT = 0.02


def frames(path: str, count: int = SAMPLES):
    """`count` frames spread across the clip, as grayscale arrays."""
    import numpy as np

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,nb_frames", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True).stdout.strip().split(",")
    width, height = int(probe[0]), int(probe[1])
    total = int(probe[2]) if probe[2].strip().isdigit() else 0

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo",
         "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    all_frames = np.frombuffer(raw, dtype="u1").reshape(-1, height, width)
    total = total or len(all_frames)
    idx = [int(round(i * (total - 1) / max(count - 1, 1)))
           for i in range(count)]
    return [(i, all_frames[i]) for i in idx if i < len(all_frames)]


def smear_runs(frame, border_pct: float = BORDER_PCT) -> dict[str, Any]:
    """Runs of near-constant pixels along each row, split by where they are."""
    import numpy as np

    h, w = frame.shape
    margin = max(1, int(w * border_pct))
    diff = np.abs(np.diff(frame.astype(np.int16), axis=1)) <= FLAT_LEVEL

    interior = border = 0
    worst = 0
    for y in range(0, h, 4):                      # every fourth row is plenty
        row = diff[y]
        run = 0
        for x in range(len(row)):
            if row[x]:
                run += 1
                continue
            if run >= RUN_PIXELS:
                start = x - run
                patch = frame[max(0, y - 2):y + 3, max(0, start - 4):x + 4]
                if float(patch.std()) >= FEATURELESS_STD:
                    if start < margin or x > w - margin:
                        border += 1
                    else:
                        interior += 1
                        worst = max(worst, run)
            run = 0
        if run >= RUN_PIXELS:
            border += 1                            # a run to the right edge
    return {"interior_runs": interior, "border_runs": border,
            "worst_interior_run_px": worst}


def baseline(image: str, width: int, height: int,
             samples: int = SAMPLES) -> dict[str, Any]:
    """What the same photograph reads under the treatment being replaced.

    A VIDEO reference is measured as it is. That is the control that matters
    and the one to pass: the 2D push this work replaces moves the same
    photograph over the same seconds and resamples it every frame, and a flat
    zoompan CANNOT tear. Anything it reads is the detector meeting the
    picture, not an artefact. So the question the gate answers is the owner's
    one — does the 2.5D render introduce tearing the 2D treatment does not.

    A still reference is held motionless through the same scale and codec. It
    is the weaker control and it over-reports, because a moving render
    resamples every frame and a static one does not: measured on the Tiryns
    wall, a still control left the flat 2D push reading 51 runs and the 2.5D
    render reading 35.

    THE THRESHOLD DOES NOT TRANSFER BETWEEN PHOTOGRAPHS. 48 px was calibrated
    on a moai-quarry still where it gave zero on a motionless frame. On the
    Tiryns wall and the Sacsayhuamán joint the same threshold reads 361 and
    387 runs on a FLAT 2D ZOOMPAN, which cannot tear — those pictures simply
    contain long smooth stretches of sky and dressed stone.

    So a photograph is its own control: the question is not how many runs a
    render has, it is how many MORE it has than the picture it was made from.
    """
    import tempfile

    if str(image).lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
        got = [smear_runs(f) for _, f in frames(str(image), samples)]
        return {
            "interior_runs": round(sum(g["interior_runs"] for g in got)
                                   / len(got)),
            "border_runs": round(sum(g["border_runs"] for g in got) / len(got)),
            "worst_interior_run_px": max(g["worst_interior_run_px"]
                                         for g in got),
            "how": "the 2D treatment this replaces, on the same photograph",
        }

    # THROUGH THE SAME ENCODE. A PIL resize is not the control: the renders
    # are resampled by a shader or by zoompan and then compressed by h264,
    # and both of those smooth a picture in ways a Lanczos resize does not.
    # Measured with a PIL control, the flat 2D zoompan on the Tiryns wall
    # read WORSE than the 2.5D render — and a zoompan cannot tear. What was
    # being measured was the difference between two resamplers.
    #
    # So the control is the same photograph, held still, pushed through the
    # same scale and the same codec.
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as fh:
        clip = fh.name
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-loop", "1",
         "-i", str(image), "-t", "1", "-r", "30", "-vf",
         f"scale={width}:{height}:force_original_aspect_ratio=increase,"
         f"crop={width}:{height}",
         "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", clip],
        check=True, capture_output=True)
    got = [smear_runs(f) for _, f in frames(clip, 2)]
    return {
        "interior_runs": max(g["interior_runs"] for g in got),
        "border_runs": max(g["border_runs"] for g in got),
        "worst_interior_run_px": max(g["worst_interior_run_px"] for g in got),
        "how": "the same photograph held still, through the same scale and codec",
    }


def check(render: str, samples: int = SAMPLES, reference: str | None = None
          ) -> tuple[list[str], dict[str, Any]]:
    per_frame = []
    size = None
    for index, frame in frames(render, samples):
        size = frame.shape
        measured = smear_runs(frame)
        measured["frame"] = index
        per_frame.append(measured)

    control = None
    if reference and size:
        control = baseline(reference, size[1], size[0], samples)

    raw_interior = sum(f["interior_runs"] for f in per_frame)
    raw_border = sum(f["border_runs"] for f in per_frame)
    worst = max((f["worst_interior_run_px"] for f in per_frame), default=0)

    # What the render ADDS, per frame, over the photograph it was made from.
    if control is not None:
        interior = max(0, round(raw_interior / len(per_frame))
                       - control["interior_runs"])
        border = max(0, round(raw_border / len(per_frame))
                     - control["border_runs"])
    else:
        interior = raw_interior
        border = raw_border

    problems: list[str] = []
    if interior:
        problems.append(
            f"{interior} stretched-pixel run(s) inside the frame beyond what "
            f"the source photograph itself reads, the longest {worst}px. "
            f"That is "
            f"the renderer smearing the last pixel it had across a gap that "
            f"opened at a depth discontinuity — the foreground moved and the "
            f"background did not.")
    if border:
        problems.append(
            f"{border} stretched-pixel run(s) at the frame border. The move "
            f"is pulling in pixels from outside the photograph; keep it "
            f"inside a margin (raise the base zoom) rather than inpainting "
            f"the edge.")
    return problems, {
        "samples": len(per_frame), "run_pixels": RUN_PIXELS,
        "interior_runs": interior, "border_runs": border,
        "raw_interior_runs": raw_interior, "raw_border_runs": raw_border,
        "control": control,
        "measured_against": "the source photograph" if control else
                            "an absolute threshold (no --reference given)",
        "worst_interior_run_px": worst, "per_frame": per_frame,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("render")
    ap.add_argument("--samples", type=int, default=SAMPLES)
    ap.add_argument("--reference",
                    help="the control: the 2D render this replaces (best), "
                         "or the source still (weaker, over-reports)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    problems, measured = check(args.render, args.samples, args.reference)
    if args.json:
        print(json.dumps(measured, indent=1))
    else:
        ctrl = measured.get("control")
        print(f"{measured['samples']} frames: "
              f"{measured['interior_runs']} interior smear runs over control "
              f"(worst {measured['worst_interior_run_px']}px), "
              f"{measured['border_runs']} at the border"
              + (f"  [control {ctrl['interior_runs']}/"
                 f"{ctrl['border_runs']}, raw "
                 f"{round(measured['raw_interior_runs']/measured['samples'])}/"
                 f"{round(measured['raw_border_runs']/measured['samples'])}]"
                 if ctrl else "  [no control]"))
    for p in problems:
        print("  -", p)
    print("DEPTH TEARING:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

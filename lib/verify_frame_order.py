"""Is every frame the frame it should be, and is it where it should be?

WHY THIS CHECK EXISTS
---------------------
`verify_frame_motion` asks whether the picture moves. The act 2 demo passed it
and was still wrong: the picture moved, the timestamps were exact, there were
no duplicates — and the frames were in the wrong ORDER.

The film look runs as a second pass over a rendered frame sequence, and
`<ThreeCanvas>` draws once per frame, in an effect keyed on the frame number,
which fires before the image for that frame has decoded. Nothing redraws
afterwards, so the capture kept an earlier frame's texture. Measured on a
sequence with its own index burned into every frame: 118 of 120 output frames
carried the wrong source frame, lagging three to five and locally shuffled.
On screen that is a cliff appearing for one frame inside a diagram, over and
over — which reads as a stutter and is invisible to every other check here.

THE RULES
---------
1. **No isolated black frame.** Fewer than three consecutive black frames is
   never deliberate: the fade through black at an act boundary lasts about a
   second, and one black frame in the middle of a shot is a frame from
   somewhere else.
2. **No out-of-order frame.** A frame whose difference to BOTH its neighbours
   is more than four times the local median, WHILE those two neighbours
   resemble each other, is a frame that does not belong where it sits. A cut
   has the first shape on one side only, so it never fires; a dissolve has it
   on both sides but keeps travelling, so its neighbours do not resemble each
   other either. That second clause is what separates them — measured, a
   dissolve scores 8.35x and up, an inserted frame 1.3 to 1.8x.
3. **The delivered film matches the picture render frame for frame**, when
   that reference is available — which in this pipeline it always is, because
   the look is a pass over it. Compared as difference profiles rather than
   pixels, so a grade, a vignette and grain do not count as a mismatch.

Rule 3 is the one with teeth; rules 1 and 2 are what can be checked when
there is only one file. All three are calibrated in
`tests/lib/test_frame_order.py` against a known-good render with defects
deliberately injected into it.

What rule 3 cannot see: a permutation among frames whose motion is identical,
because it compares motion profiles rather than pixels. Matching each frame to
its own reference frame directly was tried instead and is worse than useless
here — through the grade, the vignette and the grain it called 136 of 584
frames wrong on a CORRECT render and 100 on a scrambled one, the margins
being four decimal places wide. A permutation invisible to the profile is also
a permutation invisible on screen; one that shows is one that changes how the
picture moves.

    python3 lib/verify_frame_order.py <film.mp4> [--reference picture.mp4]
                                      [--cuts props.json] [--map]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any

#: Frames are compared at this size, as in verify_frame_motion: big enough
#: that a sub-pixel move is not thrown away by the downscale.
MEASURE_SIZE = (480, 270)

#: Mean luma below which a frame counts as black. Measured through the full
#: look chain, which is where it has to hold: a black frame comes out at
#: EXACTLY 0.0 — the vignette cannot lift it and the grain is an overlay
#: blend, which leaves black alone — while the darkest real content, an
#: authored card under the act 2 grade, sits at 7.2. Four is near the midpoint.
BLACK_LUMA = 4.0

#: Shorter than this many consecutive black frames is not a planned hold.
MIN_BLACK_RUN = 3

#: How much more different than its neighbourhood a frame has to be, on BOTH
#: sides, before it is a candidate for being out of order.
OUT_OF_ORDER_RATIO = 4.0

#: ...and how much its two NEIGHBOURS must resemble each other for it to be
#: called out of order rather than a dissolve.
#:
#: This is the discriminator, and the boundary window below is only a second
#: net. A frame that does not belong sits between two frames that are ordinary
#: neighbours of each other, so skipping over it changes almost nothing. A
#: dissolve is the opposite: it keeps moving, so its frames differ from each
#: other too. Measured over the whole demo — 76 both-sides spikes on two
#: known-good renders, and two deliberately injected defects:
#:
#:     legitimate (dissolves, entrance animations)   8.35x and up
#:     an inserted black frame                       1.82x
#:     a frame borrowed from 53 seconds later        1.28x
#:
#: 3.5 is between them with better than twice the margin on each side.
NEIGHBOURS_RESEMBLE_RATIO = 3.5

#: Half-width of the neighbourhood the median is taken over, in frames.
LOCAL_WINDOW = 15

#: How far either side of a declared cut the rule is suspended.
#:
#: Deliberately narrow. The first version of this exempted 0.75s either side,
#: because that is how far from a boundary a legitimate spike was measured to
#: reach — and a frame borrowed from another scene, injected 0.27s from a cut
#: to test the check, walked straight through the hole. With the neighbour
#: test above doing the work, a hard cut cannot fire the rule anyway: it is
#: one-sided, and the rule needs both sides. Three frames is for a transition
#: that lands exactly on a boundary.
BOUNDARY_WINDOW_S = 0.1

#: Below this correlation between the delivered film's difference profile and
#: the picture render's, the frames are not in the same order. Measured: a
#: scrambled render scores 0.19, a correct one 0.9995.
MIN_REFERENCE_CORRELATION = 0.95


def profile(path: str, size: tuple[int, int] = MEASURE_SIZE):
    """Per-frame mean luma, the difference to the frame before, and the
    difference ACROSS each frame — frame i-1 against frame i+1, which is what
    says whether a frame's neighbours belong together without it."""
    import numpy as np

    width, height = size
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={width}:{height}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, dtype="uint8").reshape(-1, height, width).astype("float32")
    luma = frames.mean(axis=(1, 2))
    diff = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
    # across[i - 1] is the difference between frame i-1 and frame i+1
    across = (np.abs(frames[2:] - frames[:-2]).mean(axis=(1, 2))
              if len(frames) > 2 else np.zeros(0, dtype="float32"))
    return luma, diff, across


def luma_map(luma, fps: float = 30.0, per_row: int = 30) -> list[str]:
    """The film as one character per frame, so the cuts can be seen.

    `#` is black, `+` nearly so, and `.` through `@` are eight steps of
    brightness. A cut is a step in the row; a frame from somewhere else is a
    single character that does not belong to either side of it.
    """
    def ch(v: float) -> str:
        if v < BLACK_LUMA:
            return "#"
        if v < 12:
            return "+"
        return ".:-=*oO@"[min(7, int(v / 32))]

    rows = []
    for start in range(0, len(luma), per_row):
        chunk = luma[start:start + per_row]
        rows.append(f"{start / fps:7.1f}s |" + "".join(ch(float(v)) for v in chunk))
    return rows


def _runs(flags) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    start = None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i - start))
            start = None
    if start is not None:
        out.append((start, len(flags) - start))
    return out


def boundaries(cuts: list[dict[str, Any]] | None) -> list[float]:
    """Every declared cut boundary, in seconds."""
    if not cuts:
        return []
    edges = {0.0}
    for cut in cuts:
        for key in ("in_seconds", "out_seconds"):
            if cut.get(key) is not None:
                edges.add(float(cut[key]))
    return sorted(edges)


def check(film: str, cuts: list[dict[str, Any]] | None = None,
          reference: str | None = None, fps: float = 30.0
          ) -> tuple[list[str], dict[str, Any]]:
    import numpy as np

    luma, diff, across = profile(film)
    problems: list[str] = []
    edges = boundaries(cuts)

    # 1. isolated black frames
    black = _runs(luma < BLACK_LUMA)
    isolated = [(a, n) for a, n in black if n < MIN_BLACK_RUN]
    for a, n in isolated:
        problems.append(
            f"{a / fps:.2f}s: {n} black frame{'s' if n > 1 else ''} on their own — "
            f"a hold on black lasts about a second, so this is a frame from "
            f"somewhere else")

    # 2. frames that belong to neither neighbour, while the neighbours belong
    #    to each other
    out_of_order = []
    for i in range(1, len(diff)):
        lo, hi = max(0, i - LOCAL_WINDOW), min(len(diff), i + LOCAL_WINDOW + 1)
        local = float(np.median(diff[lo:hi])) or 1e-6
        if diff[i - 1] <= OUT_OF_ORDER_RATIO * local or diff[i] <= OUT_OF_ORDER_RATIO * local:
            continue
        if i - 1 >= len(across):
            continue
        skip = float(across[i - 1])
        if skip >= NEIGHBOURS_RESEMBLE_RATIO * local:
            continue                       # still travelling: a dissolve
        t = i / fps
        if edges and min(abs(t - e) for e in edges) <= BOUNDARY_WINDOW_S:
            continue                       # a declared cut
        out_of_order.append({
            "seconds": round(t, 3),
            "to_previous": round(float(diff[i - 1] / local), 1),
            "to_next": round(float(diff[i] / local), 1),
            "across": round(skip / local, 2),
            "luma": round(float(luma[i]), 1),
        })
        problems.append(
            f"{t:.2f}s: this frame differs from both its neighbours by "
            f"{diff[i - 1] / local:.0f}x and {diff[i] / local:.0f}x the local "
            f"median, while the two neighbours differ from EACH OTHER by only "
            f"{skip / local:.1f}x — they are consecutive and this frame is "
            f"not one of them")

    # 3. against the picture render it is supposed to be a pass over
    correlation = None
    if reference:
        _, ref_diff, _ = profile(reference)
        n = min(len(diff), len(ref_diff))
        if n < 2:
            problems.append("the reference render is too short to compare")
        else:
            correlation = float(np.corrcoef(diff[:n], ref_diff[:n])[0, 1])
            if correlation < MIN_REFERENCE_CORRELATION:
                problems.append(
                    f"the delivered film's motion profile correlates "
                    f"{correlation:.3f} with the picture render it is a pass "
                    f"over (floor {MIN_REFERENCE_CORRELATION}) — the frames "
                    f"are not in the same order")

    measured = {
        "frames": int(len(luma)),
        "black_frames": int((luma < BLACK_LUMA).sum()),
        "black_runs": [{"start_seconds": round(a / fps, 2), "frames": n}
                       for a, n in black],
        "isolated_black_runs": len(isolated),
        "out_of_order": out_of_order[:40],
        "out_of_order_count": len(out_of_order),
        "reference_correlation": None if correlation is None else round(correlation, 4),
        "declared_boundaries": len(edges),
        "luma_min": round(float(luma.min()), 2),
        "luma_median": round(float(np.median(luma)), 2),
        "luma_map": luma_map(luma, fps),
    }
    return problems, measured


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("film")
    ap.add_argument("--reference", default=None,
                    help="the picture render the look is a pass over")
    ap.add_argument("--cuts", default=None,
                    help="render_props/edit_decisions JSON, for the declared cuts")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--map", action="store_true", help="print the luma map")
    args = ap.parse_args()

    cuts = None
    if args.cuts:
        blob = json.loads(open(args.cuts, encoding="utf-8").read())
        cuts = blob["cuts"] if isinstance(blob, dict) else blob

    problems, measured = check(args.film, cuts, args.reference, args.fps)
    if args.map:
        print("LUMA MAP — one character per frame, 30 per row")
        print("  # black   + under 12   . : - = * o O @  brightening")
        for row in measured["luma_map"]:
            print(row)
        print()
    print(f"{measured['frames']} frames, {measured['black_frames']} black "
          f"({measured['isolated_black_runs']} isolated), "
          f"{measured['out_of_order_count']} out of place, "
          f"reference correlation {measured['reference_correlation']}")
    for p in problems[:20]:
        print("  -", p)
    if len(problems) > 20:
        print(f"  ... and {len(problems) - 20} more")
    print("FRAME ORDER:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

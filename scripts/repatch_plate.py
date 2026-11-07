"""Re-render only the frames a composition change touches, and splice them in.

WHY THIS EXISTS
---------------
2026-11-07, king-tut. Three delivery gates failed, and two of them were one
defect: `TextCard`, `StatCard` and `ActTitleCard` painted their words with no
type class and then stopped moving. Eighteen cuts, 3,643 frames, 9.9% of the
film.

The plate those frames belong to had just taken two hours and forty-seven
minutes to render, and the other 33,160 frames in it were correct. Rendering
all 36,803 again to fix 3,643 is most of an evening spent reproducing bytes
that already existed.

So this renders the ranges, puts them into the stills the look pass actually
reads, and rebuilds the plate from those stills.

WHY THE STILLS ARE THE REAL TARGET
----------------------------------
`render_film.py` runs the look pass over `public/frames_<project>/f_*.jpg`,
not over `plate.mp4` — WebGL cannot sample a <video>. The delivered film is
therefore made from the stills, and the plate is read afterwards by the
gates. Patching the stills is patching what ships; rebuilding the plate from
them keeps what the gates read in step with it, and means plate purity is
measured on the same pixels the film was made from rather than on a second
encode of them.

The unchanged stills are not touched, so nothing outside the named cuts is
re-encoded, re-rendered, or moved.

    python3 scripts/repatch_plate.py king-tut --types text_card,stat_card
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from film_render import (COMPOSER, FPS, frame_count, props_for_layer,  # noqa: E402
                         render_plate, run, verified_stills, verified_video)

#: Frames rendered either side of a changed cut.
#:
#: A cut's own range is [round(in*fps), that + round(duration*fps) - 1], which
#: is what `Explainer` gives its `<Sequence>`. The padding is for the fade a
#: transition puts at a boundary: it is rendered inside the cut that owns it,
#: but a neighbour's last frames are cheap and a render is deterministic, so
#: paying for ten of them either side costs nothing and removes the question.
PAD = 10


def ranges_for(cuts: list[dict[str, Any]], wanted: set[str], by: str,
               total: int, pad: int = PAD) -> list[tuple[int, int, list[str]]]:
    """The merged, padded frame ranges the named cuts occupy."""
    spans: list[tuple[int, int, str]] = []
    for cut in cuts:
        key = cut.get("id") if by == "id" else cut.get("type")
        if key not in wanted:
            continue
        start = round(float(cut["in_seconds"]) * FPS)
        length = round((float(cut["out_seconds"]) - float(cut["in_seconds"])) * FPS)
        spans.append((max(0, start - pad),
                      min(total - 1, start + length - 1 + pad),
                      str(cut.get("id"))))
    spans.sort()
    merged: list[tuple[int, int, list[str]]] = []
    for a, b, cid in spans:
        if merged and a <= merged[-1][1] + 1:
            last = merged[-1]
            merged[-1] = (last[0], max(last[1], b), last[2] + [cid])
        else:
            merged.append((a, b, [cid]))
    return merged


def stills_from(segment: Path, frames_dir: Path, first: int) -> None:
    """Write a rendered range over the stills it replaces.

    `-start_number` is the still's own number, and the stills are one-based:
    `f_00001.jpg` is frame 0. Getting this wrong writes a correct render into
    the wrong seconds of the film, which no gate would catch — frame order
    correlates the delivered file against the plate, and both would have
    moved together.
    """
    run(["ffmpeg", "-v", "error", "-y", "-i", str(segment),
         "-q:v", "2", "-start_number", str(first + 1),
         str(frames_dir / "f_%05d.jpg")])


#: How far either side of a seam the alignment is measured, in frames.
#:
#: The outer padding only. A range is padded by `PAD` frames of the
#: NEIGHBOURING cut, which this change does not touch, so those frames are a
#: re-render of pixels that already exist and must come back identical. The
#: frames inside the named cut are supposed to differ — that is the point —
#: so they are not compared to anything.
SEAM_WINDOW = PAD

#: A seam is aligned when matching at no shift beats matching at one frame
#: either way by this factor.
#:
#: Relative, not absolute, because the absolute number depends on the picture:
#: a seam in a slow dissolve differs from one in a hard cut. Measured on a
#: deliberately mis-spliced range, shifting by one frame reads 20 to 400 times
#: the aligned difference; on an aligned one the ratio is under 0.05 in the
#: other direction. There is no overlap anywhere near 4.
SEAM_MARGIN = 4.0

#: The frame-order gate's own floor, applied to the seam window: the new
#: plate's motion profile against the old one's, where the two are supposed
#: to be the same film.
MIN_SEAM_CORRELATION = 0.95


def _stills(frames_dir: Path, first: int, last: int):
    """A run of stills as the gates read them: 480x270, grey."""
    import numpy as np
    from PIL import Image

    out = []
    for n in range(first, last + 1):
        path = frames_dir / f"f_{n + 1:05d}.jpg"
        if not path.exists():
            raise SystemExit(f"still {path.name} is missing")
        out.append(np.asarray(
            Image.open(path).convert("L").resize((480, 270)), dtype="float32"))
    return np.stack(out)


def seam_alignment(before, after) -> dict[str, float]:
    """Does the patched run sit where the run it replaced sat?

    A ONE-FRAME OFFSET IS THE DEFECT A SPLICE CAN INTRODUCE AND A RE-RENDER
    CANNOT. `-start_number` is off by one, or a range is rendered from a-1,
    and the result is a correct picture in the wrong frame: every gate still
    passes, because the delivered film and the plate were patched from the
    same wrong place and agree with each other perfectly.

    So the patched frames are compared with the ORIGINAL frames they
    overwrote, at three shifts. These are padding frames — a neighbouring
    cut, untouched by the change — so at the right shift they are the same
    picture and the difference collapses.
    """
    import numpy as np

    def mad(shift: int) -> float:
        if shift < 0:
            a, b = before[-shift:], after[:shift]
        elif shift > 0:
            a, b = before[:-shift], after[shift:]
        else:
            a, b = before, after
        if not len(a):
            return float("inf")
        return float(np.abs(a - b).mean())

    aligned = mad(0)
    off = min(mad(-1), mad(1))
    # The frame-order gate's measure, on the window where the two renders are
    # supposed to be the same film.
    corr = 1.0
    if len(before) > 2:
        d_before = np.abs(np.diff(before, axis=0)).mean(axis=(1, 2))
        d_after = np.abs(np.diff(after, axis=0)).mean(axis=(1, 2))
        if d_before.std() > 1e-6 and d_after.std() > 1e-6:
            corr = float(np.corrcoef(d_before, d_after)[0, 1])
    return {"aligned": aligned, "shifted": off,
            "margin": float("inf") if aligned <= 0 else off / aligned,
            "correlation": corr}


def check_seams(seams: list[dict[str, Any]]) -> list[str]:
    """Every seam, reported whether it passes or not."""
    problems = []
    for seam in seams:
        m = seam["measured"]
        print(f"   seam {seam['edge']:>4} of {seam['range']}: "
              f"aligned {m['aligned']:.4f}, one frame off {m['shifted']:.4f} "
              f"({m['margin']:.1f}x), motion correlation {m['correlation']:.4f}")
        if m["margin"] < SEAM_MARGIN:
            problems.append(
                f"{seam['range']} {seam['edge']}: the patched frames match "
                f"the frames they replaced {m['aligned']:.4f} at no shift and "
                f"{m['shifted']:.4f} one frame either way — only "
                f"{m['margin']:.1f}x better, under {SEAM_MARGIN}x. A splice "
                f"that landed one frame out looks exactly like this.")
        if m["correlation"] < MIN_SEAM_CORRELATION:
            problems.append(
                f"{seam['range']} {seam['edge']}: the motion profile across "
                f"the seam correlates {m['correlation']:.4f} with the plate it "
                f"replaced (floor {MIN_SEAM_CORRELATION})")
    return problems


def rebuild_plate(frames_dir: Path, dest: Path, count: int) -> None:
    """The plate, from the stills the film is made of."""
    tmp = dest.with_suffix(".repatch.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS),
         "-start_number", "1", "-i", str(frames_dir / "f_%05d.jpg"),
         "-frames:v", str(count), "-c:v", "libx264", "-crf", "16",
         "-preset", "medium", "-pix_fmt", "yuv420p", str(tmp)])
    tmp.replace(dest)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--types", default="",
                    help="cut types whose frames changed, comma separated")
    ap.add_argument("--cuts", default="",
                    help="cut ids whose frames changed, comma separated")
    ap.add_argument("--pad", type=int, default=PAD)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the ranges and the cost, render nothing")
    args = ap.parse_args()

    types = {w.strip() for w in args.types.split(",") if w.strip()}
    ids = {w.strip() for w in args.cuts.split(",") if w.strip()}
    if bool(types) == bool(ids):
        raise SystemExit("name either --types or --cuts, and only one of them")

    project = ROOT / "projects" / args.project
    props_path = project / "artifacts" / "render_props.json"
    cuts = json.loads(props_path.read_text())["cuts"]
    count = frame_count(cuts, FPS)
    work = COMPOSER / "out" / args.project
    picture = work / "plate.mp4"
    frames_dir = COMPOSER / "public" / f"frames_{args.project}"

    known = {c.get("type") for c in cuts} | {c.get("id") for c in cuts}
    unknown = (types | ids) - known
    if unknown:
        raise SystemExit(f"this film has no {', '.join(sorted(unknown))}")

    merged = ranges_for(cuts, types or ids, "type" if types else "id",
                        count, args.pad)
    if not merged:
        raise SystemExit("nothing named matched a cut")
    changed = sum(b - a + 1 for a, b, _ in merged)
    print(f"{args.project}: {len(merged)} ranges, {changed} of {count} frames "
          f"({100 * changed / count:.1f}%)")
    for a, b, who in merged:
        print(f"   {a:6d}-{b:6d}  {b - a + 1:5d} frames  {a / FPS:8.2f}s  "
              f"{','.join(who)}")
    if args.dry_run:
        return 0

    # Both inputs have to be the film they claim to be BEFORE anything is
    # overwritten: a patch written into a half-extracted stills directory, or
    # beside a truncated plate, is not recoverable without the full render
    # this script exists to avoid.
    ok, why = verified_stills(frames_dir, count)
    if not ok:
        raise SystemExit(f"the stills are not whole ({why}); re-extract them "
                         f"from the plate before patching")
    ok, why = verified_video(picture, count)
    if not ok:
        raise SystemExit(f"the plate is not whole ({why})")

    props = props_for_layer(props_path, "plate", work, args.project)
    seams: list[dict[str, Any]] = []
    for a, b, who in merged:
        segment = work / f"patch_{a:05d}_{b:05d}.mp4"
        label = f"{a}-{b}"
        print(f"   rendering {label} ({','.join(who)})")
        # The frames about to be overwritten, kept so the splice can be
        # checked against them. Only the padding windows: they are a
        # neighbouring cut this change does not touch, so the patch must
        # reproduce them exactly, at exactly the same indices.
        head = min(SEAM_WINDOW, (b - a + 1) // 2)
        before_head = _stills(frames_dir, a, a + head - 1) if head > 1 else None
        before_tail = _stills(frames_dir, b - head + 1, b) if head > 1 else None

        render_plate(props, segment, count, cuts, frames=(a, b))
        stills_from(segment, frames_dir, a)
        segment.unlink()

        if before_head is not None:
            seams.append({"range": label, "edge": "head", "measured":
                          seam_alignment(before_head,
                                         _stills(frames_dir, a, a + head - 1))})
            seams.append({"range": label, "edge": "tail", "measured":
                          seam_alignment(before_tail,
                                         _stills(frames_dir, b - head + 1, b))})

    # ----- the splice, checked before anything is built on top of it -----
    ok, why = verified_stills(frames_dir, count)
    if not ok:
        raise SystemExit(f"the stills are no longer whole after patching: {why}")
    print(f"   checking {len(seams)} seams")
    problems = check_seams(seams)
    if problems:
        for problem in problems:
            print("   SEAM FAIL:", problem)
        raise SystemExit(
            "the splice is not aligned. The stills directory now holds a "
            "patch that cannot be trusted; re-extract it from the plate "
            "(which is untouched) before trying again.")

    print("   rebuilding the plate from the stills")
    rebuild_plate(frames_dir, picture, count)
    ok, why = verified_video(picture, count)
    if not ok:
        raise SystemExit(f"the rebuilt plate does not verify: {why}")
    print(f"   plate: {why}")
    print(f"   {len(seams)} seams aligned, "
          f"worst margin {min(s['measured']['margin'] for s in seams):.1f}x, "
          f"lowest correlation "
          f"{min(s['measured']['correlation'] for s in seams):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

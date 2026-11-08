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
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from buildability import frame_span  # noqa: E402
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
    """The merged, padded frame ranges the named cuts occupy.

    `frame_span` IS THE COMPOSITION'S OWN ARITHMETIC — both edges rounded
    from the timeline, JavaScript's rounding. A patch laid out by any other
    sum writes the right pixels at the wrong frame, and the frame a cut
    gained when that arithmetic was fixed is precisely the one that most
    needs rewriting.
    """
    spans: list[tuple[int, int, str]] = []
    for cut in cuts:
        key = cut.get("id") if by == "id" else cut.get("type")
        if key not in wanted:
            continue
        start, last = frame_span(cut, FPS)
        spans.append((max(0, start - pad),
                      min(total - 1, last + pad),
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


def spans_for(cuts: list[dict[str, Any]], wanted: set[str], by: str
              ) -> list[tuple[int, int]]:
    """The frames a changed cut OWNS — its padding is not one of them.

    The padding is rendered, because it is the only witness that the splice
    landed where it should. It is never WRITTEN, because a frame outside the
    cuts this change touches has no business being replaced by a second
    render of itself:

        TitleSequence paints its backdrop with a CSS `backgroundImage:
        url(...)`, which — unlike Remotion's `<Img>` — does not hold the
        frame until the image decodes. Measured on c006, whose first frame
        is 1384: a render of 1384-1560 at concurrency 4 matched the plate on
        all 177 frames (max 0.2555), and the same range at concurrency 1 came
        back wrong on 1385, 1386 and 1387 (2.518, 4.226, 5.428). Same props,
        same composition, same machine, different timing.

    None of the eighteen cuts this change touches carries an image at all —
    they are flat colour and procedural plate — so the race cannot reach a
    frame that gets written. Leaving the padding alone keeps it that way.
    """
    out = []
    for cut in cuts:
        key = cut.get("id") if by == "id" else cut.get("type")
        if key not in wanted:
            continue
        out.append(frame_span(cut, FPS))
    return sorted(out)


def stills_from(segment: Path, frames_dir: Path, first: int,
                skip: int = 0) -> None:
    """Write a rendered range over the stills it replaces.

    `-start_number` is the still's own number, and the stills are one-based:
    `f_00001.jpg` is frame 0. Getting this wrong writes a correct render into
    the wrong seconds of the film, which no gate would catch — frame order
    correlates the delivered file against the plate, and both would have
    moved together.

    `skip` drops the lead-in frames `render_plate` renders in front of the
    range so that the first frame the caller asked for is not the first frame
    the renderer painted. They are dropped HERE rather than trimmed from the
    segment, so the frame that lands on `first` is the frame the renderer
    produced for `first` and nothing has been re-encoded in between.
    """
    select = ["-vf", rf"select='gte(n\,{skip})'", "-vsync", "0"] if skip else []
    run(["ffmpeg", "-v", "error", "-y", "-i", str(segment), *select,
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

#: A frame of padding is wrong when its difference from the frame it
#: overwrote stands this far above the rest of its own window.
#:
#: MEASURED, and the first version of this was measured on the wrong thing.
#: It compared the window as a whole at shifts of -1, 0 and +1 and demanded
#: that no shift win by 4x, which is what synthetic noise does. Real film at
#: 30fps does not: a documentary cut drifting at 1.2%/s barely changes
#: between consecutive frames, so a one-frame shift barely changes the
#: difference either. On king-tut's own seams that rule fired on 10 of 36,
#: nine of them correct — and the one real defect it found, it found for the
#: wrong reason.
#:
#: Per frame against its own window is far sharper, because the thing being
#: looked for is one frame that does not belong:
#:
#:     head padding of 1548-1747, per-frame difference from the plate
#:         frame 1548   6.2876      <- the defect
#:         frame 1549   0.1552
#:         frame 1550   0.0848
#:         frames 1551-1557  0.0776 down to 0.0000
#:
#:     tail padding of the same range, all correct
#:         frames 1738-1747  0.0004, 0.0316, 0.1676 ... up to 0.4744
#:
#: A bad frame is 200x its window's median; the worst correct frame in any
#: window on this film is 1.7x. Six is nowhere near either.
SEAM_OUTLIER = 6.0

#: The smallest per-frame difference worth calling a defect.
#:
#: Without it the outlier rule has no floor: a window whose frames all agree
#: to 0.0001 would fail on one frame at 0.002, which is two encodes being
#: two encodes. The worst CORRECT per-frame difference measured anywhere on
#: this film's 36 seams is 0.78 and the defect read 6.29.
SEAM_FLOOR = 1.0

#: And a ceiling on the window's MEDIAN, because a window where every frame
#: is equally wrong has no outlier in it.
#:
#: The worst correct per-frame difference measured anywhere on this film's
#: 36 seams is 0.78, on a bright detailed photograph where the two encodes
#: disagree most. The defect read 6.29. 2.0 sits between them with more than
#: twice the headroom either way.
SEAM_CEILING = 2.0

#: The shift test is kept, because an offset that moved a WHOLE window would
#: pass both rules above: every frame would be wrong by the same amount, so
#: there would be no outlier, and on slow content no frame need exceed the
#: ceiling. What it asserts is only that the best match is at no shift —
#: not by how much, which is the part that was not measurable.
#:
#: Measured over all 36 seams of this patch: 35 put their minimum at 0, and
#: the one that did not was the defect above.
SEAM_SHIFTS = (-2, -1, 0, 1, 2)

#: How many times a range may be rendered before the splice is abandoned.
#:
#: The witness frames can fail for a reason that is not the splice: the
#: composition has an asset race (see `spans_for`) and a neighbouring cut can
#: come back different through no fault of this patch. Retrying is the honest
#: response to a race; retrying forever is not.
ATTEMPTS = 3


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


def seam_alignment(before, after) -> dict[str, Any]:
    """Does the patched run sit where the run it replaced sat, frame for frame?

    A ONE-FRAME OFFSET IS THE DEFECT A SPLICE CAN INTRODUCE AND A RE-RENDER
    CANNOT. `-start_number` is off by one, or a range is rendered from a-1,
    and the result is a correct picture in the wrong frame: every gate still
    passes, because the delivered film and the plate were patched from the
    same wrong place and agree with each other perfectly.

    A SINGLE WRONG FRAME IS THE OTHER ONE, and it is the one that actually
    happened — the first frame a range render paints, before its backdrop
    image has loaded. Nothing downstream would report it either: one frame
    in 36,803, inside a fade, is not a freeze and not a dropped frame.

    So the padding is compared with the frames it overwrote twice over: each
    frame against its own window, which finds the one that does not belong,
    and the window against itself at five shifts, which finds a run that
    moved.
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

    per_frame = np.abs(before - after).mean(axis=(1, 2))
    median = float(np.median(per_frame))
    worst = int(np.argmax(per_frame))
    curve = {s: mad(s) for s in SEAM_SHIFTS}
    best = min(curve, key=lambda k: curve[k])
    return {"per_frame": [round(float(v), 4) for v in per_frame],
            "median": median, "worst": float(per_frame[worst]),
            "worst_at": worst, "best_shift": best,
            "curve": {k: round(v, 4) for k, v in curve.items()}}


def check_seams(seams: list[dict[str, Any]]) -> list[str]:
    """Every seam, reported whether it passes or not."""
    problems = []
    for seam in seams:
        m = seam["measured"]
        where = f"{seam['range']} {seam['edge']}"
        print(f"   seam {seam['edge']:>4} of {seam['range']}: "
              f"worst frame {m['worst']:.4f} (median {m['median']:.4f}), "
              f"best shift {m['best_shift']:+d}")
        if m["median"] > SEAM_CEILING:
            problems.append(
                f"{where}: every frame of the padding differs from the frame "
                f"it overwrote, by {m['median']:.4f} at the median against a "
                f"ceiling of {SEAM_CEILING}. The padding is a cut this change "
                f"does not touch, so the whole window has to come back the "
                f"same.")
        allowed = max(SEAM_FLOOR, SEAM_OUTLIER * m["median"])
        if m["worst"] > allowed:
            problems.append(
                f"{where}: frame {m['worst_at']} of the padding differs from "
                f"the frame it overwrote by {m['worst']:.4f}, against a "
                f"median of {m['median']:.4f} across the window and a ceiling "
                f"of {allowed:.4f}. The padding is a cut this change does not "
                f"touch, so it has to come back the same.")
        if m["best_shift"] != 0:
            problems.append(
                f"{where}: the patched frames match the frames they replaced "
                f"best at a shift of {m['best_shift']:+d}, not at 0 "
                f"({m['curve']}). A splice that landed in the wrong place "
                f"looks exactly like this.")
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
    spans = spans_for(cuts, types or ids, "type" if types else "id")
    written = sum(b - a + 1 for a, b in spans)
    print(f"   {written} frames will be written; the rest of each range is "
          f"rendered as a witness and left alone")
    seams: list[dict[str, Any]] = []
    for a, b, who in merged:
        label = f"{a}-{b}"
        head = min(SEAM_WINDOW, (b - a + 1) // 2)
        before_head = _stills(frames_dir, a, a + head - 1)
        before_tail = _stills(frames_dir, b - head + 1, b)
        staging = work / f"patch_{a:05d}_{b:05d}"

        for attempt in range(1, ATTEMPTS + 1):
            segment = work / f"patch_{a:05d}_{b:05d}.mp4"
            if staging.exists():
                shutil.rmtree(staging)
            staging.mkdir(parents=True)
            print(f"   rendering {label} ({','.join(who)})"
                  + (f", attempt {attempt}" if attempt > 1 else ""))
            rendered_from = render_plate(props, segment, count, cuts, frames=(a, b))
            stills_from(segment, staging, a, skip=a - rendered_from)
            segment.unlink()
            measured = [
                {"range": label, "edge": "head", "measured": seam_alignment(
                    before_head, _stills(staging, a, a + head - 1))},
                {"range": label, "edge": "tail", "measured": seam_alignment(
                    before_tail, _stills(staging, b - head + 1, b))},
            ]
            problems = check_seams(measured)
            if not problems:
                break
            for problem in problems:
                print("   SEAM FAIL:", problem)
            if attempt == ATTEMPTS:
                shutil.rmtree(staging, ignore_errors=True)
                raise SystemExit(
                    f"{label} did not splice cleanly in {ATTEMPTS} attempts. "
                    f"Nothing has been written: the stills and the plate are "
                    f"as they were.")
            print(f"   {label}: retrying — the witness frames did not come "
                  f"back the same")

        # Only now, and only the frames the changed cuts own.
        moved = 0
        for first, last in spans:
            if first > b or last < a:
                continue
            for n in range(max(first, a), min(last, b) + 1):
                name = f"f_{n + 1:05d}.jpg"
                shutil.copyfile(staging / name, frames_dir / name)
                moved += 1
        shutil.rmtree(staging)
        print(f"   {label}: {moved} frames written, seams clean")
        seams += measured

    # ----- the splice, checked before anything is built on top of it -----
    ok, why = verified_stills(frames_dir, count)
    if not ok:
        raise SystemExit(f"the stills are no longer whole after patching: {why}")

    print("   rebuilding the plate from the stills")
    rebuild_plate(frames_dir, picture, count)
    ok, why = verified_video(picture, count)
    if not ok:
        raise SystemExit(f"the rebuilt plate does not verify: {why}")
    print(f"   plate: {why}")
    print(f"   {len(seams)} seams aligned, worst frame "
          f"{max(s['measured']['worst'] for s in seams):.4f}, "
          f"every one of them matching best at no shift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Does an annotation's anchor stay on the feature it points at?

An annotation's two ends live in different coordinate systems: the anchor is a
point on the photograph and travels with it, the label is type and is locked,
and the leader is redrawn between them every frame. That is easy to assert and
easy to get subtly wrong — a sign or an ordering wrong in the projection puts
every anchor somewhere plausible and wrong.

So this does not check the arithmetic. It renders the first and last frame of
a real annotated still, finds where the FEATURE went by matching a patch of
the photograph itself, finds where the DOT went by looking for the accent
colour, and compares the two displacements. It also measures what the dot
would have done locked, which is the control: without it, a check that passes
proves nothing about whether anything moved at all.

    python scripts/check_anchor_tracking.py --project <id> --cuts c089 c177
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

COMPOSER = ROOT / "remotion-composer"
ENTRY = "src/index.tsx"
FPS = 30

#: Half-width of the patch of photograph matched between the two frames.
PATCH = 90

#: The radius AnnotatedStill draws the anchor dot at. The dot is identified by
#: being this size, not by being the biggest thing in the difference — a
#: fragment of the label panel's edge measured 207px against the dot's 163 and
#: won on area alone, putting the anchor 121px from where it was.
ANCHOR_RADIUS_PX = 7

#: How close the dot has to land to the feature, in pixels. A patch match on a
#: scaled photograph is itself worth about a pixel, and the dot's centroid
#: another.
TOLERANCE_PX = 4.0


def stage(cut: dict, into: Path) -> dict:
    """Copy the cut's image where Chrome can fetch it.

    Chrome refuses a file:// URL outside the bundle's public directory, so a
    render driven from a props file somewhere else has to bring its picture
    with it. Same reason the demo builder stages its shots.
    """
    into.mkdir(parents=True, exist_ok=True)
    cut = dict(cut)
    for key in ("source", "image", "backgroundImage"):
        src = cut.get(key)
        if not isinstance(src, str) or not src:
            continue
        path = Path(src) if src.startswith("/") else ROOT / src
        if not path.exists():
            continue
        dest = into / f"{cut['id']}__{path.name}"
        if not dest.exists():
            dest.write_bytes(path.read_bytes())
        cut[key] = f"anchors/{dest.name}"
    return cut


def render_clip(props: Path, dest: Path, frames: int) -> Path:
    subprocess.run(
        ["npx", "remotion", "render", ENTRY, "Explainer", str(dest),
         f"--props={props}", f"--frames=0-{frames - 1}", "--gl=angle"],
        cwd=COMPOSER, check=True, capture_output=True)
    return dest


def render_still(props: Path, dest: Path, frame: int) -> Path:
    subprocess.run(
        ["npx", "remotion", "still", ENTRY, "Explainer", str(dest),
         f"--props={props}", f"--frame={frame}", "--gl=angle"],
        cwd=COMPOSER, check=True, capture_output=True)
    return dest


def anchor_dot(with_annotation: Path, without: Path):
    """The centroid of the anchor dot, found by what the annotation ADDED.

    Not by colour. The first two attempts were: the largest accent blob, which
    picked up the act number and stood in for a dot 371px from the real one;
    and then the only filled accent disc, which found nothing, because the
    accent is ochre and the photograph is a sandstone quarry — 111,483 pixels
    of the frame are in the accent's hue range and 8,369 of them form blobs.

    So the same frame is rendered twice, with the annotation and without, and
    the difference is the annotation and nothing else: a filled disc, a ring
    around it, a one-pixel leader and a label on an opaque panel. The disc is
    the one that fills most of its bounding box and is about fourteen pixels
    across.
    """
    import cv2
    import numpy as np

    a = cv2.imread(str(with_annotation), cv2.IMREAD_GRAYSCALE).astype("int16")
    b = cv2.imread(str(without), cv2.IMREAD_GRAYSCALE).astype("int16")
    diff = (np.abs(a - b) > 24).astype("uint8")
    # The leader starts at the dot's centre and the ring surrounds it, so all
    # three arrive as one 44x38 component. An opening with a 7px disc erases
    # anything thinner than itself — the one-pixel leader and the 1.5px ring —
    # and leaves the filled disc at 14x14, which is what is wanted.
    diff = cv2.morphologyEx(
        diff, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    n, _, stats, centroids = cv2.connectedComponentsWithStats(diff, 8)
    import math

    expected_area = math.pi * ANCHOR_RADIUS_PX ** 2
    expected_side = 2 * ANCHOR_RADIUS_PX
    best = None
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        w, h = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        # 0.55, not 0.7: where the dot sits over a bright part of the
        # photograph some of its antialiased edge does not clear the
        # difference threshold, and it measured 0.67. The shape score below
        # is what actually separates the dot from a panel edge — 0.15
        # against 68 — so this only has to reject a ring.
        if w < 1 or h < 1 or area / float(w * h) < 0.55:
            continue
        if not (0.7 <= w / float(h) <= 1.4):
            continue
        # how far this is from being the disc the component draws
        score = (abs(area - expected_area) / expected_area
                 + abs(w - expected_side) / expected_side
                 + abs(h - expected_side) / expected_side)
        if score > 0.6:
            continue
        if best is None or score < best[0]:
            best = (score, (float(centroids[i][0]), float(centroids[i][1])))
    return None if best is None else best[1]


def feature_moved_to(first: Path, second: Path, x: float, y: float):
    """Where the patch of photograph around (x, y) has got to in `second`."""
    import cv2
    import numpy as np

    a = cv2.imread(str(first), cv2.IMREAD_GRAYSCALE)
    b = cv2.imread(str(second), cv2.IMREAD_GRAYSCALE)
    x0, y0 = int(x) - PATCH, int(y) - PATCH
    patch = a[y0:y0 + 2 * PATCH, x0:x0 + 2 * PATCH]
    best = None
    # the image grows a little across the hold, so the patch is matched at a
    # few scales and the best is taken
    for s in np.arange(0.98, 1.13, 0.01):
        scaled = cv2.resize(patch, None, fx=float(s), fy=float(s),
                            interpolation=cv2.INTER_CUBIC)
        if scaled.shape[0] >= b.shape[0] or scaled.shape[1] >= b.shape[1]:
            continue
        res = cv2.matchTemplate(b, scaled, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(res)
        if best is None or score > best[0]:
            best = (score, (loc[0] + scaled.shape[1] / 2,
                            loc[1] + scaled.shape[0] / 2), float(s))
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--cuts", nargs="+", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    props = json.loads((project / "artifacts" / "render_props.json").read_text())
    by_id = {c["id"]: c for c in props["cuts"]}
    work = Path(args.out) if args.out else COMPOSER / "out" / "anchors"
    work.mkdir(parents=True, exist_ok=True)

    rows = []
    failures = []
    for cut_id in args.cuts:
        cut = by_id[cut_id]
        length = float(cut["out_seconds"]) - float(cut["in_seconds"])
        last = max(1, round(length * FPS) - 1)

        # the cut on its own, from its own start, so frame 0 is the hold's start
        one = stage(cut, COMPOSER / "public" / "anchors")
        one["in_seconds"] = 0.0
        one["out_seconds"] = round(length, 3)
        solo = {**props, "cuts": [one], "captions": [], "overlays": [],
                "burn_in_captions": False}
        with_props = work / f"{cut_id}_with.json"
        with_props.write_text(json.dumps(solo))
        bare = {**solo, "cuts": [{**one, "annotations": []}]}
        bare_props = work / f"{cut_id}_bare.json"
        bare_props.write_text(json.dumps(bare))

        first_bare = render_still(bare_props, work / f"{cut_id}_bare_0.png", 0)
        last_bare = render_still(bare_props, work / f"{cut_id}_bare_1.png", last)
        width, height = 1920, 1080

        for n, a in enumerate(cut.get("annotations") or []):
            # one annotation, nothing else in the frame wearing the accent
            alone = {**one, "annotations": [{**a, "reveal_at": 0.0}]}
            for key in ("actNumber", "actTitle", "sceneIndex", "coords",
                        "title", "kicker", "caption", "source"):
                alone.pop(key, None)
            alone_props = work / f"{cut_id}_a{n}.json"
            alone_props.write_text(json.dumps({**solo, "cuts": [alone]}))
            last_with = render_still(alone_props, work / f"{cut_id}_a{n}_1.png", last)
            # the same frame with the annotation taken away, to difference against
            none_props = work / f"{cut_id}_a{n}_none.json"
            none_props.write_text(json.dumps(
                {**solo, "cuts": [{**alone, "annotations": []}]}))
            last_none = render_still(none_props, work / f"{cut_id}_a{n}_none.png", last)

            locked = (a["x"] * width, a["y"] * height)
            match = feature_moved_to(first_bare, last_bare, *locked)
            if match is None:
                failures.append(f"{cut_id} {a['label']}: the patch could not be matched")
                continue
            score, (fx, fy), scale = match
            dot = anchor_dot(last_with, last_none)
            if dot is None:
                failures.append(f"{cut_id} {a['label']}: no anchor dot found")
                continue
            off = ((dot[0] - fx) ** 2 + (dot[1] - fy) ** 2) ** 0.5
            drift_if_locked = ((locked[0] - fx) ** 2 + (locked[1] - fy) ** 2) ** 0.5
            rows.append({
                "cut": cut_id, "label": a["label"],
                "frames": last + 1,
                "feature_at_start": [round(v, 1) for v in locked],
                "feature_at_end": [round(fx, 1), round(fy, 1)],
                "dot_at_end": [round(dot[0], 1), round(dot[1], 1)],
                "match_score": round(score, 3),
                "match_scale": round(scale, 3),
                "anchor_off_feature_px": round(off, 2),
                "would_be_off_if_locked_px": round(drift_if_locked, 2),
            })
            if off > TOLERANCE_PX:
                failures.append(
                    f"{cut_id} {a['label']}: the dot is {off:.1f}px from the "
                    f"feature at the end of the hold (tolerance {TOLERANCE_PX})")

    # The other half of the rule: the labels have to be standing still while
    # the anchors move. Rendered flat — type over the moving photograph, with
    # the treatment on it — which is a harder test than the delivered film,
    # where the type is composited on afterwards.
    type_rows = []
    for cut_id in args.cuts:
        cut = by_id[cut_id]
        length = float(cut["out_seconds"]) - float(cut["in_seconds"])
        frames = max(2, round(length * FPS))
        one = stage(cut, COMPOSER / "public" / "anchors")
        one["in_seconds"] = 0.0
        one["out_seconds"] = round(length, 3)
        clip_props = work / f"{cut_id}_clip.json"
        # no audio: the film's mix is an absolute path the renderer refuses to
        # fetch, and this reads the picture
        clip_props.write_text(json.dumps(
            {**props, "cuts": [one], "captions": [], "overlays": [],
             "burn_in_captions": False, "audio": {}}))
        clip = render_clip(clip_props, work / f"{cut_id}_clip.mp4", frames)

        from verify_type_lock import check as check_type
        problems, measured = check_type(
            str(clip), [{"id": cut_id, "in_seconds": 0.0,
                         "out_seconds": round(length, 3)}], FPS)
        type_rows.append((cut_id, measured, problems))
        failures.extend(f"type lock: {p}" for p in problems)

    lines = [
        "# Anchor tracking — run #1 act 3 and act 4 annotated stills",
        "",
        "An annotation's anchor is a point on the photograph and travels with",
        "it; its label is type and is locked; the leader is redrawn between",
        "them. This renders the first and last frame of each hold, finds where",
        "the FEATURE went by matching a patch of the photograph, finds where",
        "the DOT went by rendering the frame with and without the annotation",
        "and taking the difference, and compares the two.",
        "",
        "`would be off if locked` is the control: it is how far the dot would",
        "sit from its feature under the previous behaviour, and it is what",
        "makes a passing number mean something.",
        "",
        "| cut | annotation | frames | feature start | feature end | dot end | off | if locked | match |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['cut']} | {r['label']} | {r['frames']} | "
            f"{r['feature_at_start'][0]},{r['feature_at_start'][1]} | "
            f"{r['feature_at_end'][0]},{r['feature_at_end'][1]} | "
            f"{r['dot_at_end'][0]},{r['dot_at_end'][1]} | "
            f"**{r['anchor_off_feature_px']}px** | "
            f"{r['would_be_off_if_locked_px']}px | {r['match_score']} |")
    lines += [
        "",
        "## And the labels did not move",
        "",
        "| cut | words read | scenes with a word in a different place | worst |",
        "|---|---|---|---|",
    ]
    for cut_id, m, _ in type_rows:
        words = sum(s["measured"] for s in m["samples"]) or 0
        lines.append(f"| {cut_id} | {words} | {m['scenes_with_movement']} | "
                     f"{m['worst_shift_px']}px |")
    lines += ["", f"Frames and clips: `{work.relative_to(ROOT)}`", ""]
    if failures:
        lines += ["## Failures", ""] + [f"- {f}" for f in failures] + [""]
    dest = ROOT / "reports" / "anchor_tracking.md"
    dest.write_text("\n".join(lines))

    for r in rows:
        print(f"{r['cut']} {r['label']}: dot {r['anchor_off_feature_px']}px from "
              f"the feature, would have been {r['would_be_off_if_locked_px']}px "
              f"if locked (match {r['match_score']})")
    for cut_id, m, _ in type_rows:
        print(f"{cut_id} type lock: {m['scenes_with_movement']} scenes with a "
              f"word in a different place, worst {m['worst_shift_px']}px")
    for f in failures:
        print("  FAIL:", f)
    print(f"-> {dest.relative_to(ROOT)}")
    print("ANCHOR TRACKING:", "PASS" if not failures else "FAIL")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

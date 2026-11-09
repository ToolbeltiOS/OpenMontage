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
    # `depth_clip` is staged for the same reason as the picture: with a 2.5D
    # plate the moving image IS the clip, and a cut whose clip Chrome cannot
    # fetch renders as an empty frame with the annotations floating on it —
    # which measures as a perfect anchor match over a black plate.
    for key in ("source", "image", "backgroundImage", "depth_clip"):
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

    # IN COLOUR, AND THE GREY VERSION WAS WRONG. The accent is ochre, and
    # ochre on weathered grey stone has almost the same LUMA: measured on
    # c154's fifth anchor the dot reads BGR (59,132,184) against a
    # background of (117,132,141), which in grey is 139.2 against 133.0 -- a
    # difference of 6.2, under any usable threshold. The dot was plainly
    # visible in the frame and entirely absent from the grey difference, and
    # the gate reported "no anchor dot found" for a dot that was drawn
    # exactly where the track said it would be.
    #
    # Summed over the channels the same pixel differs by 101. Colour is safe
    # here in a way it was NOT for finding the dot by its hue -- this
    # compares the same frame with and against itself without the
    # annotation, so only the annotation can account for a difference.
    a = cv2.imread(str(with_annotation)).astype("int16")
    b = cv2.imread(str(without)).astype("int16")
    diff = (np.abs(a - b).sum(axis=2) > 60).astype("uint8")
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


#: The score a match must reach AFTER the warp is fitted, by normalised
#: correlation between the first frame's patch warped into the second and
#: what is actually there.
#:
#: 0.8. The 2D cuts matched at 0.906-0.985 under a plain template match
#: because a CSS scale moves a patch rigidly. A depth displacement does not:
#: the patch is warped, and on the 2.5D c053 the same template match scored
#: 0.604 and put the feature 385px from where it was. A score below this is
#: reported as a FAILED MEASUREMENT rather than a moved anchor, because that
#: is what it is -- and the old code never checked the score at all, so a
#: 0.604 match was allowed to condemn the render.
MATCH_FLOOR = 0.8

#: How far out the seed may be before ECC is asked to refine it. ECC's
#: capture range is small: measured on a synthetic 11px translation it fails
#: to converge from identity at all, and converges to cc=0.9996 from a seed
#: 2px off. So the template match does the finding and ECC only polishes.
ECC_CRITERIA = (300, 1e-7)


def _template_seed(a, b, x: float, y: float):
    """Where the patch has roughly got to, by rigid multi-scale matching.

    This is the SEED and no longer the answer. It is good at finding a patch
    anywhere in the frame and bad at saying precisely where, once the patch
    has been warped rather than moved.
    """
    import cv2
    import numpy as np

    x0, y0 = int(x) - PATCH, int(y) - PATCH
    patch = a[y0:y0 + 2 * PATCH, x0:x0 + 2 * PATCH]
    if patch.size == 0:
        return None
    best = None
    for sc in np.arange(0.98, 1.13, 0.01):
        scaled = cv2.resize(patch, None, fx=float(sc), fy=float(sc),
                            interpolation=cv2.INTER_CUBIC)
        if scaled.shape[0] >= b.shape[0] or scaled.shape[1] >= b.shape[1]:
            continue
        res = cv2.matchTemplate(b, scaled, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(res)
        if best is None or score > best[0]:
            best = (score, (loc[0] + scaled.shape[1] / 2,
                            loc[1] + scaled.shape[0] / 2), float(sc))
    return best


def _window(img, cx: float, cy: float, half: int):
    """A `half`-radius window about (cx, cy), and where its corner sits."""
    h, w = img.shape[:2]
    x0 = max(0, min(int(round(cx)) - half, w - 2 * half))
    y0 = max(0, min(int(round(cy)) - half, h - 2 * half))
    return img[y0:y0 + 2 * half, x0:x0 + 2 * half], x0, y0


def _ncc(p, q, valid=None) -> float:
    """Normalised correlation between two same-size patches.

    `valid` IS NOT OPTIONAL IN PRACTICE, and leaving it out is what made the
    first version of this useless. Warping a patch into a window leaves a
    border of zeros where the patch no longer covers, and scoring over the
    whole window pulls a good alignment down: textured c154 anchors whose
    dots sat 3.5px from their features scored 0.637 that way. The score has
    to be taken only where the warped patch actually landed.
    """
    import numpy as np

    p = p.astype("float64")
    q = q.astype("float64")
    if valid is not None:
        p, q = p[valid], q[valid]
    p = p.ravel() - p.mean()
    q = q.ravel() - q.mean()
    d = float(np.linalg.norm(p) * np.linalg.norm(q))
    return float(p @ q / d) if d else 0.0


def _ecc_refine(a, b, x: float, y: float, seed):
    """Refine the seed with an AFFINE fit, which a warped patch needs.

    The first frame's patch is the template and the second frame's window is
    the input, which is the orientation that makes the recovered translation
    the feature's own displacement -- determined by measurement on a
    synthetic 11px shift, not by reading the signature: the other
    orientation returns the negation, and both look plausible.

    The windows are pre-aligned by the seed, so the affine ECC fits is the
    RESIDUAL: a couple of pixels of translation plus whatever scale, shear
    and rotation the depth displacement introduced.
    """
    import cv2
    import numpy as np

    (_, (sx, sy), _) = seed
    patch, _, _ = _window(a, x, y, PATCH)
    region, rx0, ry0 = _window(b, sx, sy, PATCH)
    if patch.shape != region.shape or patch.size == 0:
        return None

    warp = np.eye(2, 3, dtype=np.float32)
    try:
        cv2.findTransformECC(
            patch.astype(np.float32) / 255.0,
            region.astype(np.float32) / 255.0,
            warp, cv2.MOTION_AFFINE,
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
             ECC_CRITERIA[0], ECC_CRITERIA[1]), None, 5)
    except cv2.error:
        return None                       # did not converge; SIFT next

    # the feature is the CENTRE of the template, so carry that one point
    # through the fitted affine and back out to absolute coordinates
    centre = np.array([PATCH, PATCH, 1.0])
    fx, fy = warp @ centre
    warped = cv2.warpAffine(patch, warp, (patch.shape[1], patch.shape[0]),
                            flags=cv2.INTER_LINEAR)
    cover = cv2.warpAffine(np.ones_like(patch), warp,
                           (patch.shape[1], patch.shape[0]),
                           flags=cv2.INTER_NEAREST) > 0
    if cover.sum() < 0.5 * patch.size:
        return None                       # warped mostly out of the window
    return (_ncc(warped, region, cover), (rx0 + float(fx), ry0 + float(fy)),
            float(np.linalg.det(warp[:, :2])) ** 0.5, "ecc-affine")


def _sift_refine(a, b, x: float, y: float, seed):
    """Fallback: SIFT correspondences and a homography on the local region.

    For the case ECC cannot start from -- a patch warped enough that the
    rigid seed is itself far out. Features are matched between the patch and
    a generous window of the second frame, a homography is fitted with
    RANSAC, and the score is still the correlation after warping, so it is
    comparable to the ECC path and to MATCH_FLOOR.
    """
    import cv2
    import numpy as np

    (_, (sx, sy), _) = seed
    patch, _, _ = _window(a, x, y, PATCH)
    half = PATCH * 2
    region, rx0, ry0 = _window(b, sx, sy, half)
    if patch.size == 0 or region.size == 0:
        return None
    try:
        sift = cv2.SIFT_create()
    except AttributeError:
        return None
    kp1, d1 = sift.detectAndCompute(patch, None)
    kp2, d2 = sift.detectAndCompute(region, None)
    if d1 is None or d2 is None or len(kp1) < 4 or len(kp2) < 4:
        return None

    matches = cv2.BFMatcher().knnMatch(d1, d2, k=2)
    good = [m for m, n in (p for p in matches if len(p) == 2)
            if m.distance < 0.75 * n.distance]
    if len(good) < 4:
        return None
    src = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, inliers = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
    if H is None:
        return None

    centre = np.array([PATCH, PATCH, 1.0])
    p = H @ centre
    if abs(p[2]) < 1e-9:
        return None
    fx, fy = p[0] / p[2], p[1] / p[2]
    warped = cv2.warpPerspective(patch, H, (region.shape[1], region.shape[0]))
    # Where the patch LANDED, from warping a mask rather than from `warped >
    # 0` -- a dark patch has genuine zeros in it. And the coverage is judged
    # against the PATCH's own area, not the search window's: the window is
    # four times the patch, so comparing against the window meant the test
    # could essentially never pass and SIFT returned None almost every time.
    mask = cv2.warpPerspective(np.ones_like(patch), H,
                               (region.shape[1], region.shape[0]),
                               flags=cv2.INTER_NEAREST) > 0
    if mask.sum() < 0.5 * patch.size:
        return None
    score = _ncc(warped, region, mask)
    scale = float(abs(np.linalg.det(H[:2, :2]))) ** 0.5
    return (score, (rx0 + float(fx), ry0 + float(fy)), scale, "sift-homography")


def patch_contrast(first: Path, x: float, y: float) -> float:
    """How much there is to match at (x, y), as the patch's grey sd.

    Reported alongside a failed match so the failure says WHICH failure it
    is. A patch with no contrast cannot be located by template matching, by
    ECC or by SIFT, and the answer each returns is noise -- so a low score
    over a flat patch means "this anchor is not verifiable from the
    photograph", while a low score over a textured one means something is
    wrong with the render.

    Measured on c053: the anchor that cannot be matched sits on sd 6.15 of
    255, its best template response 0.604 against a runner-up of 0.522. The
    anchor that matches at 0.954 sits on sd 43.74.
    """
    import cv2

    a = cv2.imread(str(first), cv2.IMREAD_GRAYSCALE)
    patch, _, _ = _window(a, x, y, PATCH)
    return float(patch.std()) if patch.size else 0.0


def feature_moved_to(first: Path, second: Path, x: float, y: float):
    """Where the patch of photograph around (x, y) has got to in `second`.

    Three stages, because a 2.5D plate is NOT a rigid transform of the
    photograph and the rigid matcher this started as cannot describe it. The
    template match finds the patch, an affine ECC fit refines it, and SIFT
    with a homography covers the case ECC will not start from. Whatever
    answers, the score is the correlation after the warp, so one floor
    applies to all three.
    """
    import cv2

    a = cv2.imread(str(first), cv2.IMREAD_GRAYSCALE)
    b = cv2.imread(str(second), cv2.IMREAD_GRAYSCALE)
    seed = _template_seed(a, b, x, y)
    if seed is None:
        return None

    best = None
    for refine in (_ecc_refine, _sift_refine):
        got = refine(a, b, x, y, seed)
        if got and (best is None or got[0] > best[0]):
            best = got
        if best and best[0] >= MATCH_FLOOR:
            break
    if best is None:
        score, (fx, fy), scale = seed
        return (score, (fx, fy), scale, "template-rigid")
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

            # WHERE THE FEATURE IS AT FRAME 0, which is NOT the authored
            # position on a 2.5D plate. `isometric` is 0.30 from the first
            # frame, so the shader has already displaced every point before
            # the move begins; the authored (x, y) is where the point is in
            # the PHOTOGRAPH, not where it appears in frame 0 of the render.
            #
            # Patching at the authored position therefore tracks whatever
            # happens to sit there, and compares it against a dot that
            # follows the intended point. Measured, the error IS that
            # displacement, anchor for anchor:
            #
            #   cut   frame-0 offset            reported error
            #   c154  8.6 8.4 7.2 11.5 3.7      7.8 8.3 7.5 10.3
            #   c053  2.5 1.2                   3.9 --
            #   c143  1.9                       1.4
            #
            # The authored position stays as the `if locked` CONTROL, which
            # is what it is for: how far the dot would sit from the feature
            # if it did not move at all.
            start = locked
            track = cut.get("anchor_track") or {}
            pts = (track.get("anchors") or {}).get(
                f"{a['x']:.4f},{a['y']:.4f}")
            if pts:
                start = (pts[0][0] * width, pts[0][1] * height)
            match = feature_moved_to(first_bare, last_bare, *start)
            if match is None:
                failures.append(f"{cut_id} {a['label']}: the patch could not be matched")
                continue
            score, (fx, fy), scale, method = match
            dot = anchor_dot(last_with, last_none)
            if dot is None:
                failures.append(f"{cut_id} {a['label']}: no anchor dot found")
                continue
            off = ((dot[0] - fx) ** 2 + (dot[1] - fy) ** 2) ** 0.5
            drift_if_locked = ((locked[0] - fx) ** 2 + (locked[1] - fy) ** 2) ** 0.5
            rows.append({
                "cut": cut_id, "label": a["label"],
                "frames": last + 1,
                "feature_at_start": [round(v, 1) for v in start],
                "authored_at": [round(v, 1) for v in locked],
                "feature_at_end": [round(fx, 1), round(fy, 1)],
                "dot_at_end": [round(dot[0], 1), round(dot[1], 1)],
                "match_score": round(score, 3),
                "match_scale": round(scale, 3),
                "match_method": method,
                "anchor_off_feature_px": round(off, 2),
                "would_be_off_if_locked_px": round(drift_if_locked, 2),
            })
            # THE SCORE IS CHECKED FIRST, and it never was. A match the
            # matcher does not believe cannot condemn the render: c053's
            # first annotation scored 0.604 under the rigid matcher and
            # reported the feature 385px away, which was the measurement
            # failing and was recorded as the anchor failing.
            if score < MATCH_FLOOR:
                sd = patch_contrast(first_bare, *start)
                why = ("the photograph has almost no contrast there "
                       f"(grey sd {sd:.2f} of 255), so no matcher can "
                       f"locate it and this anchor is NOT VERIFIABLE from "
                       f"the picture -- which is where the annotation was "
                       f"placed, not a fault in the render"
                       if sd < 15.0 else
                       f"the patch has contrast to spare (grey sd "
                       f"{sd:.2f}), so this is the RENDER or the track, not "
                       f"the picture")
                failures.append(
                    f"{cut_id} {a['label']}: THE MEASUREMENT FAILED, not "
                    f"necessarily the anchor -- the patch matched at "
                    f"{score:.3f} after a {method} warp, under the "
                    f"{MATCH_FLOOR} floor. {why}.")
            elif off > TOLERANCE_PX:
                failures.append(
                    f"{cut_id} {a['label']}: the dot is {off:.1f}px from the "
                    f"feature at the end of the hold (tolerance "
                    f"{TOLERANCE_PX}, matched {score:.3f} by {method})")

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
        "| cut | annotation | frames | feature start | feature end | dot end | off | if locked | match | by |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['cut']} | {r['label']} | {r['frames']} | "
            f"{r['feature_at_start'][0]},{r['feature_at_start'][1]} | "
            f"{r['feature_at_end'][0]},{r['feature_at_end'][1]} | "
            f"{r['dot_at_end'][0]},{r['dot_at_end'][1]} | "
            f"**{r['anchor_off_feature_px']}px** | "
            f"{r['would_be_off_if_locked_px']}px | {r['match_score']} | "
            f"{r.get('match_method','-')} |")
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
              f"if locked (match {r['match_score']} by "
              f"{r.get('match_method','-')})")
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

#!/usr/bin/env python3
"""An annotation must anchor to something the photograph actually shows.

WHY THIS IS AN AUTHORING RULE AND NOT A RENDER GATE
---------------------------------------------------
easter-island c053 carries an annotation reading "twenty-one tree species"
anchored at (0.26, 0.44), which in that photograph is a dark hillside with a
grey standard deviation of 8.61 out of 255. Nothing is there. The dot points
at an absence, the leader line arrives from a label at something the viewer
cannot see, and no measurement can confirm the dot is in the right place
because there is no right place: template matching, ECC and SIFT all return
noise, and `scripts/check_anchor_tracking.py` correctly refuses to certify
it.

That is not a fault in the render and no render gate can fix it. The anchor
was placed where the picture has nothing to point at, so it is caught HERE,
when the annotation is bound to the photograph, and the anchor is moved to
somewhere with texture or the annotation is dropped.

THE THRESHOLD
-------------
Calibrated against every anchor whose match outcome is known, measured on
the source photograph under the same 16:9 crop the renderer applies:

    cut   anchor                       sd    match    outcome
    c053  twenty-one tree species    8.61    0.476    NOT VERIFIABLE
    c143  3.9 hectares of land      15.06    0.887    verified, 0.99px
    c154  a sooty tern              26.90    0.972    verified, 0.72px
    c154  ceremonial paddles        44.29    0.983    verified, 0.83px
    c154  two birdmen               48.63    0.991    verified, 0.60px
    c154  added after the statue    48.92    0.982    verified, 0.66px
    c154  the statue religion       50.15    0.992    verified, 3.72px
    c053  every land bird           68.27    0.996    verified, 1.15px

Verified anchors run 15.06 to 68.27; the one unverifiable anchor is 8.61.
MIN_SD = 15 separates them, AND IT IS TIGHT ON THE LOW SIDE: c143 clears it
by 0.06, so this rule will sometimes move an anchor that would have
verified. That is the safe direction to be wrong in -- an anchor on texture
is never worse than one on a flat patch -- but it is worth knowing it is not
a comfortable margin.

    python3 lib/verify_anchor_texture.py --image a.jpg --anchors 0.26,0.44
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

#: Minimum local grey standard deviation, 0..255, in the patch an anchor
#: sits in. See THE THRESHOLD above.
MIN_SD = 15.0

#: Half-width of the patch, matching `scripts/check_anchor_tracking.py`'s
#: PATCH so the number this rule measures is the number that gate will.
PATCH = 90

#: How far an anchor may be moved to find texture, as a fraction of frame
#: width. Beyond this it is no longer pointing at the same thing, and the
#: annotation is dropped instead of quietly relocated: a label that has
#: wandered to a different feature is worse than no label.
MAX_MOVE = 0.06

#: The frame the renderer will actually show.
WIDTH, HEIGHT = 1920, 1080


def framed(image_path: str):
    """The photograph as the renderer frames it: 16:9 centre crop, 1920x1080.

    The anchor's (x, y) is in the FRAME, not in the original file, so the
    contrast has to be measured after the same crop and scale the renderer
    applies -- otherwise an anchor near the edge is measured against a strip
    of picture that will never be on screen.
    """
    import cv2

    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise SystemExit(f"cannot read {image_path}")
    h, w = img.shape
    target = WIDTH / HEIGHT
    if w / h > target:
        nw = int(round(h * target))
        img = img[:, (w - nw) // 2:(w - nw) // 2 + nw]
    else:
        nh = int(round(w / target))
        img = img[(h - nh) // 2:(h - nh) // 2 + nh, :]
    return cv2.resize(img, (WIDTH, HEIGHT))


def contrast_at(img, x: float, y: float) -> float:
    """The grey standard deviation of the patch an anchor sits in."""
    cx, cy = int(x * WIDTH), int(y * HEIGHT)
    patch = img[max(0, cy - PATCH):cy + PATCH, max(0, cx - PATCH):cx + PATCH]
    return float(patch.std()) if patch.size else 0.0


def nearest_textured(img, x: float, y: float) -> tuple[float, float] | None:
    """The closest point to (x, y) with enough texture, or None.

    Searched outwards in rings so the first acceptable point found is the
    least disturbance to what the annotation was pointing at.
    """
    import math

    step = 0.01
    rings = int(MAX_MOVE / step)
    for ring in range(1, rings + 1):
        r = ring * step
        best = None
        for k in range(ring * 8):
            a = 2 * math.pi * k / (ring * 8)
            nx = min(max(x + r * math.cos(a), 0.06), 0.94)
            ny = min(max(y + r * math.sin(a) * (WIDTH / HEIGHT), 0.06), 0.94)
            sd = contrast_at(img, nx, ny)
            if sd >= MIN_SD and (best is None or sd > best[0]):
                best = (sd, nx, ny)
        if best:
            return (round(best[1], 4), round(best[2], 4))
    return None


def screen(image_path: str, annotations: list[dict]) -> list[dict[str, Any]]:
    """Keep, move or drop each annotation. One decision per annotation."""
    img = framed(image_path)
    out = []
    for a in annotations:
        x, y = float(a["x"]), float(a["y"])
        sd = contrast_at(img, x, y)
        row: dict[str, Any] = {"label": a.get("label", ""), "x": x, "y": y,
                               "sd": round(sd, 2)}
        if sd >= MIN_SD:
            row["action"] = "keep"
        else:
            moved = nearest_textured(img, x, y)
            if moved:
                row["action"] = "move"
                row["to"] = moved
                row["to_sd"] = round(contrast_at(img, *moved), 2)
                row["moved_px"] = round(
                    (((moved[0] - x) * WIDTH) ** 2
                     + ((moved[1] - y) * HEIGHT) ** 2) ** 0.5, 1)
            else:
                row["action"] = "drop"
        out.append(row)
    return out


def apply(annotations: list[dict], decisions: list[dict]) -> list[dict]:
    """The annotations as the rule leaves them."""
    kept = []
    for a, d in zip(annotations, decisions):
        if d["action"] == "drop":
            continue
        a = dict(a)
        if d["action"] == "move":
            a["x"], a["y"] = d["to"]
            a["anchor_moved_from"] = [d["x"], d["y"]]
        kept.append(a)
    return kept


def proof(image_path: str, decisions: list[dict], out_png: str) -> str:
    """One frame showing every decision, so a person can see what was done.

    A rule that silently relocates an annotation is worse than the defect it
    fixes, so it writes down what it did in the only terms that settle it:
    the picture, with the patch each anchor sits in drawn on it.
    """
    import cv2

    img = cv2.cvtColor(framed(image_path), cv2.COLOR_GRAY2BGR)
    colour = {"keep": (120, 220, 120), "move": (60, 200, 255),
              "drop": (70, 70, 240)}

    def label(text, at, c, scale=0.7):
        # Twice: a heavy black pass under a coloured one. A single pass is
        # unreadable wherever the photograph is bright, and this proof is
        # read over sky as often as over rock.
        for col, th in ((0, 0, 0), 5), (c, 2):
            cv2.putText(img, text, at, cv2.FONT_HERSHEY_SIMPLEX, scale,
                        col, th, cv2.LINE_AA)
    for d in decisions:
        c = colour[d["action"]]
        px, py = int(d["x"] * WIDTH), int(d["y"] * HEIGHT)
        cv2.rectangle(img, (px - PATCH, py - PATCH), (px + PATCH, py + PATCH),
                      c, 2)
        cv2.circle(img, (px, py), 7, c, -1)
        label(f"sd {d['sd']}", (px - PATCH, py - PATCH - 10), c)
        label(f"{d['action'].upper()}  {d['label'][:34]}",
              (px - PATCH, py + PATCH + 26), c, 0.6)
        if d["action"] == "move":
            qx, qy = int(d["to"][0] * WIDTH), int(d["to"][1] * HEIGHT)
            cv2.arrowedLine(img, (px, py), (qx, qy), c, 2, tipLength=0.25)
            cv2.circle(img, (qx, qy), 7, c, 2)
            label(f"sd {d['to_sd']}", (qx + 12, qy - 10), c)
    label(f"anchor texture, MIN_SD {MIN_SD}", (40, 56), (240, 240, 240), 0.9)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_png), img)
    return out_png


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--anchors", nargs="+", required=True)
    ap.add_argument("--proof", default=None)
    args = ap.parse_args()

    anns = []
    for i, spec in enumerate(args.anchors):
        x, y = spec.split(",")
        anns.append({"label": f"anchor {i}", "x": float(x), "y": float(y)})
    decisions = screen(args.image, anns)
    for d in decisions:
        line = f"  {d['action']:<5} ({d['x']}, {d['y']})  sd {d['sd']}"
        if d["action"] == "move":
            line += f" -> {d['to']} sd {d['to_sd']} ({d['moved_px']}px)"
        print(line)
    if args.proof:
        print(f"  proof -> {proof(args.image, decisions, args.proof)}")
    return 1 if any(d["action"] == "drop" for d in decisions) else 0


if __name__ == "__main__":
    raise SystemExit(main())

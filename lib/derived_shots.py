#!/usr/bin/env python3
"""Derive extra framings from large stills, so one photograph is several shots.

A 7712x4352 photograph used once at full frame is a wasted asset: the same
file holds a wide, a detail and an extreme detail that read as different
shots. This cuts them, but only where there is something to cut to.

"Subject-centred, never a blank region" is the whole difficulty. The crop
window is chosen by local detail density — the standard deviation of a
downscaled grayscale, summed over a window — so the crop lands where the
picture has structure (carved stone, a face, a joint) rather than on sky,
sand or shadow. A window whose detail never rises above the floor produces no
derived shot at all; a flat image is left as a wide.

Every derived shot is its own asset id carrying parent_id, so the reuse rule
can see that two shots came from one photograph.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np

PROXY_W = 320               # analysis resolution
MIN_LONG_EDGE = 3000
DETAIL_FRAC = 0.45          # of the long edge
EXTREME_FRAC = 0.30
DETAIL_FLOOR = 10.0         # grayscale std inside the window, 0-255 scale
MIN_CROP_PX = 1600          # below this the crop upscales past ~1.2x and softens
VEG_PENALTY = 1.6           # weight subtracted for green/magenta foliage


def rgb(path: str, width: int = PROXY_W) -> np.ndarray | None:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf",
         f"format=rgb24,scale={width}:-2", "-frames:v", "1", "-f", "rawvideo", "-"],
        capture_output=True).stdout
    if not raw:
        return None
    h = len(raw) // (width * 3)
    if h == 0:
        return None
    return np.frombuffer(raw[: width * h * 3], dtype=np.uint8).reshape(h, width, 3).astype(np.float32)


def gray(path: str, width: int = PROXY_W) -> np.ndarray | None:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf",
         f"format=gray,scale={width}:-2", "-frames:v", "1", "-f", "rawvideo", "-"],
        capture_output=True).stdout
    if not raw:
        return None
    # height follows from the byte count
    h = len(raw) // width
    if h == 0:
        return None
    return np.frombuffer(raw[: width * h], dtype=np.uint8).reshape(h, width).astype(np.float32)


def detail_map(g: np.ndarray, cell: int = 8, colour: np.ndarray | None = None) -> np.ndarray:
    """Where the STRUCTURE is — which is not the same as where the texture is.

    Local standard deviation alone picks whatever has the most high-frequency
    content, and in a landscape that is foliage. The first pass cropped
    Preseli onto a bank of pink fireweed and the extreme framing onto blurry
    grass stalks: maximum detail, no subject.

    So two corrections. Vegetation is penalised by its colour — green or
    magenta dominance over the other channels — and the map is weighted toward
    the middle of the frame, because a photographer points the camera at the
    thing.
    """
    h, w = g.shape
    gh, gw = h // cell, w // cell
    m = np.zeros((gh, gw), dtype=np.float32)
    for y in range(gh):
        for x in range(gw):
            m[y, x] = g[y * cell:(y + 1) * cell, x * cell:(x + 1) * cell].std()

    if colour is not None:
        ch, cw = colour.shape[0] // cell, colour.shape[1] // cell
        gh2, gw2 = min(gh, ch), min(gw, cw)
        for y in range(gh2):
            for x in range(gw2):
                blk = colour[y * cell:(y + 1) * cell, x * cell:(x + 1) * cell]
                r, gg, b = blk[..., 0].mean(), blk[..., 1].mean(), blk[..., 2].mean()
                veg = max(0.0, gg - (r + b) / 2) + max(0.0, (r + b) / 2 - gg) * 0.25
                m[y, x] = max(0.0, m[y, x] - VEG_PENALTY * veg)

    yy = np.linspace(-1, 1, gh)[:, None]
    xx = np.linspace(-1, 1, gw)[None, :]
    m *= (1.0 - 0.45 * (yy ** 2 + xx ** 2) / 2)
    return m


def best_window(m: np.ndarray, frac: float, aspect: float) -> tuple[float, float, float]:
    """Return (cx, cy, score) in 0..1 image coords for the densest window."""
    gh, gw = m.shape
    win_w = max(2, int(round(gw * frac)))
    win_h = max(2, int(round(win_w / aspect)))
    if win_h >= gh:
        win_h = max(2, gh - 1)
        win_w = max(2, int(round(win_h * aspect)))
    # integral image for a fast window sum
    ii = m.cumsum(0).cumsum(1)
    ii = np.pad(ii, ((1, 0), (1, 0)))
    best = (-1.0, 0, 0)
    for y in range(0, gh - win_h + 1):
        for x in range(0, gw - win_w + 1):
            s = ii[y + win_h, x + win_w] - ii[y, x + win_w] - ii[y + win_h, x] + ii[y, x]
            s /= (win_w * win_h)
            if s > best[0]:
                best = (s, x, y)
    score, x, y = best
    cx = (x + win_w / 2) / gw
    cy = (y + win_h / 2) / gh
    return cx, cy, score


def crop_rect(w: int, h: int, cx: float, cy: float, frac: float) -> dict:
    """A 16:9 window of `frac` of the long edge, centred and clamped in frame."""
    # The window stays 16:9. Clamping width and height independently loses
    # the aspect on a panorama — Sacsayhuaman is 21685x3261, so 45% of the
    # long edge is 9758 wide against only 3261 of height, and the crop came
    # out letterboxed inside a 16:9 frame. Bound the width by what the height
    # can support first.
    long_edge = max(w, h)
    cw = int(round(long_edge * frac))
    cw = min(cw, w, int(h * 16 / 9))
    ch = int(round(cw * 9 / 16))
    x = int(round(cx * w - cw / 2))
    y = int(round(cy * h - ch / 2))
    x = max(0, min(x, w - cw))
    y = max(0, min(y, h - ch))
    return {"x": x, "y": y, "w": cw, "h": ch}


def derive(assets: list[dict], out_dir: str) -> list[dict]:
    os.makedirs(out_dir, exist_ok=True)
    derived: list[dict] = []
    for a in assets:
        path = a["path"]
        if not os.path.exists(path):
            continue
        w, h = int(a.get("width", 0)), int(a.get("height", 0))
        if max(w, h) < MIN_LONG_EDGE:
            continue
        g = gray(path)
        if g is None:
            continue
        m = detail_map(g, colour=rgb(path))

        for label, frac in (("detail", DETAIL_FRAC), ("extreme", EXTREME_FRAC)):
            cx, cy, score = best_window(m, frac, 16 / 9)
            if score < DETAIL_FLOOR:
                print(f"    {os.path.basename(path)}: no {label} (detail {score:.1f} "
                      f"below floor {DETAIL_FLOOR})", flush=True)
                continue
            rect = crop_rect(w, h, cx, cy, frac)
            if rect["w"] < MIN_CROP_PX:
                print(f"    {os.path.basename(path)}: no {label} "
                      f"(crop {rect['w']}px would upscale)", flush=True)
                continue
            aid = f"{a['asset_id']}_{label}"
            dest = os.path.join(out_dir, aid + ".jpg")
            if not os.path.exists(dest):
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-y", "-i", path, "-vf",
                     f"crop={rect['w']}:{rect['h']}:{rect['x']}:{rect['y']},"
                     f"scale='min(2560,iw)':-2", "-q:v", "2", dest], check=True)
            derived.append({
                "asset_id": aid, "parent_id": a["asset_id"], "framing": label,
                "path": dest, "subject": a.get("subject"), "crop": rect,
                "detail_score": round(float(score), 1),
                "artist": a.get("artist"), "licence": a.get("licence"),
                "title": a.get("title"), "page": a.get("page"),
                "provider": a.get("provider", "wikimedia"),
            })
            print(f"    {aid}: {rect['w']}x{rect['h']} at ({rect['x']},{rect['y']}) "
                  f"detail {score:.1f}", flush=True)
    return derived


if __name__ == "__main__":
    bank = json.load(open(sys.argv[1]))
    out_dir = sys.argv[2]
    flat = [a for s in bank["subjects"].values() for a in s["assets"]]
    print(f"parents >= {MIN_LONG_EDGE}px: "
          f"{sum(1 for a in flat if max(a.get('width',0), a.get('height',0)) >= MIN_LONG_EDGE)}"
          f" of {len(flat)}")
    d = derive(flat, out_dir)
    bank["derived"] = d
    json.dump(bank, open(sys.argv[1], "w"), indent=1, ensure_ascii=False)
    print(f"derived shots: {len(d)}")

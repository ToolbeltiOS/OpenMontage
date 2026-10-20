"""Does the picture actually move, frame by frame?

WHY THIS CHECK EXISTS
---------------------
The act 2 demo stuttered. Everything that was being measured said it was
fine: 2724 frames, constant frame rate, every presentation timestamp exactly
1/30 apart, the right duration, the right shot count, the rhythm gate green.

The picture was frozen for 51% of its running time. One authored scene held
341 identical frames — 11.4 seconds — inside a 15.5-second reveal, because an
authored graphic animates its reveals and then stops, and nothing in the
pipeline looked at consecutive frames.

A freeze is indistinguishable from a dropped frame to a viewer, and it is
invisible to every container-level measurement. So this one decodes the film
and looks.

THE RULE
--------
No run of more than two identical consecutive frames, except where the frame
is deliberately black — the fade through black at an act boundary is a
planned hold and the only legitimate freeze in the film.

Comparison is on a downscaled greyscale frame, because the question is whether
the PICTURE moved, not whether the encoder dithered a pixel.

    python3 lib/verify_frame_motion.py <film.mp4>
"""
from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

#: Mean absolute 8-bit difference below which two frames are "the same",
#: measured at MEASURE_SIZE.
#:
#: Both numbers are calibrated against a deliberately frozen render of the
#: same material. At 160x90 — the first size tried — a scene moving at a
#: legitimate documentary pace averages out to 54% "duplicate" frames, because
#: downscaling throws away exactly the sub-pixel change the check is looking
#: for. At 480x270 a moving scene never falls under 0.02 and a frozen one is
#: EXACTLY zero 42% of the time.
SAME_FRAME_MAD = 0.02
MEASURE_SIZE = (480, 270)
#: Longest permitted run of identical frames, in frames.
MAX_IDENTICAL_RUN = 2
#: Mean luma below which a frame counts as a planned hold on black.
BLACK_LUMA = 12.0


def decode(path: str, width: int = MEASURE_SIZE[0], height: int = MEASURE_SIZE[1]):
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={width}:{height}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="uint8").reshape(-1, height, width).astype("float32")


def timestamps(path: str) -> list[float]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "frame=pts_time", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True).stdout
    # csv=p=0 still emits a trailing comma per row when a field is empty,
    # so the token is "0.000000," rather than "0.000000".
    values = []
    for token in out.split():
        token = token.strip().rstrip(",")
        if token and token != "N/A":
            values.append(float(token))
    return values


def check(path: str, fps: float = 30.0) -> tuple[list[str], dict[str, Any]]:
    import numpy as np

    frames = decode(path)
    mad = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
    luma = frames.mean(axis=(1, 2))
    same = mad < SAME_FRAME_MAD

    runs: list[tuple[int, int]] = []
    start = None
    for i, s in enumerate(same):
        if s and start is None:
            start = i
        elif not s and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(same)))

    problems: list[str] = []
    offending = []
    for a, b in runs:
        length = (b - a) + 1          # n identical diffs is n+1 identical frames
        if length <= MAX_IDENTICAL_RUN:
            continue
        if luma[a:b + 1].mean() < BLACK_LUMA:
            continue                  # a planned hold on black
        offending.append({"start_seconds": round(a / fps, 2),
                          "frames": length,
                          "seconds": round(length / fps, 2)})
        problems.append(
            f"{a / fps:.2f}s: {length} identical frames ({length / fps:.2f}s) — "
            f"a freeze is indistinguishable from a dropped frame")

    pts = timestamps(path)
    deltas = [round(pts[i + 1] - pts[i], 6) for i in range(len(pts) - 1)]
    expected = 1.0 / fps
    irregular = [(i, d) for i, d in enumerate(deltas) if abs(d - expected) > 1e-4]
    if irregular:
        problems.append(
            f"{len(irregular)} timestamps are not {expected:.6f}s apart "
            f"(first at frame {irregular[0][0]}, delta {irregular[0][1]})")

    measured = {
        "frames": int(len(frames)),
        "duplicate_pairs_pct": round(100 * float(same.mean()), 1),
        "runs_over_limit": len(offending),
        "longest_freeze_seconds": max((o["seconds"] for o in offending), default=0.0),
        "freezes": offending[:40],
        "timestamps_constant": not irregular,
        "mean_frame_difference": round(float(mad.mean()), 4),
    }
    return problems, measured


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: verify_frame_motion.py <film.mp4> [fps]")
        return 2
    fps = float(argv[2]) if len(argv) > 2 else 30.0
    problems, measured = check(argv[1], fps)
    print(f"{measured['frames']} frames, "
          f"{measured['duplicate_pairs_pct']}% duplicate pairs, "
          f"mean frame difference {measured['mean_frame_difference']}, "
          f"timestamps {'constant' if measured['timestamps_constant'] else 'IRREGULAR'}")
    for p in problems[:20]:
        print("  -", p)
    if len(problems) > 20:
        print(f"  ... and {len(problems) - 20} more")
    print("FRAME MOTION:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

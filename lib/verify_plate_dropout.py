"""A frame whose picture did not arrive, in the film that is about to ship.

THE BLIND SPOT THIS FILLS
-------------------------
None of the other gates can see this one:

  * frame count      the frame is PRESENT, it is just wrong
  * frame motion     one frame is not a freeze
  * frame order      it compares the delivered file to the PLATE, and the
                     defect is IN the plate, so the two agree perfectly

they-said-it-couldnt-be-built is published with eight of them in it, and
king-tut's first delivery had five — two of them plain to the eye — and
passed 7 of 7 gates on the way out.

WHAT IS BEING LOOKED FOR
------------------------
A frame unlike both of its neighbours while the neighbours are like each
other: the picture jumps away for a thirtieth of a second and comes
straight back. That is the opposite of a cut, where the neighbours differ
from each other as much as from the frame between them, and of motion,
where all three differ steadily.

    d_prev   = |f[i]   - f[i-1]|
    d_next   = |f[i]   - f[i+1]|
    d_across = |f[i+1] - f[i-1]|      the neighbours, to each other

BOTH TESTS ARE RELATIVE, for the same reason the splice seams and the
dropout thresholds had to be: how much a film changes between two frames is
a property of the film, not a constant. A fast cut and a locked card differ
by two orders of magnitude and neither is a defect. So the spike is measured
against the LOCAL motion around it, and the neighbours' resemblance against
the spike itself.

WHAT IT COSTS
-------------
A full decode of the delivered film at 480x270 greyscale, streamed three
frames at a time because 36,000 frames at full resolution is not something
to hold in memory. MEASURED, not estimated: 99.7 seconds for king-tut's
36,803 frames — 1.17 GB, twenty and a half minutes of film — on this Mac.
That is the price of the only gate that can see a defect the plate and the
delivered file agree about.
"""
from __future__ import annotations

import subprocess
from collections import deque
from typing import Any

import numpy as np

W, H = 480, 270
FRAME = W * H

#: The neighbours have to resemble EACH OTHER far better than either
#: resembles the frame between them, or this is a cut or ordinary motion.
#: Relative to the spike, so it holds at any pace.
ACROSS_RATIO = 0.6

#: How far the middle frame has to stand out from the film's local pace. A
#: dropout on real material reads about ten times the local motion; the
#: deliberately awkward control in the tests reads three.
SPIKE_RATIO = 2.5

#: How many consecutive differences the local pace is taken over. The same
#: window `verify_frame_order` uses, for the same reason: a median over half
#: a second is long enough to be a baseline and short enough not to average
#: a whole scene into it.
LOCAL_WINDOW = 15

#: Below this the film is not moving at all and a ratio against it means
#: nothing — a locked card differs from itself by rounding.
LOCAL_FLOOR = 0.05

#: How strongly the neighbours outresemble the frame between them. A LABEL
#: FOR THE REPORT, NOT A THRESHOLD: every hit fails the film.
#:
#: It was a threshold for an hour, on the reasoning that a weak reading is
#: probably fast motion. The control killed that: two frames injected with
#: the SAME darkening read 0.196 and 0.546, the difference being only that
#: the second sits in faster-moving material.
#:
#: Then the film with known ground truth settled it. king-tut's first
#: delivery had 13 frames uncovered by the timeline arithmetic, and the
#: scan found five of them — 6902 and 18765 at 0.125 and 0.205, and 5381,
#: 9136 and 19940 at 0.377, 0.256 and 0.518. ALL FIVE ARE IN THE LIST OF
#: THIRTEEN. The three "marginal" ones were real dropouts in a published-
#: quality delivery, and a gate blocking only on the certain ones would
#: have waved them through.
#:
#: Across the four films made so far — about 146,000 frames — the scan has
#: 13 hits and every one of them is a defect with an independent
#: explanation: eight in they-said-it (five timeline gaps, three unpainted
#: subtrees), five in king-tut's first delivery (all timeline gaps), none
#: in easter-island, none in noah, and none in king-tut's re-render. No
#: false positive has ever been measured.
CERTAIN_RATIO = 0.25

#: An absolute floor on the spike, in grey levels, for scanning a PLATE.
#:
#: WHY THE RELATIVE TESTS ALONE CANNOT READ A PLATE. Every threshold above
#: is relative, because how much a film changes between two frames is a
#: property of the film. That holds on a DELIVERED film, where the grain
#: keeps the frame-to-frame baseline around 0.45 grey levels — comfortably
#: above LOCAL_FLOOR, so the floor never binds and the ratio means what it
#: says. A plate has no grain. Measured on run #6's plate, 2026-11-15,
#: frames 25118-25148:
#:
#:     median consecutive difference      0.0744 grey levels
#:     the two frames this gate flagged   0.1664 and 0.1942
#:     a real dropout injected there      5.5506   (MEASURED_COST, the
#:                                                  cost of a lost backdrop
#:                                                  on the film it was
#:                                                  found in)
#:
#: So on a plate the baseline is near zero, the floor becomes the comparator,
#: and a flicker of a sixth of ONE grey level out of 255 — 0.07%, invisible —
#: reads as "the picture is gone for one frame". The real thing is 33x
#: larger. Both of those frames were in a delivered film that passed this
#: same gate at delivery, where grain held the baseline above the floor.
#:
#: APPLIED AT DELIVERY TOO, on the owner's ruling of 2026-11-16 and only
#: with the control below in the same commit. It was plate-only for a day,
#: on the reasoning that a gate with a clean record across four films should
#: not change as a side effect of adding a new caller. The right answer to
#: that was to measure it rather than to leave it.
#:
#: THE CONTROL. Run #1 — they-said-it-couldnt-be-built, the one film whose
#: delivery survives on disk, 36,238 frames — scanned twice:
#:
#:     min_spike = 0.0     115 hits, 8 certain, weakest spike 3.8060
#:     min_spike = 1.0     115 hits, 8 certain, weakest spike 3.8060
#:
#: Identical. The floor costs this film nothing. Its eight real dropouts,
#: by frame and spike in grey levels:
#:
#:     16648  16.7750      24603  17.9820
#:     21332  15.6800      26725  17.3860
#:     21715  16.8120      27668  16.9190
#:     24220  16.7740      32992  18.1940
#:
#: 15.7x to 18.2x the floor. Each is ~17 grey levels brighter than BOTH
#: neighbours — luma ~32 against ~15 — which is the unpainted-frame
#: signature; 32992 is the known dropout and reads the most decisive value
#: in the film at 0.010. The weakest hit of ANY kind, certain or marginal,
#: is 3.8060, still 3.8x clear. And a lost backdrop of MEASURED_COST
#: injected into this same film reads 5.7534, 5.8x clear.
#:
#: KING TUT'S THREE COULD NOT BE RE-MEASURED, and the ruling was made
#: knowing that. Its first delivery — the one with five hits, three of them
#: marginal — was replaced by the re-render that shipped, and the gate
#: report records `certain_frames`, `marginal_frames` and
#: `worst_decisiveness` but never a per-frame spike. So there is no file and
#: no record to read those three off. They were timeline gaps, which is the
#: same class as five of run #1's eight, and those read 15.68 to 18.19.
#:
#: A NOTE ON "13 HITS ACROSS FOUR FILMS" in CERTAIN_RATIO above: that counts
#: CERTAIN hits. Run #1 alone yields 115 at any floor, 107 of them marginal
#: and mostly at decisiveness 0.50-0.60, which is a compressed delivery's
#: own noise rather than a missing picture. The count is not wrong, it is
#: narrower than it reads.
MIN_SPIKE_LEVELS = 1.0


def frames(path: str, threads: int = 2):
    """Every decoded frame, in decode order, with nothing invented.

    `-vsync 0` IS NOT OPTIONAL. Without it ffmpeg is free to resample to a
    constant rate, and they-said-it-couldnt-be-built is not quite 30fps —
    `r_frame_rate` says 30/1 while `avg_frame_rate` says 21742800/724859,
    which is 29.9959. Decoding it without `-vsync 0` returned 36,244 frames
    from a container that indexes 36,238: six frames invented, and every
    index after each one shifted. The bright frame this scan found at 32,992
    was reported at 32,996, and extracting 32,996 to check it showed an
    ordinary frame — which looked exactly like the scan hallucinating. It
    was not.
    """
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-threads", str(threads), "-i", path,
         "-vsync", "0", "-vf", f"scale={W}:{H}", "-pix_fmt", "gray",
         "-f", "rawvideo", "-"],
        stdout=subprocess.PIPE)
    try:
        while True:
            buf = proc.stdout.read(FRAME)
            if len(buf) < FRAME:
                return
            yield np.frombuffer(buf, "uint8").reshape(H, W).astype("float32")
    finally:
        proc.stdout.close()
        proc.wait()


def scan(path: str, fps: float = 30.0, threads: int = 2,
         min_spike: float = 0.0
         ) -> tuple[list[dict[str, Any]], int]:
    hits: list[dict[str, Any]] = []
    a = b = None
    n = 0
    recent: deque[float] = deque(maxlen=LOCAL_WINDOW)
    pending: list[dict[str, Any]] = []
    for c in frames(path, threads):
        if b is not None and a is not None:
            d_prev = float(np.abs(b - a).mean())
            d_next = float(np.abs(b - c).mean())
            d_across = float(np.abs(c - a).mean())
            recent.append(d_prev)
            pending.append({"frame": n - 1, "seconds": (n - 1) / fps,
                            "spike": min(d_prev, d_next),
                            "d_prev": round(d_prev, 3),
                            "d_next": round(d_next, 3),
                            "d_across": round(d_across, 3),
                            "luma": round(float(b.mean()), 2),
                            "luma_neighbours": round(
                                float((a.mean() + c.mean()) / 2), 2)})
        a, b = b, c
        n += 1

    # The local pace is taken from the diffs AROUND a frame, which means the
    # last of them is not known until the film has been read. A dropout
    # inflates the window it sits in, so the median is taken over a window
    # that EXCLUDES the frame being judged.
    diffs = np.array([p["d_prev"] for p in pending], dtype="float64")
    half = LOCAL_WINDOW // 2
    for i, p in enumerate(pending):
        lo, hi = max(0, i - half), min(len(diffs), i + half + 1)
        window = np.concatenate([diffs[lo:i], diffs[i + 1:hi]])
        local = max(float(np.median(window)) if len(window) else 0.0,
                    LOCAL_FLOOR)
        if (p["spike"] > SPIKE_RATIO * local
                and p["spike"] >= min_spike
                and p["d_across"] < ACROSS_RATIO * p["spike"]):
            hits.append({**p, "local": round(local, 3),
                         "spike": round(p["spike"], 3),
                         "decisiveness": round(p["d_across"] / p["spike"], 3)})
    return hits, n


def _stamp(seconds: float) -> str:
    minutes, rest = divmod(seconds, 60)
    return f"{int(minutes):02d}:{rest:06.3f}"


def check(film: str, fps: int = 30, min_spike: float = MIN_SPIKE_LEVELS
          ) -> tuple[list[str], dict[str, Any]]:
    """Blocking. ANY dropout fails the film — see `CERTAIN_RATIO` for the
    measurement that says a weak reading is not a weak defect.

    `min_spike` is MIN_SPIKE_LEVELS everywhere now, plate and delivery
    alike, with the control for that in the constant's own comment: run #1
    yields the same 115 hits and the same 8 certain ones at a floor of 0.0
    and of 1.0. A frame whose picture is GONE does not differ from its
    neighbours by a fraction of one grey level in any regime.
    """
    hits, total = scan(film, float(fps), min_spike=min_spike)
    certain = [h for h in hits if h["decisiveness"] < CERTAIN_RATIO]
    marginal = [h for h in hits if h["decisiveness"] >= CERTAIN_RATIO]

    problems = []
    for h in hits:
        problems.append(
            f"frame {h['frame']} at {_stamp(h['seconds'])}: the picture is "
            f"gone for one frame — it differs from the frame before by "
            f"{h['d_prev']} and from the one after by {h['d_next']}, while "
            f"those two differ from each other by only {h['d_across']} "
            f"({h['decisiveness']:.3f} of the spike). Luma {h['luma']} "
            f"against {h['luma_neighbours']} either side.")

    measured = {
        "frames": total,
        "certain": len(certain),
        "marginal": len(marginal),
        "worst_decisiveness": (round(min(h["decisiveness"] for h in hits), 3)
                               if hits else None),
        "certain_frames": [h["frame"] for h in certain],
        "marginal_frames": [h["frame"] for h in marginal],
        "marginal_seconds": [_stamp(h["seconds"]) for h in marginal],
        "min_spike_levels": min_spike,
    }
    return problems, measured

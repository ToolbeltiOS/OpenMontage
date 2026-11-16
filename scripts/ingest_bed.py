#!/usr/bin/env python3
"""Turn a raw music candidate into a loopable bed, or refuse it.

WHY THIS EXISTS: THE HAND TRIM THAT FIXED THE RULE
--------------------------------------------------
`scripts/measure_music.py` screens candidates and `lib/mix_audio` gates the
bed it builds, and for five films the step between them was done by hand and
recorded nowhere. On 2026-11-15, measuring the audition against the mixer
showed what that hand step was worth:

    candidates/bed_cinematic_quiet.mp3    168.0s   hole 46.59 dB
    candidates/trimmed/bed_cinematic_quiet.wav 117.6s  hole  7.04 dB

Same music. The raw file carries near-silence at its edges — a median of
-22.81 LUFS against a minimum of -69.40 — and looping it over a 600s span
conditions out at 28.21 dB, well past the 10 dB the mixer allows. The
trimmed 117.6s core is the bed film #5 actually used, and `span_hole_db`
predicts its in-film hole to 0.00 dB. So looping a raw candidate measures
its silence, not its music, and an audition pointed at raw files refuses
every bed whose source fades in — which on that library is all of them.

The hand trim was therefore the measurement that fixed the rule, and this is
the rule: THE LIBRARY HOLDS LOOPABLE BEDS, and everything enters through
here. `span_hole_db` is then a true gate rather than a reading of fades.

WHAT IT LOOKS FOR
-----------------
The longest contiguous window whose hole stays under `BED_HOLE_MAX_DB`,
where hole is the MIXER'S OWN MEASURE — median minus minimum of the
K-weighted short-term loudness, `internal_dynamics`'s `hole_db` — and not
max minus min, which is a different and stricter number that the 10 dB
ceiling was never calibrated against.

A window shorter than `MIN_BED_SECONDS` is refused rather than written: a
bed that short turns over so often that the loop becomes the rhythm.

    scripts/ingest_bed.py "Lake Jupiter - John Patitucci.mp3"
    scripts/ingest_bed.py --dry-run candidates/*.mp3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter, minimum_filter1d

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

from lib.mix_audio import BED_HOLE_MAX_DB, internal_dynamics  # noqa: E402
from lib.shared_state import music_dir  # noqa: E402
from lib.verify_sfx_level import HOP_S, WINDOW_S, short_term  # noqa: E402

#: Below this a bed turns over so often the loop becomes the rhythm.
MIN_BED_SECONDS = 90.0

#: The hole an ingested window is allowed, which is the MIXER'S ceiling by
#: default — the rule as asked for: the longest window under
#: BED_HOLE_MAX_DB. Separate from it because the two answer different
#: questions, and measurement says they may want different numbers:
#:
#: bed_cinematic_quiet, through the real gate over film #5's own 622.82s
#: span, looped and conditioned:
#:
#:     raw candidate      168.1s    28.25 dB   REFUSED
#:     ingested at 10.0   161.7s     9.29 dB   passes, 0.71 dB of headroom
#:     the hand trim      117.6s     4.92 dB   passes, 5.08 dB of headroom
#:
#: So ingesting at the mixer's own ceiling WORKS — it turns a refused bed
#: into an accepted one, which is the point. It just leaves almost no room,
#: and the gate it has to clear later fails a whole film.
#:
#: What the margin costs, on the same bed:
#:
#:     ceiling 10.0   window 161.7s   6.83 -> in-span 9.29 dB   0.71 dB left
#:     ceiling  7.0   window 160.5s   6.83 -> in-span 7.29 dB   2.71 dB left
#:
#: ONE AND A TWO TENTHS OF A SECOND buys two and a half decibels, because
#: the length that clears 10 dB is held back by one brief dip near an edge
#: and trimming a little more removes it. And the in-span figure barely
#: moves with the span — 7.24 dB over 300s, 7.29 over 622.8s, 7.29 over
#: 900s — so once a bed is loopable its hole is a property of the bed
#: rather than of the film it is used in.
#:
#: Hence 7.0 rather than BED_HOLE_MAX_DB, which is also what the hand trim
#: achieved (7.04 dB) and what was predicted of this rule. Raise it to
#: BED_HOLE_MAX_DB for the longest possible bed and no margin.
INGEST_HOLE_CEILING_DB = 7.0

#: The mixer's rate, so a library bed needs no conversion to be used.
SR = 48000

MANIFEST = "MANIFEST.json"


def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def decode(src: str, dest: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src,
                    "-ar", str(SR), "-ac", "2", dest], check=True)


#: `internal_dynamics` discards anything below this before measuring, so a
#: window hole computed without the same filter is a different number. The
#: first version of this file omitted it and read 60.57 dB on a file the
#: mixer's own measure puts at 46.59.
SILENCE_FLOOR_LUFS = -70.0


def hole_of(levels: np.ndarray) -> float:
    """`internal_dynamics`'s measure, on an arbitrary stretch of levels."""
    live = levels[levels > SILENCE_FLOOR_LUFS]
    if not len(live):
        return float("inf")
    return float(np.median(live) - live.min())


def longest_quiet_window(levels: np.ndarray,
                         limit: float = INGEST_HOLE_CEILING_DB
                         ) -> tuple[int, int] | None:
    """The longest [start, end) over which the hole stays under `limit`.

    Searched by LENGTH, longest first, so the first hit is the answer. For
    each length the per-position minimum and median come from sliding
    filters, which is O(n log L) rather than the O(n^2) of testing every
    window separately.

    Coarse to fine — one second, then one frame — because the file is tens of
    minutes of 10 Hz samples and the answer only has to be right to a
    tenth of a second. The refinement re-checks every length between the
    last failure and the first success, so the result is exact at frame
    resolution rather than rounded to the coarse step.
    """
    n = len(levels)
    if n == 0:
        return None

    def first_valid(length: int) -> int | None:
        if length > n:
            return None
        # Below the floor the frame is not material, and `internal_dynamics`
        # drops it. Raising those frames to the floor keeps them OUT of the
        # minimum without letting a silent stretch masquerade as steady: a
        # window that is mostly silence has its median at the floor too, so
        # its hole collapses to zero and the length test is what rejects it.
        usable = np.maximum(levels, SILENCE_FLOOR_LUFS)
        lo = minimum_filter1d(usable, size=length, mode="nearest")
        mid = median_filter(usable, size=length, mode="nearest")
        half = length // 2
        # Only positions whose whole window lies inside the file.
        for centre in range(half, n - (length - 1 - half)):
            if float(mid[centre] - lo[centre]) < limit:
                return centre - half
        return None

    coarse = max(1, int(round(1.0 / HOP_S)))          # one second
    best: tuple[int, int] | None = None
    length = n
    while length >= 1:
        start = first_valid(length)
        if start is not None:
            best = (start, start + length)
            break
        length -= coarse
    if best is None:
        return None

    # Fine pass: anything longer than what the coarse step found, up to the
    # length that failed.
    for longer in range(best[1] - best[0] + 1,
                        min(n, best[1] - best[0] + coarse) + 1):
        start = first_valid(longer)
        if start is not None:
            best = (start, start + longer)
    return best


def ingest(src: str, out_dir: Path, min_seconds: float,
           dry_run: bool, ceiling: float = INGEST_HOLE_CEILING_DB) -> dict:
    """Measure, trim, write, and record. Returns the manifest row."""
    row: dict = {"source": str(src), "track": Path(src).stem + ".wav"}
    with tempfile.TemporaryDirectory() as tmp:
        decoded = os.path.join(tmp, "in.wav")
        decode(src, decoded)

        import soundfile as sf
        data, sr = sf.read(decoded, dtype="float32", always_2d=True)
        _, levels = short_term(data, sr)
        row["source_seconds"] = round(len(data) / sr, 2)
        row["source_hole_db"] = round(hole_of(levels), 2)

        found = longest_quiet_window(levels, ceiling)
        if found is None:
            row["refused"] = (
                f"no window of any length holds its level within "
                f"{ceiling:.1f} dB")
            return row

        i, j = found
        # A short-term value is the centre of a WINDOW_S window, so the
        # audible stretch runs half a window either side of the centres.
        start = max(0.0, float(i) * HOP_S)
        end = min(row["source_seconds"], float(j - 1) * HOP_S + WINDOW_S)
        seconds = end - start
        row.update({"window_start_s": round(start, 2),
                    "window_end_s": round(end, 2),
                    "seconds": round(seconds, 2),
                    "window_hole_db": round(hole_of(levels[i:j]), 2),
                    "ingest_ceiling_db": ceiling})

        if seconds < min_seconds:
            row["refused"] = (
                f"its longest steady window is {seconds:.1f}s, under the "
                f"{min_seconds:.0f}s a bed needs")
            return row

        if dry_run:
            row["written"] = False
            return row

        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / row["track"]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}",
                        "-i", decoded, "-t", f"{seconds:.3f}",
                        "-ar", str(SR), "-ac", "2", str(dest)], check=True)
        # The authority is the file that was written, not the search.
        row["hole_db"] = internal_dynamics(str(dest))["hole_db"]
        row["sha256"] = sha256(dest)
        row["source_sha256"] = sha256(src)
        row["bytes"] = dest.stat().st_size
        row["ingested"] = datetime.now(timezone.utc).isoformat(
            timespec="seconds")
        row["hole_ceiling_db"] = BED_HOLE_MAX_DB
        row["written"] = True
    return row


def record(out_dir: Path, rows: list[dict]) -> Path:
    """Merge into the library manifest, keyed on the written track."""
    path = out_dir / MANIFEST
    book = {}
    if path.exists():
        existing = json.loads(path.read_text())
        book = {b["track"]: b for b in existing.get("beds", [])
                if isinstance(b, dict) and "track" in b}
    for row in rows:
        if row.get("written"):
            book[row["track"]] = row

    # A MANIFEST DESCRIBES THE LIBRARY, NOT ITS HISTORY. Merging alone kept
    # rows for files that are no longer there: a hand-written manifest left
    # three raw mp3s listed after ingest had replaced them with two wavs, so
    # the manifest claimed five beds over a library of two. A row whose file
    # is gone is not a record, it is a wrong answer to "what is in here".
    book = {name: row for name, row in book.items()
            if (out_dir / name).exists()}

    path.write_text(json.dumps({
        "what": "Loopable documentary beds. Every one entered through "
                "scripts/ingest_bed.py.",
        "why": "A raw candidate's fades are not the bed's hole. "
               "bed_cinematic_quiet reads 46.59 dB as a file and 7.04 dB as "
               "the 117.6s core a hand trim found; the mixer allows 10. See "
               "the module docstring of scripts/ingest_bed.py.",
        "read_by": "lib/shared_state.music_dir(), overridable with "
                   "MUSIC_LIBRARY_DIR",
        "mixer_hole_ceiling_db": BED_HOLE_MAX_DB,
        "ingest_hole_ceiling_db": INGEST_HOLE_CEILING_DB,
        "min_bed_seconds": MIN_BED_SECONDS,
        "beds": [book[k] for k in sorted(book)],
    }, indent=1) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("candidates", nargs="+")
    ap.add_argument("--out-dir", default=None,
                    help="default: the shared library, music_dir()")
    ap.add_argument("--min-seconds", type=float, default=MIN_BED_SECONDS)
    ap.add_argument("--hole-ceiling", type=float,
                    default=INGEST_HOLE_CEILING_DB,
                    help="the hole an ingested window may hold; see "
                         "INGEST_HOLE_CEILING_DB for what it buys")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir) if args.out_dir else music_dir()
    rows, refused = [], 0
    for src in args.candidates:
        row = ingest(src, out_dir, args.min_seconds, args.dry_run,
                     args.hole_ceiling)
        rows.append(row)
        name = Path(src).name
        if "refused" in row:
            refused += 1
            print(f"REFUSED  {name}\n         {row['refused']}"
                  f"  (file hole {row['source_hole_db']} dB)")
            continue
        verb = "would take" if args.dry_run else "took"
        print(f"{'OK      ' if not args.dry_run else 'DRY     '} {name}")
        print(f"         {verb} {row['seconds']:.1f}s of "
              f"{row['source_seconds']:.1f}s at "
              f"{row['window_start_s']:.1f}s-{row['window_end_s']:.1f}s")
        print(f"         file hole {row['source_hole_db']:.2f} dB -> window "
              f"{row['window_hole_db']:.2f} dB"
              + (f" -> written {row['hole_db']:.2f} dB"
                 if row.get("written") else ""))

    if not args.dry_run and any(r.get("written") for r in rows):
        print(f"\nmanifest: {record(out_dir, rows)}")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())

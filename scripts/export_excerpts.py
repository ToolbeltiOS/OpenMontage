#!/usr/bin/env python3
"""Cut review excerpts out of a delivered film.

An audio change is judged by ear on the passages where it matters, not on a
twenty-minute file somebody has to scrub through. The two that matter after a
mix change are the head — where a bed's character is most exposed, because
there is least narration over it — and an act boundary, where the bed
crossfades, the envelope lifts to its loudest level and the sting lands. Those
three things happen within five seconds of each other and nowhere else.

The video is re-encoded and the audio is not resampled. That is the right way
round for this job: `-c:v copy` can only start on a keyframe, so an excerpt
asked for at 598.6s would silently begin somewhere else, and the picture is
not what is being reviewed. The AUDIO is copied from the delivered mix stream
bit-for-bit via `-c:a copy`, so what the owner hears is the delivered film and
not a second-generation encode of it.

    python3 scripts/export_excerpts.py --project easter-island
    python3 scripts/export_excerpts.py --project easter-island \
        --window 0:180:first-3-minutes --out ~/Downloads
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Seconds either side of an act boundary. The owner's ask, 2026-10-25.
BOUNDARY_PAD = 30.0

#: The head of the film, in seconds.
HEAD_SECONDS = 180.0


def act_boundaries(project: str) -> list[tuple[str, float]]:
    """(name, seconds) of each act boundary, from the mix report.

    The mix report is the authority because `lib/mix_audio.py` writes it from
    the timeline it actually built — the narration segments laid end to end
    with the written air between them. Taking the boundaries from the script's
    section durations instead would be a second opinion, and the two drifting
    apart is how the picture and the sound came out of step once already.
    """
    report = ROOT / "projects" / project / "renders" / "mix_report.json"
    if not report.exists():
        return []
    air = (json.loads(report.read_text()) or {}).get("air") or {}
    bounds = air.get("act_boundaries") or []
    return [(f"boundary-{i + 1}", float(b)) for i, b in enumerate(bounds)]


def cut(film: Path, start: float, duration: float, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(film),
         "-t", f"{duration:.3f}",
         "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", "-c:a", "copy",
         "-movflags", "+faststart", str(dest)], check=True)


def seconds(path: Path) -> float:
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)]).strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--film", default=None)
    ap.add_argument("--out", default=str(Path.home() / "Downloads"))
    ap.add_argument("--window", action="append", default=[],
                    metavar="START:DURATION:NAME",
                    help="an explicit window; repeatable. Overrides the "
                         "defaults when given")
    ap.add_argument("--boundary", type=int, default=None,
                    help="only this act boundary (1-based)")
    args = ap.parse_args()

    film = Path(args.film) if args.film else \
        ROOT / "projects" / args.project / "renders" / "final.mp4"
    if not film.exists():
        raise SystemExit(f"no film at {film}")
    total = seconds(film)
    out = Path(args.out).expanduser()

    windows: list[tuple[str, float, float]] = []
    if args.window:
        for spec in args.window:
            start, dur, name = spec.split(":", 2)
            windows.append((name, float(start), float(dur)))
    else:
        windows.append(("first-3-minutes", 0.0, min(HEAD_SECONDS, total)))
        bounds = act_boundaries(args.project)
        if args.boundary is not None:
            bounds = [bounds[args.boundary - 1]] if \
                0 < args.boundary <= len(bounds) else []
        for name, at in bounds:
            start = max(0.0, at - BOUNDARY_PAD)
            windows.append((f"{name}-{at:.0f}s", start,
                            min(2 * BOUNDARY_PAD, total - start)))

    print(f"{film} — {total:.1f}s")
    for name, start, dur in windows:
        dest = out / f"{args.project}-{name}.mp4"
        cut(film, start, dur, dest)
        print(f"  {start:8.2f}s +{dur:6.2f}s  ->  {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

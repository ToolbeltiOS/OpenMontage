"""No cut lands on top of a cut the source already had.

WHY
---
A third of this film's shots are clips, and a clip is not a continuous take —
stock footage is frequently a cut-together sequence, and an archive reel is
almost always one. When the edit cuts away 8 frames before the source's own
cut, the viewer gets two cuts a quarter of a second apart and reads the second
one as a mistake. When the edit cuts away 8 frames AFTER one, they get a shot
that begins on the tail of a different shot.

Neither is visible in the EDL, which knows only that the clip starts at
31.98s and runs for 6.6 seconds. It is visible in the clip, which is where
this looks.

THE RULE
--------
No edit boundary within 12 frames of a scene change in the material it is
cutting from or to. Twelve because the playbook's shortest transition is 1.5s
and its shortest hold 1.5s, so a gap under half a second between two cuts is
never deliberate at this pace.

A scene change strictly INSIDE a used span is reported, not failed: it is a
cut the viewer sees that the EDL did not plan, which may be exactly what the
shot is for — a montage clip used as a montage — but should never be a
surprise.

    python3 lib/verify_source_cuts.py <render_props.json>
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: How close an edit boundary may come to a cut the source already had.
MIN_GAP_FRAMES = 12

#: PySceneDetect's content threshold. Its default is 27, which is tuned for
#: broadcast material; stock footage is graded flatter and misses real cuts at
#: that setting. 24 found every cut in the hand-checked clips below and no
#: false ones.
CONTENT_THRESHOLD = 24.0

#: Scene changes closer together than this are one change, not several. A hard
#: cut through a bright frame can register twice.
MERGE_WITHIN_S = 0.2

#: Above this correlation between the frames either side of it, a detected
#: change is the SAME SCENE ADVANCED rather than a cut to another one.
#:
#: Timelapse is why. One of run #1's clips is a satellite sequence of an
#: eruption: every step is a jump in content and PySceneDetect calls each one
#: a scene change, correctly about the pixels and wrongly about the edit —
#: the steps ARE the shot, and cutting near one is invisible. Measured on this
#: film's own clips, a quarter second either side at 64x36:
#:
#:     timelapse steps                     0.952  0.954  0.972
#:     real cuts in the same file         -0.194 -0.118
#:     a cut-together sequence             0.203 -0.060 -0.144  0.231
#:     everything else                     0.000 .. 0.714
#:
#: 0.85 sits in the gap with room on both sides. A step is reported and never
#: fails the gate; a cut is both.
SAME_SCENE_CORRELATION = 0.85

#: How far either side of a change the comparison frames are taken.
STEP_PROBE_S = 0.25

VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".avi"}


def scene_changes(path: str, threshold: float = CONTENT_THRESHOLD) -> list[float]:
    """Seconds, from the start of the file, where the source cuts."""
    from scenedetect import ContentDetector, SceneManager, open_video

    video = open_video(str(path))
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=threshold))
    manager.detect_scenes(video, show_progress=False)
    scenes = manager.get_scene_list()

    # the start of every scene but the first is a cut
    cuts = [s[0].seconds for s in scenes[1:]]
    merged: list[float] = []
    for t in sorted(cuts):
        if not merged or t - merged[-1] > MERGE_WITHIN_S:
            merged.append(t)
    return merged


def _frame(path: str, seconds: float, width: int = 64, height: int = 36):
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{max(seconds, 0.0):.3f}", "-i", path,
         "-frames:v", "1", "-vf", f"scale={width}:{height}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True).stdout
    if len(raw) < width * height:
        return None
    return np.frombuffer(raw[:width * height], dtype="uint8").astype("float32")


def is_a_step(path: str, seconds: float) -> bool:
    """Is this the same scene advanced, rather than a cut to another one?"""
    import numpy as np

    before = _frame(path, seconds - STEP_PROBE_S)
    after = _frame(path, seconds + STEP_PROBE_S)
    if before is None or after is None:
        return False
    before = before - before.mean()
    after = after - after.mean()
    scale = np.sqrt((before ** 2).sum()) * np.sqrt((after ** 2).sum())
    if not scale:
        return False
    return float((before * after).sum() / scale) >= SAME_SCENE_CORRELATION


def _cache_path(project_dir: Path) -> Path:
    return project_dir / "artifacts" / "source_scene_changes.json"


def check(cuts: list[dict[str, Any]], fps: float = 30.0,
          cache: dict[str, list[float]] | None = None, root: Path = ROOT
          ) -> tuple[list[str], dict[str, Any]]:
    cache = {} if cache is None else cache
    steps: dict[str, list[float]] = {}
    problems: list[str] = []
    notes: list[dict[str, Any]] = []
    gap_seconds = MIN_GAP_FRAMES / fps
    checked = 0

    for cut in cuts:
        source = cut.get("source")
        if not isinstance(source, str) or Path(source).suffix.lower() not in VIDEO_SUFFIXES:
            continue
        full = Path(source) if source.startswith("/") else root / source
        if not full.exists():
            continue
        key = os.path.relpath(full, root)
        if key not in cache:
            cache[key] = scene_changes(str(full))
        changes = cache[key]
        if not changes:
            checked += 1
            continue
        if key not in steps:
            steps[key] = [t for t in changes if is_a_step(str(full), t)]
        stepped = set(steps[key])

        # where in the SOURCE this shot begins and ends
        start = float(cut.get("source_in_seconds") or 0.0)
        length = float(cut["out_seconds"]) - float(cut["in_seconds"])
        end = start + length
        checked += 1

        for change in changes:
            if change in stepped:
                # a timelapse step: part of the shot, not a cut in it
                continue
            for name, boundary in (("in", start), ("out", end)):
                distance = abs(change - boundary)
                if distance <= gap_seconds:
                    problems.append(
                        f"{cut.get('id')}: the {name} point is "
                        f"{distance * fps:.1f} frames from a cut the source "
                        f"already has at {change:.2f}s in "
                        f"{Path(source).name} — two cuts that close read as "
                        f"one mistake")
            if start + gap_seconds < change < end - gap_seconds:
                notes.append({
                    "cut": cut.get("id"),
                    "seconds_into_shot": round(change - start, 2),
                    "source": Path(source).name,
                })

    measured = {
        "video_cuts_checked": checked,
        "sources_analysed": len(cache),
        "timelapse_steps_ignored": sum(len(v) for v in steps.values()),
        "boundaries_too_close": len(problems),
        "cuts_inside_a_shot": notes[:40],
        "cuts_inside_a_shot_count": len(notes),
    }
    return problems, measured


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("props")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--project", default=None,
                    help="cache the scene detection in the project's artifacts")
    args = ap.parse_args()

    blob = json.loads(Path(args.props).read_text())
    cuts = blob["cuts"] if isinstance(blob, dict) else blob

    cache_file = None
    cache: dict[str, list[float]] = {}
    if args.project:
        cache_file = _cache_path(ROOT / "projects" / args.project)
        if cache_file.exists():
            cache = json.loads(cache_file.read_text())

    problems, measured = check(cuts, args.fps, cache)
    if cache_file is not None:
        cache_file.write_text(json.dumps(cache, indent=1) + "\n")

    print(f"{measured['video_cuts_checked']} video cuts over "
          f"{measured['sources_analysed']} sources; "
          f"{measured['boundaries_too_close']} boundaries within "
          f"{MIN_GAP_FRAMES} frames of a source cut; "
          f"{measured['cuts_inside_a_shot_count']} source cuts inside a shot")
    for p in problems[:20]:
        print("  -", p)
    for n in measured["cuts_inside_a_shot"][:10]:
        print(f"  note: {n['cut']} carries a cut of its own "
              f"{n['seconds_into_shot']}s in ({n['source']})")
    print("SOURCE CUTS:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

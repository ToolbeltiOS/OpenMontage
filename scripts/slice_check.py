#!/usr/bin/env python3
"""Run a short slice of a real film through the whole delivery chain.

WHAT IT IS FOR
--------------
Merging a branch that touches the picture means answering one question:
does the real chain still produce a film that passes every gate? A full
render answers it in four hours. A two-minute slice answers it in about
twenty minutes, through `render_film.py` itself — the same plate pass, look
pass, type pass, mux and gates, not a reduced copy of them.

WHAT IT IS NOT
--------------
Not proof that the film is good. It is proof that the chain is not broken,
which is the question a merge asks.

HOW IT STAYS OUT OF THE FILM'S WAY
----------------------------------
  * it writes nothing into `projects/` — the topic picker treats any
    directory there as a film that exists, so a slice could quietly make a
    subject unpickable;
  * it renders into its own `out/<label>` so the film's plate, look and
    type passes are untouched; and
  * `render_film.py` already names its report after the delivered file
    rather than the project, so the slice's report cannot read as the
    film's.

    scripts/slice_check.py --project king-tut --seconds 120
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))


def source_project(slug: str) -> Path:
    for root in ("runner", "OpenMontage", "fix-render-finalise",
                 "asset-library"):
        project = ROOT.parent / root / "projects" / slug
        if (project / "artifacts" / "render_props.json").exists():
            return project
    raise SystemExit(f"{slug}: no render_props.json in any worktree")


def carve(props: dict, seconds: float) -> dict:
    """The cuts that fit WHOLE inside the window, and nothing half-in.

    Whole cuts only, because `check_timeline_coverage` refuses a timeline
    with a hole in it and a truncated cut leaves one. The slice therefore
    ends at a cut boundary, a little before the asked-for seconds.
    """
    kept = [c for c in props["cuts"] if float(c["out_seconds"]) <= seconds]
    if not kept:
        raise SystemExit(f"no cut ends within {seconds}s")
    end = max(float(c["out_seconds"]) for c in kept)
    out = dict(props)
    out["cuts"] = kept
    for key in ("overlays", "captions"):
        items = props.get(key) or []
        out[key] = [i for i in items
                    if float(i.get("out_seconds", 0)) <= end]
    out.pop("audio", None)
    return out, end


def trim_mix(mix: Path, seconds: float, dest: Path) -> Path:
    """The mix, cut to the slice.

    The delivery muxes picture and sound with `-shortest`. A full-length
    mix against a two-minute picture is not wrong, but a mix SHORTER than
    the picture takes the end off the film — which is how easter-island
    shipped 15 frames short — so the trim is to the slice's own end and the
    frame-count gate is left to check the result.
    """
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mix),
                    "-t", f"{seconds:.3f}", "-c", "copy", str(dest)],
                   check=True)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="the film to slice")
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--label", default=None,
                    help="work name; defaults to <project>-slice")
    ap.add_argument("--work", default=None,
                    help="where the slice's inputs and output go")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    label = args.label or f"{args.project}-slice"
    work = Path(args.work) if args.work else (
        Path("/private/tmp") / "openmontage-slices" / label)
    work.mkdir(parents=True, exist_ok=True)

    project = source_project(args.project)
    props = json.loads((project / "artifacts" / "render_props.json").read_text())

    # A FILM'S RELATIVE ASSET PATHS BELONG TO ITS OWN WORKTREE. `stage_assets`
    # resolves them against the tree it is running in, so slicing a film that
    # lives elsewhere reported dozens of assets as missing — measured on
    # they-said-it, 34 of them — when every one was on disk. Absolute paths
    # are untouched.
    sys.path.insert(0, str(ROOT / "lib"))
    from film_render import _asset_values
    owner = project.parent.parent
    for node, key, value in list(_asset_values(props)):
        if not value.startswith("/"):
            candidate = owner / value
            if candidate.exists():
                node[key] = str(candidate)

    sliced, end = carve(props, args.seconds)
    props_path = work / "render_props.json"
    props_path.write_text(json.dumps(sliced))

    from buildability import check_timeline_coverage
    holes, coverage = check_timeline_coverage(sliced["cuts"], 30)
    print(f"{args.project}: {len(sliced['cuts'])} cuts, {end:.2f}s, "
          f"{coverage['frames']} frames, {len(holes)} timeline problem(s)")
    if holes:
        for hole in holes[:5]:
            print("   TIMELINE:", hole)
        return 1

    mix = trim_mix(project / "renders" / "mix_final.wav", end, work / "mix.wav")
    dest = work / f"{label}.mp4"
    cmd = [sys.executable, str(ROOT / "scripts" / "render_film.py"),
           "--project", label, "--props", str(props_path),
           "--mix", str(mix), "--out", str(dest), "--force"]
    print("   " + " ".join(cmd))
    if args.dry_run:
        return 0
    done = subprocess.run(cmd)
    print(f"slice {'PASSED' if done.returncode == 0 else 'FAILED'} "
          f"({args.seconds:.0f}s asked, {end:.2f}s rendered)")
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main())

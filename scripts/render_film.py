#!/usr/bin/env python3
"""Render the whole film, and refuse to deliver a broken one.

THE ONLY FULL-FILM RENDER PATH
------------------------------
Run #1 was composed through the pipeline's compose stage and finished by
hand, and the gates that were written afterwards have never run on it. A film
produced by a different path from the demo is a film whose checks are a
different film's checks — so there is one path now, and both the demo and the
film go down it. The stages are in lib/film_render.py and are shared; the
only differences here are which props, which mix and how long.

    python scripts/render_film.py --project <id>

WHAT IT WILL NOT DO
-------------------
Overwrite a delivered film. Run #1 is published and must not be re-rendered,
so the output path is checked against every mp4 already in renders/ and the
run refuses rather than asking.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

from film_render import (COMPOSER, FPS, act_spans, deliver, extract_frames,  # noqa: E402
                         frame_count, gates, props_for_layer, remux,
                         render_look, render_plate, render_type, report)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", default=None,
                    help="delivered file; defaults to renders/final.mp4")
    ap.add_argument("--mix", default=None,
                    help="the mix to carry; defaults to renders/mix_final.wav")
    ap.add_argument("--props", default=None,
                    help="defaults to the project's artifacts/render_props.json")
    ap.add_argument("--force", action="store_true",
                    help="overwrite the output if it already exists")
    ap.add_argument("--skip-picture", action="store_true",
                    help="reuse the existing plate render and frame sequence")
    ap.add_argument("--gates-only", action="store_true",
                    help="re-run the gates and rewrite the report, rendering nothing")
    ap.add_argument("--remux", action="store_true",
                    help="put the mix onto the delivered film with -c:v copy "
                         "and re-run the gates; renders no picture")
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    props_path = Path(args.props) if args.props else project / "artifacts" / "render_props.json"
    props = json.loads(props_path.read_text())
    cuts = props["cuts"]
    count = frame_count(cuts, FPS)
    seconds = count / FPS

    renders = project / "renders"
    dest = Path(args.out) if args.out else renders / "final.mp4"
    mix = Path(args.mix) if args.mix else renders / "mix_final.wav"
    work = COMPOSER / "out" / args.project
    picture = work / "plate.mp4"
    look = work / "look.mp4"
    type_layer = work / "type.mov"
    frames_dir = COMPOSER / "public" / f"frames_{args.project}"

    if not mix.exists():
        raise SystemExit(f"no mix at {mix}")
    if args.remux and not dest.exists():
        raise SystemExit(f"--remux needs a delivered film at {dest}")
    if dest.exists() and not (args.force or args.gates_only or args.remux):
        raise SystemExit(
            f"{dest} already exists. A delivered film is not overwritten by "
            f"accident — run #1 is published. Pass --force if that is really "
            f"what you want, or --out to deliver somewhere else.")

    spans = act_spans(cuts)
    print(f"{args.project}: {len(cuts)} cuts, {seconds:.1f}s, {count} frames, "
          f"{len(spans)} act spans, mix {mix.name}")

    if args.remux:
        print("5. remux (picture copied, audio replaced)")
        remux(dest, mix)
    elif not args.gates_only:
        if not args.skip_picture:
            print("1. plate")
            render_plate(props_for_layer(props_path, "plate", work, args.project),
                         picture, count)
            print("2. frames")
            extract_frames(picture, frames_dir, count)
        print("3. look pass")
        render_look(frames_dir, look, count,
                    act=spans[0]["act"] if spans else "act1", acts=spans)
        if not args.skip_picture:
            print("4. type")
            render_type(props_for_layer(props_path, "type", work, args.project),
                        type_layer, count)
        print("5. deliver")
        deliver(look, type_layer, mix, dest)

    print("6. gates")
    mix_report = renders / "mix_report.json"
    expected = None
    if mix_report.exists():
        expected = ((json.loads(mix_report.read_text()) or {}).get("final") or {}).get("lufs")
    problems, results = gates(dest, picture, cuts, expected, FPS)
    # named after the file delivered, not the project: a slice rendered to
    # check the path works must not leave a report that reads as the film's
    out = report(f"Film delivery — {args.project} — {dest.name}", dest, picture,
                 count, seconds, results, problems, expected,
                 ROOT / "reports" / f"film_delivery_{dest.stem}.md")

    print(f"   -> {dest}")
    print(f"   -> {out.relative_to(ROOT)}")
    for p in problems[:20]:
        print("   FAIL:", p)
    print("FILM DELIVERY:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

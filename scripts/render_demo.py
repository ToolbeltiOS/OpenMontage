#!/usr/bin/env python3
"""Render the act 2 demo end to end, and refuse to deliver a broken one.

The ninety-second window, down the same path as the film. Every stage and
every gate is in lib/film_render.py and shared with scripts/render_film.py —
the only differences are which props, which mix and how long.

WHY THIS SCRIPT EXISTS
----------------------
The first demo was rendered by hand: a picture render, a frame extraction, a
look pass and an encode, four commands typed in order. It shipped silent,
because the fifth command — the one that puts the mix into the file — was
never typed, and nothing was responsible for noticing. It also shipped with
its frames out of order, because the only thing that looked at the result was
a human watching it on a laptop. A stage that exists only as a habit is a
stage that can be skipped.

    python scripts/render_demo.py --project they-said-it-couldnt-be-built --bed 30
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

from film_render import (COMPOSER, FPS, deliver, extract_frames, frame_count,  # noqa: E402
                         gates, props_for_layer, render_look, render_plate,
                         render_type, report)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--bed", type=int, default=30,
                    help="which bed level's mix to deliver: 36, 30 or 28")
    ap.add_argument("--skip-picture", action="store_true",
                    help="reuse the existing plate render and frame sequence")
    ap.add_argument("--gates-only", action="store_true",
                    help="re-run the gates and rewrite the report, rendering nothing")
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    props_path = project / "artifacts" / "demo_act2_props.json"
    cuts = json.loads(props_path.read_text())["cuts"]
    count = frame_count(cuts, FPS)
    seconds = count / FPS

    out_dir = project / "renders" / "demo"
    work = COMPOSER / "out" / "demo"
    picture = work / "act2_base.mp4"
    look = work / "act2_look.mp4"
    type_layer = work / "act2_type.mov"
    frames_dir = COMPOSER / "public" / "demoframes"
    mix = out_dir / f"act2_demo_bed{args.bed}.wav"
    dest = out_dir / "act2_demo.mp4"

    if not mix.exists():
        raise SystemExit(f"no mix at {mix} — run scripts/build_demo_audio.py first")
    if args.gates_only and not dest.exists():
        raise SystemExit(f"nothing delivered at {dest} to check")

    print(f"demo: {len(cuts)} cuts, {seconds:.1f}s, {count} frames, bed -{args.bed}")
    if not args.gates_only:
        if not args.skip_picture:
            print("1. plate")
            render_plate(props_for_layer(props_path, "plate", work), picture, count)
            print("2. frames")
            extract_frames(picture, frames_dir, count)
        print("3. look pass")
        render_look(frames_dir, look, count, act="act2")
        if not args.skip_picture:
            print("4. type")
            render_type(props_for_layer(props_path, "type", work), type_layer, count)
        print("5. deliver")
        deliver(look, type_layer, mix, dest)

    print("6. gates")
    audio_report = json.loads((out_dir / "demo_audio_report.json").read_text())
    expected = next((m["mix_measured_lufs"] for m in audio_report["mixes"]
                     if m["file"] == mix.name), None)
    problems, results = gates(dest, picture, cuts, expected, FPS)
    out = report(f"Demo delivery — act 2, bed -{args.bed}", dest, picture, count,
                 seconds, results, problems, expected,
                 ROOT / "reports" / f"demo_delivery_bed{args.bed}.md")

    print(f"   -> {dest.relative_to(ROOT)}")
    print(f"   -> {out.relative_to(ROOT)}")
    for p in problems[:20]:
        print("   FAIL:", p)
    print("DEMO DELIVERY:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

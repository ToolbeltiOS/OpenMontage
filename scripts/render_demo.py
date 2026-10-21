#!/usr/bin/env python3
"""Render the act 2 demo end to end, and refuse to deliver a broken one.

WHY THIS SCRIPT EXISTS
----------------------
The first demo was rendered by hand: a picture render, a frame extraction, a
look pass and an encode, four commands typed in order. It shipped silent,
because the fifth command — the one that puts the mix into the file — was
never typed, and nothing was responsible for noticing. It also shipped with
its frames out of order, because the only thing that looked at the result was
a human watching it on a laptop.

A stage that exists only as a habit is a stage that can be skipped. So the
whole path is here, the mux is not optional, and the gates run on the file
that is about to be delivered rather than on the plans behind it:

    1. picture      Explainer over the demo props, treatment off
    2. frames       the picture as a JPEG sequence, for the shader to sample
    3. look         FilmLookPass over that sequence
    4. deliver      trim the composition's trailing padding, mux the mix
    5. gates        frame motion, frame order, delivery audio — all blocking

    python scripts/render_demo.py --project they-said-it-couldnt-be-built --bed 30
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

FPS = 30
COMPOSER = ROOT / "remotion-composer"
ENTRY = "src/index.tsx"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("  $", " ".join(str(c) for c in cmd[:9]), "..." if len(cmd) > 9 else "")
    subprocess.run(cmd, cwd=cwd, check=True)


def render_picture(props: Path, dest: Path) -> None:
    """The film itself, with the CSS treatment off: the look is a second pass."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["npx", "remotion", "render", ENTRY, "Explainer", str(dest),
         f"--props={props}", "--gl=angle"], cwd=COMPOSER)


def extract_frames(picture: Path, frames_dir: Path, count: int) -> None:
    """The picture as stills, because WebGL cannot sample a <video>.

    Only as many frames as the edit declares: the composition pads a second
    onto the end for a fade the demo does not have, and that second is an
    empty background. It is dropped here rather than encoded and trimmed.
    """
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(picture),
         "-frames:v", str(count), "-q:v", "2",
         str(frames_dir / "f_%05d.jpg")])
    got = len(list(frames_dir.glob("f_*.jpg")))
    if got != count:
        raise SystemExit(f"extracted {got} frames, expected {count}")


def render_look(frames_dir: Path, dest: Path, count: int, act: str = "act2") -> None:
    props = json.dumps({"dir": frames_dir.name, "act": act, "stack": "full"})
    run(["npx", "remotion", "render", ENTRY, "FilmLookPass", str(dest),
         f"--props={props}", f"--frames=0-{count - 1}", "--gl=angle"], cwd=COMPOSER)


def mux(picture: Path, mix: Path, dest: Path) -> None:
    """The step that was missing. The picture is copied, never re-encoded."""
    run(["ffmpeg", "-v", "error", "-y", "-i", str(picture), "-i", str(mix),
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "320k", "-shortest", str(dest)])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--bed", type=int, default=30,
                    help="which bed level's mix to deliver: 36, 30 or 28")
    ap.add_argument("--skip-picture", action="store_true",
                    help="reuse the existing picture render and frame sequence")
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    props_path = project / "artifacts" / "demo_act2_props.json"
    props = json.loads(props_path.read_text())
    cuts = props["cuts"]
    end = max(float(c["out_seconds"]) for c in cuts)
    count = round(end * FPS)

    out_dir = project / "renders" / "demo"
    work = COMPOSER / "out" / "demo"
    picture = work / "act2_base.mp4"
    look = work / "act2_look.mp4"
    frames_dir = COMPOSER / "public" / "demoframes"
    mix = out_dir / f"act2_demo_bed{args.bed}.wav"
    dest = out_dir / "act2_demo.mp4"

    if not mix.exists():
        raise SystemExit(f"no mix at {mix} — run scripts/build_demo_audio.py first")

    print(f"demo: {len(cuts)} cuts, {end:.1f}s, {count} frames, bed -{args.bed}")
    if not args.skip_picture:
        print("1. picture")
        render_picture(props_path, picture)
        print("2. frames")
        extract_frames(picture, frames_dir, count)
    print("3. look pass")
    render_look(frames_dir, look, count)
    print("4. deliver")
    mux(look, mix, dest)

    print("5. gates")
    from verify_delivery_audio import check as check_audio
    from verify_frame_motion import check as check_motion
    from verify_frame_order import check as check_order

    audio_report = json.loads((out_dir / "demo_audio_report.json").read_text())
    expected = next((m["mix_measured_lufs"] for m in audio_report["mixes"]
                     if m["file"] == mix.name), None)

    problems: list[str] = []
    motion_problems, motion = check_motion(str(dest), FPS)
    order_problems, order = check_order(str(dest), cuts, str(picture), FPS)
    audio_problems, audio = check_audio(str(dest), expected)
    problems += [f"frame motion: {p}" for p in motion_problems]
    problems += [f"frame order: {p}" for p in order_problems]
    problems += [f"delivery audio: {p}" for p in audio_problems]

    lines = [
        f"# Demo delivery — act 2, bed -{args.bed}",
        "",
        f"`{dest.relative_to(ROOT)}` · {count} frames · {end:.1f}s · "
        f"picture `{picture.relative_to(ROOT)}`",
        "",
        "## Gates", "",
        "| check | measured | verdict |",
        "|---|---|---|",
        f"| frame motion | {motion['duplicate_pairs_pct']}% duplicate pairs, "
        f"longest freeze {motion['longest_freeze_seconds']}s, timestamps "
        f"{'constant' if motion['timestamps_constant'] else 'IRREGULAR'} | "
        f"{'PASS' if not motion_problems else 'FAIL'} |",
        f"| frame order | {order['out_of_order_count']} frames out of place, "
        f"{order['isolated_black_runs']} isolated black, correlation with the "
        f"picture render {order['reference_correlation']} | "
        f"{'PASS' if not order_problems else 'FAIL'} |",
        f"| delivery audio | {audio.get('mean_dbfs')} dBFS mean, "
        f"{audio.get('integrated_lufs')} LUFS against the mix's {expected} "
        f"({audio.get('loudness_delta_db')} dB) | "
        f"{'PASS' if not audio_problems else 'FAIL'} |",
        "",
        "## Luma map", "",
        "One character per frame, 30 per row — a second a row. `#` is black, "
        "`+` under 12, then `.` `:` `-` `=` `*` `o` `O` `@` brightening. A cut "
        "is a step; a frame from somewhere else is one character that belongs "
        "to neither side of it.", "",
        "```",
    ]
    lines += order["luma_map"]
    lines += ["```", ""]
    if problems:
        lines += ["## Failures", ""] + [f"- {p}" for p in problems] + [""]
    report = ROOT / "reports" / f"demo_delivery_bed{args.bed}.md"
    report.write_text("\n".join(lines))

    print(f"   -> {dest.relative_to(ROOT)}")
    print(f"   -> {report.relative_to(ROOT)}")
    for p in problems[:20]:
        print("   FAIL:", p)
    print("DEMO DELIVERY:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

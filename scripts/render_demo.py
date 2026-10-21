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

    1. plate        Explainer with the type hidden, treatment off
    2. frames       the plate as a JPEG sequence, for the shader to sample
    3. look         FilmLookPass over that sequence
    4. type         Explainer with ONLY the type, over transparency
    5. deliver      type over the graded plate, and the mix with it
    6. gates        frame motion, frame order, type lock, delivery audio

Stages 1 and 4 are the same film rendered twice from the same tree, so that
the composite order can be plate -> grade and vignette and grain -> type. A
single flat render puts the grain on the glyph edges, which is half of why
the type shook; see src/design/layers.tsx for the other half.

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


def props_for_layer(props: Path, mode: str, work: Path) -> Path:
    """The same props with one field added, written where the renderer can see it."""
    blob = json.loads(props.read_text())
    blob["layer_mode"] = mode
    dest = work / f"props_{mode}.json"
    dest.write_text(json.dumps(blob))
    return dest


def render_plate(props: Path, dest: Path, count: int) -> None:
    """The film with the type laid out but not inked. The shader runs over this."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["npx", "remotion", "render", ENTRY, "Explainer", str(dest),
         f"--props={props}", f"--frames=0-{count - 1}", "--gl=angle"], cwd=COMPOSER)


def render_type(props: Path, dest: Path, count: int) -> None:
    """Only the type, over transparency.

    ProRes 4444 because it is the one format in the renderer that carries an
    alpha channel losslessly. It is a working file — 726MB for ninety seconds
    — and it stays in remotion-composer/out, which is gitignored, so that
    --skip-picture and --gates-only can reuse it.
    """
    run(["npx", "remotion", "render", ENTRY, "Explainer", str(dest),
         f"--props={props}", f"--frames=0-{count - 1}",
         "--codec=prores", "--prores-profile=4444",
         "--pixel-format=yuva444p10le", "--image-format=png", "--gl=angle"],
        cwd=COMPOSER)


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


def deliver(look: Path, type_layer: Path, mix: Path, dest: Path) -> None:
    """Type over the graded plate, and the mix with it.

    One ffmpeg call, so the picture is encoded once rather than once for the
    composite and again for the mux. The mux half of this is the step that was
    missing entirely when the demo first shipped silent.
    """
    run(["ffmpeg", "-v", "error", "-y",
         "-i", str(look), "-i", str(type_layer), "-i", str(mix),
         "-filter_complex", "[0:v][1:v]overlay=format=auto:eof_action=pass[v]",
         "-map", "[v]", "-map", "2:a:0",
         "-c:v", "libx264", "-crf", "16", "-preset", "medium",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k",
         "-shortest", str(dest)])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--bed", type=int, default=30,
                    help="which bed level's mix to deliver: 36, 30 or 28")
    ap.add_argument("--skip-picture", action="store_true",
                    help="reuse the existing picture render and frame sequence")
    ap.add_argument("--gates-only", action="store_true",
                    help="re-run the gates and rewrite the report, rendering nothing")
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    props_path = project / "artifacts" / "demo_act2_props.json"
    props = json.loads(props_path.read_text())
    cuts = props["cuts"]
    end = max(float(c["out_seconds"]) for c in cuts)
    count = round(end * FPS)

    out_dir = project / "renders" / "demo"
    work = COMPOSER / "out" / "demo"
    work.mkdir(parents=True, exist_ok=True)
    picture = work / "act2_base.mp4"
    look = work / "act2_look.mp4"
    type_layer = work / "act2_type.mov"
    frames_dir = COMPOSER / "public" / "demoframes"
    mix = out_dir / f"act2_demo_bed{args.bed}.wav"
    dest = out_dir / "act2_demo.mp4"

    if not mix.exists():
        raise SystemExit(f"no mix at {mix} — run scripts/build_demo_audio.py first")

    print(f"demo: {len(cuts)} cuts, {end:.1f}s, {count} frames, bed -{args.bed}")
    if args.gates_only and not dest.exists():
        raise SystemExit(f"nothing delivered at {dest} to check")
    if not args.gates_only and not args.skip_picture:
        print("1. plate")
        render_plate(props_for_layer(props_path, "plate", work), picture, count)
        print("2. frames")
        extract_frames(picture, frames_dir, count)
    if not args.gates_only:
        print("3. look pass")
        render_look(frames_dir, look, count)
        if not args.skip_picture:
            print("4. type")
            render_type(props_for_layer(props_path, "type", work), type_layer, count)
        print("5. deliver")
        deliver(look, type_layer, mix, dest)

    print("6. gates")
    from verify_delivery_audio import check as check_audio
    from verify_frame_motion import check as check_motion
    from verify_frame_order import check as check_order
    from verify_type_lock import check as check_type, plate_is_clean

    audio_report = json.loads((out_dir / "demo_audio_report.json").read_text())
    expected = next((m["mix_measured_lufs"] for m in audio_report["mixes"]
                     if m["file"] == mix.name), None)

    problems: list[str] = []
    motion_problems, motion = check_motion(str(dest), FPS)
    order_problems, order = check_order(str(dest), cuts, str(picture), FPS)
    audio_problems, audio = check_audio(str(dest), expected)
    type_problems, type_lock = check_type(str(dest), cuts, FPS)
    # ...and that the split was complete in the first place. A text element
    # nobody marked is baked into the plate, grained on its edges and drifting
    # with it — which is the defect, wearing the fix as a disguise.
    plate_problems, plate_purity = plate_is_clean(str(picture), cuts)
    problems += [f"frame motion: {p}" for p in motion_problems]
    problems += [f"frame order: {p}" for p in order_problems]
    problems += [f"type lock: {p}" for p in type_problems]
    problems += [f"plate purity: {p}" for p in plate_problems]
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
        f"| plate purity | {plate_purity['words_in_plate']} words legible in "
        f"the plate pass | {'PASS' if not plate_problems else 'FAIL'} |",
        f"| type lock | {type_lock['scenes_sampled']} text-bearing scenes "
        f"sampled a second apart, {type_lock['scenes_with_movement']} with any "
        f"word in a different place, worst {type_lock['worst_shift_px']}px | "
        f"{'PASS' if not type_problems else 'FAIL'} |",
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

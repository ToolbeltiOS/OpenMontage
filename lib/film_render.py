"""The render path: plate, look, type, deliver, gates.

ONE PATH, NOT TWO
-----------------
The act 2 demo was first rendered by hand — a picture render, a frame
extraction, a look pass and an encode, four commands typed in order — and it
shipped silent, because the fifth command, the one that puts the mix into the
file, was never typed and nothing was responsible for noticing. The demo got
a script. The film did not, and a film rendered by a different path from the
demo is a film whose gates have never run on it.

So the stages live here and both scripts call them. `scripts/render_demo.py`
is the ninety-second window; `scripts/render_film.py` is the whole film; the
only differences between them are which props, which mix and how long.

THE STAGES
----------
  1. plate      the film with the type laid out but not inked
  2. frames     the plate as a JPEG sequence, for the shader to sample
  3. look       FilmLookPass over that sequence
  4. type       the film with ONLY the type, over transparency
  5. deliver    type over the graded plate, and the mix with it
  6. gates      frame motion, frame order, plate purity, type lock, delivery
                audio — all blocking

Stages 1 and 4 are the same film rendered twice from the same tree, so that
the composite order can be plate -> grade and vignette and grain -> type. A
single flat render puts the grain on the glyph edges, which is half of why
the type shook; see remotion-composer/src/design/layers.tsx for the other
half.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "remotion-composer"
ENTRY = "src/index.tsx"
FPS = 30


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("  $", " ".join(str(c) for c in cmd[:9]), "..." if len(cmd) > 9 else "")
    subprocess.run(cmd, cwd=cwd, check=True)


def frame_count(cuts: list[dict[str, Any]], fps: int = FPS) -> int:
    """Frames up to the last cut's end.

    Not the composition's own duration: `calculateMetadata` adds a second of
    padding for a final fade, and in anything without one that second is an
    empty background gradient. Dropping it here also makes the picture and the
    mix exactly the same length.
    """
    return round(max(float(c["out_seconds"]) for c in cuts) * fps)


def act_spans(cuts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """When each act is on screen, for the shader's per-act grade.

    The grade is per act and the look pass is one composition, so without this
    a twenty-minute film is graded as whichever act was named first.
    """
    spans: list[dict[str, Any]] = []
    for cut in cuts:
        raw = cut.get("actNumber") or cut.get("act")
        if raw is None:
            continue
        name = f"act{int(str(raw).strip().lstrip('0') or 0)}"
        start, end = float(cut["in_seconds"]), float(cut["out_seconds"])
        if spans and spans[-1]["act"] == name:
            spans[-1]["to_seconds"] = end
        else:
            spans.append({"act": name, "from_seconds": start, "to_seconds": end})
    return spans


def props_for_layer(props_path: Path, mode: str, work: Path) -> Path:
    """The same props with one field added, written where the renderer sees it."""
    blob = json.loads(props_path.read_text())
    blob["layer_mode"] = mode
    work.mkdir(parents=True, exist_ok=True)
    dest = work / f"props_{mode}.json"
    dest.write_text(json.dumps(blob))
    return dest


def render_plate(props: Path, dest: Path, count: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["npx", "remotion", "render", ENTRY, "Explainer", str(dest),
         f"--props={props}", f"--frames=0-{count - 1}", "--gl=angle"], cwd=COMPOSER)


def extract_frames(picture: Path, frames_dir: Path, count: int) -> None:
    """The plate as stills, because WebGL cannot sample a <video>."""
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(picture),
         "-frames:v", str(count), "-q:v", "2", str(frames_dir / "f_%05d.jpg")])
    got = len(list(frames_dir.glob("f_*.jpg")))
    if got != count:
        raise SystemExit(f"extracted {got} frames, expected {count}")


def render_look(frames_dir: Path, dest: Path, count: int,
                act: str = "act2", acts: list[dict[str, Any]] | None = None) -> None:
    props: dict[str, Any] = {"dir": frames_dir.name, "act": act, "stack": "full",
                             "frames": count}
    if acts:
        props["acts"] = acts
    run(["npx", "remotion", "render", ENTRY, "FilmLookPass", str(dest),
         f"--props={json.dumps(props)}", f"--frames=0-{count - 1}", "--gl=angle"],
        cwd=COMPOSER)


def render_type(props: Path, dest: Path, count: int) -> None:
    """Only the type, over transparency.

    ProRes 4444 because it is the one format in the renderer that carries an
    alpha channel losslessly. It is a working file — about 8MB a second — and
    it stays in remotion-composer/out, which is gitignored.
    """
    run(["npx", "remotion", "render", ENTRY, "Explainer", str(dest),
         f"--props={props}", f"--frames=0-{count - 1}",
         "--codec=prores", "--prores-profile=4444",
         "--pixel-format=yuva444p10le", "--image-format=png", "--gl=angle"],
        cwd=COMPOSER)


def deliver(look: Path, type_layer: Path, mix: Path, dest: Path) -> None:
    """Type over the graded plate, and the mix with it.

    One ffmpeg call, so the picture is encoded once rather than once for the
    composite and again for the mux. The mux half is the step that was missing
    entirely when the demo first shipped silent.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y",
         "-i", str(look), "-i", str(type_layer), "-i", str(mix),
         "-filter_complex", "[0:v][1:v]overlay=format=auto:eof_action=pass[v]",
         "-map", "[v]", "-map", "2:a:0",
         "-c:v", "libx264", "-crf", "16", "-preset", "medium",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k",
         "-shortest", str(dest)])


def gates(dest: Path, picture: Path, cuts: list[dict[str, Any]],
          expected_lufs: float | None, fps: int = FPS
          ) -> tuple[list[str], dict[str, Any]]:
    """Every blocking check, on the file that is about to be delivered."""
    sys.path.insert(0, str(ROOT / "lib"))
    from verify_delivery_audio import check as check_audio
    from verify_frame_motion import check as check_motion
    from verify_frame_order import check as check_order
    from verify_type_lock import check as check_type, plate_is_clean

    results: dict[str, Any] = {}
    problems: list[str] = []
    for name, (found, measured) in {
        "frame motion": check_motion(str(dest), fps),
        "frame order": check_order(str(dest), cuts, str(picture), fps),
        "plate purity": plate_is_clean(str(picture), cuts),
        "type lock": check_type(str(dest), cuts, fps),
        "delivery audio": check_audio(str(dest), expected_lufs),
    }.items():
        results[name] = measured
        problems += [f"{name}: {p}" for p in found]
    return problems, results


def report(title: str, dest: Path, picture: Path, count: int, seconds: float,
           results: dict[str, Any], problems: list[str], expected_lufs: float | None,
           out: Path) -> Path:
    motion = results["frame motion"]
    order = results["frame order"]
    purity = results["plate purity"]
    type_lock = results["type lock"]
    audio = results["delivery audio"]

    def verdict(name: str) -> str:
        return "FAIL" if any(p.startswith(name + ":") for p in problems) else "PASS"

    lines = [
        f"# {title}",
        "",
        f"`{dest.relative_to(ROOT) if dest.is_relative_to(ROOT) else dest}` · "
        f"{count} frames · {seconds:.1f}s · plate "
        f"`{picture.relative_to(ROOT) if picture.is_relative_to(ROOT) else picture}`",
        "",
        "## Gates", "",
        "| check | measured | verdict |",
        "|---|---|---|",
        f"| frame motion | {motion['duplicate_pairs_pct']}% duplicate pairs, "
        f"longest freeze {motion['longest_freeze_seconds']}s, timestamps "
        f"{'constant' if motion['timestamps_constant'] else 'IRREGULAR'} | "
        f"{verdict('frame motion')} |",
        f"| frame order | {order['out_of_order_count']} frames out of place, "
        f"{order['isolated_black_runs']} isolated black, correlation with the "
        f"plate {order['reference_correlation']} | {verdict('frame order')} |",
        f"| plate purity | {purity['words_in_plate']} words legible in the "
        f"plate pass | {verdict('plate purity')} |",
        f"| type lock | {type_lock['scenes_sampled']} text-bearing scenes "
        f"sampled a second apart, {type_lock['scenes_with_movement']} with a "
        f"word in a different place, worst {type_lock['worst_shift_px']}px | "
        f"{verdict('type lock')} |",
        f"| delivery audio | {audio.get('mean_dbfs')} dBFS mean, "
        f"{audio.get('integrated_lufs')} LUFS against the mix's {expected_lufs} "
        f"({audio.get('loudness_delta_db')} dB) | {verdict('delivery audio')} |",
        "",
        "## Luma map", "",
        "One character per frame, 30 per row — a second a row. `#` is black, "
        "`+` under 12, then `.` `:` `-` `=` `*` `o` `O` `@` brightening. A cut "
        "is a step; a frame from somewhere else is one character that belongs "
        "to neither side of it.", "",
        "```",
    ] + order["luma_map"] + ["```", ""]
    if problems:
        lines += ["## Failures", ""] + [f"- {p}" for p in problems] + [""]
    out.write_text("\n".join(lines))
    return out

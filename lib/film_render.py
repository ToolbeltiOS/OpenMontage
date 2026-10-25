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

import hashlib
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

    Act names are section ids, and a film has sections that are not numbered:
    this crashed on `cold_open` with `invalid literal for int()`, because it
    coerced every label to `act<N>` and the demo's cuts were numbered "01".
    `gradeForAct` in design/system.ts has always normalised the same two
    forms — a section id as it stands, a bare number to `act<N>` — so this
    mirrors it rather than inventing a third rule, and `cold_open` and
    `outro` keep the grades the playbook writes for them.
    """
    spans: list[dict[str, Any]] = []
    for cut in cuts:
        # The SECTION ID first, the chrome's display number only as a
        # fallback. They agree on a numbered act and disagree on every other
        # section: the cold open carries actNumber "00", which normalises to
        # `act0` — a key no grade table has — so 35 seconds of it was being
        # graded with the fallback while `act: cold_open` sat right beside it
        # naming the grade the playbook writes. It also split the cold open
        # into two spans with a third in between.
        raw = cut.get("act") or cut.get("actNumber")
        if raw is None:
            continue
        key = str(raw).strip().lower()
        name = f"act{int(key)}" if key.isdigit() else key
        start, end = float(cut["in_seconds"]), float(cut["out_seconds"])
        if spans and spans[-1]["act"] == name:
            spans[-1]["to_seconds"] = end
        else:
            spans.append({"act": name, "from_seconds": start, "to_seconds": end})
    return spans


#: File extensions a props value has to end in to be treated as an asset.
ASSET_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif",
                  ".mp4", ".mov", ".webm")


def _asset_values(blob: Any):
    """Every (container, key, value) in the props that names a local asset."""
    stack: list[Any] = [blob]
    while stack:
        node = stack.pop()
        items = (node.items() if isinstance(node, dict)
                 else enumerate(node) if isinstance(node, list) else ())
        for key, value in items:
            if isinstance(value, str):
                plain = value.split("?")[0].lower()
                if (plain.endswith(ASSET_SUFFIXES)
                        and not value.startswith(("http://", "https://", "data:"))):
                    yield node, key, value
            elif isinstance(value, (dict, list)):
                stack.append(value)


def stage_assets(blob: Any, project: str) -> dict[str, Any]:
    """Put every asset the props name where the renderer can actually read it.

    WHY THIS STAGE EXISTS
    ---------------------
    The first real film render died at frame 0 with

        Not allowed to load local resource:
        file:///Users/.../renders/proxies/wm_20150500.jpg

    87 of the 104 asset paths in the props were absolute filesystem paths.
    `resolveAsset` in the composer turns an absolute path into a `file://`
    URL, and a page served from http://localhost is not allowed to load one —
    so that branch of the resolver cannot work in a render or in the Studio.
    It looks accommodating and is a dead end.

    Remotion reads assets from `remotion-composer/public/`, which is why the
    demo path worked: `build_demo_cut.py` copied its assets in. The film path
    had no such step, because run #1 was finished by hand and the gates were
    written against the demo. So the one documented full-film path had never
    once resolved a real project's assets.

    Hard links, not copies: the proxies are hundreds of megabytes and the
    staging directory is gitignored working space. A cross-device link falls
    back to a copy.
    """
    stage = COMPOSER / "public" / f"assets_{project}"
    stage.mkdir(parents=True, exist_ok=True)

    missing: list[str] = []
    for node, key, value in list(_asset_values(blob)):
        source = Path(value) if value.startswith("/") else ROOT / value
        if not source.exists():
            missing.append(value)
            continue
        # The basename alone collides: two acts can both carry a detail.jpg.
        digest = hashlib.sha1(str(source.resolve()).encode()).hexdigest()[:8]
        dest = stage / f"{digest}_{source.name}"
        if not dest.exists():
            try:
                os.link(source, dest)
            except OSError:
                shutil.copy2(source, dest)
        node[key] = f"{stage.name}/{dest.name}"

    if missing:
        raise SystemExit(
            f"{len(missing)} asset(s) in the props do not exist, and a render "
            f"finds that out at the frame that needs them:\n  "
            + "\n  ".join(missing[:10]))
    return blob


def props_for_layer(props_path: Path, mode: str, work: Path,
                    project: str | None = None) -> Path:
    """The same props with one field added, written where the renderer sees it.

    `project` names the staging directory under `public/`. Without it the
    props go through unstaged, which is only right for props that already
    point into `public/` — the demo's do, because its own builder copied them
    there.
    """
    blob = json.loads(props_path.read_text())
    blob["layer_mode"] = mode
    if project:
        # The renderer has no business with the mix. `deliver()` is the one
        # place the audio enters, by ffmpeg, onto the finished picture — and
        # the plate, look and type passes would otherwise each carry a
        # 232MB wav through Remotion's asset downloader, which refuses a
        # file:// URL anyway. Picture-only layers, mix at the mux.
        blob.pop("audio", None)
        blob = stage_assets(blob, project)
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


def remux(dest: Path, mix: Path) -> None:
    """Put a new mix onto a delivered film without touching the picture.

    `-c:v copy`, so the video stream is the bytes that were already graded,
    composited and encoded — not a second generation of them. An audio change
    is the one kind of change that can be delivered this way, and a twenty
    minute ProRes-to-h264 pass is the one kind of cost worth avoiding.

    THIS IS NOT A LICENCE TO FIX AUDIO DOWNSTREAM. The mix it carries has to
    be one `lib/mix_audio.py` built from the EDL, which is what the input hash
    beside `mix_final.wav` exists to say. A remux of a mix that was adjusted
    by hand is exactly the defect that put rejected music back into run #1 on
    the next re-render.
    """
    tmp = dest.with_suffix(".remux.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(dest), "-i", str(mix),
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
         "-shortest", "-movflags", "+faststart", str(tmp)])
    # Only once ffmpeg has written a whole file. Replacing the delivered film
    # with a truncated one because the remux died halfway is not a trade
    # anybody would make.
    tmp.replace(dest)


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

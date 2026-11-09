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
                         render_look, render_plate, render_type, report, verified_stills,
                         verified_video)


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
    ap.add_argument("--redo", default="",
                    help="comma-separated passes to render again even though "
                         "their output verifies: plate, frames, look, type. "
                         "A pass whose output holds the frames the edit asks "
                         "for is reused by default — see verified_video.")
    ap.add_argument("--skip-picture", action="store_true",
                    help="reuse the existing plate render and frame sequence")
    ap.add_argument("--gates-only", action="store_true",
                    help="re-run the gates and rewrite the report, rendering nothing")
    ap.add_argument("--remux", action="store_true",
                    help="put the mix onto the delivered film with -c:v copy "
                         "and re-run the gates; renders no picture")
    ap.add_argument("--deliver-only", action="store_true",
                    help="re-composite the look and type passes already on "
                         "disk into the delivered file and re-run the gates; "
                         "renders nothing in Remotion. Use this, not --remux, "
                         "when the delivered file is missing frames: a remux "
                         "copies the stream it is given and cannot put back "
                         "what is not in it")
    args = ap.parse_args()

    redo = {w.strip() for w in args.redo.split(",") if w.strip()}
    unknown = redo - {"plate", "frames", "look", "type"}
    if unknown:
        raise SystemExit(f"--redo names no such pass: {', '.join(sorted(unknown))}")

    project = ROOT / "projects" / args.project
    props_path = Path(args.props) if args.props else project / "artifacts" / "render_props.json"
    props = json.loads(props_path.read_text())
    cuts = props["cuts"]

    # BEFORE ANY PASS, because this is answerable from the props in a
    # millisecond and costs hours to find afterwards. A frame no cut covers
    # is painted as the composition's bare background and survives every
    # delivery gate there is; film #1 shipped with eight of them.
    sys.path.insert(0, str(ROOT / "lib"))
    from buildability import check_timeline_coverage
    holes, coverage = check_timeline_coverage(cuts, FPS)
    if holes:
        for hole in holes[:20]:
            print("   TIMELINE:", hole)
        raise SystemExit(
            f"{args.project}: {coverage['gap_frames']} frame(s) belong to no "
            f"cut and {coverage['overlap_frames']} to more than one. The "
            f"timeline has to cover every frame exactly once before anything "
            f"is rendered from it.")

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
    if args.deliver_only:
        for needed in (look, type_layer):
            if not needed.exists():
                raise SystemExit(
                    f"--deliver-only needs {needed}, which is a Remotion "
                    f"render. Drop the flag to rebuild it.")
    if dest.exists() and not (args.force or args.gates_only or args.remux
                              or args.deliver_only):
        raise SystemExit(
            f"{dest} already exists. A delivered film is not overwritten by "
            f"accident — run #1 is published. Pass --force if that is really "
            f"what you want, or --out to deliver somewhere else.")

    def reuse(name: str, path: Path, stills: bool = False) -> bool:
        """Is this pass already done? Printed either way, never guessed.

        A reused pass prints WHAT WAS CHECKED, because "reusing plate.mp4"
        with no number beside it is how a half-written file gets inherited by
        four more passes and a gate report.
        """
        if name in redo:
            print(f"   {name}: re-rendering, --redo says so")
            return False
        ok, why = (verified_stills(path, count) if stills
                   else verified_video(path, count))
        if ok:
            print(f"   {name}: reusing {path.name} — {why}")
        elif why != "missing":
            print(f"   {name}: re-rendering — {why}")
        return ok

    spans = act_spans(cuts)
    print(f"{args.project}: {len(cuts)} cuts, {seconds:.1f}s, {count} frames, "
          f"{len(spans)} act spans, mix {mix.name}")

    if args.remux:
        print("5. remux (picture copied, audio replaced)")
        remux(dest, mix)
    elif args.deliver_only:
        print("5. deliver (look and type passes reused, picture re-encoded)")
        deliver(look, type_layer, mix, dest)
    elif not args.gates_only:
        if not args.skip_picture:
            print("1. plate")
            if not reuse("plate", picture):
                render_plate(props_for_layer(props_path, "plate", work,
                                             args.project),
                             picture, count, cuts)
            print("2. frames")
            if not reuse("frames", frames_dir, stills=True):
                extract_frames(picture, frames_dir, count)
        print("3. look pass")
        if not reuse("look", look):
            render_look(frames_dir, look, count,
                        act=spans[0]["act"] if spans else "act1", acts=spans,
                        cuts=cuts)
        if not args.skip_picture:
            print("4. type")
            if not reuse("type", type_layer):
                render_type(props_for_layer(props_path, "type", work,
                                            args.project),
                            type_layer, count, cuts)
        print("5. deliver")
        deliver(look, type_layer, mix, dest)

    print("6. gates")
    mix_report = renders / "mix_report.json"
    expected = None
    if mix_report.exists():
        expected = ((json.loads(mix_report.read_text()) or {}).get("final") or {}).get("lufs")

    # IS THIS A FILM, OR A SLICE OF ONE?
    #
    # A real film has a project directory, and its delivery MUST be compared
    # against the loudness its own mixer recorded — a missing mix_report.json
    # is then a failure, not a reason to skip the check. A slice rendered to
    # prove the chain works has no mix report by construction, and the gate
    # says SKIPPED with the reason instead of printing a PASS it did not
    # earn. The slice on 2026-11-09 printed "-14.06 LUFS against the mix's
    # None ... PASS", which reads as checked-and-fine and meant not-checked.
    real_film = (project / "artifacts" / "render_props.json").exists()
    problems, results = gates(dest, picture, cuts, expected, FPS, type_layer,
                              loudness_reference_required=real_film)
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

    # THE THUMBNAIL GATE, AND IT DOES NOT BLOCK.
    #
    # Generated here, shown here, and the upload goes ahead without it: the
    # schedule is the one thing that cannot slip, and a reply that arrives
    # on Sunday must not decide whether a film goes out on Monday. If
    # nobody answers, `scripts/after_publish.py` sets it anyway on Sunday
    # evening and says so — a generated thumbnail beats YouTube's
    # auto-frame, so silence must not cost the film one.
    #
    # Wrapped, because a photo that fails to send is not a reason to fail a
    # film that just passed every gate.
    if not problems:
        from thumbnail_gate import post_quietly
        print("   " + post_quietly(args.project))

    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

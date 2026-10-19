#!/usr/bin/env python3
"""Render the film one act at a time, then concatenate.

A single 36,000-frame pass is about 2.5 hours on this machine and one frame
exceeding the per-frame timeout discards all of it. Rendering per act bounds
the loss to one act, makes progress observable, and lets a single act be
re-rendered after a fix without repeating the rest.

The acts are cut at the narration section boundaries, which are also the
playbook's fade-through-black points, so no transition is split.
"""
from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.video.video_compose import VideoCompose  # noqa: E402

ART = "projects/they-said-it-couldnt-be-built/artifacts/"
OUT = "projects/they-said-it-couldnt-be-built/renders/"
SECTIONS = ["cold_open", "act1", "act2", "act3", "act4", "outro"]


def main() -> int:
    concurrency = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    only = sys.argv[2] if len(sys.argv) > 2 else None

    props = json.load(open(ART + "render_props.json", encoding="utf-8"))
    ed = json.load(open(ART + "edit_decisions.json", encoding="utf-8"))
    sp = json.load(open(ART + "scene_plan.json", encoding="utf-8"))
    section_of = {s["slot_id"]: s["script_section_id"] for s in sp["metadata"]["slots"]}

    import re
    def sid(cut):
        m = re.search(r"(cold_open_s\d+|act\d_s\d+|outro_s\d+)", cut.get("reason", ""))
        return m.group(1) if m else None

    buckets: dict[str, list] = {s: [] for s in SECTIONS}
    for cut in props["cuts"]:
        buckets[section_of.get(sid(cut), "act1")].append(cut)

    os.makedirs(OUT + "acts", exist_ok=True)
    manifest = []
    grand_start = time.time()

    for section in SECTIONS:
        cuts = buckets[section]
        if not cuts or (only and section != only):
            continue
        base = cuts[0]["in_seconds"]
        part = dict(props)
        part["cuts"] = [{**c, "in_seconds": round(c["in_seconds"] - base, 3),
                         "out_seconds": round(c["out_seconds"] - base, 3)} for c in cuts]
        end = part["cuts"][-1]["out_seconds"]
        part["overlays"] = [{**o, "in_seconds": round(o["in_seconds"] - base, 3),
                             "out_seconds": round(o["out_seconds"] - base, 3)}
                            for o in props["overlays"]
                            if base <= o["in_seconds"] < base + end]
        part["captions"] = [{**c, "startMs": c["startMs"] - round(base * 1000),
                             "endMs": c["endMs"] - round(base * 1000)}
                            for c in props["captions"]
                            if base * 1000 <= c["startMs"] < (base + end) * 1000]
        # each act carries its own slice of the finished mix
        part["audio"] = {"narration": {"src": props["audio"]["narration"]["src"],
                                       "volume": 1.0, "startFrom": round(base, 3)}}
        part["render_runtime"] = ed["render_runtime"]
        part["renderer_family"] = ed["renderer_family"]
        part["composition_mode"] = ed["composition_mode"]

        out = f"{OUT}acts/{section}.mp4"
        t0 = time.time()
        print(f"[{section}] {len(part['cuts'])} cuts, {end:.1f}s, "
              f"{round(end * 30)} frames — starting", flush=True)
        res = VideoCompose().execute({
            "operation": "render",
            "edit_decisions": part,
            "asset_manifest": json.load(open(ART + "asset_manifest.json", encoding="utf-8")),
            "output_path": out,
            "profile": "youtube_landscape",
            "remotion_timeout_ms": 300000,
            "concurrency": concurrency,
        })
        wall = time.time() - t0
        fps = (round(end * 30) / wall) if wall else 0
        print(f"[{section}] success={res.success} wall={wall:.0f}s ({fps:.2f} fps)", flush=True)
        if not res.success:
            print(f"[{section}] ERROR {res.error}", flush=True)
            return 1
        manifest.append({"section": section, "path": out, "wall_seconds": round(wall, 1),
                         "frames": round(end * 30), "fps": round(fps, 2)})

    if only:
        print(json.dumps(manifest, indent=1))
        return 0

    # concat without re-encoding; every part came from the same encoder settings
    listfile = OUT + "acts/concat.txt"
    with open(listfile, "w", encoding="utf-8") as fh:
        for m in manifest:
            fh.write(f"file '{os.path.abspath(m['path'])}'\n")
    final = OUT + "they-said-it-couldnt-be-built.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", listfile, "-c", "copy", final], check=True)

    total_wall = time.time() - grand_start
    peak_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / (1024 * 1024)
    report = {"parts": manifest, "total_wall_seconds": round(total_wall, 1),
              "peak_rss_mb_children": round(peak_mb, 1), "concurrency": concurrency,
              "output": final}
    json.dump(report, open(ART + "render_report.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(report, indent=1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

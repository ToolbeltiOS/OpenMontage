#!/usr/bin/env python3
"""Look at the finished film and say where it left the playbook.

WHY A PASS AND NOT A GATE
-------------------------
The gates run on plans: a scene plan that cannot be built, an edit whose curve
is flat, a caption track that cannot be read. By the time a film exists they
have all passed, and the question is different — not "is this buildable" but
"is this the film the playbook describes".

So this fails on **structural violations only**, the things no downstream step
can repair, and reports everything else with a timestamp so a human can go and
look. A critic that fails on taste gets switched off.

WHAT IT MEASURES
----------------
  - a frame every ten seconds, as a contact sheet, because half of what is
    wrong with a film is visible and none of it is in a number;
  - the shot-length histogram per act, from the EDL, which is exact;
  - the cuts-per-minute curve against the playbook envelope;
  - the narration and bed energy curves, and where the bed rises;
  - realised air against planned.

    python scripts/critic_pass.py --project <id> --film <mp4> [--edit <json>]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

SHEET_INTERVAL_S = 10


def ffprobe_duration(path: Path) -> float:
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)]).strip())


def contact_sheet(film: Path, dest: Path, interval: int = SHEET_INTERVAL_S) -> tuple[Path, int]:
    """One frame every `interval` seconds, tiled. The thing a human reads first."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, int(ffprobe_duration(film) // interval))
    cols = min(6, frames) or 1
    rows = math.ceil(frames / cols)
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(film),
         "-vf", f"fps=1/{interval},scale=480:-2,tile={cols}x{rows}",
         "-frames:v", "1", str(dest)],
        check=True)
    return dest, frames


def energy_curve(film: Path, hop: float = 0.5) -> dict:
    """Short-time level of the finished mix, and where the quiet passages are.

    Measured off the delivered file rather than the stems: this is the pass
    that asks what the viewer actually gets.
    """
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(film), "-vn", "-f", "f32le",
         "-acodec", "pcm_f32le", "-ac", "1", "-ar", "48000", "-"],
        capture_output=True, check=True).stdout
    mono = np.frombuffer(raw, dtype=np.float32)
    step = int(48000 * hop)
    n = max(len(mono) // step, 1)
    db = []
    for i in range(n):
        seg = mono[i * step:(i + 1) * step]
        db.append(float(20 * np.log10(np.sqrt(np.mean(seg ** 2) + 1e-12) + 1e-12)))
    arr = np.array(db)
    quiet_floor = float(np.percentile(arr, 15))
    quiet = [round(i * hop, 1) for i, v in enumerate(db) if v <= quiet_floor]
    return {
        "hop_seconds": hop,
        "dbfs": [round(v, 1) for v in db],
        "median_dbfs": round(float(np.median(arr)), 1),
        "p15_dbfs": round(quiet_floor, 1),
        "quiet_seconds_total": round(len(quiet) * hop, 1),
    }


def act_histograms(cuts: list[dict]) -> dict:
    """Shot lengths per act, from the EDL."""
    bins = [0, 2, 4, 6, 8, 12, 20, 30, 1e9]
    out: dict[str, dict] = {}
    for cut in cuts:
        act = str(cut.get("act") or cut.get("actNumber") or "?")
        length = float(cut.get("duration_seconds") or
                       (float(cut["out_seconds"]) - float(cut["in_seconds"])))
        row = out.setdefault(act, {"shots": 0, "seconds": 0.0, "hist": Counter()})
        row["shots"] += 1
        row["seconds"] += length
        for i in range(len(bins) - 1):
            if bins[i] <= length < bins[i + 1]:
                label = (f"{bins[i]:g}-{bins[i+1]:g}s" if bins[i + 1] < 1e8
                         else f"{bins[i]:g}s+")
                row["hist"][label] += 1
                break
    for row in out.values():
        row["hist"] = dict(row["hist"])
        row["mean_shot_seconds"] = round(row["seconds"] / max(row["shots"], 1), 2)
        row["seconds"] = round(row["seconds"], 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--film", required=True)
    ap.add_argument("--edit", default=None,
                    help="edit_decisions or render_props; defaults to the project's")
    ap.add_argument("--slug", default=None)
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    film = Path(args.film)
    if not film.exists():
        raise SystemExit(f"no film at {film}")
    slug = args.slug or film.stem

    edit_path = Path(args.edit) if args.edit else project / "artifacts" / "edit_decisions.json"
    edit = json.loads(edit_path.read_text())
    cuts = edit["cuts"] if isinstance(edit, dict) else edit

    from verify_frame_motion import check as check_motion
    from verify_rhythm import check as check_rhythm

    problems, measured = check_rhythm(cuts)

    # Does the picture actually move? Everything else here measures the plan
    # or the container; this decodes the film. The act 2 demo passed every
    # other check in this file while frozen for 51% of its running time.
    motion_problems, motion = check_motion(str(film))
    problems.extend(motion_problems)
    acts = act_histograms(cuts)
    energy = energy_curve(film)
    duration = ffprobe_duration(film)

    sheet_dir = ROOT / "reports" / "critic"
    sheet, sheet_frames = contact_sheet(film, sheet_dir / f"{slug}_sheet.jpg")

    # air, as the mix actually delivered it
    mix_report_path = project / "renders" / "mix_report.json"
    air = None
    if mix_report_path.exists():
        air = (json.loads(mix_report_path.read_text()) or {}).get("air")

    import yaml

    playbook = yaml.safe_load((ROOT / "styles" / "wak3up-documentary.yaml").read_text())
    env = playbook["rhythm"]["film_envelope"]
    air_band = playbook["structure"]["air"]["film_total_pct"]

    notes = list(measured.get("notes", []))
    if air:
        pct = air.get("air_pct_of_total")
        if pct is not None and not (air_band[0] <= pct <= air_band[1]):
            notes.append(f"realised air {pct}% of runtime, outside "
                         f"{air_band[0]}-{air_band[1]}%")
        if air.get("air_planned") is False:
            notes.append("the mix carries no PLANNED air: it fell back to whole "
                         "sections, so every gap in the film is one the "
                         "synthesiser happened to leave")

    lines = [
        f"# Critic pass — {slug}",
        "",
        f"`{film}` · {duration:.1f}s · {len(cuts)} shots · "
        f"{measured['cuts_per_minute_mean']} cuts/min",
        "",
        "Structural violations fail this pass. Everything else is a note with a",
        "timestamp, for a human to go and look at.",
        "",
        "## Rhythm",
        "",
        f"| | measured | playbook |",
        f"|---|---|---|",
        f"| mean cuts/min | {measured['cuts_per_minute_mean']} | "
        f"{env['cuts_per_minute_mean'][0]}–{env['cuts_per_minute_mean'][1]} |",
        f"| curve spread | {measured['cuts_per_minute_spread']} | "
        f"≥ {env['cuts_per_minute_spread_min']} |",
        f"| shot p10 | {measured['shot_length']['p10']}s | "
        f"≤ {env['shot_length_p10_max_seconds']}s |",
        f"| shot p90 | {measured['shot_length']['p90']}s | "
        f"≥ {env['shot_length_p90_min_seconds']}s |",
        f"| fullest 2s band | {measured['pct_in_fullest_2s_band']}% | "
        f"≤ {env['max_pct_of_shots_in_any_2s_band']}% |",
        "",
        "Per-minute cuts: `" + " ".join(str(n) for n in measured["cuts_per_minute_series"]) + "`",
        "",
        "## Shot lengths by act",
        "",
        "| act | shots | runtime | mean shot | histogram |",
        "|---|---|---|---|---|",
    ]
    for act in sorted(acts):
        row = acts[act]
        hist = ", ".join(f"{k} ×{v}" for k, v in sorted(row["hist"].items()))
        lines.append(f"| {act} | {row['shots']} | {row['seconds']}s | "
                     f"{row['mean_shot_seconds']}s | {hist} |")

    lines += [
        "",
        "## Frame motion",
        "",
        f"{motion['duplicate_pairs_pct']}% of consecutive frame pairs are "
        f"identical; mean frame difference {motion['mean_frame_difference']}; "
        f"timestamps {'constant' if motion['timestamps_constant'] else '**irregular**'}.",
        "",
    ]
    if motion["freezes"]:
        lines += ["| at | frames | seconds |", "|---|---|---|"]
        lines += [f"| {f['start_seconds']}s | {f['frames']} | {f['seconds']}s |"
                  for f in motion["freezes"][:20]]
        lines.append("")
    lines += [
        "## Energy",
        "",
        f"Median level {energy['median_dbfs']} dBFS; the quietest 15% of the "
        f"film sits at or below {energy['p15_dbfs']} dBFS, "
        f"{energy['quiet_seconds_total']}s in total.",
        "",
    ]
    if air:
        lines += [
            f"Air: {air.get('realised_air_seconds')}s realised across "
            f"{air.get('realised_gaps')} gaps of {air.get('air_threshold_s')}s "
            f"or longer ({air.get('air_pct_of_total')}% of runtime); "
            f"{air.get('pauses_over_0_6s')} shorter pauses.",
            "",
        ]

    lines += ["## Contact sheet", "",
              f"One frame every {SHEET_INTERVAL_S}s, {sheet_frames} frames: "
              f"`{sheet.relative_to(ROOT)}`", ""]

    if problems:
        lines += ["## Structural violations", ""]
        lines += [f"- {p}" for p in problems]
        lines.append("")
    if notes:
        lines += ["## Notes", ""]
        lines += [f"- {n}" for n in notes]
        lines.append("")
    if not problems and not notes:
        lines += ["## Findings", "", "None.", ""]

    dest = ROOT / "reports" / f"critic_{slug}.md"
    dest.write_text("\n".join(lines))

    print(f"{len(cuts)} shots over {duration:.1f}s -> {dest.relative_to(ROOT)}")
    print(f"  sheet: {sheet.relative_to(ROOT)} ({sheet_frames} frames)")
    for p in problems:
        print("  VIOLATION:", p)
    for n in notes:
        print("  note:", n)
    print("CRITIC:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

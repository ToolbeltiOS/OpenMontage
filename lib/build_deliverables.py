#!/usr/bin/env python3
"""Assemble the delivery folder and the measured render report.

Everything here is measured from the rendered file with ffprobe, or read from
the artifacts. Nothing is a planned figure reported as if it were observed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = "they-said-it-couldnt-be-built"
PROJ = os.path.join(ROOT, "projects", SLUG)
ART = os.path.join(PROJ, "artifacts")
DEST = os.path.expanduser(f"~/Developer/wak3up-docs/output/{SLUG}")


def probe(path: str) -> dict:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ], text=True)
    return json.loads(out)


def loudness(path: str) -> dict:
    err = subprocess.run(
        ["ffmpeg", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "/dev/null"],
        capture_output=True, text=True).stderr
    tail = err[-4000:]
    def grab(pattern: str) -> float | None:
        ms = re.findall(pattern, tail)
        return float(ms[-1]) if ms else None
    return {
        "integrated_lufs": grab(r"I:\s+(-?\d+\.\d+)\s*LUFS"),
        "loudness_range_lu": grab(r"LRA:\s+(-?\d+\.\d+)\s*LU"),
        "true_peak_dbfs": grab(r"Peak:\s+(-?\d+\.\d+)\s*dBFS"),
    }


def main() -> int:
    mp4 = sys.argv[1]
    rr_path = os.path.join(ART, "render_report.json")
    rr = json.load(open(rr_path, encoding="utf-8")) if os.path.exists(rr_path) else {}
    wall_seconds = rr.get("total_wall_seconds")
    peak_rss_mb = rr.get("peak_rss_mb_children")

    os.makedirs(DEST, exist_ok=True)
    final = os.path.join(DEST, f"{SLUG}.mp4")
    shutil.copy2(mp4, final)

    info = probe(final)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    duration = float(info["format"]["duration"])

    # thumbnail: a frame from the act 4 Sacsayhuaman material, not frame 0
    thumb = os.path.join(DEST, "thumbnail.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1130", "-i", final,
                    "-frames:v", "1", "-q:v", "2", thumb], check=True)

    ed = json.load(open(os.path.join(ART, "edit_decisions.json"), encoding="utf-8"))
    am = json.load(open(os.path.join(ART, "asset_manifest.json"), encoding="utf-8"))
    sc = json.load(open(os.path.join(ART, "script.json"), encoding="utf-8"))
    sp = json.load(open(os.path.join(ART, "scene_plan.json"), encoding="utf-8"))

    treatments: dict[str, int] = {}
    for slot in sp["metadata"]["slots"]:
        treatments[slot["treatment"]] = treatments.get(slot["treatment"], 0) + 1
    total_slots = len(sp["metadata"]["slots"])
    mix_measured = {k: round(100 * c / total_slots, 1) for k, c in sorted(treatments.items())}

    chapters, t = [], 0.0
    for s in sc["sections"]:
        wav = os.path.join(PROJ, "assets", "audio", s["id"] + ".wav")
        chapters.append({"start_seconds": round(t, 2), "title": s["label"]})
        t += float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", wav]).strip())

    credits = am["metadata"]["youtube_description_credits"]
    music_credit = "\n".join(
        f"{b['track'].rsplit('.', 1)[0]}" for b in ed["music"]["beds"]
    )

    description = (
        f"{sc['title']}\n\n"
        "Four cases where the usual explanation runs out: the walls at Tiryns, the statues of "
        "Rapa Nui and the Altar Stone of Stonehenge, a drilled core from Giza, and the spaces "
        "inside Khufu's Pyramid that have been measured but never entered.\n\n"
        "Every figure in this film is sourced. Where published figures disagree, the "
        "disagreement is stated instead of a number being picked.\n\n"
        "CHAPTERS\n"
        + "\n".join(
            f"{int(c['start_seconds']) // 60:02d}:{int(c['start_seconds']) % 60:02d} {c['title']}"
            for c in chapters
        )
        + "\n\nMUSIC\n" + music_credit
        + "\n\n" + credits
    )

    metadata = {
        "title": sc["title"],
        "slug": SLUG,
        "description": description,
        "chapters": chapters,
        "tags": ["archaeology", "Stonehenge", "Rapa Nui", "Great Pyramid", "Pumapunku",
                 "Sacsayhuaman", "Tiryns", "documentary"],
        "language": "en",
        "attribution": {
            "credit_required_assets": am["metadata"]["credit_required"],
            "share_alike_assets": am["metadata"]["share_alike"],
            "block": credits,
            "music": [b["track"] for b in ed["music"]["beds"]],
            "narration": "Kokoro-82M (bm_george), run locally. No paid API was used.",
        },
        "measured": {
            "duration_seconds": round(duration, 2),
            "duration_hms": f"{int(duration) // 60}:{int(duration) % 60:02d}",
            "width": v["width"],
            "height": v["height"],
            "fps": v["r_frame_rate"],
            "video_codec": v["codec_name"],
            "audio_codec": a["codec_name"] if a else None,
            "shot_count": len(ed["cuts"]),
            "slot_treatment_pct": mix_measured,
            "audio": loudness(final),
            "file_bytes": int(info["format"]["size"]),
        },
        "render": {
            "runtime": ed["render_runtime"],
            "composition": "Explainer",
            "rendered_in_parts": [p["section"] for p in rr.get("parts", [])],
            "concurrency": rr.get("concurrency"),
            "wall_seconds": wall_seconds,
            "wall_hms": (f"{int(wall_seconds) // 3600}:{(int(wall_seconds) % 3600) // 60:02d}:"
                         f"{int(wall_seconds) % 60:02d}") if wall_seconds else None,
            "peak_rss_mb": peak_rss_mb,
            "parts": rr.get("parts", []),
        },
    }
    json.dump(metadata, open(os.path.join(DEST, "metadata.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    shutil.copy2(os.path.join(ART, "research_brief.json"), os.path.join(DEST, "research_brief.json"))

    print(json.dumps(metadata["measured"], indent=1))
    print("delivered to", DEST)
    return 0


if __name__ == "__main__":
    sys.exit(main())

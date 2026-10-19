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


SECTIONS = ["cold_open", "act1", "act2", "act3", "act4", "outro"]


def stream_durations(path: str) -> dict:
    out = {}
    for kind in ("v", "a"):
        try:
            out[kind] = float(subprocess.check_output([
                "ffprobe", "-v", "error", "-select_streams", f"{kind}:0",
                "-show_entries", "stream=duration", "-of", "csv=p=0", path,
            ], text=True).strip().rstrip(","))
        except Exception:
            out[kind] = None
    return out


def hard_checks(final: str, tail_seconds: float = 0.5) -> list[dict]:
    """Three things that must be true of a delivered film. Any failure is fatal.

    Each of these has already shipped a broken file once:

    (a) A film can be internally consistent and still end before its own last
        sentence — run #2 cut "you know where to find it" because the edit was
        written against a narration total that later changed.
    (b) A 48 kHz stereo section among 24 kHz mono ones is not resampled by the
        concat demuxer, it is misread: the outro decoded at four times its
        length and added 33 seconds of slurred audio. The mix still normalised
        to spec and the file was still valid.
    (c) The same bug seen from the other side — the streams disagreeing is the
        symptom you can test for without knowing the cause.
    """
    results = []

    # (c) every narration section must agree on format, BEFORE any concat
    fmts = {}
    for sec in SECTIONS:
        wav = os.path.join(PROJ, "assets", "audio", sec + ".wav")
        fmts[sec] = subprocess.check_output([
            "ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
            "stream=codec_name,sample_rate,channels", "-of", "csv=p=0", wav,
        ], text=True).strip()
    distinct = sorted(set(fmts.values()))
    results.append({
        "check": "narration sections share codec, sample rate and channels",
        "pass": len(distinct) == 1,
        "detail": distinct if len(distinct) == 1 else fmts,
    })

    # (a) duration == planned narration + tail, within half a second
    def _dur(path: str) -> float:
        return float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", path], text=True).strip())

    narration = sum(_dur(os.path.join(PROJ, "assets", "audio", sec + ".wav"))
                    for sec in SECTIONS)
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", final], text=True).strip())
    expected = narration + tail_seconds
    results.append({
        "check": "final duration == narration + tail (+/- 0.5s)",
        "pass": abs(dur - expected) <= 0.5,
        "detail": {"measured": round(dur, 3), "expected": round(expected, 3),
                   "delta": round(dur - expected, 3)},
    })

    # (b) the two streams must agree
    sd = stream_durations(final)
    agree = (sd["v"] is not None and sd["a"] is not None
             and abs(sd["v"] - sd["a"]) <= 0.1)
    results.append({
        "check": "video and audio stream durations agree (+/- 0.1s)",
        "pass": agree,
        "detail": {"video": sd["v"], "audio": sd["a"],
                   "delta": None if None in sd.values() else round(sd["v"] - sd["a"], 3)},
    })
    return results


def main() -> int:
    mp4 = sys.argv[1]
    rr_path = os.path.join(ART, "render_report.json")
    rr = json.load(open(rr_path, encoding="utf-8")) if os.path.exists(rr_path) else {}
    wall_seconds = rr.get("total_wall_seconds")
    peak_rss_mb = rr.get("peak_rss_mb_children")

    # Reuse is part of the self-review, and a planner violation fails the
    # build: a film that repeats its pictures is a defect you can measure.
    sys.path.insert(0, os.path.join(ROOT, "lib"))
    from reuse_rules import check as reuse_check, metrics as reuse_metrics
    plan_slots = json.load(open(os.path.join(ART, "scene_plan.json"),
                                encoding="utf-8"))["metadata"]["slots"]
    reuse = reuse_metrics(plan_slots)
    reuse_violations = reuse_check(plan_slots)

    # Hard checks first: nothing is delivered if any of them fails.
    checks = hard_checks(mp4)
    checks.append({
        "check": "scene plan obeys the reuse rule",
        "pass": not reuse_violations,
        "detail": reuse if not reuse_violations else reuse_violations[:10],
    })
    for c in checks:
        print(("  PASS  " if c["pass"] else "  FAIL  ") + c["check"])
        if not c["pass"]:
            print("        " + json.dumps(c["detail"]))
    if not all(c["pass"] for c in checks):
        print("\nDELIVERY BLOCKED: a post-render check failed. "
              "Nothing was written to the output folder.")
        return 2

    os.makedirs(DEST, exist_ok=True)
    final = os.path.join(DEST, f"{SLUG}.mp4")
    shutil.copy2(mp4, final)

    info = probe(final)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    duration = float(info["format"]["duration"])

    # Thumbnail. Not pulled from the finished film: narration captions are on
    # screen for almost its whole length (DocCaption holds a page until the
    # next one starts), and a thumbnail carrying a half-sentence of subtitle is
    # a worse picture than the shot underneath it. It is rendered from the
    # SlotPreview composition instead, which has no caption layer — the
    # Sacsayhuaman joint with its contact line annotated, which is the film's
    # argument in one frame.
    thumb = os.path.join(DEST, "thumbnail.jpg")
    slot_props = os.environ.get("THUMBNAIL_PROPS")
    if slot_props and os.path.exists(slot_props):
        png = os.path.join(DEST, ".thumb.png")
        subprocess.run(["npx", "remotion", "still", "SlotPreview", png,
                        "--frame=170", f"--props={slot_props}", "--log=error"],
                       check=True, cwd=os.path.join(ROOT, "remotion-composer"))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", png, "-q:v", "2", thumb],
                       check=True)
        os.remove(png)
    else:
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
        "thumbnail": {
            "source": "SlotPreview render of act4_s177 (Sacsayhuam\u00e1n joint)",
            "why": "frames taken from the film carry burned-in narration captions",
        },
        "post_render_checks": checks,
        "reuse": reuse,
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

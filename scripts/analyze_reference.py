#!/usr/bin/env python3
"""Measure one reference film: rhythm, text density, energy, shot material.

Reads a downloaded reference from the reference cache and writes
``measure.json`` beside it. Every stage is cached, so re-running after a
crash or with --only costs nothing for the stages already done.

What each number is, and what it is not
---------------------------------------
cuts        PySceneDetect ContentDetector boundaries. A detector sees visual
            discontinuity, not editorial intent: a dissolve reads as one or
            two soft boundaries, and a hard camera move inside one shot can
            read as a cut. Treated as an estimate of cut rhythm, with a
            threshold sensitivity sweep (--sweep, run on the primary reference) so
            the estimate's stability
            is visible rather than assumed.
text        Tesseract in sparse-text mode on one frame per second. Counts
            confident words and the area they occupy. Burnt-in captions and
            title cards are indistinguishable to OCR, so the caption-style
            question is answered from the subtitle track instead.
energy      Short-time RMS of the final mix, split by a narration mask built
            from the published subtitle timings. During narration the mix is
            voice-led and says nothing about the bed; the bed is therefore
            measured only in the gaps, which is the one place it is audible
            on its own. Stated as such in the report.
material    CLIP zero-shot over one frame per shot, crossed with inter-frame
            motion inside the shot. Separates authored graphics from archival
            stills from moving footage well enough to get a ratio; it is not
            a shot log.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import wave
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

CACHE = Path.home() / "Developer/wak3up-docs/reference_cache"
STAGES = ("cuts", "text", "energy", "material", "conventions")

# ── cut detection, calibrated — see the module docstring ────────────────
CUT_THRESHOLD = 16.0
CUT_MIN_LEN_S = 0.27
CUT_CONFIRM_CORR = 0.95

#: Mean absolute 8-bit difference over a quarter second, above which a shot is
#: treated as moving rather than a still under a camera move. A slow push on a
#: photograph lands around 1-3; real footage is an order of magnitude above it.
MOTION_PER_QUARTER_SECOND = 6.0

# Collapsed onto three buckets after scoring; the prompts are deliberately
# more specific than the buckets so CLIP has something to separate.
CLIP_PROMPTS = {
    "graphics": [
        "a motion graphic with large text on a plain background",
        "a diagram or schematic drawing",
        "a map with labels and routes",
        "a title card with typography",
        "a 3d rendered animation",
        "a chart or graph",
    ],
    "archive": [
        "an old archival black and white photograph",
        "a vintage documentary photograph",
        "a scan of an old document or newspaper page",
        "grainy archival newsreel film footage",
    ],
    "footage": [
        "modern live action video footage of a landscape",
        "handheld video footage of a city street",
        "a person speaking to camera in an interview",
        "aerial drone footage",
    ],
}


# ─────────────────────────────── helpers ────────────────────────────────
def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def proxy(ref_dir: Path, slug: str) -> Path:
    """A 640x360 short-GOP copy, used for detection and frame sampling.

    Content detection compares downscaled frames anyway, and seeking a long-GOP
    720p file dominates the runtime of both the cut pass and the per-shot
    sampling. The proxy is written once and reused by every stage.
    """
    out = ref_dir / f"{slug}.proxy.mp4"
    if out.exists():
        return out
    # Written under a temp name and renamed, because the moov atom lands last:
    # a reader that finds the file by name mid-write opens a headerless file and
    # fails with "moov atom not found". Two of these running at once is exactly
    # how that happens.
    tmp = ref_dir / f".{slug}.proxy.{os.getpid()}.mp4"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
         "-i", str(ref_dir / f"{slug}.mp4"), "-an",
         "-vf", "scale=640:-2", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "26", "-g", "15", "-pix_fmt", "yuv420p", str(tmp)],
        check=True,
    )
    tmp.replace(out)
    return out


def load_cache(ref_dir: Path) -> dict:
    p = ref_dir / "measure.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_cache(ref_dir: Path, data: dict) -> None:
    (ref_dir / "measure.json").write_text(json.dumps(data, indent=1) + "\n")


# ──────────────────────────────── cuts ─────────────────────────────────
def confirm_cuts(src: Path, candidates: list[float]) -> tuple[list[float], list[float]]:
    """Split candidate cut times into confirmed and rejected.

    A cut is confirmed when the colour distribution either side of it differs.
    Rejected candidates are kept and reported, because a reference whose
    rejections run high is one where the number should be read with care.
    """
    import cv2

    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    def small(ts: float):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(ts * fps))
        ok, fr = cap.read()
        return cv2.resize(fr, (160, 90)) if ok else None

    def hist(fr):
        h = cv2.calcHist([cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)], [0, 1], None,
                         [32, 32], [0, 180, 0, 256])
        return cv2.normalize(h, h).flatten()

    confirmed, rejected = [], []
    for c in candidates:
        a, b = small(max(c - 0.25, 0.0)), small(c + 0.25)
        if a is None or b is None:
            confirmed.append(c)       # cannot test it; do not silently drop it
            continue
        corr = float(cv2.compareHist(hist(a), hist(b), cv2.HISTCMP_CORREL))
        (confirmed if corr < CUT_CONFIRM_CORR else rejected).append(c)
    cap.release()
    return confirmed, rejected


def stage_cuts(ref_dir: Path, slug: str, duration: float, sweep: bool = False) -> dict:
    from tools.analysis.scene_detect import SceneDetect

    src = proxy(ref_dir, slug)

    def detect(threshold: float) -> list[dict]:
        res = SceneDetect().execute({
            "input_path": str(src),
            "method": "content",
            "threshold": threshold,
            "min_scene_length_seconds": CUT_MIN_LEN_S,
            "output_path": str(ref_dir / f"scenes_t{int(threshold)}.json"),
        })
        if not res.success:
            raise RuntimeError(res.error)
        return res.data["scenes"]

    candidates = [s["start_seconds"] for s in detect(CUT_THRESHOLD)[1:]]
    cut_times, rejected = confirm_cuts(src, candidates)

    bounds = [0.0] + cut_times + [duration]
    lengths = [b - a for a, b in zip(bounds, bounds[1:]) if b > a]

    per_minute = []
    for m in range(math.ceil(duration / 60)):
        lo, hi = m * 60, min((m + 1) * 60, duration)
        n = sum(1 for t in cut_times if lo <= t < hi)
        per_minute.append({"minute": m, "cuts": n,
                           "cuts_per_minute": round(n * 60 / max(hi - lo, 1e-6), 2)})

    bins = [0, 1, 2, 3, 5, 8, 12, 20, 30, 60, 1e9]
    hist = Counter()
    for L in lengths:
        for i in range(len(bins) - 1):
            if bins[i] <= L < bins[i + 1]:
                hist[f"{bins[i]:g}-{bins[i+1]:g}s" if bins[i + 1] < 1e8 else "60s+"] += 1
                break

    swept = {}
    if sweep:
        for t in (12.0, 22.0):
            try:
                swept[f"threshold_{int(t)}_raw"] = len(detect(t)) - 1
            except Exception as exc:  # pragma: no cover - diagnostic only
                swept[f"threshold_{int(t)}_raw"] = f"failed: {exc}"

    arr = np.array(lengths) if lengths else np.array([0.0])
    return {
        "shots": len(lengths),
        "duration_s": round(duration, 2),
        "cuts_per_minute_mean": round(len(cut_times) * 60 / duration, 2),
        "candidates_detected": len(candidates),
        "candidates_rejected": len(rejected),
        "rejected_pct": round(100 * len(rejected) / max(len(candidates), 1), 1),
        "shot_length_s": {
            "mean": round(float(arr.mean()), 2),
            "median": round(float(np.median(arr)), 2),
            "p10": round(float(np.percentile(arr, 10)), 2),
            "p90": round(float(np.percentile(arr, 90)), 2),
            "max": round(float(arr.max()), 2),
        },
        "shot_length_histogram": dict(hist),
        "cuts_per_minute_series": per_minute,
        "cut_times_s": [round(t, 3) for t in cut_times],
        "shot_lengths_s": [round(x, 3) for x in lengths],
        "detected_on": src.name,
        "detector": {"threshold": CUT_THRESHOLD, "min_scene_len_s": CUT_MIN_LEN_S,
                     "confirm_hist_corr_below": CUT_CONFIRM_CORR},
        "threshold_sensitivity_raw_candidates": swept,
    }


# ──────────────────────────────── text ─────────────────────────────────
def stage_text(ref_dir: Path, slug: str, duration: float) -> dict:
    import pytesseract
    from PIL import Image

    frames = ref_dir / "frames_1fps"
    if not frames.exists() or not any(frames.iterdir()):
        frames.mkdir(exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
             "-i", str(ref_dir / f"{slug}.mp4"),
             "-vf", "fps=1,scale=960:-2", "-q:v", "3",
             str(frames / "f_%05d.jpg")],
            check=True,
        )

    files = sorted(frames.glob("f_*.jpg"))
    rows = []
    for i, f in enumerate(files):
        img = Image.open(f)
        W, H = img.size
        data = pytesseract.image_to_data(
            img, config="--psm 11", output_type=pytesseract.Output.DICT
        )
        words, area = 0, 0
        for text, conf, w, h in zip(data["text"], data["conf"], data["width"], data["height"]):
            try:
                c = float(conf)
            except (TypeError, ValueError):
                continue
            if c >= 60 and len(text.strip()) >= 2:
                words += 1
                area += w * h
        rows.append({"t": i, "words": words, "area_pct": round(100 * area / (W * H), 2)})

    any_text = [r for r in rows if r["words"] >= 1]
    strong = [r for r in rows if r["words"] >= 3]
    return {
        "frames_sampled": len(rows),
        "seconds_with_any_text_pct": round(100 * len(any_text) / max(len(rows), 1), 1),
        "seconds_with_3plus_words_pct": round(100 * len(strong) / max(len(rows), 1), 1),
        "mean_text_area_pct_when_present": round(
            float(np.mean([r["area_pct"] for r in any_text])) if any_text else 0.0, 2),
        "text_seconds_series": rows,
    }


# ─────────────────────────────── energy ────────────────────────────────
VTT_TS = re.compile(
    r"(\d+):(\d\d):(\d\d)[.,](\d\d\d)\s*-->\s*(\d+):(\d\d):(\d\d)[.,](\d\d\d)")
VTT_WORD = re.compile(r"<(\d+):(\d\d):(\d\d)\.(\d\d\d)>")

#: A pause longer than this ends a narration span.
SPEECH_GAP_S = 0.7
#: How long the last word of a span is assumed to run.
WORD_TAIL_S = 0.4
#: A gap must be at least this long for the bed to be audible on its own.
CLEAR_MIN_S = 0.6


def _secs(h, m, s, ms) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def narration_spans(path: Path) -> tuple[list[tuple[float, float]], str]:
    """Narration intervals from a subtitle file, and how they were derived.

    Word timings first. YouTube's automatic track carries an onset for every
    word inside the cue text, and those are timed to speech. The cue spans
    around them are not: an automatic track rolls each cue forward to meet the
    next one, so their union covers the whole file including every pause —
    measured at 100% narration coverage and zero clear seconds on one
    reference, which would have silently removed the music measurement.

    A hand-written track has no word timings; there the cue spans are all
    there is, and the caller is told so, because they hold a line on screen
    through a pause and will under-report the gaps.
    """
    text = path.read_text(errors="ignore")

    onsets = sorted({_secs(*m.groups()) for m in VTT_WORD.finditer(text)})
    if len(onsets) > 20:
        spans: list[list[float]] = []
        for t in onsets:
            if spans and t - spans[-1][1] <= SPEECH_GAP_S:
                spans[-1][1] = t
            else:
                spans.append([t, t])
        return [(a, b + WORD_TAIL_S) for a, b in spans], "word_timings"

    cues = sorted(
        (_secs(*m.groups()[:4]), _secs(*m.groups()[4:])) for m in VTT_TS.finditer(text)
    )
    merged: list[list[float]] = []
    for a, b in cues:
        if merged and a <= merged[-1][1] + 0.15:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged], "cue_spans"


def stage_energy(ref_dir: Path, slug: str, duration: float,
                 subtitle_offset: float = 0.0) -> dict:
    with wave.open(str(ref_dir / f"{slug}.wav")) as w:
        sr = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

    hop = int(sr * 0.1)
    n = len(pcm) // hop
    rms = np.array([
        math.sqrt(float(np.mean(pcm[i * hop:(i + 1) * hop] ** 2)) + 1e-12) for i in range(n)
    ])
    db = 20 * np.log10(rms + 1e-12)
    times = np.arange(n) * 0.1

    # Prefer the auto-generated original-language track: its cues are timed to
    # speech, which is what a narration mask wants. A hand-written track is
    # timed for reading and can hold a line on screen through a pause.
    subs = sorted(ref_dir.glob(f"{slug}*.vtt"))
    auto = [p for p in subs if ".en-orig." in p.name or ".en-en." in p.name]
    chosen = (auto or subs)[0] if subs else None
    narration, basis = narration_spans(chosen) if chosen else ([], "none")
    # A sectioned download carries the WHOLE film's subtitles, so a window taken
    # from the middle of a film needs its subtitle clock moved back to zero.
    # Without this the mask for the closing window was the opening window's
    # speech, and the bed read louder than the voice.
    if subtitle_offset:
        narration = [(a - subtitle_offset, b - subtitle_offset) for a, b in narration]
        narration = [(max(a, 0.0), b) for a, b in narration if b > 0 and a < duration]
    mask = np.zeros(n, dtype=bool)
    for a, b in narration:
        mask[int(a / 0.1):int(min(b, duration) / 0.1)] = True

    # Gaps of at least CLEAR_MIN_S are where the bed is audible on its own; trim the
    # edges so neither the tail of a word nor the attack of the next one leaks in.
    clear = np.zeros(n, dtype=bool)
    gaps = []
    prev_end = 0.0
    for a, b in narration + [(duration, duration)]:
        if a - prev_end >= CLEAR_MIN_S:
            gaps.append((prev_end, a))
            clear[int((prev_end + 0.2) / 0.1):int((a - 0.2) / 0.1)] = True
        prev_end = max(prev_end, b)

    bed_db = db[clear]
    voice_db = db[mask]

    # Bed level per minute, from the clear samples inside that minute only.
    bed_series = []
    for m in range(math.ceil(duration / 60)):
        sel = clear & (times >= m * 60) & (times < (m + 1) * 60)
        bed_series.append({
            "minute": m,
            "bed_dbfs_median": round(float(np.median(db[sel])), 1) if sel.any() else None,
            "clear_seconds": round(float(sel.sum()) * 0.1, 1),
        })

    # A rise: the bed's minute-median climbing at least 3 dB over <= 3 minutes.
    vals = [(r["minute"], r["bed_dbfs_median"]) for r in bed_series if r["bed_dbfs_median"] is not None]
    rises = []
    for i in range(len(vals)):
        for j in range(i + 1, min(i + 4, len(vals))):
            if vals[j][1] - vals[i][1] >= 3.0:
                rises.append({"from_minute": vals[i][0], "to_minute": vals[j][0],
                              "gain_db": round(vals[j][1] - vals[i][1], 1)})
                break
    return {
        "subtitle_track": chosen.name if chosen else None,
        "subtitle_track_kind": "auto-generated" if (chosen and chosen in auto) else "published",
        "narration_mask_basis": basis,
        "subtitle_offset_s": subtitle_offset,
        "narration_coverage_pct": round(100 * float(mask.sum()) / n, 1),
        "narration_cues": len(narration),
        "clear_window_count": len(gaps),
        "clear_seconds_total": round(float(clear.sum()) * 0.1, 1),
        "longest_clear_window_s": round(max((b - a for a, b in gaps), default=0.0), 1),
        "mix_dbfs_median_under_narration": round(float(np.median(voice_db)), 1) if voice_db.size else None,
        "bed_dbfs_median_in_clear": round(float(np.median(bed_db)), 1) if bed_db.size else None,
        "bed_under_voice_db": (
            round(float(np.median(bed_db) - np.median(voice_db)), 1)
            if bed_db.size and voice_db.size else None),
        "bed_dbfs_per_minute": bed_series,
        "bed_rises": rises,
        "mix_dbfs_per_second": [round(float(x), 1) for x in db[::10]],
    }


# ────────────────────────────── material ───────────────────────────────
def stage_material(ref_dir: Path, slug: str, duration: float, cuts: dict) -> dict:
    import cv2

    from lib import clip_embedder

    cap = cv2.VideoCapture(str(proxy(ref_dir, slug)))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    starts = [0.0] + list(cuts["cut_times_s"])
    ends = list(cuts["cut_times_s"]) + [duration]
    shots = [(a, b) for a, b in zip(starts, ends) if b - a >= 0.4]

    def frame_at(t: float):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, fr = cap.read()
        return fr if ok else None

    stills, samples = [], []
    for a, b in shots:
        mid = frame_at((a + b) / 2)
        if mid is None:
            continue
        # Motion RATE, over a quarter second in the middle of the shot. The
        # first version compared the shot's first frame to its last, which on a
        # forty-second hold reports a huge number for a shot that barely moves.
        mid_t = (a + b) / 2
        nxt = frame_at(min(mid_t + 0.25, b - 0.05))
        motion = 0.0
        if nxt is not None:
            small = [cv2.resize(f, (160, 90)).astype(np.float32) for f in (mid, nxt)]
            motion = float(np.mean(np.abs(small[0] - small[1])))
        p = ref_dir / "shot_frames"
        p.mkdir(exist_ok=True)
        fp = p / f"shot_{len(samples):04d}.jpg"
        cv2.imwrite(str(fp), mid)
        samples.append({"start_s": round(a, 2), "end_s": round(b, 2),
                        "motion": round(motion, 2), "frame": str(fp)})
        stills.append(motion)
    cap.release()
    if not samples:
        return {"error": "no shots sampled"}

    prompts = [p for group in CLIP_PROMPTS.values() for p in group]
    owner = [k for k, group in CLIP_PROMPTS.items() for _ in group]
    text_vecs = clip_embedder.embed_texts(prompts)
    img_vecs = clip_embedder.embed_images([s["frame"] for s in samples])
    sims = np.asarray(img_vecs) @ np.asarray(text_vecs).T

    counts = Counter()
    for s, row in zip(samples, sims):
        bucket = owner[int(np.argmax(row))]
        # A still frame classified as footage is a photograph held on screen.
        if bucket == "footage" and s["motion"] < MOTION_PER_QUARTER_SECOND:
            bucket = "archive"
        s["class"] = bucket
        counts[bucket] += 1

    total = sum(counts.values())
    moving = sum(1 for s in samples if s["motion"] >= MOTION_PER_QUARTER_SECOND)
    return {
        "shots_classified": total,
        "ratio_pct": {k: round(100 * v / total, 1) for k, v in counts.items()},
        "moving_shot_pct": round(100 * moving / total, 1),
        "still_shot_pct": round(100 * (total - moving) / total, 1),
        "motion_threshold": MOTION_PER_QUARTER_SECOND,
        "shots": samples,
    }


# ───────────────────────────── conventions ─────────────────────────────
def stage_conventions(ref_dir: Path, slug: str) -> dict:
    import cv2
    import pytesseract
    from PIL import Image

    infos = sorted(ref_dir.glob("*.info.json"))
    info = json.loads(infos[0].read_text()) if infos else {}
    title = info.get("title", "")

    thumbs = [p for p in ref_dir.iterdir() if p.suffix.lower() in (".webp", ".jpg", ".png")
              and "frames" not in p.name and not p.name.startswith("shot_")]
    thumb = {}
    if thumbs:
        tp = thumbs[0]
        img = Image.open(tp).convert("RGB")
        words = [t for t, c in zip(*[pytesseract.image_to_data(
            img, config="--psm 11", output_type=pytesseract.Output.DICT)[k]
            for k in ("text", "conf")])
            if str(c).replace(".", "", 1).isdigit() and float(c) >= 60 and len(t.strip()) >= 2]
        arr = np.asarray(img).reshape(-1, 3).astype(np.float32)
        gray = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY)
        thumb = {
            "file": tp.name,
            "size": list(img.size),
            "ocr_words": words,
            "ocr_word_count": len(words),
            "mean_rgb": [round(float(x), 1) for x in arr.mean(axis=0)],
            "mean_saturation": round(float(
                cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2HSV)[:, :, 1].mean()), 1),
            "contrast_std": round(float(gray.std()), 1),
            # Whether a face is on the thumbnail is read by eye in the report.
            # A Haar cascade on three images is a worse instrument than looking.
        }

    return {
        "title": title,
        "title_chars": len(title),
        "title_words": len(title.split()),
        "title_has_colon": ":" in title,
        "title_has_dash": any(d in title for d in ("—", " - ", "–")),
        "title_titlecase": title[:1].isupper() and not title.isupper(),
        "description_chars": len(info.get("description") or ""),
        "tag_count": len(info.get("tags") or []),
        "chapters": [c.get("title") for c in (info.get("chapters") or [])],
        "chapter_count": len(info.get("chapters") or []),
        "upload_date": info.get("upload_date"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "fps": info.get("fps"),
        "thumbnail": thumb,
    }


# ──────────────────────────────── main ─────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--only", nargs="*", choices=STAGES)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--subtitle-offset", type=float, default=0.0,
                    help="seconds to subtract from subtitle times, for a window "
                         "cut out of a longer film")
    ap.add_argument("--sweep", action="store_true",
                    help="also detect at thresholds 22 and 32, to show the estimate's stability")
    args = ap.parse_args()

    ref_dir = CACHE / args.slug
    mp4 = ref_dir / f"{args.slug}.mp4"
    if not mp4.exists():
        sys.exit(f"missing {mp4}")

    data = load_cache(ref_dir)
    data.setdefault("slug", args.slug)
    duration = data.get("duration_s") or ffprobe_duration(mp4)
    data["duration_s"] = round(duration, 2)

    wanted = args.only or list(STAGES)
    for stage in wanted:
        if stage in data and not args.force:
            print(f"· {args.slug}/{stage} cached")
            continue
        print(f"→ {args.slug}/{stage}")
        if stage == "cuts":
            data[stage] = stage_cuts(ref_dir, args.slug, duration, args.sweep)
        elif stage == "text":
            data[stage] = stage_text(ref_dir, args.slug, duration)
        elif stage == "energy":
            data[stage] = stage_energy(ref_dir, args.slug, duration,
                                       args.subtitle_offset)
        elif stage == "material":
            if "cuts" not in data:
                data["cuts"] = stage_cuts(ref_dir, args.slug, duration)
            data[stage] = stage_material(ref_dir, args.slug, duration, data["cuts"])
        elif stage == "conventions":
            data[stage] = stage_conventions(ref_dir, args.slug)
        save_cache(ref_dir, data)
    print(f"wrote {ref_dir / 'measure.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Turn edit_decisions into the props Remotion actually renders.

Three things the edit artifact does not carry in renderable form:

1. **Cut timing.** `in_seconds`/`out_seconds` in edit_decisions are per-cut
   DURATIONS — every cut starts at 0 and they sum to the measured narration
   length. The Explainer composition sequences on absolute timeline positions
   (`from = in_seconds * fps`), so rendering the artifact as-written stacks all
   183 cuts on frame 0 and produces an eight-second film. They are laid
   back-to-back here, durations preserved.

2. **Audio.** The edit names six narration files and five music beds with a
   ducking target. Remotion is given one finished mix.

3. **Captions.** Six per-section word-level transcripts, each timed from zero,
   are merged into one track with each section's offset applied.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.join(ROOT, "projects", "they-said-it-couldnt-be-built")
ART = os.path.join(PROJ, "artifacts")
AUD = os.path.join(PROJ, "assets", "audio")
CAP = os.path.join(PROJ, "assets", "captions")
OUT = os.path.join(PROJ, "renders")

SECTIONS = ["cold_open", "act1", "act2", "act3", "act4", "outro"]


def slot_id(cut: dict) -> str | None:
    m = re.search(r"(cold_open_s\d+|act\d_s\d+|outro_s\d+)", cut.get("reason", ""))
    return m.group(1) if m else None


def dur(path: str) -> float:
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]
    ).strip())


def build_audio(music_dir: str, ed: dict, reuse: bool = False) -> tuple[str, list[float]]:
    """Narration concat + crossfaded music bed, ducked, then loudness-normalised."""
    os.makedirs(OUT, exist_ok=True)
    final_path = os.path.join(OUT, "mix_final.wav")
    if reuse and os.path.exists(final_path):
        offsets, t = [], 0.0
        for s in SECTIONS:
            offsets.append(t)
            t += dur(os.path.join(AUD, s + ".wav"))
        print("audio: reusing existing mix_final.wav")
        return final_path, offsets
    narration = os.path.join(OUT, "narration.wav")
    offsets, t = [], 0.0
    for s in SECTIONS:
        offsets.append(t)
        t += dur(os.path.join(AUD, s + ".wav"))
    total = t

    concat_list = os.path.join(OUT, "narration_concat.txt")
    with open(concat_list, "w", encoding="utf-8") as fh:
        for s in SECTIONS:
            fh.write(f"file '{os.path.join(AUD, s + '.wav')}'\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", concat_list, "-c", "copy", narration], check=True)

    beds = [os.path.join(music_dir, b["track"].replace("/", "_")) for b in ed["music"]["beds"]]
    beds = [b if os.path.exists(b) else None for b in beds]
    missing = [b["track"] for b, p in zip(ed["music"]["beds"], beds) if p is None]
    if missing:
        raise SystemExit("music beds not found: " + ", ".join(missing))

    # Crossfade the beds into one continuous bed, then loop-trim to narration.
    xf = ed["music"]["crossfade_seconds"]
    music_raw = os.path.join(OUT, "music_bed.wav")
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for b in beds:
        cmd += ["-i", b]
    chain, prev = [], "0:a"
    for i in range(1, len(beds)):
        label = f"x{i}"
        chain.append(f"[{prev}][{i}:a]acrossfade=d={xf}:c1=tri:c2=tri[{label}]")
        prev = label
    chain.append(f"[{prev}]apad,atrim=0:{total:.3f},asetpts=N/SR/TB[mout]")
    cmd += ["-filter_complex", ";".join(chain), "-map", "[mout]", music_raw]
    subprocess.run(cmd, check=True)

    # Duck the bed under narration, mix, then normalise to the playbook target.
    duck_db = ed["audio"]["ducking_db"]
    lufs = ed["audio"]["target_lufs"]
    tp = ed["audio"]["true_peak_db"]
    mixed = os.path.join(OUT, "mix.wav")
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", narration, "-i", music_raw,
        "-filter_complex",
        f"[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,asplit=2[nar][key];"
        f"[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,volume={duck_db / 3:.2f}dB[bed];"
        f"[bed][key]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400:makeup=1[ducked];"
        f"[nar][ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[pre];"
        f"[pre]loudnorm=I={lufs}:TP={tp}:LRA=11[out]",
        "-map", "[out]", "-ar", "48000", "-ac", "2", mixed,
    ], check=True)

    # Single-pass loudnorm lands about 1.3 LU hot on a mix this dense, so the
    # mix is measured and corrected. Two passes, not an estimate.
    final = os.path.join(OUT, "mix_final.wav")
    probe = subprocess.run(
        ["ffmpeg", "-nostats", "-i", mixed, "-af",
         f"loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=json", "-f", "null", "/dev/null"],
        capture_output=True, text=True).stderr
    m = json.loads(re.search(r'\{[^{}]*"input_i"[\s\S]*?\}', probe).group(0))
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", mixed, "-af",
        f"loudnorm=I={lufs}:TP={tp}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
        f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
        f"offset={m['target_offset']}:linear=true",
        "-ar", "48000", "-ac", "2", final,
    ], check=True)
    return final, offsets


def build_captions(offsets: list[float]) -> list[dict]:
    words: list[dict] = []
    for section, off in zip(SECTIONS, offsets):
        path = os.path.join(CAP, section, "transcript.json")
        if not os.path.exists(path):
            continue
        items = json.load(open(path, encoding="utf-8"))
        for i, w in enumerate(items):
            text = w["text"]
            words.append({
                "word": text,
                "startMs": round((w["start"] + off) * 1000),
                "endMs": round((w["end"] + off) * 1000),
                # Sentence-final punctuation is a real break: the narration was
                # synthesised per sentence, so these are the natural pages.
                "pageBreakAfter": text.endswith((".", "?", "!", "”")) or i == len(items) - 1,
            })
    return words


def main() -> int:
    ed = json.load(open(os.path.join(ART, "edit_decisions.json"), encoding="utf-8"))
    music_dir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MUSIC_LIBRARY_DIR", "")
    if not music_dir or not os.path.isdir(music_dir):
        raise SystemExit("pass the music library dir as argv[1] or set MUSIC_LIBRARY_DIR")

    mixed, offsets = build_audio(music_dir, ed, reuse="--reuse-audio" in sys.argv)
    captions = build_captions(offsets)

    # cuts: durations -> absolute timeline positions, back to back
    t = 0.0
    for cut in ed["cuts"]:
        length = cut["out_seconds"] - cut["in_seconds"]
        cut["source_in_seconds"] = cut.get("source_in_seconds", 0)
        cut["in_seconds"] = round(t, 3)
        cut["out_seconds"] = round(t + length, 3)
        t += length

    # Overlays reference a scene_id and carry no timing, and their text still
    # has the plan's `text — "..."` wrapper around it. Both are resolved here:
    # an overlay with no finite in_seconds makes Remotion throw on a NaN
    # Sequence `from`, and the wrapper would have been read out on screen.
    cut_by_slot = {}
    for cut in ed["cuts"]:
        sid = slot_id(cut)
        if sid:
            cut_by_slot.setdefault(sid, cut)
    overlays = []
    dropped = []
    for ov in ed.get("overlays", []):
        cut = cut_by_slot.get(ov.get("scene_id"))
        raw = (ov.get("text") or "").strip()
        kind = raw.split("\u2014", 1)[0].strip().lower()
        body = raw.split("\u2014", 1)[-1].strip().strip('\u201c\u201d"')
        if not cut or kind not in ("text", "stat"):
            # Two entries are slot descriptions that leaked into the overlay
            # list ("comparison — ancient reading vs modern quoted rate"). They
            # are display copy for nothing; dropped rather than read out.
            dropped.append(raw)
            continue
        length = cut["out_seconds"] - cut["in_seconds"]
        overlays.append({
            "type": "emphasis",
            "level": "data" if kind == "stat" else "display",
            "text": body,
            "in_seconds": cut["in_seconds"],
            "out_seconds": cut["out_seconds"],
            "hold": max(1.6, length - 1.8),
        })

    props = {
        "cuts": ed["cuts"],
        "overlays": overlays,
        "captions": captions,
        "caption_style": "documentary",
        "playbook": "wak3up-documentary",
        "audio": {"narration": {"src": os.path.abspath(mixed), "volume": 1.0}},
    }
    out = os.path.join(ART, "render_props.json")
    json.dump(props, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"timeline: {t:.2f}s over {len(ed['cuts'])} cuts")
    print(f"captions: {len(captions)} words, last at {captions[-1]['endMs'] / 1000:.2f}s")
    print(f"mix: {mixed} ({dur(mixed):.2f}s)")
    print(f"overlays: {len(overlays)} kept, {len(dropped)} dropped as slot descriptions")
    for d in dropped:
        print("  dropped:", d)
    print(f"props: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

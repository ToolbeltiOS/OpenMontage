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


PROXY_MAX = 2560  # long edge; leaves headroom for the 1.0 -> 1.08 parallax push


def proxy_image(path: str) -> str:
    """Downscale an oversized still once, and render against the copy.

    Several of the sourced stills are 7712x4352 — 33 megapixels. Chrome decodes
    the full image on every frame it appears in, which dominated the render:
    measured 1.0fps with the originals against 3.8fps without them, and single
    frames exceeding the 180-second per-frame timeout. Nothing is lost; the
    canvas is 1920x1080 and the largest push is 1.08.
    """
    if not os.path.isfile(path) or os.path.splitext(path)[1].lower() not in (".jpg", ".jpeg", ".png"):
        return path
    out_dir = os.path.join(OUT, "proxies")
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, os.path.basename(path))
    if os.path.exists(dest) and os.path.getmtime(dest) >= os.path.getmtime(path):
        return dest
    probe = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0", path,
    ], text=True).strip().split(",")
    w, h = int(probe[0]), int(probe[1])
    if max(w, h) <= PROXY_MAX:
        return path
    scale = f"scale={PROXY_MAX}:-2" if w >= h else f"scale=-2:{PROXY_MAX}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf", scale,
                    "-q:v", "2", dest], check=True)
    return dest


VIDEO_EXT = (".mp4", ".mov", ".webm", ".mkv", ".ogv", ".avi", ".m4v")


def proxy_video(path: str) -> str:
    """Transcode oversized footage to a 1080p h264 proxy.

    Remotion extracts frames from source video on every frame it renders. Act 1
    alone carries 652 MB of footage including a 162 MB 4K webm, and with
    several workers extracting at once the machine saturates — a neighbouring
    frame of a pure-SVG schematic, with no media in it at all, exceeded the
    300-second per-frame timeout waiting its turn.
    """
    if not os.path.isfile(path) or os.path.splitext(path)[1].lower() not in VIDEO_EXT:
        return path
    out_dir = os.path.join(OUT, "proxies")
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, os.path.splitext(os.path.basename(path))[0] + "_1080.mp4")
    if os.path.exists(dest) and os.path.getmtime(dest) >= os.path.getmtime(path):
        return dest
    try:
        w, h = subprocess.check_output([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0", path,
        ], text=True).strip().split(",")[:2]
        w, h = int(w), int(h)
    except Exception:
        return path
    size_mb = os.path.getsize(path) / 1e6
    if max(w, h) <= 1920 and size_mb <= 40 and path.lower().endswith(".mp4"):
        return path
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", path,
        "-vf", "scale='min(1920,iw)':-2:flags=bicubic",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-an", dest,
    ], check=True)
    return dest


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


def _norm(w: str) -> str:
    return w.lower().strip(".,;:!?\u201c\u201d'\"")


def build_captions(offsets: list[float], script: dict) -> tuple[list[dict], int]:
    """Script words, transcript timing.

    The transcripts come from forced alignment of the synthesised audio, so
    they carry the recogniser's spelling rather than the script's: Tiryns
    arrives as "Turin", Pausanias as "Porsanias", moai as "mowie", Pumapunku
    as "Puma Punku", and every spelled-out number comes back as digits. 128 of
    2,909 words were wrong. Burned captions are the most-read text in the film,
    so the words come from the approved script and only the timing comes from
    the transcript.

    Alignment is a plain sequence diff. Where the two agree, the script's
    spelling is used with the transcript's times; where they do not, the script
    words are distributed evenly across the span the transcript gives them.
    """
    import difflib

    words: list[dict] = []
    corrected = 0
    by_id = {sec["id"]: sec for sec in script["sections"]}

    for section, off in zip(SECTIONS, offsets):
        path = os.path.join(CAP, section, "transcript.json")
        if not os.path.exists(path):
            continue
        tr = json.load(open(path, encoding="utf-8"))
        # Keep the punctuation: it is what the caption pages break on, and a
        # subtitle track with none reads as a transcript dump.
        script_words = re.findall(
            r"[\u201c\"(]?[A-Za-z0-9'\u2019-]+[.,;:!?\u2014\u201d\")]*", by_id[section]["text"]
        )
        script_words = [w for w in script_words if any(c.isalnum() for c in w)]
        sm = difflib.SequenceMatcher(
            a=[_norm(w["text"]) for w in tr], b=[_norm(w) for w in script_words]
        )
        out: list[dict] = []
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal":
                for k in range(i2 - i1):
                    out.append({"word": script_words[j1 + k],
                                "start": tr[i1 + k]["start"], "end": tr[i1 + k]["end"]})
                continue
            if j1 == j2:
                continue  # the recogniser heard a word the script does not have
            if i2 > i1:
                span_start, span_end = tr[i1]["start"], tr[i2 - 1]["end"]
            else:
                # pure insertion: borrow the gap around the insertion point
                span_start = tr[i1 - 1]["end"] if i1 > 0 else 0.0
                span_end = tr[i1]["start"] if i1 < len(tr) else span_start + 0.3
                if span_end <= span_start:
                    span_end = span_start + 0.25
            n = j2 - j1
            step = (span_end - span_start) / n
            for k in range(n):
                out.append({"word": script_words[j1 + k],
                            "start": span_start + k * step,
                            "end": span_start + (k + 1) * step})
            corrected += n

        for i, w in enumerate(out):
            words.append({
                "word": w["word"],
                "startMs": round((w["start"] + off) * 1000),
                "endMs": round((w["end"] + off) * 1000),
                # Sentence-final punctuation is a real break: the narration was
                # synthesised per sentence, so these are the natural pages.
                "pageBreakAfter": w["word"].endswith((".", "?", "!")) or i == len(out) - 1,
            })
    return words, corrected


def main() -> int:
    ed = json.load(open(os.path.join(ART, "edit_decisions.json"), encoding="utf-8"))
    music_dir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MUSIC_LIBRARY_DIR", "")
    if not music_dir or not os.path.isdir(music_dir):
        raise SystemExit("pass the music library dir as argv[1] or set MUSIC_LIBRARY_DIR")

    mixed, offsets = build_audio(music_dir, ed, reuse="--reuse-audio" in sys.argv)
    script = json.load(open(os.path.join(ART, "script.json"), encoding="utf-8"))
    captions, corrected = build_captions(offsets, script)

    # Every cut carries the act chrome, authored or sourced. The frame and the
    # grade key off it, so a sourced photograph gets the same treatment as a
    # schematic instead of announcing itself as stock.
    ACTS = {
        "cold_open": ("00", "Cold open"),
        "act1": ("01", "A verdict two thousand years old"),
        "act2": ("02", "The statues that walked"),
        "act3": ("03", "The hole in the granite"),
        "act4": ("04", "The cases nobody has closed"),
        "outro": ("05", "Outro"),
    }
    slot_meta = {s["slot_id"]: s for s in
                 json.load(open(os.path.join(ART, "scene_plan.json"), encoding="utf-8"))["metadata"]["slots"]}
    for cut in ed["cuts"]:
        sid = slot_id(cut)
        if not sid:
            continue
        section = slot_meta.get(sid, {}).get("script_section_id", "")
        num, title = ACTS.get(section, ("", ""))
        cut.setdefault("actNumber", num)
        cut.setdefault("actTitle", title)
        cut.setdefault("sceneIndex", "S " + sid.rsplit("_s", 1)[-1])

    # Oversized stills are rendered against downscaled proxies.
    proxied = 0
    for cut in ed["cuts"]:
        for key in ("source", "backgroundImage"):
            src = cut.get(key)
            if not isinstance(src, str):
                continue
            new = proxy_image(src)
            if new == src:
                new = proxy_video(src)
            if new != src:
                cut[key] = new
                proxied += 1

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
    print(f"proxies: {proxied} oversized assets replaced (stills {PROXY_MAX}px, footage 1080p)")
    print(f"timeline: {t:.2f}s over {len(ed['cuts'])} cuts")
    print(f"captions: {len(captions)} words from the script, "
          f"{corrected} re-timed where the transcript disagreed, "
          f"last at {captions[-1]['endMs'] / 1000:.2f}s")
    print(f"mix: {mixed} ({dur(mixed):.2f}s)")
    print(f"overlays: {len(overlays)} kept, {len(dropped)} dropped as slot descriptions")
    for d in dropped:
        print("  dropped:", d)
    print(f"props: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

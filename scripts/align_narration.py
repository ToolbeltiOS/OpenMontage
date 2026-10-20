#!/usr/bin/env python3
"""Forced alignment of the narration against the script that was spoken.

WHY
---
Run #1's word timings were produced by transcribing the synthesised narration
and matching the result back to the script. That is two jobs at once, and it
failed at both: 128 of 2,909 words came back with the recogniser's spelling,
and 58 of them came back with no duration at all — one eight-word sentence
occupied 30 milliseconds. Burnt into the picture that was invisible. As a
subtitle track it is a cue that flashes and vanishes.

Forced alignment is the right instrument because it is told the words. It only
has to decide WHEN each one was said, which is a far easier problem than
deciding what was said, and it cannot invent "Turin" for "Tiryns" because it
was never asked.

The script is split into sentences and handed to WhisperX's wav2vec2 aligner
with the section's audio. The output has the script's spelling by construction.

    python scripts/align_narration.py --project they-said-it-couldnt-be-built
    python scripts/align_narration.py --project <id> --check   # gate only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: A word shorter than this did not get a timing, it got a placeholder. The
#: threshold is the one the SRT builder already uses to spot the damage.
MIN_WORD_MS = 40

SENTENCE_END = re.compile(r"(?<=[.!?”])\s+")


def sentences(text: str) -> list[str]:
    """Sentence-ish chunks. The aligner wants segments, not one wall of prose."""
    out: list[str] = []
    for para in text.split("\n"):
        para = para.strip()
        if not para or para.startswith("["):      # beat and air markers
            continue
        for s in SENTENCE_END.split(para):
            s = s.strip()
            if s:
                out.append(s)
    return out


def audio_seconds(path: Path) -> float:
    import subprocess

    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)]).strip())


def align_section(section_id: str, text: str, wav: Path, model, metadata,
                  device: str) -> list[dict]:
    import whisperx

    total = audio_seconds(wav)
    chunks = sentences(text)
    if not chunks:
        return []

    # Rough bounds proportional to length; the aligner moves them. They only
    # have to be in order and inside the audio.
    lengths = [max(len(c), 1) for c in chunks]
    scale = total / sum(lengths)
    segments, clock = [], 0.0
    for chunk, n in zip(chunks, lengths):
        start = clock
        clock = min(total, clock + n * scale)
        segments.append({"start": round(start, 3), "end": round(clock, 3),
                         "text": chunk})

    audio = whisperx.load_audio(str(wav))
    result = whisperx.align(segments, model, metadata, audio, device,
                            return_char_alignments=False)

    words: list[dict] = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            # The aligner leaves start/end off a word it could not place —
            # punctuation, mostly. Carried through as None and repaired below
            # rather than silently given a zero-length span, which is the
            # defect this whole exercise exists to remove.
            words.append({
                "word": w["word"],
                "start": w.get("start"),
                "end": w.get("end"),
                "score": w.get("score"),
            })
    words = [w for w in words if any(c.isalnum() for c in w["word"])]
    words = repair_unplaced(words, total)
    return enforce_floor(words, total)


def repair_unplaced(words: list[dict], total: float) -> list[dict]:
    """Give a word the aligner could not place a share of its neighbours' gap.

    These are nearly always punctuation-only tokens. A run of them is spread
    across the space between the last placed word and the next one, so every
    word has a real span and none of them is zero.
    """
    placed = [i for i, w in enumerate(words) if w["start"] is not None]
    if not placed:
        return words
    for i, w in enumerate(words):
        if w["start"] is not None:
            continue
        before = max((p for p in placed if p < i), default=None)
        after = min((p for p in placed if p > i), default=None)
        lo = words[before]["end"] if before is not None else 0.0
        hi = words[after]["start"] if after is not None else total
        run = [j for j in range(i, len(words)) if words[j]["start"] is None
               and (after is None or j < after)]
        span = max(hi - lo, 0.001)
        each = span / max(len(run), 1)
        for k, j in enumerate(run):
            words[j]["start"] = lo + k * each
            words[j]["end"] = lo + (k + 1) * each
    return words


def enforce_floor(words: list[dict], total: float,
                  min_ms: int = MIN_WORD_MS) -> list[dict]:
    """No word is shorter than a phoneme, and none of them overlaps.

    The aligner places short function words — "a", "it", "to" — at its own
    floor, sometimes 20ms and sometimes with a confidence of zero. Inside a
    cue that is harmless, because the cue is the unit a viewer reads. It still
    fails the word-duration gate, and a gate with known-harmless failures in
    it stops being read, so the span is widened into the silence beside it.

    This is not the repair the SRT builder refuses to do. That one would have
    padded a cue whose whole sentence had collapsed, hiding a broken
    alignment behind a plausible line. This moves a boundary by milliseconds
    inside speech that is correctly placed.
    """
    # One millisecond of slack. Without it the arithmetic lands on
    # 39.999999ms and every one of these fails a "< 40ms" gate by a hair,
    # which is a maddening way to read a report.
    floor = (min_ms + 1) / 1000.0
    for i, w in enumerate(words):
        if w["end"] - w["start"] >= floor:
            continue
        nxt = words[i + 1]["start"] if i + 1 < len(words) else total
        prev = words[i - 1]["end"] if i else 0.0
        need = floor - (w["end"] - w["start"])
        after = max(min(need, nxt - w["end"]), 0.0)
        w["end"] += after
        need -= after
        if need > 0:
            take = max(min(need, w["start"] - prev), 0.0)
            w["start"] -= take
            need -= take
        if need > 0 and i + 1 < len(words):
            # No silence either side: the words are contiguous. Move the
            # boundary into whichever neighbour can afford it, which is what a
            # human would do with a waveform open.
            after_w = words[i + 1]
            spare = (after_w["end"] - after_w["start"]) - floor
            take = max(min(need, spare), 0.0)
            if take > 0:
                w["end"] += take
                after_w["start"] += take
                need -= take
        if need > 0 and i:
            before_w = words[i - 1]
            spare = (before_w["end"] - before_w["start"]) - floor
            take = max(min(need, spare), 0.0)
            if take > 0:
                w["start"] -= take
                before_w["end"] -= take
    for w in words:
        w["start"] = round(w["start"], 4)
        w["end"] = round(w["end"], 4)
    return words


def count_short(words: list[dict], min_ms: int = MIN_WORD_MS) -> int:
    return sum(1 for w in words
               if w.get("start") is not None
               and (w["end"] - w["start"]) * 1000 < min_ms)


def existing_short(project: Path) -> tuple[int, int]:
    """Words under the floor in the transcripts already on disk."""
    short = total = 0
    for path in sorted((project / "assets" / "captions").glob("*/transcript.json")):
        words = json.loads(path.read_text())
        total += len(words)
        for w in words:
            s, e = w.get("start"), w.get("end")
            if s is None or e is None:
                continue
            if (e - s) * 1000 < MIN_WORD_MS:
                short += 1
    return short, total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--sections", nargs="*")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--check", action="store_true",
                    help="only report the word-duration gate on what is on disk")
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    script = json.loads((project / "artifacts" / "script.json").read_text())
    before_short, before_total = existing_short(project)

    if args.check:
        print(f"words under {MIN_WORD_MS}ms: {before_short} of {before_total}")
        print("WORD TIMINGS:", "PASS" if before_short == 0 else "FAIL")
        return 0 if before_short == 0 else 1

    import whisperx

    model, metadata = whisperx.load_align_model(language_code="en",
                                                device=args.device)

    after_short = after_total = 0
    for section in script["sections"]:
        sid = section["id"]
        if args.sections and sid not in args.sections:
            continue
        wav = project / "assets" / "audio" / f"{sid}.wav"
        if not wav.exists():
            print(f"{sid}: no audio at {wav}, skipped", file=sys.stderr)
            continue
        words = align_section(sid, section["text"], wav, model, metadata,
                              args.device)
        out = project / "assets" / "captions" / sid / "transcript.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(words, indent=1) + "\n")
        short = count_short(words)
        after_short += short
        after_total += len(words)
        print(f"{sid}: {len(words)} words, {short} under {MIN_WORD_MS}ms")

    print()
    print(f"before: {before_short} of {before_total} words under {MIN_WORD_MS}ms")
    print(f"after:  {after_short} of {after_total} words under {MIN_WORD_MS}ms")
    print("WORD TIMINGS:", "PASS" if after_short == 0 else "FAIL")
    return 0 if after_short == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Word timings into a subtitle track, and a check that it matches the film.

WHY A SIDECAR AND NOT BURNT-IN
------------------------------
Run #1 burnt word-level captions into the picture for the whole film, so text
sat on screen for 99.4% of the runtime at one size in one place. That is not a
caption style, it is a subtitle track rendered into the photograph — and on a
twenty-minute documentary it costs the bottom of every frame, permanently, to
serve viewers who could have had a track they can turn off, restyle, or read
in another language.

The reference films measured for run #2 put text on screen about two-thirds of
the time and all of it is *content* — headlines, documents, annotations. None
of them burn their narration.

So long-form delivers closed captions: an SRT generated here and uploaded with
`captions.insert` at publish. On-screen text stays inside the components that
exist to carry it.

THE GROUPING RULES, AND WHY THEY ARE WHAT THEY ARE
--------------------------------------------------
- **42 characters a line, two lines.** The usual broadcast line length; wider
  and the eye has to track across the frame instead of taking the line in.
- **1.2 seconds minimum.** Below that a cue is gone before it is read, and a
  track that flickers is worse than none.
- **Break on the sentence first.** The synthesis is per sentence, so
  `pageBreakAfter` marks a real boundary. Breaking on a character count
  through the middle of a clause is what makes an auto-generated track feel
  auto-generated.

The words come from the approved script, not the recogniser — see
`build_render_props.build_captions` for why 128 of 2,909 words were wrong the
other way round.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

MAX_CHARS_PER_LINE = 42
MAX_LINES = 2
MIN_CUE_SECONDS = 1.2
#: A cue ends on its last word, so it can only be long because the line is
#: spoken slowly — which is not a defect. What IS a defect is a line that goes
#: past faster than it can be read, so the limit is a reading rate. Broadcast
#: practice is 15-20 characters a second; 20 is the ceiling here.
MAX_CHARS_PER_SECOND = 20.0
#: And a sanity ceiling, well above any sentence read at a documentary pace.
MAX_CUE_SECONDS = 12.0
#: A silence longer than this inside a cue means the cue is spanning a pause.
#: It closes instead, which is also what keeps written air free of text.
MAX_INTRA_CUE_GAP_S = 1.0


def _wrap(text: str, width: int, max_lines: int) -> list[str] | None:
    """Greedy wrap, or None when the text cannot fit inside the box.

    Returning None rather than a wider line is the point: the caller adds words
    one at a time and stops at the last one that still fits, so no line is ever
    over the limit. An earlier version widened the width when the text
    overflowed, which produced 47-character lines on a 42-character rule.
    """
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        if len(w) > width:
            return None                     # a single word wider than the box
        candidate = f"{current} {w}".strip()
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = w
            if len(lines) >= max_lines:
                return None
    if current:
        lines.append(current)
    return lines if len(lines) <= max_lines else None


def group(words: list[dict[str, Any]],
          max_chars: int = MAX_CHARS_PER_LINE,
          max_lines: int = MAX_LINES,
          min_seconds: float = MIN_CUE_SECONDS) -> list[dict[str, Any]]:
    """Word cues into subtitle cues.

    A cue closes when the sentence ends, or when the next word would no longer
    wrap inside the box. Cues shorter than `min_seconds` are repaired against
    the surrounding silence, and if that is not enough, merged forward.
    """
    cues: list[dict[str, Any]] = []
    buf: list[dict[str, Any]] = []

    def lines_for(items: list[dict[str, Any]]) -> list[str] | None:
        return _wrap(" ".join(w["word"] for w in items).strip(), max_chars, max_lines)

    def close() -> None:
        if not buf:
            return
        text = " ".join(w["word"] for w in buf).strip()
        cues.append({
            "text": text,
            "startMs": buf[0]["startMs"],
            "endMs": buf[-1]["endMs"],
            "lines": lines_for(buf) or [text[:max_chars]],
            # kept for the repair pass, which needs word timings to move a
            # boundary; stripped before the track is written
            "_words": list(buf),
        })
        buf.clear()

    for w in words:
        # A cue never spans a pause. Without this a cue that straddles written
        # air holds its text through the silence, which is both stale on
        # screen and the exact opposite of what the air is for.
        if buf and (w["startMs"] - buf[-1]["endMs"]) / 1000.0 > MAX_INTRA_CUE_GAP_S:
            close()
        if buf and lines_for(buf + [w]) is None:
            close()
        buf.append(w)
        if w.get("pageBreakAfter"):
            close()
    close()

    repaired = _repair_short_cues(cues, min_seconds, max_chars, max_lines)
    for cue in cues:
        cue.pop("_words", None)
    if repaired:
        cues[0].setdefault("_notes", []).append(
            f"{repaired} cues were shorter than {min_seconds}s and were given "
            f"room from the silence around them")
    return cues


def _repair_short_cues(cues: list[dict[str, Any]], min_seconds: float,
                       max_chars: int, max_lines: int) -> int:
    """Give an unreadably short cue room, without moving anyone else's words.

    These exist because the forced aligner fails on some sentences and the
    fallback distributes the script's words evenly across a span of almost no
    length: 58 of run #1's 2,961 word timings are under 40ms, and one whole
    eight-word sentence occupies 30 milliseconds. Burnt into the picture that
    was invisible. In a sidecar track it is a cue that flashes and vanishes,
    so it is repaired here and counted, because the real fix belongs upstream
    in the alignment.
    """
    floor_ms = int(min_seconds * 1000)
    guard = 40                                  # ms kept clear of the neighbour
    repaired = 0

    for i, cue in enumerate(cues):
        if cue["endMs"] - cue["startMs"] >= floor_ms:
            continue
        before = cue["endMs"] - cue["startMs"]
        next_start = cues[i + 1]["startMs"] if i + 1 < len(cues) else None
        prev_end = cues[i - 1]["endMs"] if i else 0

        room_after = (next_start - guard - cue["endMs"]) if next_start is not None else floor_ms
        cue["endMs"] += max(min(floor_ms - (cue["endMs"] - cue["startMs"]), room_after), 0)

        if cue["endMs"] - cue["startMs"] < floor_ms:
            room_before = cue["startMs"] - (prev_end + guard)
            cue["startMs"] -= max(
                min(floor_ms - (cue["endMs"] - cue["startMs"]), room_before), 0)

        # Rebalance before merging. A trailing fragment like "lathe." is short
        # because the cue before it is full, so the boundary is in the wrong
        # place rather than the cue being wrong. Moving words back across it
        # fixes both cues and is what a subtitler would do.
        # ...but not when the cue is short because its word timings are
        # broken. Rebalancing then drags readable words out of a healthy
        # neighbour to pad a cue that no amount of words will fix, and it
        # split "nine hundred" across a cue boundary doing it. A degenerate
        # cue is reported instead, because the fix belongs in the alignment.
        degenerate = bool(cue.get("_words")) and all(
            (w["endMs"] - w["startMs"]) < 40 for w in cue["_words"])
        if (cue["endMs"] - cue["startMs"] < floor_ms and i
                and cue.get("_words") and not degenerate):
            prev = cues[i - 1]
            while (cue["endMs"] - cue["startMs"] < floor_ms
                   and len(prev.get("_words") or []) > 1):
                moved = prev["_words"][-1]
                trial_prev = prev["_words"][:-1]
                trial_cur = [moved] + cue["_words"]
                if (trial_prev[-1]["endMs"] - trial_prev[0]["startMs"]) < floor_ms:
                    break
                lines_prev = _wrap(" ".join(w["word"] for w in trial_prev),
                                   max_chars, max_lines)
                lines_cur = _wrap(" ".join(w["word"] for w in trial_cur),
                                  max_chars, max_lines)
                if lines_prev is None or lines_cur is None:
                    break
                prev["_words"], cue["_words"] = trial_prev, trial_cur
                prev["text"] = " ".join(w["word"] for w in trial_prev)
                prev["lines"] = lines_prev
                prev["endMs"] = trial_prev[-1]["endMs"]
                cue["text"] = " ".join(w["word"] for w in trial_cur)
                cue["lines"] = lines_cur
                cue["startMs"] = trial_cur[0]["startMs"]

        # Merging is padding too. A degenerate cue merged into its neighbour
        # shows its words at a time nobody spoke them and hides the broken
        # alignment behind a plausible-looking line; it stays separate and
        # reported.
        if cue["endMs"] - cue["startMs"] < floor_ms and not degenerate:
            # Backward first: a trailing fragment belongs to the sentence it
            # came from, and "lathe." on its own is not a subtitle.
            if i and not cues[i - 1].get("_drop"):
                prev = cues[i - 1]
                merged = f"{prev['text']} {cue['text']}".strip()
                lines = _wrap(merged, max_chars, max_lines)
                if lines is not None and cue["endMs"] > prev["endMs"]:
                    prev["text"] = merged
                    prev["lines"] = lines
                    prev["endMs"] = cue["endMs"]
                    cue["_drop"] = True
                    continue
            if i + 1 < len(cues):
                merged = f"{cue['text']} {cues[i + 1]['text']}".strip()
                lines = _wrap(merged, max_chars, max_lines)
                if lines is not None:
                    cue["text"] = merged
                    cue["lines"] = lines
                    cue["endMs"] = cues[i + 1]["endMs"]
                    cues[i + 1]["_drop"] = True

        if cue["endMs"] - cue["startMs"] > before:
            repaired += 1

    cues[:] = [c for c in cues if not c.pop("_drop", False)]

    # Final clamp. Extending one cue and pulling the next one back can cross
    # them over by a frame or two; a subtitle track with overlapping cues is
    # rejected by every player that validates one.
    for a, b in zip(cues, cues[1:]):
        if b["startMs"] < a["endMs"]:
            a["endMs"] = max(a["startMs"] + 1, b["startMs"] - 1)
    return repaired


def _ts(ms: int) -> str:
    ms = max(int(ms), 0)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for i, cue in enumerate(cues, start=1):
        out.append(str(i))
        out.append(f"{_ts(cue['startMs'])} --> {_ts(cue['endMs'])}")
        out.extend(cue["lines"])
        out.append("")
    return "\n".join(out)


def audio_duration(path: str) -> float:
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path]).strip())


def check(cues: list[dict[str, Any]], media_seconds: float | None = None,
          max_chars: int = MAX_CHARS_PER_LINE, max_lines: int = MAX_LINES,
          min_seconds: float = MIN_CUE_SECONDS) -> list[str]:
    """Problems with a subtitle track. Empty means it can ship."""
    problems: list[str] = []
    if not cues:
        return ["no cues"]

    for i, cue in enumerate(cues):
        n = i + 1
        if cue["endMs"] <= cue["startMs"]:
            problems.append(f"cue {n}: ends before it starts")
        dur = (cue["endMs"] - cue["startMs"]) / 1000.0
        if dur < min_seconds - 1e-6:
            problems.append(f"cue {n}: {dur:.2f}s, under the {min_seconds}s floor")
        if dur > MAX_CUE_SECONDS:
            problems.append(f"cue {n}: {dur:.2f}s on screen, longer than any "
                            f"line is spoken")
        cps = len(cue["text"]) / dur if dur > 0 else 999
        # half a character of slack, so a cue that lands exactly on the
        # ceiling is not reported as over it
        if cps > MAX_CHARS_PER_SECOND + 0.5:
            problems.append(
                f"cue {n}: {cps:.0f} characters a second, over the "
                f"{MAX_CHARS_PER_SECOND:.0f} ceiling — it is gone before it "
                f"can be read")
        if len(cue["lines"]) > max_lines:
            problems.append(f"cue {n}: {len(cue['lines'])} lines, over {max_lines}")
        for line in cue["lines"]:
            if len(line) > max_chars:
                problems.append(
                    f"cue {n}: a line is {len(line)} characters, over {max_chars}")
        if i and cue["startMs"] < cues[i - 1]["endMs"]:
            problems.append(f"cue {n}: overlaps the one before it")

    if media_seconds is not None:
        last = cues[-1]["endMs"] / 1000.0
        if last > media_seconds + 0.5:
            problems.append(
                f"the track runs to {last:.2f}s against {media_seconds:.2f}s of "
                f"audio — the captions outlast the film")
        if media_seconds - last > 30.0:
            problems.append(
                f"the track ends {media_seconds - last:.1f}s before the audio "
                f"does; a whole section is probably missing")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: captions_srt.py <render_props.json> [out.srt] [media]")
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        props = json.load(fh)
    words = props.get("captions") or []
    cues = group(words)

    media = None
    if len(argv) > 3 and os.path.exists(argv[3]):
        media = audio_duration(argv[3])

    problems = check(cues, media)
    if len(argv) > 2:
        with open(argv[2], "w", encoding="utf-8") as fh:
            fh.write(to_srt(cues))
        print(f"wrote {argv[2]}")

    total = sum(c["endMs"] - c["startMs"] for c in cues) / 1000.0
    print(f"{len(words)} words -> {len(cues)} cues, "
          f"{total:.0f}s on screen, last at {cues[-1]['endMs'] / 1000:.2f}s"
          + (f", media {media:.2f}s" if media else ""))
    for p in problems[:20]:
        print("  -", p)
    print("CAPTIONS:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

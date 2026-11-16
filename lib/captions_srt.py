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
import re
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


#: A sentence ends where the aligner says it does, or where the writing
#: does. `pageBreakAfter` is the authority when it is there; the punctuation
#: fallback matters because the two together are what the feasibility
#: measurement was taken over, and a grouping that drew its boundaries
#: differently would not inherit its result.
_SENTENCE_END = re.compile(r"[.!?]['\"\u2019\u201d]?$")


def _ends_a_sentence(word: dict[str, Any]) -> bool:
    if word.get("pageBreakAfter"):
        return True
    return bool(_SENTENCE_END.search(str(word.get("word") or "").strip()))


def _split_evenly(items: list[dict[str, Any]], pieces: int,
                  max_chars: int, max_lines: int
                  ) -> list[list[dict[str, Any]]] | None:
    """`items` into `pieces` groups of similar length, or None if they won't fit.

    Similar LENGTH, not similar word count: what a viewer reads is
    characters, and the rate each piece ends up at is characters over its
    share of the window.
    """
    if pieces <= 0 or pieces > len(items):
        return None
    lengths = [len(w["word"]) + 1 for w in items]
    target = sum(lengths) / pieces
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    size = 0
    for i, (word, length) in enumerate(zip(items, lengths)):
        current.append(word)
        size += length
        left = len(items) - i - 1
        if (len(groups) < pieces - 1 and size >= target
                and left >= pieces - len(groups) - 1):
            groups.append(current)
            current, size = [], 0
    if current:
        groups.append(current)
    if len(groups) != pieces:
        return None
    for group in groups:
        if _wrap(" ".join(w["word"] for w in group), max_chars,
                 max_lines) is None:
            return None
    return groups


def _cue_pieces(items: list[dict[str, Any]], max_chars: int, max_lines: int
                ) -> list[list[dict[str, Any]]]:
    """The fewest balanced pieces this run of words fits into.

    GREEDY FILL LEAVES ORPHANS. Filling line one and line two and letting
    the remainder become its own cue is how king-tut's track opened with
    "At Abydos, seventy-six kings are carved along one wall of the temple of
    Seti the" and then, alone for 1.3 seconds, "First." Measured across the
    two films that still have word timings: 26 of 296 cues and 29 of 269
    were fourteen characters or fewer, and the mid-sentence ones read as
    mistakes — "off.", "cameras.", "in.".

    They survived the repair pass because they were not SHORT: 1.28s is over
    the floor, so nothing looked at them. The boundary was wrong, not the
    duration, which is the same diagnosis the rebalance step was written
    for and the same fix, applied before the fact instead of after.
    """
    for pieces in range(1, len(items) + 1):
        got = _split_evenly(items, pieces, max_chars, max_lines)
        if got is not None:
            return got
    return [[w] for w in items]        # unwrappable even one word at a time


def group(words: list[dict[str, Any]],
          max_chars: int = MAX_CHARS_PER_LINE,
          max_lines: int = MAX_LINES,
          min_seconds: float = MIN_CUE_SECONDS) -> list[dict[str, Any]]:
    """Word cues into subtitle cues.

    A cue closes when the sentence ends, or when the next word would no longer
    wrap inside the box. Cues shorter than `min_seconds` are repaired against
    the surrounding silence, and if that is not enough, merged forward.
    """
    # SEGMENTS FIRST. A segment is a run of words that belongs together: it
    # ends at a sentence end, or at a pause, because a cue never spans
    # written air and two cues either side of silence are not one sentence
    # being read. Only a segment's own pieces share a window.
    segments: list[list[dict[str, Any]]] = []
    run: list[dict[str, Any]] = []
    for w in words:
        if run and (w["startMs"] - run[-1]["endMs"]) / 1000.0 > MAX_INTRA_CUE_GAP_S:
            segments.append(run)
            run = []
        run.append(w)
        if _ends_a_sentence(w):
            segments.append(run)
            run = []
    if run:
        segments.append(run)

    cues: list[dict[str, Any]] = []
    for sentence, segment in enumerate(segments):
        for piece in _cue_pieces(segment, max_chars, max_lines):
            text = " ".join(w["word"] for w in piece).strip()
            cues.append({
                "text": text,
                "startMs": piece[0]["startMs"],
                "endMs": piece[-1]["endMs"],
                "lines": _wrap(text, max_chars, max_lines) or [text[:max_chars]],
                # which segment this came out of, so the pieces of a split
                # sentence can be given its whole window back
                "_sentence": sentence,
                # kept for the repair pass, which needs word timings to move
                # a boundary; stripped before the track is written
                "_words": list(piece),
            })

    _fit_sentences(cues)
    repaired = _repair_short_cues(cues, min_seconds, max_chars, max_lines)
    if repaired:
        # AND FIT AGAIN, because the repair moves boundaries. Its rebalance
        # step moves words out of the previous cue and resets that cue's end
        # to its new last word — which throws away the reading time the fit
        # had given it. Measured on run #6: 37 cues repaired, and two
        # neighbours pushed over the ceiling paying for them, cue 103 from
        # 12.9 to 21.2 characters a second and cue 218 from 17.0 to 28.3.
        # Fitting again is safe: it only ever widens a sentence that is
        # short of reading time, and never past its neighbours.
        _fit_sentences(cues)
    for cue in cues:
        cue.pop("_words", None)
        cue.pop("_sentence", None)
    if repaired:
        cues[0].setdefault("_notes", []).append(
            f"{repaired} cues were shorter than {min_seconds}s and were given "
            f"room from the silence around them")
    return cues


#: How far a cue may hold past its last word, into the silence that follows.
HOLD_INTO_GAP_S = 1.5
#: And the rate it is trying to reach by doing so. A cue already readable at
#: this rate takes nothing from the gap, which is what keeps written air clear
#: of text where the narration was not rushing in the first place.
COMFORTABLE_CHARS_PER_SECOND = 17.0
#: And how much of that silence is left clear before the next cue.
GAP_GUARD_S = 0.08

#: How far a cue may appear BEFORE its first word, into the silence in front
#: of it.
#:
#: `_hold_into_gaps` only ever extended the END, and that is half a gap. A
#: sentence's reading time is the silence on BOTH sides of it, and the ones
#: that read too fast are short sentences whose following pause is short —
#: nothing to hold into, while a second and a half of silence sits unused in
#: front. Measured on run #6's own track, one cue per sentence:
#:
#:     lead 0.0s, lag 1.5s     9 cues over 20 cps, worst 34.1
#:     lead 0.5s, lag 1.5s     2 cues over 20 cps, worst 23.3
#:     lead 1.0s, lag 1.5s     0 cues over 20 cps, worst 17.9
#:
#: One second, because that is what reaches zero and nothing is gained by
#: more. It is comfortable against this narration's pauses: the gaps between
#: sentences run to a median of 1.69s and a p90 of 3.57s.
LEAD_IN_S = 1.0


def _hold_into_gaps(cues: list[dict[str, Any]]) -> None:
    """Let a cue stay on screen into the pause after it.

    A cue that ends on its last word gives the viewer no reading time in the
    silence that follows, which is where most of the reading actually happens.
    Ending on the word is also why 92 of 311 cues read as "too fast" the first
    time a properly aligned track went through here: the words were right and
    the reading time was missing.

    It takes only what it needs to reach a comfortable rate, never a flat
    amount. A cue that is already readable leaves the gap alone, which is what
    keeps written air free of text where the narration was not rushing.
    """
    for i, cue in enumerate(cues):
        needed = len(cue["text"]) / COMFORTABLE_CHARS_PER_SECOND * 1000
        shortfall = needed - (cue["endMs"] - cue["startMs"])
        if shortfall <= 0:
            continue                      # readable already; the gap stays clear
        limit = (cues[i + 1]["startMs"] - int(GAP_GUARD_S * 1000)
                 if i + 1 < len(cues) else cue["endMs"] + int(HOLD_INTO_GAP_S * 1000))
        cue["endMs"] = max(cue["endMs"],
                           min(limit, cue["endMs"] + int(min(shortfall,
                                                             HOLD_INTO_GAP_S * 1000))))


def _fit_sentences(cues: list[dict[str, Any]]) -> None:
    """Give each sentence the reading time it needs, and share it out.

    THE SENTENCE IS THE AUTHORITY, and it is the unit that owns the silence
    around it. Three things were wrong with doing this per cue:

    1. ONLY THE END WAS EXTENDED. A cue that ends on its last word gives the
       viewer no reading time in the silence that follows, which is where
       most of the reading happens — ending on the word is why 92 of 311
       cues read as too fast the first time a properly aligned track came
       through here. But a sentence's reading time is the silence on BOTH
       sides of it, and the cues that still read too fast after the end was
       extended were short sentences with a short pause after them and a
       second and a half sitting unused in front.

    2. A SPLIT SENTENCE LEFT ITS EARLIER PIECES WITH NOTHING. A sentence
       longer than two lines must be split — 41 of run #6's 245 sentences
       were, at a median of 95 characters — and the last piece inherited the
       whole trailing pause while the earlier ones hugged their own words.
       That is exactly where run #6's 25 fast cues came from, every one a
       mid-sentence fragment ending on "came", "with", "north-west of". The
       gap after such a fragment is the next fragment, 0.02–0.08s away.

    3. THE NEED WAS COMPUTED PER FRAGMENT. A fragment can look readable on
       its own while the sentence it belongs to is not.

    So: take the sentence's whole text, work out what it needs at a
    comfortable rate, and widen the sentence's window — into the pause after
    it first, then into the pause in front, each capped — until it has that
    or the neighbours are reached. Then apportion the window across the
    sentence's pieces by how much text each carries, so every piece reads at
    the sentence's own rate.

    A sentence already readable in its own span is left exactly alone, which
    is what keeps written air clear of text where the narration was not
    rushing.
    """
    runs: list[tuple[int, int]] = []
    at = 0
    while at < len(cues):
        end = at
        while (end + 1 < len(cues)
               and cues[end + 1].get("_sentence") == cues[at].get("_sentence")):
            end += 1
        runs.append((at, end))
        at = end + 1

    for index, (first, last) in enumerate(runs):
        here = cues[first:last + 1]
        chars = sum(len(c["text"]) for c in here) or 1
        span = cues[last]["endMs"] - cues[first]["startMs"]
        # WHAT EACH PIECE NEEDS, summed — not what the sentence averages.
        # Proportional sharing alone satisfies the ceiling and breaks the
        # floor: a piece carrying nine characters of an eighty-five
        # character sentence gets a ninth of the window, 0.28s, and twenty
        # of run #6's cues landed under the floor that way while none was
        # over the ceiling. A sentence needs room for the SUM of its
        # pieces' minima.
        floors = [_readable_ms(c) for c in here]
        needed = max(sum(floors),
                     int(chars / COMFORTABLE_CHARS_PER_SECOND * 1000))

        # WIDENING IS CONDITIONAL. SHARING IS NOT.
        #
        # `continue` here used to skip both, and that stranded the very cues
        # this pass exists for. Sentence 192 of run #6 splits into a 6.18s
        # piece and "contempt." at 0.40s — 85 characters in a 6.6s window,
        # 12.9 a second, readable by any measure. So the widening was
        # skipped, correctly, and the SHARING was skipped with it. The
        # repair pass then moved words back across the boundary to lift
        # "contempt." off the floor and handed the result 1.2s for 34
        # characters: 28.3 a second, the worst cue in the track, inside a
        # sentence with four seconds of slack sitting next to it.
        #
        # Sharing takes nothing from anybody — it only moves a boundary
        # inside a window the sentence already holds.
        guard = int(GAP_GUARD_S * 1000)
        if span < needed:
            after_limit = (cues[last + 1]["startMs"] - guard
                           if last + 1 < len(cues)
                           else cues[last]["endMs"] + int(HOLD_INTO_GAP_S * 1000))
            before_limit = (cues[first - 1]["endMs"] + guard if first
                            else max(0, cues[first]["startMs"]
                                     - int(LEAD_IN_S * 1000)))

            # the pause behind first, then the pause in front
            room_after = min(int(HOLD_INTO_GAP_S * 1000),
                             max(0, after_limit - cues[last]["endMs"]))
            take = min(needed - span, room_after)
            cues[last]["endMs"] += take
            span += take

            if span < needed:
                room_before = min(int(LEAD_IN_S * 1000),
                                  max(0, cues[first]["startMs"] - before_limit))
                take = min(needed - span, room_before)
                cues[first]["startMs"] -= take
                span += take

        if last == first:
            continue

        # ALLOCATE: every piece its minimum first, then the surplus by how
        # much text it carries.
        window = cues[last]["endMs"] - cues[first]["startMs"]
        if sum(floors) <= window:
            surplus = window - sum(floors)
            shares = [f + int(surplus * len(c["text"]) / chars)
                      for f, c in zip(floors, here)]
        else:
            # Not enough room for every minimum even after widening. Split
            # what there is in proportion to those minima and let `check`
            # report the remainder: the honest answer is that this sentence
            # is spoken too fast for its own span, and the fix is upstream
            # in the pace or the writing, not in the arithmetic here.
            total = sum(floors) or 1
            shares = [int(window * f / total) for f in floors]

        edge = cues[first]["startMs"]
        for cue, share in zip(here, shares):
            cue["startMs"], cue["endMs"] = edge, edge + share
            edge += share
        here[-1]["endMs"] = max(here[-1]["endMs"], cues[first]["startMs"] + window)


#: A word timing this short is the aligner failing, not speech.
DEGENERATE_WORD_MS = 40


def _readable_ms(cue: dict[str, Any], min_seconds: float = MIN_CUE_SECONDS
                 ) -> int:
    """How long a cue must be on screen to be readable: BOTH rules.

    `min_seconds` stops it flashing; MAX_CHARS_PER_SECOND stops it going by
    faster than it can be read. Satisfying one and not the other is exactly
    how run #6 could be made to have no cue over the ceiling and twenty
    under the floor, or the reverse, but not neither.

    A degenerate cue is held to the floor alone: stretching broken alignment
    until the arithmetic looks readable hides it, and the fix is upstream.
    """
    floor = int(min_seconds * 1000)
    if _is_degenerate(cue):
        return floor
    return max(floor, int(len(cue["text"]) / MAX_CHARS_PER_SECOND * 1000))


def _is_degenerate(cue: dict[str, Any]) -> bool:
    """Every word in it is too short to have been said.

    Shared, because the repair's target and its rebalance have to agree
    about which cues are broken; they were two copies of the same condition.
    """
    words = cue.get("_words") or []
    return bool(words) and all(
        (w["endMs"] - w["startMs"]) < DEGENERATE_WORD_MS for w in words)


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
    base_floor_ms = int(min_seconds * 1000)
    guard = 40                                  # ms kept clear of the neighbour
    repaired = 0

    def target(cue: dict[str, Any]) -> int:
        """`_readable_ms` at this call's floor. The repair knew only the
        floor, so it handed a cue exactly 1.2s for 34 characters — 28 a
        second, run #6's worst, sitting precisely on the number it was
        given."""
        return _readable_ms(cue, min_seconds)

    for i, cue in enumerate(cues):
        floor_ms = target(cue)
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
        degenerate = _is_degenerate(cue)
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

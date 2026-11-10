#!/usr/bin/env python3
"""Does this act read like speech, or like a paragraph read aloud?

WHY A NUMBER AND NOT A NOTE IN A SKILL
--------------------------------------
Four rounds of voice A/Bs on 2026-11-10 ended with the unmodified
synthesiser winning, and the thing being judged was never the synthesiser.
A spectral chain was measured and rejected; a per-sentence pause model was
built and rejected; a second engine was cloned, verified sentence by
sentence, and rejected. What was actually tiring was the PROSE: every
sentence about the same length, every one with a subordinate clause hanging
off it, and nothing for the voice to land on.

The script director now asks for the opposite — vary the length, put a
question in where one is natural, a dash before each turn, one subordinate
clause at most, and let the landing line be a fragment. That is a style
note, and a style note is not checkable. These three numbers are the part
of it that is:

  mean sentence length   <= 16 words
  sentences under 8      >= 20% of them
  longest sentence       <= 30 words

THEY ARE A FLOOR, NOT THE GOAL. A script can pass all three and still read
flat; no measurement hears rhythm, and the only judge of that is the ear
that rejected four takes. What these numbers catch is the specific failure
they were derived from, which is an act of uniform mid-length sentences —
and that failure is invisible to every other check in this repo.

WHY THE SHORT-SENTENCE RULE NEEDS A MINIMUM SAMPLE
--------------------------------------------------
"20% of sentences under 8 words" is meaningless on a section with three
sentences in it: one short sentence is 33% and none is 0%, and neither
number says anything about rhythm. Below MIN_SENTENCES the fraction is
measured and reported but not enforced, and the report says so rather than
quietly passing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_fact_coverage import paragraphs, sentences  # noqa: E402

MEAN_MAX = 16.0
SHORT_WORDS = 8
SHORT_MIN_FRACTION = 0.20
LONG_MAX = 30
#: Below this many sentences the short-sentence fraction is noise.
MIN_SENTENCES = 5


def words(sentence: str) -> int:
    """Words a narrator says. Numerals count as one word each."""
    return len(re.findall(r"[0-9]+(?:[.,][0-9]+)*|[A-Za-zÀ-ɏ'’]+", sentence))


def measure(text: str) -> dict:
    lengths = [words(s) for s in sentences(text or "")]
    lengths = [n for n in lengths if n]
    if not lengths:
        return {"sentences": 0, "mean": 0.0, "short": 0,
                "short_fraction": 0.0, "longest": 0, "longest_text": "",
                "questions": 0, "dashes": 0, "paragraphs": 0}
    sents = sentences(text or "")
    longest_i = max(range(len(lengths)), key=lambda i: lengths[i])
    return {
        "sentences": len(lengths),
        "mean": round(sum(lengths) / len(lengths), 2),
        "short": sum(1 for n in lengths if n < SHORT_WORDS),
        "short_fraction": round(
            sum(1 for n in lengths if n < SHORT_WORDS) / len(lengths), 3),
        "longest": max(lengths),
        "longest_text": sents[longest_i],
        # reported, not enforced: "where natural" is not a number
        "questions": sum(1 for s in sents if s.rstrip().endswith("?")),
        "dashes": sum(1 for s in sents if "—" in s or " - " in s),
        "paragraphs": len(paragraphs(text or "")),
    }


def check(text: str, label: str = "") -> tuple[list[str], dict]:
    """The three enforced numbers. Everything else is information."""
    m = measure(text)
    problems: list[str] = []
    where = f"{label}: " if label else ""
    if not m["sentences"]:
        return problems, m

    if m["mean"] > MEAN_MAX:
        problems.append(
            f"{where}mean sentence length is {m['mean']} words, over the "
            f"{MEAN_MAX:.0f}-word limit. Cut the subordinate clauses; one "
            f"per sentence at most.")

    if m["longest"] > LONG_MAX:
        problems.append(
            f"{where}longest sentence is {m['longest']} words, over the "
            f"{LONG_MAX}-word limit: {m['longest_text'][:90]!r}")

    if m["sentences"] >= MIN_SENTENCES:
        if m["short_fraction"] < SHORT_MIN_FRACTION:
            problems.append(
                f"{where}only {m['short']} of {m['sentences']} sentences are "
                f"under {SHORT_WORDS} words ({m['short_fraction']:.0%}, needs "
                f"{SHORT_MIN_FRACTION:.0%}). The voice has nothing to land "
                f"on — make a landing line a fragment.")
    else:
        m["short_fraction_enforced"] = False
    return problems, m


def check_script(script: dict, only: list[str] | None = None
                 ) -> tuple[list[str], list[dict]]:
    problems: list[str] = []
    rows: list[dict] = []
    for section in script.get("sections", []):
        sid = section.get("id") or "?"
        if only and sid not in only:
            continue
        section_problems, m = check(section.get("text") or "", sid)
        m["id"] = sid
        rows.append(m)
        problems.extend(section_problems)
    return problems, rows

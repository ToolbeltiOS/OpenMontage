#!/usr/bin/env python3
"""WRITE FOR THE VOICE — the measurable part, enforced at the script gate.

WHY THIS EXISTS AT ALL
----------------------
Four rounds of voice A/Bs on 2026-11-10 ended with the unmodified
synthesiser beating every attempt to improve it. A spectral chain was
measured and rejected. A per-sentence pause model was built and rejected. A
second engine was cloned, verified sentence by sentence, and rejected. The
fault was never in the voice. It was prose written for the eye: every
sentence about the same length, a subordinate clause hanging off each one,
figures as digits, attribution trailing after the quote, and nothing short
for the voice to land on.

Across the three delivered scripts — 565 narration sentences — there are two
questions.

So the rule is in `skills/pipelines/narrated-documentary/script-director.md`
under "Write For The Voice", and the part of it that is a number is here.

THESE NUMBERS ARE THE OWNER'S, GIVEN WHOLE
------------------------------------------
They are not derived, tuned or defaulted, and they REPLACE an earlier,
looser set (mean 16, hard max 30) on the owner's instruction. One number is
mine and is marked as mine: BREATH_COMMA_WORDS, because "commas at breath
points even where grammar doesn't require" names no threshold.

WHAT A LINT CAN AND CANNOT DO
-----------------------------
It cannot hear rhythm. An act can satisfy every rule here and still read
flat, and the only judge of that is reading it aloud. What these catch is
the specific, repeatable, invisible-to-every-other-check failure above.

Several rules are HEURISTICS and they are written to UNDER-report rather
than over-report, because this blocks the script gate and a false positive
sends a writer to break a sentence that was fine. Each one says where its
limits are.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from script_beats import parse_section                      # noqa: E402
from verify_fact_coverage import (                          # noqa: E402
    WHITELIST, paragraphs, sentences)

# ── the owner's numbers ───────────────────────────────────────────────────
MAX_WORDS = 20
HARD_MAX_WORDS = 28
MEAN_MAX = 15.0
SHORT_WORDS = 8
SHORT_MIN_FRACTION = 0.20
MAX_SUBORDINATE_CLAUSES = 1
RHYTHM_RUN = 3
RHYTHM_BAND_WORDS = 3
LANDING_MAX_WORDS = 8
MAX_EM_DASHES_PER_PARAGRAPH = 2
MIN_QUESTIONS_PER_ACT = 1

#: Blocking violations a whole FILM may carry and still pass.
#:
#: NOT ZERO, AND THAT IS THE POINT. The script stage has 60 turns. It can
#: rewrite the worst twenty sentences in a 176-sentence film; it cannot
#: rewrite every one, and a gate demanding perfection makes it spend the cap
#: trying and then fail on the turn limit with the act half-edited. Measured
#: on the four delivered scripts, a literal zero would have refused all four
#: at between 102 and 123 violations each.
VOICE_BUDGET = 6

#: Reported, never counted against the budget. Whether "is not" is emphasis
#: or sloppiness is a writer's judgement and a regular expression cannot
#: make it: "The chronology is not the part anyone disputes" is the line the
#: act turns on.
ADVISORY_RULES = ("contractions",)

#: Zero tolerance, outside the budget. A sentence over the hard maximum and
#: a landing line that is a paragraph are the two faults that are audible on
#: their own — everything else is a tendency, and a tendency is what a
#: budget is for.
ALWAYS_BLOCKING = ("length-hard", "landing")

#: Below this many sentences the short-sentence fraction is noise: one short
#: line in three is 33% and says nothing about rhythm.
MIN_SENTENCES = 5

#: MINE, NOT THE OWNER'S. "Commas at breath points even where grammar
#: doesn't require" names no threshold, and a rule needs one to be checked.
#: Twice the short-sentence length is the longest run a narrator can take
#: without a breath, so a sentence longer than this with no comma in it has
#: nowhere to breathe. Raise or drop it on the owner's word, not by drift.
BREATH_COMMA_WORDS = 16

# ── vocabularies ─────────────────────────────────────────────────────────
#: Deliberately conservative. "as", "that", "if", "since", "before" and
#: "after" are left OUT because each is far more often a preposition or a
#: complementiser here than a subordinator, and this check blocks a gate.
#: It therefore misses some two-clause sentences and invents none.
SUBORDINATORS = ("which", "who", "whom", "whose", "because", "although",
                 "though", "whereas", "unless", "until", "while")

#: The five the owner named, with the expansion each one replaces.
CONTRACTIONS = {"it is": "it's", "that is": "that's", "did not": "didn't",
                "was not": "wasn't", "is not": "isn't"}
FORBIDDEN_CONTRACTIONS = ("could've", "would've", "should've", "there'll",
                          "it'll")

#: Read aloud, these send the listener back up the page. They cannot.
EYE_WORDS = ("the former", "the latter", "respectively", "aforementioned")

SYMBOLS = {"%": "per cent", "$": "dollars", "°": "degrees", "&": "and"}

#: Written short forms. An all-caps acronym is NOT here: "BBC" and "NASA"
#: are spoken as letters, which the rule allows.
ABBREVIATIONS = ("etc.", "e.g.", "i.e.", "vs.", "approx.", "cf.", "ibid.",
                 "Dr.", "Mr.", "Mrs.", "Ms.", "St.", "Prof.", "No.")

#: For "title before name on first mention". Scoped to names that carry an
#: attribution verb, because those are the people the rule is about, and a
#: general person-detector would block on "Egypt".
TITLES = ("doctor", "professor", "lord", "earl", "sir", "dame", "mister",
          "captain", "colonel", "major", "reverend", "the archaeologist",
          "the egyptologist", "the author", "the journalist", "the writer",
          "the historian", "the physician", "the chemist", "the curator",
          "the surgeon", "the pathologist", "the radiologist", "king",
          "queen", "pharaoh", "president", "secretary")

ATTRIBUTION_VERBS = ("says", "wrote", "said")


class Violation(NamedTuple):
    """One broken rule, with the sentence that broke it."""
    rule: str
    detail: str
    sentence: str
    where: str = ""

    def line(self) -> str:
        where = f"{self.where}: " if self.where else ""
        return f"{where}{self.detail}\n      {self.sentence!r}"


def words(text: str) -> int:
    """Words a narrator says. A numeral counts as one word."""
    return len(re.findall(r"[0-9]+(?:[.,][0-9]+)*|[A-Za-zÀ-ɏ'’]+", text))


def _lower(text: str) -> str:
    return re.sub(r"[’]", "'", text.lower())


# ── per-sentence rules ───────────────────────────────────────────────────
def check_length(sentence: str) -> list[Violation]:
    n = words(sentence)
    if n > HARD_MAX_WORDS:
        return [Violation("length-hard",
                          f"{n} words, over the {HARD_MAX_WORDS}-word HARD "
                          f"MAXIMUM. Split it.", sentence)]
    if n > MAX_WORDS:
        return [Violation("length", f"{n} words, over the {MAX_WORDS}-word "
                          f"limit.", sentence)]
    return []


def check_one_idea(sentence: str) -> list[Violation]:
    """One idea per sentence: at most one subordinate clause, no semicolon,
    no parenthesis.

    A semicolon and a bracket are both eye punctuation. A narrator has no
    way to say either, so the synthesiser reads straight through a semicolon
    as if it were a comma and a bracketed aside arrives as part of the
    sentence it interrupts.
    """
    out: list[Violation] = []
    low = _lower(sentence)
    found = [w for w in SUBORDINATORS
             if re.search(rf"\b{re.escape(w)}\b", low)]
    if len(found) > MAX_SUBORDINATE_CLAUSES:
        out.append(Violation(
            "one-idea", f"two subordinate clauses ({', '.join(found)}) — one "
            f"idea per sentence.", sentence))
    if ";" in sentence:
        out.append(Violation("one-idea", "a semicolon, which a voice cannot "
                             "say. Make it two sentences.", sentence))
    if "(" in sentence or ")" in sentence:
        out.append(Violation("one-idea", "a parenthesis, which arrives as "
                             "part of the sentence it interrupts.", sentence))
    return out


def check_contractions(sentence: str) -> list[Violation]:
    out: list[Violation] = []
    low = _lower(sentence)
    for expanded, short in CONTRACTIONS.items():
        if re.search(rf"\b{expanded}\b", low):
            out.append(Violation(
                "contractions", f"{expanded!r} where a speaker says "
                f"{short!r}.", sentence))
    for bad in FORBIDDEN_CONTRACTIONS:
        if bad in low:
            out.append(Violation(
                "contractions", f"{bad!r} is not sayable cleanly — write it "
                f"out.", sentence))
    return out


def check_spoken_forms(sentence: str) -> list[Violation]:
    """Numbers, years, units, currency and percentages as words.

    The synthesiser reads "1922" as a number and not a year, and "%" as
    whatever its front end guesses. The script is the only place this can be
    decided, because by synthesis the decision has been made badly.
    """
    out: list[Violation] = []
    digits = re.findall(r"\b[0-9][0-9.,]*\b", sentence)
    if digits:
        out.append(Violation(
            "spoken-forms", f"digits ({', '.join(digits[:4])}) — write the "
            f"number, year, unit or amount as words.", sentence))
    for sym, say in SYMBOLS.items():
        if sym in sentence:
            out.append(Violation("spoken-forms", f"{sym!r} — write {say!r}.",
                                 sentence))
    for abbr in ABBREVIATIONS:
        if abbr in sentence:
            out.append(Violation(
                "spoken-forms", f"{abbr!r} is a written abbreviation. Spell "
                f"it as it is spoken.", sentence))
    return out


def check_eye_words(sentence: str) -> list[Violation]:
    """Words that only work if the listener can look back up the page."""
    out: list[Violation] = []
    low = _lower(sentence)
    for phrase in EYE_WORDS:
        if re.search(rf"\b{re.escape(phrase)}\b", low):
            out.append(Violation(
                "eye-words", f"{phrase!r} asks the listener to look back. "
                f"Name the thing.", sentence))
    # "However" opening a sentence is a signpost and allowed; dropped into
    # the middle it is a written aside.
    mid = re.search(r"\S\s*,?\s+however\b", low)
    if mid and not low.lstrip().startswith("however"):
        out.append(Violation(
            "eye-words", "mid-sentence 'however' — start the sentence with "
            "'But' or begin a new one.", sentence))
    return out


def check_attribution(sentence: str) -> list[Violation]:
    """The source leads, and it says or wrote. It never trails.

    Trailing attribution works on the page because the eye has already seen
    the quotation marks. Spoken, the listener hears a claim with no owner
    and is told whose it was afterwards, by which point they have decided
    whether to believe it.
    """
    out: list[Violation] = []
    trailing = re.search(
        r",\s+(?:said|says|wrote)\s+([A-Z][\w'’-]+)|,\s+([A-Z][\w'’-]+)\s+"
        r"(?:said|says|wrote)\s*[.?!]?$", sentence)
    if trailing:
        who = trailing.group(1) or trailing.group(2)
        out.append(Violation(
            "attribution", f"attribution trails the claim ({who}). Lead with "
            f"the source.", sentence))
    if re.search(r"\bsaid\b", sentence):
        out.append(Violation(
            "attribution", "'said' — use 'says' for a living voice or 'wrote' "
            "for a document.", sentence))
    return out


def check_breath(sentence: str) -> list[Violation]:
    if words(sentence) > BREATH_COMMA_WORDS and "," not in sentence:
        return [Violation(
            "breath", f"over {BREATH_COMMA_WORDS} words with no comma — "
            f"nowhere to breathe.", sentence)]
    return []


PER_SENTENCE = (check_length, check_one_idea, check_contractions,
                check_spoken_forms, check_eye_words, check_attribution,
                check_breath)


# ── per-section rules ────────────────────────────────────────────────────
#: "Arthur Weigall of the Daily Mail" identifies its source without a title
#: word, and so does "Mark Nelson, a physician at". An identification is what
#: the rule is actually for — the listener needs to know who is talking — so
#: either a title or an identifying phrase satisfies it.
IDENTIFIES = re.compile(
    r"\b(?:of|at|from|with)\s+(?:the\s+)?[A-Z]|,\s*(?:a|an|the)\s+[a-z]")


def check_titles(section_text: str) -> list[Violation]:
    """A title before the name, on first mention only.

    Scoped to names carrying an attribution verb: those are the people the
    rule exists for. A general person-detector would block on "Egypt".

    THE NAME IS THE WHOLE CAPITALISED PHRASE, NOT THE WORD BEFORE THE VERB.
    Matching one word made "Arthur Weigall of the Daily Mail says" report
    `Mail` as an untitled source — the last word of the organisation, which
    is not a person and was already identified. It under-reports now: a name
    it cannot parse is left alone rather than guessed at.
    """
    out: list[Violation] = []
    sents = sentences(section_text)
    verbs = "|".join(ATTRIBUTION_VERBS)
    attributed: list[str] = []
    for sentence in sents:
        for m in re.finditer(
                rf"\b((?:[A-Z][\w'’-]+\s+)*[A-Z][\w'’-]+)"
                rf"(?:\s+of\s+(?:the\s+)?(?:[A-Z][\w'’-]+\s*)+)?"
                rf"\s+(?:{verbs})\b", sentence):
            phrase = m.group(1).strip()
            # a single capitalised word that is the tail of a longer phrase
            # ("Mail" in "the Daily Mail") is not the source's name
            parts = phrase.split()
            name = " ".join(parts[-2:]) if len(parts) >= 2 else phrase
            # A WORD CAPITALISED BY POSITION IS NOT A NAME. "Nobody wrote it
            # down" reported `Nobody` as an untitled source. The same
            # whitelist the capitalisation backend uses for exactly this —
            # one list, so the two cannot disagree about what a name is.
            if all(w.lower() in WHITELIST for w in parts):
                continue
            if name not in attributed:
                attributed.append(name)

    for name in attributed:
        first = next((s for s in sents
                      if re.search(rf"\b{re.escape(name)}\b", s)), None)
        if first is None:
            continue
        before = _lower(first.split(name)[0])
        titled = any(t in before for t in TITLES)
        identified = bool(IDENTIFIES.search(first))
        if not titled and not identified:
            out.append(Violation(
                "title", f"{name} is attributed but is neither titled nor "
                f"identified on first mention. Say who they are before what "
                f"they said.", first))
    return out


def check_rhythm(section_text: str, label: str = "") -> list[Violation]:
    """No three consecutive sentences within ±3 words of each other.

    This is the flatness, measured. It is the one rule here that no
    sentence breaks on its own.
    """
    out: list[Violation] = []
    sents = sentences(section_text)
    lengths = [words(s) for s in sents]
    i = 0
    while i + RHYTHM_RUN <= len(lengths):
        run = lengths[i:i + RHYTHM_RUN]
        # A RUN OF FRAGMENTS IS A DEVICE, NOT FLATNESS, and this is a real
        # collision between two of the rules: "at least a fifth of sentences
        # under 8 words" is satisfied by putting short lines together, and
        # a literal ±3 band then refuses them. "Arthur Mace. / Mervyn
        # Herbert. / Richard Bethell." is [2, 2, 2] and is the OPPOSITE of
        # the uniform mid-length prose this rule is against. So a run whose
        # every sentence is already a landing-length fragment is allowed.
        # MINE, not the owner's — flagged for a ruling.
        if max(run) < SHORT_WORDS:
            i += RHYTHM_RUN
            continue
        if max(run) - min(run) <= RHYTHM_BAND_WORDS:
            out.append(Violation(
                "rhythm", f"{RHYTHM_RUN} consecutive sentences of {run} words "
                f"— all within {RHYTHM_BAND_WORDS}. Break the pattern.",
                " / ".join(s[:40] for s in sents[i:i + RHYTHM_RUN]), label))
            i += RHYTHM_RUN           # report a run once, not every window
        else:
            i += 1
    return out


def check_questions(section_text: str, label: str = "") -> list[Violation]:
    sents = sentences(section_text)
    asked = sum(1 for s in sents if s.rstrip().endswith("?"))
    if sents and asked < MIN_QUESTIONS_PER_ACT:
        return [Violation(
            "questions", f"no question in this act. One per act, where it is "
            f"natural.", f"{len(sents)} sentences, {asked} questions", label)]
    return []


def check_landings(section_text: str, label: str = "") -> list[Violation]:
    """A landing line is short or it does not land."""
    out: list[Violation] = []
    for beat in parse_section(section_text):
        if beat["type"] != "landing":
            continue
        sents = sentences(beat["text"])
        if not sents:
            continue
        last = sents[-1]
        n = words(last)
        if n > LANDING_MAX_WORDS:
            out.append(Violation(
                "landing", f"the landing line is {n} words, over "
                f"{LANDING_MAX_WORDS}. A landing is a fragment.", last, label))
    return out


def check_paragraph_dashes(section_text: str, label: str = "") -> list[Violation]:
    out: list[Violation] = []
    for i, para in enumerate(paragraphs(section_text)):
        n = para.count("—")
        if n > MAX_EM_DASHES_PER_PARAGRAPH:
            out.append(Violation(
                "dashes", f"{n} em dashes in one paragraph, over "
                f"{MAX_EM_DASHES_PER_PARAGRAPH}. Each one is a turn; three "
                f"is a list.", para[:90], label))
    return out


def measure(text: str) -> dict[str, Any]:
    sents = sentences(text or "")
    lengths = [words(s) for s in sents]
    lengths = [n for n in lengths if n]
    if not lengths:
        return {"sentences": 0, "mean": 0.0, "short": 0, "short_fraction": 0.0,
                "longest": 0, "longest_text": "", "questions": 0, "dashes": 0,
                "paragraphs": 0}
    longest_i = max(range(len(lengths)), key=lambda i: lengths[i])
    short = sum(1 for n in lengths if n < SHORT_WORDS)
    return {
        "sentences": len(lengths),
        "mean": round(sum(lengths) / len(lengths), 2),
        "short": short,
        "short_fraction": round(short / len(lengths), 3),
        "longest": max(lengths),
        "longest_text": sents[longest_i],
        "questions": sum(1 for s in sents if s.rstrip().endswith("?")),
        "dashes": sum(1 for s in sents if "—" in s),
        "paragraphs": len(paragraphs(text or "")),
    }


def check(text: str, label: str = "") -> tuple[list[Violation], dict[str, Any]]:
    """Every rule, over one section."""
    m = measure(text)
    out: list[Violation] = []
    if not m["sentences"]:
        return out, m

    for sentence in sentences(text):
        for rule in PER_SENTENCE:
            for v in rule(sentence):
                out.append(v._replace(where=label))

    if m["mean"] > MEAN_MAX:
        out.append(Violation(
            "mean", f"mean sentence length is {m['mean']} words, over "
            f"{MEAN_MAX:.0f}. Cut the subordinate clauses.",
            f"{m['sentences']} sentences", label))

    if m["sentences"] >= MIN_SENTENCES:
        if m["short_fraction"] < SHORT_MIN_FRACTION:
            out.append(Violation(
                "short-lines", f"only {m['short']} of {m['sentences']} "
                f"sentences are under {SHORT_WORDS} words "
                f"({m['short_fraction']:.0%}, needs "
                f"{SHORT_MIN_FRACTION:.0%}). Nothing to land on.",
                f"{m['sentences']} sentences", label))
    else:
        m["short_fraction_enforced"] = False

    out += check_titles(text)
    out += check_rhythm(text, label)
    out += check_questions(text, label)
    out += check_landings(text, label)
    out += check_paragraph_dashes(text, label)
    return out, m


def check_script(script: dict, only: list[str] | None = None
                 ) -> tuple[list[Violation], list[dict[str, Any]]]:
    out: list[Violation] = []
    rows: list[dict[str, Any]] = []
    for section in script.get("sections", []):
        sid = section.get("id") or "?"
        if only and sid not in only:
            continue
        violations, m = check(section.get("text") or "", sid)
        m["id"] = sid
        m["violations"] = len(violations)
        rows.append(m)
        out.extend(violations)
    return out, rows


def summarise(violations: list[Violation]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for v in violations:
        counts[v.rule] = counts.get(v.rule, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def classify(violations: list[Violation]) -> dict[str, list[Violation]]:
    """Split a run into what fails, what always fails, and what only warns."""
    advisory = [v for v in violations if v.rule in ADVISORY_RULES]
    blocking = [v for v in violations if v.rule not in ADVISORY_RULES]
    hard = [v for v in blocking if v.rule in ALWAYS_BLOCKING]
    return {"advisory": advisory, "blocking": blocking, "hard": hard}


def verdict(violations: list[Violation], whole_film: bool = True
            ) -> tuple[bool, list[str]]:
    """Does this pass VOICE? With the reasons it does not.

    THE BUDGET IS A WHOLE-FILM NUMBER. Run against one act it cannot be
    judged, because six across a film is not six per act, so a single-act
    run enforces only the zero-tolerance faults and says that the budget is
    still owed. Pretending otherwise would let a film through at five
    violations an act, which is thirty.
    """
    parts = classify(violations)
    reasons: list[str] = []
    for v in parts["hard"]:
        reasons.append(f"[{v.rule}] {v.detail}  {v.sentence[:90]!r}")
    if whole_film and len(parts["blocking"]) > VOICE_BUDGET:
        reasons.append(
            f"{len(parts['blocking'])} blocking violations across the film, "
            f"over the budget of {VOICE_BUDGET}. Fix the worst "
            f"{len(parts['blocking']) - VOICE_BUDGET} and the rest can stand.")
    return (not reasons), reasons

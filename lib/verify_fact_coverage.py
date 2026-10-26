#!/usr/bin/env python3
"""Every factual sentence carries a ledger claim, and the claim has a source.

THE RULE (owner, 2026-10-26, blocking at the script stage)
----------------------------------------------------------
A sentence containing a date, a number, a proper noun or a quotation is
making a claim about the world. It must carry at least one ledger claim id in
its paragraph's claims list, and that claim must have a source URL.

WHAT THIS FOUND THE FIRST TIME IT RAN
--------------------------------------
The claim ids the delivered films cite do not resolve. `research_brief.json`
carries `data_points` with no `id` field at all, so every citation is matched
positionally or not at all — and easter-island's script cites c03 to c58
against a fifteen-entry ledger. Forty-two of its fifty-four cited ids are
past the end of the list under any reading. The attribution chain looked like
provenance and pointed at nothing.

That is the finding the sentence counts sit inside, and it is why this gate
checks that a cited id RESOLVES rather than that a citation is present.

WHERE THE CLAIMS ARE LOOKED FOR
-------------------------------
In order, first one wins:

1. the paragraph's own `claims` list — what the rule asks for, and what the
   script stage must produce from now on;
2. the section's `claims` list;
3. claim ids parsed out of the section's `source_ref` string, which is what
   the existing scripts have: free prose reading "research_brief claim ledger
   c17, c07, c18 — projects/<id>/artifacts/research_brief.json".

Level 3 is how the delivered films can be measured at all, and it is weaker
in a way worth stating: it attributes a whole section to a bag of ids, so it
cannot tell which sentence rests on which claim. It is reported as
`attribution: section` so a pass at that level is never mistaken for a pass
at the level the rule asks for.

NUMBERS ARE SPELLED OUT IN THIS CHANNEL'S SCRIPTS
-------------------------------------------------
"three hundred and ninety-four", "about ninety-five per cent". A digit regex
finds none of them. Both forms are detected, and on the delivered films the
spelled-out form is the overwhelming majority — a digits-only gate would have
passed almost every number in the catalogue.

    python3 lib/verify_fact_coverage.py --project easter-island
    python3 lib/verify_fact_coverage.py --script a.json --brief b.json --report r.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

#: Production markers the script carries, which are not narration.
MARKERS = re.compile(r"\[[^\]]*\]")

#: A year, or a month name, or an explicit date.
DATE = re.compile(
    r"\b(?:1[0-9]{3}|20[0-9]{2})s?\b"
    r"|\b(?:January|February|March|April|May|June|July|August|September"
    r"|October|November|December)\b"
    r"|\b(?:BCE?|AD|CE)\b", re.I)

#: Digits in any form, including ordinals and percentages.
DIGITS = re.compile(r"\d")

#: Numbers as this channel writes them. The scripts spell them out, so a
#: digits-only rule would see almost none of the film's figures.
WORD_NUMBERS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million",
    "billion", "trillion", "dozen", "half", "quarter", "third", "twice",
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
    "eighth", "ninth", "tenth", "hundredth", "thousandth",
}

#: Section types the gate does not examine, read from the playbook.
#:
#: BY SECTION TYPE, NEVER BY SENTENCE. A per-sentence whitelist is a way to
#: turn the gate off one line at a time, and the line that most wants
#: exempting is always the one that most needs checking. A section type is a
#: claim about what a section IS, and it is arguable in one place instead of
#: fifty.
DEFAULT_EXEMPT = ("outro",)

#: Sections that may never be exempted, whatever the playbook says. The cold
#: open is the most claim-dense minute in the film and it is where a viewer
#: decides whether to believe the rest.
NEVER_EXEMPT = ("cold_open", "act1", "act2", "act3", "act4", "title_sequence")


def exempt_sections(playbook: dict[str, Any] | None = None) -> set[str]:
    """Which section types the gate skips.

    A playbook that tries to exempt a section in NEVER_EXEMPT is refused
    rather than obeyed: the list exists so that turning the gate off on the
    argument requires editing this file, in a commit, with a reason.
    """
    if playbook is None:
        playbook = _playbook()
    asked = set((playbook.get("fact_gate") or {}).get("exempt_sections")
                or DEFAULT_EXEMPT)
    forbidden = asked & set(NEVER_EXEMPT)
    if forbidden:
        raise SystemExit(
            f"the playbook exempts {sorted(forbidden)} from the fact gate, "
            f"and those sections carry the film's argument. Exempting them "
            f"is a change to lib/verify_fact_coverage.py, not to a list.")
    return asked


def _playbook() -> dict[str, Any]:
    import yaml

    path = Path(__file__).resolve().parents[1] / "styles" / "wak3up-documentary.yaml"
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


#: Quotation marks, straight and typographic.
QUOTES = re.compile(r"[\"“”‘’']{1}[^\"“”]{8,}"
                    r"[\"“”‘’']")

#: Capitalised words that are not proper nouns in this channel's register:
#: the channel's own name, and the words a narrator opens a sentence with.
#: Deliberately SHORT. Every word here is a word the gate stops asking about,
#: so a long list is a quiet way to turn the gate off.
WHITELIST = {
    # the channel
    "wak3up", "wak3up society", "openmontage",
    # narrator framing: sentence openers that are capitalised by position
    "the", "a", "an", "and", "but", "so", "then", "now", "here", "there",
    "this", "that", "these", "those", "it", "its", "they", "their", "he",
    "she", "we", "you", "his", "her", "if", "when", "what", "which", "who",
    "why", "how", "no", "not", "none", "nobody", "nothing", "almost",
    "nearly", "more", "most", "less", "fewer", "about", "over", "under",
    "between", "before", "after", "every", "each", "both", "neither",
    "either", "whatever", "whichever", "some", "any", "all",
}


def sentences(text: str) -> list[str]:
    """Narration sentences, with the production markers taken out."""
    clean = MARKERS.sub(" ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])", clean)
    return [p.strip() for p in parts if p.strip()]


def paragraphs(text: str) -> list[str]:
    """Paragraphs of a section, as the script writes them."""
    return [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]


# ───────────────────────── proper nouns ──────────────────────────────────
def _propn_spacy(sentence: str) -> list[str]:
    import spacy

    global _NLP
    try:
        _NLP
    except NameError:
        _NLP = spacy.load("en_core_web_sm")
    return [t.text for t in _NLP(sentence) if t.pos_ == "PROPN"]


def _propn_capitalised(sentence: str) -> list[str]:
    """A deliberately OVER-flagging substitute for spaCy.

    It calls any capitalised word that is not whitelisted a proper noun,
    including a sentence-initial one. That is wrong about words like "Almost"
    and right about "Noah", and the error is in the safe direction: a false
    positive asks for a citation that was not strictly required, and a false
    negative lets an unsourced claim through.

    It is NOT the specified detector and the report says which one ran. The
    number it produces is an UPPER bound on the failures spaCy would find.
    """
    found = []
    for word in re.findall(r"\b[A-Z][a-zA-ZÀ-ɏ'’-]+", sentence):
        if word.lower() in WHITELIST:
            continue
        found.append(word)
    return found


BACKENDS = {"spacy": _propn_spacy, "capitalisation": _propn_capitalised}


def triggers(sentence: str, backend: str = "spacy") -> dict[str, list[str]]:
    """Why this sentence needs a claim, if it does."""
    words = re.findall(r"[a-zA-ZÀ-ɏ'’-]+", sentence.lower())
    out: dict[str, list[str]] = {}
    dates = DATE.findall(sentence)
    if dates:
        out["date"] = sorted(set(dates))
    numbers = [w for w in words if w in WORD_NUMBERS]
    if DIGITS.search(sentence):
        numbers = ["<digits>"] + numbers
    if numbers:
        out["number"] = sorted(set(numbers))
    quoted = QUOTES.findall(sentence)
    if quoted:
        out["quotation"] = ["<quoted>"]
    propn = BACKENDS[backend](sentence)
    if propn:
        out["proper_noun"] = sorted(set(propn))
    return out


# ───────────────────────── the ledger ────────────────────────────────────
#: A claim id in free prose. The PREFIX is captured, not assumed: the ledger
#: uses `c` for the research stage's own claims and `r` for entries added by a
#: provenance repair, and a pattern that only knew about `c` made every `r`
#: id invisible — a section citing r01-r26 read as citing nothing at all.
CLAIM_ID = re.compile(r"\b([cr])(\d{1,3})\b", re.I)


def ledger(brief: dict[str, Any]) -> dict[str, dict]:
    """Claim id -> claim. Positional when the ledger carries no ids.

    `data_points` has no `id` field on either delivered film, so an id is
    read positionally: the first data point is c01. That is a GUESS about
    what the script meant, stated here rather than hidden — and it is the
    most generous reading available, so a citation that does not resolve
    under it does not resolve at all.
    """
    out: dict[str, dict] = {}
    for i, point in enumerate(brief.get("data_points") or [], 1):
        key = str(point.get("id") or f"c{i:02d}").lower()
        out[key] = point
    return out


def cited_in(blob: Any) -> list[str]:
    """Claim ids in a `claims` list or in a free-text `source_ref`."""
    if isinstance(blob, list):
        return [str(c).lower() for c in blob]
    if isinstance(blob, str):
        return [f"{p.lower()}{int(n):02d}" for p, n in CLAIM_ID.findall(blob)]
    return []


def claims_for(section: dict, paragraph_index: int) -> tuple[list[str], str]:
    """(claim ids, how they were attributed) for one paragraph."""
    paras = section.get("paragraphs")
    if isinstance(paras, list) and paragraph_index < len(paras):
        entry = paras[paragraph_index]
        if isinstance(entry, dict) and entry.get("claims"):
            return cited_in(entry["claims"]), "paragraph"
    if section.get("claims"):
        return cited_in(section["claims"]), "section"
    if section.get("source_ref"):
        return cited_in(section["source_ref"]), "section"
    return [], "none"


def check(script: dict, brief: dict, backend: str = "spacy",
          playbook: dict[str, Any] | None = None
          ) -> tuple[list[str], dict[str, Any]]:
    """Problems and a per-sentence report."""
    book = ledger(brief)
    skip = exempt_sections(playbook)
    rows: list[dict[str, Any]] = []
    for section in script.get("sections", []):
        if section.get("id") in skip:
            continue
        for p_index, para in enumerate(paragraphs(section.get("text") or "")):
            ids, how = claims_for(section, p_index)
            resolved = [i for i in ids if i in book]
            sourced = [i for i in resolved if book[i].get("source_url")]
            for sentence in sentences(para):
                why = triggers(sentence, backend)
                rows.append({
                    "section": section.get("id"),
                    "paragraph": p_index,
                    "sentence": sentence,
                    "needs_claim": bool(why),
                    "triggers": why,
                    "attribution": how,
                    "cited": ids,
                    "resolved": resolved,
                    "sourced": sourced,
                    "covered": bool(why) is False or bool(sourced),
                })

    uncovered = [r for r in rows if not r["covered"]]
    problems = [
        f"{r['section']}/p{r['paragraph']}: {r['sentence'][:90]!r} — "
        + ", ".join(f"{k} {v}" for k, v in r["triggers"].items())
        + (f"; cites {r['cited']} and none resolve to a sourced claim"
           if r["cited"] else "; cites nothing")
        for r in uncovered
    ]

    needing = [r for r in rows if r["needs_claim"]]
    measured = {
        "backend": backend,
        "exempt_sections": sorted(skip),
        "sentences": len(rows),
        "sentences_needing_a_claim": len(needing),
        "sentences_uncovered": len(uncovered),
        "pct_uncovered": (round(100 * len(uncovered) / len(needing), 1)
                          if needing else 0.0),
        "ledger_size": len(book),
        "ids_cited": sorted({i for r in rows for i in r["cited"]}),
        "ids_that_do_not_resolve": sorted(
            {i for r in rows for i in r["cited"]} - set(book)),
        "attribution_levels": sorted({r["attribution"] for r in rows}),
        "rows": rows,
    }
    return problems, measured


def report(measured: dict[str, Any], problems: list[str]) -> str:
    m = measured
    lines = [
        "# Fact coverage", "",
        f"`{m['backend']}` proper-noun backend · {m['sentences']} sentences · "
        f"{m['sentences_needing_a_claim']} carry a date, a number, a proper "
        f"noun or a quotation", "",
        f"**{m['sentences_uncovered']} uncovered** "
        f"({m['pct_uncovered']}% of those that need a claim).", "",
        f"Ledger: {m['ledger_size']} claims. Cited: {len(m['ids_cited'])}. "
        f"**Do not resolve: {len(m['ids_that_do_not_resolve'])}** — "
        + (", ".join(m["ids_that_do_not_resolve"][:20]) or "none") + "", "",
        f"Attribution levels present: {', '.join(m['attribution_levels'])}.",
        "",
    ]
    if problems:
        lines += ["## Uncovered sentences", ""]
        lines += [f"- {p}" for p in problems[:200]]
        if len(problems) > 200:
            lines.append(f"- … and {len(problems) - 200} more")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--script")
    ap.add_argument("--brief")
    ap.add_argument("--backend", choices=sorted(BACKENDS), default="spacy")
    ap.add_argument("--report")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    if args.project:
        art = root / "projects" / args.project / "artifacts"
        script_path = Path(args.script or art / "script.json")
        brief_path = Path(args.brief or art / "research_brief.json")
    else:
        if not (args.script and args.brief):
            print("pass --project, or both --script and --brief", file=sys.stderr)
            return 2
        script_path, brief_path = Path(args.script), Path(args.brief)

    if args.backend == "spacy":
        try:
            import spacy  # noqa: F401
            spacy.load("en_core_web_sm")
        except Exception as exc:
            print(
                f"the spaCy backend is not available ({type(exc).__name__}).\n"
                f"  .venv/bin/pip3 install spacy\n"
                f"  .venv/bin/python -m spacy download en_core_web_sm\n"
                f"A blocking gate does not quietly swap its detector; pass\n"
                f"--backend capitalisation to run the over-flagging substitute,\n"
                f"whose count is an UPPER bound on what spaCy would find.",
                file=sys.stderr)
            return 2

    script = json.loads(script_path.read_text())
    brief = json.loads(brief_path.read_text())
    problems, measured = check(script, brief, args.backend)

    print(f"{measured['sentences']} sentences, "
          f"{measured['sentences_needing_a_claim']} need a claim, "
          f"{measured['sentences_uncovered']} uncovered "
          f"({measured['pct_uncovered']}%)")
    print(f"ledger {measured['ledger_size']} claims; "
          f"{len(measured['ids_that_do_not_resolve'])} cited ids do not resolve")
    for p in problems[:15]:
        print("  -", p)
    if len(problems) > 15:
        print(f"  … and {len(problems) - 15} more")
    if args.report:
        Path(args.report).write_text(report(measured, problems))
        print(f"-> {args.report}")
    print("FACT COVERAGE:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

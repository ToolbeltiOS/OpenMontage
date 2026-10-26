#!/usr/bin/env python3
"""Does this act cite only claims that exist? Run it AS THE ACT IS WRITTEN.

WHY IT IS A SEPARATE SCRIPT AND NOT JUST THE GATE
--------------------------------------------------
The gate runs once, after the whole script is written, and tells the writer
that something somewhere is wrong. By then the act has been composed around
a claim that was never in the brief, and the cheapest repair is to rewrite
it.

easter-island was written this way. Its script cites fifty-four claim ids
against a fifteen-claim ledger: c16 through c58 do not exist and never did.
Forty-two invented references, discovered weeks later by a gate, in a film
that was already public. Act 4 cited fourteen of them and not one resolved.

So this is the same two checks, scoped to ONE act, cheap enough to run after
each one:

  1. every id the act cites exists in the research brief and has a source URL;
  2. every factual sentence has a claim attributable to IT — the paragraph's
     own `claims` list, or a ledger entry naming the sentence in `supports`.

If a sentence needs a source the brief does not have, the answer is to
research it and add the data point, or to cut the sentence. It is never to
write down an id and move on.

    python3 scripts/check_claims.py --project noah --section act1
    python3 scripts/check_claims.py --project noah            # every section
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from verify_fact_coverage import (  # noqa: E402
    _norm_sentence, cited_anywhere, claims_for, exempt_sections, ledger,
    paragraphs, sentence_index, sentences, triggers)


def check_section(section: dict, book: dict, by_sentence: dict,
                  backend: str = "spacy") -> tuple[list[str], dict]:
    problems: list[str] = []

    unknown = [c for c in cited_anywhere(section) if c not in book]
    for cited in unknown:
        problems.append(
            f"cites {cited!r}, which is not in the research brief. Add the "
            f"data point (with a source_url) or stop citing it — do not "
            f"renumber it to something that happens to exist.")

    no_url = [c for c in cited_anywhere(section)
              if c in book and not book[c].get("source_url")]
    for cited in no_url:
        problems.append(f"cites {cited!r}, which has no source_url.")

    needing = uncovered = 0
    for index, para in enumerate(paragraphs(section.get("text") or "")):
        ids, _ = claims_for(section, index)
        for sentence in sentences(para):
            if not triggers(sentence, backend):
                continue
            needing += 1
            own = by_sentence.get(_norm_sentence(sentence), [])
            usable = [c for c in (own or ids)
                      if c in book and book[c].get("source_url")]
            if not usable:
                uncovered += 1
                problems.append(
                    f"p{index}: {sentence[:100]!r} carries a fact and no "
                    f"claim is attributable to it.")

    return problems, {"id": section.get("id"), "cites": len(cited_anywhere(section)),
                      "unknown": len(unknown), "without_url": len(no_url),
                      "sentences_needing_a_claim": needing,
                      "uncovered": uncovered}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--section", action="append", default=[],
                    help="one act; repeatable. Default: every section")
    ap.add_argument("--backend", default="spacy")
    args = ap.parse_args()

    art = ROOT / "projects" / args.project / "artifacts"
    script = json.loads((art / "script.json").read_text())
    brief = json.loads((art / "research_brief.json").read_text())
    book = ledger(brief)
    by_sentence = sentence_index(book)
    skip = exempt_sections()

    wanted = set(args.section)
    found = False
    failed = False
    for section in script.get("sections", []):
        sid = section.get("id")
        if wanted and sid not in wanted:
            continue
        found = True
        if sid in skip:
            print(f"{sid}: exempt")
            continue
        problems, m = check_section(section, book, by_sentence, args.backend)
        print(f"{sid}: cites {m['cites']} claim(s), {m['unknown']} unknown, "
              f"{m['sentences_needing_a_claim']} sentences need a claim, "
              f"{m['uncovered']} uncovered")
        for p in problems[:20]:
            print("  -", p)
        if len(problems) > 20:
            print(f"  … and {len(problems) - 20} more")
        failed = failed or bool(problems)

    if wanted and not found:
        print(f"no section matched {sorted(wanted)}", file=sys.stderr)
        return 2
    print("CLAIMS:", "PASS" if not failed else "FAIL")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

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

`[framing]` is honoured here exactly as the gate honours it, and for the same
reason the marker exists: a check that disagreed with the gate about which
sentences are exempt would send the writer to repair a line the gate was
always going to pass, which is the opposite of the job. A marker is still not
a licence — a framing sentence carrying a proper noun, a number of ten or
more, or a date is reported with the word that blocked it.

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
    _norm_sentence, cited_anywhere, claims_for, exempt_sections,
    framing_disqualifiers, ledger, paragraphs, sentence_index,
    sentences_marked, triggers)

import script_cadence as SC  # noqa: E402


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

    needing = uncovered = framing = framing_skipped = 0
    for index, para in enumerate(paragraphs(section.get("text") or "")):
        ids, _ = claims_for(section, index)
        # `sentences_marked`, not `sentences`: this script is advertised as
        # the gate's two checks scoped to one act, and the gate honours
        # `[framing]`. Reading the paragraph with `sentences()` strips the
        # marker along with every other production marker, so a structural
        # sentence — "Four cases, and only one of them is closed" — came back
        # as an uncovered fact. The only ways to satisfy that are to invent a
        # citation for a sentence that makes no claim, or to delete the
        # sentence: both are worse than the thing being checked for, and the
        # gate would have passed either way. Found by running this against a
        # script the gate passes.
        for sentence, is_framing in sentences_marked(para):
            # `[framing]` marks a sentence that counts or signposts the FILM's
            # own structure. It is skipped ONLY if it carries no proper noun,
            # no number of ten or more and no date — and a marker that does
            # not exempt the sentence says which word blocked it. Read here
            # for the same reason the gate reads it: a check that disagreed
            # with the gate on this would send the writer to fix a sentence
            # the gate was always going to pass.
            blocked = (framing_disqualifiers(sentence, backend)
                       if is_framing else {})
            if is_framing:
                framing += 1
                if not blocked:
                    framing_skipped += 1
                else:
                    problems.append(
                        f"p{index}: {sentence[:80]!r} is marked [framing] but "
                        + ", ".join(f"{k} {v}" for k, v in blocked.items())
                        + " — the marker says what a sentence is FOR, not "
                          "that it makes no claim.")
            if not triggers(sentence, backend) or (is_framing and not blocked):
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
                      "uncovered": uncovered, "framing": framing,
                      "framing_skipped": framing_skipped}


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
    all_violations: list = []
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
              f"{m['uncovered']} uncovered, {m['framing']} framing "
              f"({m['framing_skipped']} skipped)")
        for p in problems[:20]:
            print("  -", p)
        if len(problems) > 20:
            print(f"  … and {len(problems) - 20} more")
        failed = failed or bool(problems)

        # ── WRITE FOR THE VOICE ──────────────────────────────────────────
        # Reported separately from the sourcing, because the two fail for
        # different reasons and are fixed by different edits. The fact checks
        # above are untouched by this: a sourcing check that also had
        # opinions about sentence length would be two gates in a coat.
        violations, vm = SC.check(section.get("text") or "", sid)
        parts = SC.classify(violations)
        print(f"{sid}: {vm['sentences']} sentences, mean {vm['mean']} words, "
              f"{vm['short_fraction']:.0%} under {SC.SHORT_WORDS}, longest "
              f"{vm['longest']}, {vm['questions']} question(s) — "
              f"{len(parts['blocking'])} blocking, "
              f"{len(parts['advisory'])} advisory")
        for v in parts["blocking"][:40]:
            mark = "!" if v.rule in SC.ALWAYS_BLOCKING else "·"
            print(f"  {mark} [{v.rule}] {v.detail}")
            print(f"      {v.sentence[:160]!r}")
        if len(parts["blocking"]) > 40:
            print(f"  … and {len(parts['blocking']) - 40} more blocking")
        for v in parts["advisory"][:10]:
            print(f"  ~ [{v.rule}] {v.detail} (advisory)")
            print(f"      {v.sentence[:160]!r}")
        if len(parts["advisory"]) > 10:
            print(f"  … and {len(parts['advisory']) - 10} more advisory")
        all_violations.extend(violations)

    if wanted and not found:
        print(f"no section matched {sorted(wanted)}", file=sys.stderr)
        return 2
    print("CLAIMS:", "PASS" if not failed else "FAIL")

    # THE BUDGET IS A WHOLE-FILM NUMBER, so it is only judged on a whole-film
    # run. Six across a film is not six per act: enforcing it per act would
    # pass a film carrying five in each of six acts, which is thirty. A
    # single-act run still fails on the zero-tolerance faults and says what
    # is still owed.
    whole_film = not wanted
    parts = SC.classify(all_violations)
    ok, reasons = SC.verdict(all_violations, whole_film=whole_film)
    scope = "film" if whole_film else f"{len(wanted)} section(s)"
    print(f"VOICE: {len(parts['blocking'])} blocking "
          f"({len(parts['hard'])} zero-tolerance), "
          f"{len(parts['advisory'])} advisory, over {scope}; "
          f"budget {SC.VOICE_BUDGET} per film")
    if reasons:
        print("  over budget or zero-tolerance:")
        for r in reasons[:25]:
            print(f"    - {r}")
        if len(reasons) > 25:
            print(f"    … and {len(reasons) - 25} more")
    if not whole_film:
        print(f"  (the {SC.VOICE_BUDGET}-violation budget is judged on the "
              f"whole film; run without --section for the verdict)")
    print("VOICE:", "PASS" if ok else "FAIL")

    # One gate, two verdicts, one exit code.
    return 0 if not (failed or not ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())

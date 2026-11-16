#!/usr/bin/env python3
"""The channel's angle, enforced at research, proposal and script.

THE ANGLE
---------
What is disputed, hidden or unexplained about a subject — not what happened
in it. The standard account appears in a film as the thing being questioned,
and never as the thing being retold.

WHY IT IS THREE GATES AND NOT A NOTE IN A PROMPT
------------------------------------------------
Because a film can lose the angle at any of three places and each loss looks
different. Research can fail to find anything disputed and hand on a tidy
summary. A proposal can be handed a disputed brief and build its acts out of
the textbook anyway. A script can be built on a disputed proposal and still
assert every theory in the narrator's own voice, which is the worst of the
three: it is the only one that reaches a viewer.

Measured across the four films that existed when this was written, by
counting `contested: true` in each brief's own ledger:

    they-said-it-couldnt-be-built   43 claims,  0 contested
    easter-island                   83 claims,  0 contested
    king-tut                        53 claims, 16 contested
    atomic-bombings                 33 claims, 13 contested

The two with nothing contested are films #1 and #2. So the angle has been
arriving on its own and this formalises it rather than inventing it — and
the two early films are what it is for: a channel that retells the outline
of a subject has no reason to exist next to the encyclopaedia it is
retelling.

ONE LEDGER, NOT TWO
-------------------
A disputed item names a `claim_id` from `data_points` rather than carrying
its own text and source. `lib/verify_fact_coverage` builds its ledger from
`data_points`, and a second id namespace would be a citation that resolves
in one gate and not in the other. So a disputed item is a POINTER into the
ledger, and the fact gate's existing rule — a cited id must resolve and have
a source — is what keeps a theory traceable to whoever said it.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

try:
    import verify_fact_coverage as F
except ImportError:                                     # imported as a package
    from lib import verify_fact_coverage as F           # type: ignore[no-redef]

#: The four shapes a disputed item may take. An enum rather than free text
#: because "disputed" on its own collects anything a researcher found
#: surprising, and the four below are the ones that make a film.
DISPUTED_KINDS = {
    "official_account_contradicted":
        "an official account later contradicted by documents",
    "rejected_by_mainstream":
        "a claim by a named investigator, witness or researcher that the "
        "mainstream rejects",
    "left_out_of_popular_tellings":
        "a fact in the primary record that popular tellings leave out",
    "unexplained":
        "an unexplained detail with no settled answer",
}

#: Below this the topic is not one this channel can tell. The picker moves on
#: rather than the research stage trying harder: a subject with four disputed
#: threads is a subject whose film would spend an act on padding.
MIN_DISPUTED = 5

#: How much of the film has to rest on something contested. Under this the
#: script is a retelling with a disputed footnote.
MIN_CONTESTED_SHARE = 0.30


def disputed_items(brief: dict[str, Any]) -> list[dict[str, Any]]:
    """The disputed section, each entry joined to the claim it names.

    Used by the gates below and by the script gate's Telegram message, so
    the owner reads the same five things the checks read.
    """
    book = F.ledger(brief)
    out = []
    for entry in brief.get("disputed") or []:
        if not isinstance(entry, dict):
            continue
        claim_id = str(entry.get("claim_id") or "").lower()
        out.append({**entry, "claim_id": claim_id,
                    "claim": book.get(claim_id)})
    return out


def contested_ids(brief: dict[str, Any]) -> set[str]:
    """Every claim in the ledger that says it is contested."""
    return {cid for cid, claim in F.ledger(brief).items()
            if isinstance(claim, dict) and claim.get("contested")}


def check_brief(brief: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    """Research: is there enough disputed here to make a film?"""
    problems: list[str] = []
    book = F.ledger(brief)
    items = disputed_items(brief)
    contested = contested_ids(brief)

    seen: set[str] = set()
    for n, entry in enumerate(items, 1):
        claim_id, kind = entry["claim_id"], entry.get("kind")
        where = f"disputed[{n}] ({claim_id or 'no claim_id'})"
        if not claim_id:
            problems.append(f"{where}: names no claim_id")
            continue
        if claim_id in seen:
            problems.append(
                f"{where}: already named by an earlier entry — five entries "
                f"pointing at three claims is three disputed threads")
            continue
        seen.add(claim_id)
        if entry["claim"] is None:
            problems.append(
                f"{where}: no such claim in data_points, so it resolves to "
                f"nothing and the fact gate would refuse a script citing it")
            continue
        if kind not in DISPUTED_KINDS:
            problems.append(
                f"{where}: kind {kind!r} is not one of "
                f"{', '.join(sorted(DISPUTED_KINDS))}")
        if not entry["claim"].get("contested"):
            problems.append(
                f"{where}: the claim it names is not marked contested, so "
                f"the script lint cannot count a sentence resting on it")
        if not entry["claim"].get("source_url"):
            problems.append(
                f"{where}: the claim it names has no source_url — a theory "
                f"has to be traceable to whoever said it")

    usable = len(seen & contested)
    if usable < MIN_DISPUTED:
        # WHOSE FAULT IS IT? The two answers are opposite and a shell cannot
        # tell them apart from a message. A brief holding 13 contested
        # claims and no `disputed` section is a STAGE that did not finish
        # its job; a brief holding two contested claims in total is a TOPIC
        # with nothing to say, and trying the stage again cannot help.
        if len(contested) >= MIN_DISPUTED:
            problems.append(
                f"only {usable} usable disputed item(s) against the "
                f"{MIN_DISPUTED} needed — but this brief already holds "
                f"{len(contested)} contested claim(s). The angle is here and "
                f"the section does not name it: declare at least "
                f"{MIN_DISPUTED} of them in `disputed`, with a kind each.")
        else:
            problems.append(
                f"only {len(contested)} contested claim(s) in the whole "
                f"brief, under the {MIN_DISPUTED} this channel needs. This "
                f"TOPIC has no angle to find: the picker should move to the "
                f"next one rather than the research stage trying harder.")

    return problems, {
        "claims": len(book),
        "contested_claims": len(contested),
        "disputed_entries": len(items),
        "usable_disputed": usable,
        "minimum": MIN_DISPUTED,
        #: Which of the two failures above applies, so a caller does not
        #: have to parse prose to find out.
        "topic_has_no_angle": len(contested) < MIN_DISPUTED,
        "kinds_used": sorted({e.get("kind") for e in items
                              if e.get("kind") in DISPUTED_KINDS}),
    }


def check_proposal(proposal: dict[str, Any], brief: dict[str, Any]
                   ) -> tuple[list[str], dict[str, Any]]:
    """Proposal: is the angle stated, and are the acts built on it?"""
    problems: list[str] = []
    chosen_id = ((proposal.get("selected_concept") or {})
                 .get("concept_id"))
    options = proposal.get("concept_options") or []
    concept = next((o for o in options
                    if isinstance(o, dict) and o.get("id") == chosen_id),
                   None)
    if concept is None:
        return ([f"selected concept {chosen_id!r} is not among the "
                 f"{len(options)} options, so there is nothing to check"],
                {"selected": chosen_id})

    disputed = {e["claim_id"] for e in disputed_items(brief) if e["claim_id"]}
    contested = contested_ids(brief)
    grounded = {str(c).lower() for c in (concept.get("grounded_in") or [])}
    named = {str(c).lower() for c in (concept.get("disputed_grounding") or [])}

    angle = (concept.get("angle") or "").strip()
    if not angle:
        problems.append(
            "the selected concept states no `angle` — the one line saying "
            "what is disputed, hidden or unexplained about this subject")

    on_the_angle = (grounded | named) & (disputed | contested)
    if not on_the_angle:
        problems.append(
            f"the selected concept rests on {len(grounded)} claim(s) and not "
            f"one of them is disputed or contested. These acts retell the "
            f"standard account, which is the one thing this channel does not "
            f"do.")
    if named - (disputed | contested):
        problems.append(
            f"disputed_grounding names {sorted(named - (disputed | contested))}, "
            f"which the brief does not hold as disputed or contested")

    return problems, {
        "selected": chosen_id,
        "angle": angle,
        "grounded_in": len(grounded),
        "on_the_angle": sorted(on_the_angle),
        "disputed_available": len(disputed),
    }


def check_script(script: dict[str, Any], brief: dict[str, Any],
                 backend: str = "spacy") -> tuple[list[str], dict[str, Any]]:
    """Script: how much of the film rests on something contested?

    Counted per sentence, through `verify_fact_coverage`'s own machinery, so
    "a sentence carries a contested claim" means exactly what "a sentence is
    covered" means to the fact gate — the paragraph's claims list, or a
    ledger claim naming the sentence in `supports`.

    Two denominators are reported because they answer different questions:
    `share_of_all` is the share of every narration sentence, and
    `share_of_factual` the share of the sentences the fact gate governs. A
    sentence with no date, number, proper noun or quotation cannot carry a
    claim at all, so the second is the one a writer can act on.
    """
    book = F.ledger(brief)
    contested = contested_ids(brief)
    by_sentence = F.sentence_index(book)

    total = factual = resting = factual_resting = 0
    per_section: list[dict[str, Any]] = []

    for section in script.get("sections") or []:
        text = section.get("text") or ""
        s_total = s_factual = s_resting = 0
        for index, para in enumerate(F.paragraphs(text)):
            covering, _how = F.claims_for(section, index)
            ids = {str(c).lower() for c in covering}
            for sentence, _framing in F.sentences_marked(para):
                s_total += 1
                hit = F.triggers(sentence, backend)
                is_factual = any(hit.values()) if isinstance(hit, dict) else bool(hit)
                here = set(ids)
                here |= set(by_sentence.get(F._norm_sentence(sentence), []))
                on_contested = bool(here & contested)
                if is_factual:
                    s_factual += 1
                    if on_contested:
                        factual_resting += 1
                if on_contested:
                    s_resting += 1
        total += s_total
        factual += s_factual
        resting += s_resting
        per_section.append({"id": section.get("id"), "sentences": s_total,
                            "on_contested": s_resting})

    share_all = (resting / total) if total else 0.0
    share_factual = (factual_resting / factual) if factual else 0.0

    problems: list[str] = []
    if share_all < MIN_CONTESTED_SHARE:
        problems.append(
            f"{resting} of {total} sentences ({share_all:.1%}) rest on a "
            f"contested claim, under the {MIN_CONTESTED_SHARE:.0%} this "
            f"channel needs. A film this far from its own angle is a "
            f"retelling with a disputed footnote.")

    return problems, {
        "sentences": total,
        "factual_sentences": factual,
        "on_contested": resting,
        "factual_on_contested": factual_resting,
        "share_of_all": round(share_all, 4),
        "share_of_factual": round(share_factual, 4),
        "minimum_share": MIN_CONTESTED_SHARE,
        "contested_claims": len(contested),
        "per_section": per_section,
    }

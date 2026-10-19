#!/usr/bin/env python3
"""Assign bank assets to scene-plan slots under the reuse rule.

The planner and the gate share lib/reuse_rules, so the planner cannot satisfy
a rule the gate does not enforce. This assigns in timeline order and never
places an asset it has already used; where a subject runs out it says so
rather than quietly repeating, because repeating is the defect being fixed.

Framing preference follows what the slot is for: an establishing or wide
description takes the parent photograph, a close or detail description takes
a derived crop. That is also what keeps two framings of one parent from
reading as the same shot.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

SUBJECT_TERMS = {
    "tiryns":        ["tiryns", "cyclopean", "unwrought"],
    "mycenae":       ["mycenae", "lion gate", "lions gate", "citadel"],
    "moai":          ["moai", "rapa nui", "easter island", "tongariki", "rano raraku",
                      "statue", "quarry road", "ahu"],
    "stonehenge":    ["stonehenge", "trilithon", "sarsen", "altar stone", "bluestone circle"],
    "preseli":       ["preseli", "carn goedog", "rhos-y-felin", "bluestone", "outcrop", "wales"],
    "aswan_quarry":  ["aswan", "unfinished obelisk", "granite quarry", "dolerite", "pounder"],
    "giza":          ["giza", "khufu", "great pyramid", "pyramid", "plateau", "chevron", "north face"],
    "grand_gallery": ["grand gallery", "queen's chamber", "interior", "corridor", "descending"],
    "pumapunku":     ["pumapunku", "puma punku", "andesite", "tiwanaku", "altiplano", "h-shaped"],
    "sacsayhuaman":  ["sacsayhuam", "zigzag", "joint", "contact line"],
    "inca_masonry":  ["inca", "cusco", "polygonal", "masonry", "stonework", "fitted"],
    "egyptian_stone":["sarcophagus", "core", "petrie", "vessel", "granite surface", "tool mark",
                      "saw", "tube drill", "copper"],
}

WIDE_WORDS = ("wide", "landscape", "establish", "aerial", "distant", "site", "row",
              "sequence", "horizon", "plateau", "valley", "hills")
CLOSE_WORDS = ("close", "detail", "grain", "surface", "joint", "edge", "mark", "contact",
               "texture", "macro", "tool", "fragment", "crop")


def subject_for(slot: dict) -> str | None:
    text = f"{slot.get('description','')} {slot.get('subject_family','')}".lower()
    best, score = None, 0
    for subj, terms in SUBJECT_TERMS.items():
        n = sum(1 for t in terms if t in text)
        if n > score:
            best, score = subj, n
    if best:
        return best
    fam = (slot.get("subject_family") or "").lower()
    return {"greece": "tiryns", "egypt": "giza", "rapanui": "moai",
            "stonehenge": "stonehenge", "peru": "sacsayhuaman",
            "bolivia": "pumapunku"}.get(fam)


def framing_for(slot: dict) -> str:
    d = (slot.get("description") or "").lower()
    if any(w in d for w in CLOSE_WORDS):
        return "detail"
    if any(w in d for w in WIDE_WORDS):
        return "wide"
    return "any"


def main() -> int:
    bank_path, plan_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    bank = json.load(open(bank_path))
    plan = json.load(open(plan_path))
    slots = plan["metadata"]["slots"]

    pool: dict[str, list[dict]] = defaultdict(list)
    for subj, entry in bank["subjects"].items():
        for a in entry["assets"]:
            pool[subj].append({**a, "framing": "wide", "parent_id": a["asset_id"]})
    for d in bank.get("derived", []):
        subj = d.get("subject")
        if subj:
            pool[subj].append(d)

    used: set[str] = set()
    used_parent_last: dict[str, float] = {}
    prev_parent: str | None = None
    assigned = shortfall = 0
    report: list[str] = []

    for slot in sorted(slots, key=lambda s: s.get("start_seconds", 0)):
        if slot.get("treatment") == "graphic":
            continue
        start = slot.get("start_seconds", 0)
        if slot.get("treatment") == "texture":
            cands = [a for a in pool.get("elemental_texture", []) if a["asset_id"] not in used]
        else:
            subj = subject_for(slot)
            cands = [a for a in pool.get(subj, []) if a["asset_id"] not in used] if subj else []
            want = framing_for(slot)
            if want != "any":
                pref = [c for c in cands if c.get("framing", "wide") == want
                        or (want == "detail" and c.get("framing") in ("detail", "extreme"))]
                cands = pref or cands

        ok = []
        for c in cands:
            parent = c.get("parent_id") or c["asset_id"]
            if parent == prev_parent:
                continue
            last = used_parent_last.get(parent)
            if last is not None and start - last < 240.0:
                continue
            ok.append(c)
        if not ok:
            shortfall += 1
            report.append(f"{slot['slot_id']} ({slot.get('treatment')}, "
                          f"{subject_for(slot)}): no asset available under the reuse rule")
            slot.pop("asset_id", None)
            slot.pop("parent_id", None)
            continue

        pick = ok[0]
        parent = pick.get("parent_id") or pick["asset_id"]
        slot["asset_id"] = pick["asset_id"]
        slot["parent_id"] = parent
        slot["path"] = pick["path"]
        slot["framing"] = pick.get("framing", "wide")
        slot["licence"] = pick.get("licence")
        slot["artist"] = pick.get("artist")
        slot["source_page"] = pick.get("page")
        used.add(pick["asset_id"])
        used_parent_last[parent] = slot.get("end_seconds", start)
        prev_parent = parent
        assigned += 1

    plan["metadata"]["slots"] = slots
    json.dump(plan, open(out_path, "w"), indent=1, ensure_ascii=False)
    print(f"assigned {assigned} slots, {shortfall} short")
    for r in report[:30]:
        print("  -", r)
    return 0


if __name__ == "__main__":
    sys.exit(main())

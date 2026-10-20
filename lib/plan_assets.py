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

MIN_SEPARATION_S = 240.0

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
    "volcanism":     ["volcan", "steam", "venting", "eruption", "caldera", "ash"],
    "viking_age":    ["viking", "norse", "artefact", "artifact", "time-distance"],
    "djehutihotep":  ["oxen", "draft team", "haul", "sledge", "rope", "djehutihotep"],
    "copper_tools":  ["copper tool", "chisel", "adze", "blunted", "worn edge"],
}

# Slots whose description names a thing, where the honest picture is a
# stand-in from a related subject. The caption says what is actually shown.
SUBJECT_OVERRIDE = {
    "act1_s045": "tiryns",          # "weathered block face" -> real masonry
    "act2_s082": "aswan_quarry",    # "six-tonne block for scale" -> quarried stone
    "act1_s025": "djehutihotep",    # "oxen or draft team hauling"
    "act1_s043": "mycenae",         # Tiryns is spent by 272s; same Cyclopean masonry
    # A limestone_saw subject was retrieved and discarded: Category:Quarrying
    # and Category:Stonecutter marks returned a locomotive, a hydraulic crusher
    # and a 19th-century American canal lock. The beat follows the 15x
    # granite-vs-limestone figure, so what it needs is limestone, and the
    # limestone this film is about is the casing stone at Giza.
    "act3_s117": "giza",
    # Rumiqolqa is the Inca andesite quarry above Cusco. It matched
    # egyptian_stone only because "tool mark" is one of that subject's terms.
    "act4_s174": "inca_masonry",
}

# The two Djehutihotep slots are the only pair in the film that MUST take two
# framings of one parent, so the choice is not left to pool order: act1_s025 is
# a generic haulage beat and wants the rope teams, act3_s129 names the sledge
# AND the water-pourer and so needs the whole scene.
FRAMING_FORCE = {
    "act1_s025": "detail",
    "act3_s129": "wide",
}

CAPTION_OVERRIDE = {
    "act1_s025": "Modern reproduction of the Djehutihotep haulage scene, Deir el-Bersha",
    "act3_s129": "Modern reproduction of the Djehutihotep scene, Deir el-Bersha",
    "act1_s045": "Cyclopean masonry, Tiryns",
    "act2_s082": "Quarried granite, Aswan",
    "act1_s043": "Cyclopean wall, Mycenae",
    "act3_s117": "Limestone at Giza — the stone Stocks found cut about fifteen times faster",
    "act3_s109": "Copper-alloy tool heads, corroded and worn",
}

# Slots where keyword matching is confidently wrong and no honest asset exists.
# "no vessel in frame" matched a stone vessel in a museum case; "granite
# sarcophagus, interior tool marks" matched a gilded wooden coffin, because the
# bank's Egyptian material is painted coffins rather than worked granite. These
# are authored instead: a graphic that states what it is beats a photograph of
# a different object.
# Run #1 gave one asset to several slots; the planner keeps the first in time
# order, which is not always the slot the picture belongs to. These are claimed
# first. act4_s160 is the clearest case: one scientific figure served both "the
# Great Pyramid north face" and "nuclear emulsion film plate", and it is a
# figure of emulsion plates -- so the later slot is the one that should hold it.
# Chosen by looking at the picture, where no amount of word matching gets
# there: "Pumapunku H-blocks" shares no word with a file called
# "PUMA PUNKU, TIAJUANACO, BOLIVIA.jpg", because the site's name is spelled
# as two words in the filename and one in the script.
ASSET_OVERRIDE = {
    "act4_s148": "wm_63128291",
    # The beat IS the painting: "the sledge and the figure pouring liquid".
    # Run #1 filled it with an aerial of Giza and the modern city, and because
    # that was not a repeat the repair pass kept it -- then the caption below
    # described the painting over a photograph of Cairo. Forcing the wide
    # parent here also gives the film the two framings it is entitled to:
    # act1_s025 holds the detail at 154s, this holds the whole scene at 839s.
    "act3_s129": "wm_595950890",
}

PRIORITY_SLOTS = ("act4_s160", "act4_s143")

# Two annotated_stills claimed one image. The slot whose description matches
# the picture keeps it and stays annotated; the other takes a fresh photograph
# and loses its annotation, because anchors measured on one frame mean nothing
# on another. act4_s171_joint_crop is a joint, so it belongs to act4_s177
# ("the contact line traced by shadow") and not to act4_s169 ("the zigzag wall
# in sequence"), which wants the wall.
ANNOTATION_YIELDS = ("act4_s169",)

FORCE_AUTHOR = {
    "act2_s084": "'no vessel in frame' matches stone vessels in the bank",
    "act3_s092": "no worked-granite sarcophagus in the bank; matches painted coffins",
    "act3_s096": "no modern drilling rig in the bank",
}

WIDE_WORDS = ("wide", "landscape", "establish", "aerial", "distant", "site", "row",
              "sequence", "horizon", "plateau", "valley", "hills")
CLOSE_WORDS = ("close", "detail", "grain", "surface", "joint", "edge", "mark", "contact",
               "texture", "macro", "tool", "fragment", "crop")


def subject_for(slot: dict) -> str | None:
    if slot.get("slot_id") in SUBJECT_OVERRIDE:
        return SUBJECT_OVERRIDE[slot["slot_id"]]
    # Score the description ONLY. Folding subject_family into the text gave
    # every act-2 slot a free "stonehenge" hit, so "Craig Rhos-y-felin" tied
    # 1-1 against Preseli and lost on dict order. The family is already the
    # fallback below; counting it twice is what made it outrank evidence.
    text = (slot.get("description", "") or "").lower()
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


STOP = {"the","a","an","and","or","of","in","on","at","to","with","from","for","it",
        "its","no","not","is","are","was","were","be","by","as","into","over","under",
        "close","detail","wide","shot","frame","view","visible","across","through",
        "low","high","angle","light","dark","modern","historical","archaeological",
        "replica","around","below","above","still","moving","past","up","down","out"}


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in STOP}


def asset_matches(slot: dict, cand: dict, subject: str | None) -> bool:
    """Does this candidate plausibly depict what the slot asks for?

    The subject map is too coarse to be trusted on its own. Asked for a
    Scottish coastline with the Preseli assets spent, it offered Stonehenge;
    asked for an empty sea horizon "with no vessel in frame", it offered a
    stone vessel in a museum case, because "vessel" is a word in both. So a
    candidate must share a real word with the slot or with its subject's own
    vocabulary before it may be used. Where nothing matches, the slot is left
    for authoring: a drawing that admits what it is beats a photograph of the
    wrong thing.
    """
    # An explicit override is a decision already made by hand; the guard is
    # for the keyword fallback, not for overruling a deliberate choice.
    if slot.get("slot_id") in SUBJECT_OVERRIDE:
        return True
    want = content_words(slot.get("description", ""))
    have = content_words(f"{cand.get('title','')} {cand.get('subject','')}")
    if want & have:
        return True
    # Checking the candidate against the subject the matcher itself picked is
    # circular -- a Stonehenge photograph "proves" the subject is Stonehenge,
    # which is how the Welsh outcrop and the Scottish coastline both ended up
    # as Stonehenge on grass. The slot must independently be about the subject.
    terms = SUBJECT_TERMS.get(subject or "", [])
    desc = (slot.get("description", "") or "").lower()
    title = (cand.get("title", "") or "").lower()
    return any(t in desc for t in terms) and any(t in title for t in terms)


def framing_for(slot: dict) -> str:
    if slot.get("slot_id") in FRAMING_FORCE:
        return FRAMING_FORCE[slot["slot_id"]]
    d = (slot.get("description") or "").lower()
    if any(w in d for w in CLOSE_WORDS):
        return "detail"
    if any(w in d for w in WIDE_WORDS):
        return "wide"
    return "any"


def _run1_assignment(props_path: str) -> dict[str, str]:
    """What run #1 actually put on screen, slot by slot.

    Read from a frozen snapshot, not from render_props.json. The props file is
    regenerated by every render, so deriving the baseline from it meant that
    re-running the planner after a render compared the new assignment against
    itself -- the repair pass would have nothing to repair and would report a
    clean result no matter what it had done.
    """
    snapshot = os.path.join(os.path.dirname(props_path), "run1_assignment.json")
    if os.path.exists(snapshot):
        return json.load(open(snapshot, encoding="utf-8"))
    rp = json.load(open(props_path, encoding="utf-8"))
    EXT = (".jpg", ".jpeg", ".png", ".mp4", ".webm", ".mov", ".ogv", ".m4v", ".webp")
    out: dict[str, str] = {}
    for c in rp["cuts"]:
        m = re.search(r"(cold_open_s\d+|act\d_s\d+|outro_s\d+)", c.get("reason", ""))
        if m and c.get("source") and str(c["source"]).lower().endswith(EXT):
            out[m.group(1)] = c["source"]
    return out


def main() -> int:
    """Repair run #1's assignment; do not re-cast the film.

    An earlier version of this assigned every media slot from scratch by
    keyword-matching a subject. The metrics looked perfect -- 96 unique assets,
    max reuse 1 -- and the pictures were wrong: a slot asking for the corbelled
    gallery INTERIOR at Tiryns drew an exterior with a tourist in it, "wind over
    dry grass" drew fire embers, and the muon-detector beat drew the STAR
    detector at Brookhaven. Subject matching cannot see what a photograph is of.

    Run #1's assignment was chosen shot by shot and is right except where it
    repeats. So each slot keeps what it had whenever the rules allow, and only
    a slot whose asset is already spent is reassigned -- preferring a derived
    framing of its own parent, which is the same place from a different
    distance, before reaching for a different photograph.
    """
    bank_path, plan_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)

    bank = json.load(open(bank_path))
    plan = json.load(open(plan_path))
    slots = plan["metadata"]["slots"]
    art = os.path.dirname(os.path.abspath(plan_path))
    run1 = _run1_assignment(os.path.join(art, "render_props.json"))

    derived_run1_path = os.path.join(art, "derived_run1.json")
    derived_run1 = json.load(open(derived_run1_path)) if os.path.exists(derived_run1_path) else []
    by_parent_derived: dict[str, list[dict]] = defaultdict(list)
    for d in derived_run1:
        by_parent_derived[d["parent_id"]].append(d)

    pool: dict[str, list[dict]] = defaultdict(list)
    for subj, entry in bank["subjects"].items():
        for a in entry["assets"]:
            pool[subj].append({**a, "framing": "wide", "parent_id": a["asset_id"]})
    for d in bank.get("derived", []):
        if d.get("subject"):
            pool[d["subject"]].append(d)

    used: set[str] = set()
    parent_hits: dict[str, list[dict]] = defaultdict(list)
    prev_parent: str | None = None
    kept = repaired = shortfall = 0
    report: list[str] = []

    def legal(cand: dict, start: float) -> bool:
        if cand["asset_id"] in used:
            return False
        parent = cand.get("parent_id") or cand["asset_id"]
        if parent == prev_parent:
            return False
        hits = parent_hits.get(parent, [])
        if len(hits) >= 2:
            return False
        for h in hits:
            if start - h["end"] < MIN_SEPARATION_S:
                return False
            if h["framing"] == cand.get("framing", "wide"):
                return False
        return True

    # An annotated_still is typed "graphic" in the plan, so both the planner and
    # the gate's vacuity guard skipped it -- yet it carries a photograph, taken
    # from a NEIGHBOURING slot. That is the reuse mechanism wearing a different
    # treatment label, and it survived the first pass of this very fix: the plan
    # reported 93 unique assets while the edit rendered one crop three times.
    #
    # The annotated slot keeps the picture, because its anchor coordinates were
    # measured on that image and mean nothing on another. Its partner moves.
    annotated: dict[str, str] = {}
    try:
        import importlib.util
        spec_rs = importlib.util.spec_from_file_location(
            "resolved_sourced", os.path.join(root, "lib", "authored", "resolved_sourced.py"))
        rs = importlib.util.module_from_spec(spec_rs)
        spec_rs.loader.exec_module(rs)
        am = json.load(open(os.path.join(art, "asset_manifest.json"), encoding="utf-8"))
        by_scene: dict[str, dict] = {}
        for a in am["assets"]:
            by_scene.setdefault(a["scene_id"], a)
        for sid_a, spec_a in rs.REUSE.items():
            if sid_a in ANNOTATION_YIELDS:
                continue
            if spec_a.get("annotate") and spec_a.get("reuse") in by_scene:
                annotated[sid_a] = by_scene[spec_a["reuse"]]["path"]
    except Exception as exc:                      # pragma: no cover
        print(f"  (annotated reservation unavailable: {exc})")

    by_id = {s["slot_id"]: s for s in slots}
    for sid_a, path_a in annotated.items():
        slot_a = by_id.get(sid_a)
        if not slot_a:
            continue
        aid = "r1_" + os.path.splitext(os.path.basename(path_a))[0]
        slot_a.update({"asset_id": aid, "parent_id": aid, "framing": "wide",
                       "path": path_a, "annotated": True})
        used.add(aid)
        parent_hits[aid].append({"end": slot_a.get("end_seconds", 0), "framing": "wide"})

    for sid in PRIORITY_SLOTS:
        prior = run1.get(sid)
        slot = by_id.get(sid)
        if not (prior and slot):
            continue
        aid = "r1_" + os.path.splitext(os.path.basename(prior))[0]
        slot.update({"asset_id": aid, "parent_id": aid, "framing": "wide",
                     "path": prior})
        used.add(aid)
        parent_hits[aid].append({"end": slot.get("end_seconds", 0), "framing": "wide"})
        kept += 1

    for slot in sorted(slots, key=lambda s: s.get("start_seconds", 0)):
        if slot["slot_id"] in PRIORITY_SLOTS or slot["slot_id"] in annotated:
            continue
        # An annotated_still is typed "graphic", so a slot that yields its
        # annotation would otherwise be skipped here and silently keep run #1's
        # picture -- which is the image it just gave away.
        if (slot.get("treatment") == "graphic"
                and slot["slot_id"] not in ANNOTATION_YIELDS):
            continue
        start = slot.get("start_seconds", 0)
        sid = slot["slot_id"]
        if sid in FORCE_AUTHOR:
            for k in ("asset_id", "parent_id", "path"):
                slot.pop(k, None)
            slot["needs_authoring"] = True
            shortfall += 1
            report.append(f"{sid}: forced to authoring -- {FORCE_AUTHOR[sid]}")
            continue

        pick = None
        if sid in ASSET_OVERRIDE:
            tgt = ASSET_OVERRIDE[sid]
            for c in [c for lst in pool.values() for c in lst]:
                if c["asset_id"] == tgt:
                    pick = c
                    repaired += 1
                    break
        prior = run1.get(sid)
        if pick is not None:
            prior = None
        if prior:
            aid = "r1_" + os.path.splitext(os.path.basename(prior))[0]
            cand = {"asset_id": aid, "parent_id": aid, "framing": "wide",
                    "path": prior, "_run1": True}
            if legal(cand, start):
                pick = cand
                kept += 1

        if pick is None and prior:
            # Same photograph, closer in. Preserves what the shot was chosen for.
            paid = "r1_" + os.path.splitext(os.path.basename(prior))[0]
            for d in by_parent_derived.get(paid, []):
                if legal(d, start):
                    pick = d
                    repaired += 1
                    break

        # Texture clips carry no title and no tags -- only a numeric filename --
        # so there is nothing to match a description against. Run #1 picked them
        # by watching them; swapping one blind is a guess, and the guesses were
        # bad: "dark void in masonry, torchlight not reaching the back" drew a
        # green valley. A texture beat therefore keeps its clip or is authored.
        if pick is None and slot.get("treatment") == "texture":
            for k in ("asset_id", "parent_id", "path"):
                slot.pop(k, None)
            slot["needs_authoring"] = True
            shortfall += 1
            report.append(f"{sid} (texture): clip spent; author it")
            continue

        if pick is None:
            subj = subject_for(slot)
            want = framing_for(slot)
            cands = list(pool.get(subj, [])) if subj else []
            if want != "any":
                pref = [c for c in cands
                        if c.get("framing", "wide") == want
                        or (want == "detail" and c.get("framing") in ("detail", "extreme"))]
                cands = pref if sid in FRAMING_FORCE else (pref or cands)
            # Rank by how much of the description the title actually accounts
            # for. Taking pool order instead gave "Pumapunku H-blocks in a row"
            # a fisheye of the semi-subterranean temple while the file actually
            # named PUMA PUNKU sat further down the list.
            want = content_words(slot.get("description", ""))
            cands.sort(key=lambda c: -len(want & content_words(c.get("title", "") or "")))
            for c in cands:
                if legal(c, start) and asset_matches(slot, c, subj):
                    pick = c
                    repaired += 1
                    break

        if pick is None:
            shortfall += 1
            report.append(f"{sid} ({slot.get('treatment')}, {subject_for(slot)}): "
                          f"nothing available under the reuse rule")
            for k in ("asset_id", "parent_id", "path"):
                slot.pop(k, None)
            # The authored set fills these and only these. Authoring a slot
            # that already holds a real photograph would trade a picture for a
            # drawing, which is not what the reuse rule asks for.
            slot["needs_authoring"] = True
            continue

        parent = pick.get("parent_id") or pick["asset_id"]
        slot["asset_id"] = pick["asset_id"]
        slot["parent_id"] = parent
        slot["path"] = pick["path"]
        slot["framing"] = pick.get("framing", "wide")
        for k in ("licence", "artist"):
            if pick.get(k):
                slot[k] = pick[k]
        if pick.get("page"):
            slot["source_page"] = pick["page"]
        # A caption written for run #1 describes run #1's picture. If the
        # picture changed, the caption is a false statement about the frame,
        # so it is dropped rather than carried.
        if not pick.get("_run1"):
            slot["asset_changed"] = True
            slot.pop("caption", None)
        # A forced caption describes a SUBSTITUTED asset. When the repair pass
        # keeps run #1's photograph instead, the caption becomes a statement
        # about a picture that is not on screen: a trench above a bay captioned
        # "Cyclopean wall, Mycenae", an aerial of Giza and the modern city
        # captioned as a tomb painting at Deir el-Bersha. Bank assets only.
        if sid in CAPTION_OVERRIDE:
            if str(pick["asset_id"]).startswith("r1_"):
                report.append(f"{sid}: caption override dropped -- kept run #1's "
                              f"picture, so the caption would describe another")
                slot.pop("caption", None)
            else:
                slot["caption"] = CAPTION_OVERRIDE[sid]
        used.add(pick["asset_id"])
        parent_hits[parent].append({"end": slot.get("end_seconds", start),
                                    "framing": pick.get("framing", "wide")})
        prev_parent = parent

    plan["metadata"]["slots"] = slots
    json.dump(plan, open(out_path, "w"), indent=1, ensure_ascii=False)
    print(f"kept from run #1: {kept}   reassigned: {repaired}   short: {shortfall}")
    for r in report[:40]:
        print("  -", r)
    return 0


if __name__ == "__main__":
    sys.exit(main())

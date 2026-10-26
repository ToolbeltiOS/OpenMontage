#!/usr/bin/env python3
"""Write the authored scene props into edit_decisions.json.

Run #1's edit carried 100 cuts whose source was the literal string
`authored:<description>` — a description where a scene should be. This merges
the authored props (lib/authored/) onto those cuts so every one of them names a
real component, and re-points the 40 photographic slots at verified assets.

Re-runnable: it keys off slot_id, so running it twice is a no-op.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "projects", "they-said-it-couldnt-be-built", "artifacts")


#: Where the one-frame proofs go. A rule that silently relocates an
#: annotation is worse than the defect it fixes, so every cut it touches
#: leaves a picture behind showing what it did.
ANCHOR_PROOFS = os.path.join(ROOT, "reports", "anchor_texture")


def screen_anchors(cut_id: str, image: str, annotations: list,
                   notes: list) -> list:
    """Keep, move or drop each anchor by the texture under it.

    Returns the annotations as the rule leaves them, appends a line per
    decision to `notes`, and writes a proof frame for any cut it changed.
    """
    sys.path.insert(0, os.path.join(ROOT, "lib"))
    import verify_anchor_texture as vat

    path = image if os.path.isabs(image) else os.path.join(ROOT, image)
    if not os.path.exists(path):
        notes.append(f"{cut_id}: anchor texture not checked, no {image}")
        return annotations
    try:
        decisions = vat.screen(path, annotations)
    except SystemExit as e:
        notes.append(f"{cut_id}: anchor texture not checked ({e})")
        return annotations

    changed = [d for d in decisions if d["action"] != "keep"]
    for d in changed:
        if d["action"] == "move":
            notes.append(
                f"{cut_id}: anchor '{d['label'][:40]}' moved {d['moved_px']}px "
                f"from sd {d['sd']} to sd {d['to_sd']} — nothing to point at "
                f"where it was")
        else:
            notes.append(
                f"{cut_id}: anchor '{d['label'][:40]}' DROPPED, sd {d['sd']} "
                f"and no textured point within {vat.MAX_MOVE:.0%} of frame "
                f"width")
    if changed:
        vat.proof(path, decisions,
                  os.path.join(ANCHOR_PROOFS, f"{cut_id}.png"))
    return vat.apply(annotations, decisions)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "lib", "authored", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def slot_id(cut: dict) -> str | None:
    m = re.search(r"(cold_open_s\d+|act\d_s\d+|outro_s\d+)", cut.get("reason", ""))
    return m.group(1) if m else None


def main() -> int:
    graphics = {}
    for mod in ("act_cold_open_1", "act_2_3", "act_4_outro", "textures", "process_shots"):
        graphics.update(_load(mod).SLOTS)
    reuse = _load("resolved_sourced").REUSE

    # The scene plan is now the authority for which photograph fills a slot:
    # lib/plan_assets.py assigns it under the reuse rule. resolved_sourced.REUSE
    # was run #1's hand-resolution, and its whole mechanism was to point one
    # slot at ANOTHER slot's asset -- the repetition being fixed. Its captions
    # and annotation anchors are kept only where the picture did not change,
    # because a caption written for one photograph is a false statement about a
    # different one.
    plan_slots = {s["slot_id"]: s
                  for s in json.load(open(os.path.join(ART, "scene_plan.json"),
                                          encoding="utf-8"))["metadata"]["slots"]}

    ed = json.load(open(os.path.join(ART, "edit_decisions.json"), encoding="utf-8"))
    am = json.load(open(os.path.join(ART, "asset_manifest.json"), encoding="utf-8"))
    by_scene = {}
    for a in am["assets"]:
        by_scene.setdefault(a["scene_id"], a)

    authored = resolved = missing = 0
    problems: list[str] = []
    #: What the anchor-texture rule did, one line per anchor it changed.
    notes: list[str] = []

    for cut in ed["cuts"]:
        sid = slot_id(cut)
        if not sid:
            continue

        pslot = plan_slots.get(sid, {})

        # Authored only where the plan says the slot cannot be filled, or where
        # run #1 already drew it. Authoring a slot that holds a real photograph
        # would trade a picture for a drawing.
        if sid in graphics and (pslot.get("needs_authoring")
                                or not pslot.get("path")):
            spec = graphics[sid]
            cut["type"] = spec["type"]
            cut.pop("source", None)
            for k, v in spec["props"].items():
                cut[k] = v
            if spec.get("_ledger"):
                cut["claim_refs"] = spec["_ledger"]
            authored += 1
            continue

        if pslot.get("path"):
            spec = dict(reuse.get(sid, {}))
            changed = bool(pslot.get("asset_changed"))
            cut["source"] = pslot["path"]
            cut.pop("reused_from", None)
            if spec.get("annotate") and not changed:
                cut["type"] = "annotated_still"
                cut["backgroundImage"] = pslot["path"]
                cut["parallax"] = True
                # AN ANCHOR HAS TO POINT AT SOMETHING THE PICTURE SHOWS.
                # This is the moment the annotation is bound to a specific
                # photograph, so it is the only place the rule can be
                # applied: an anchor on a patch with no texture is moved to
                # the nearest one that has some, or dropped. See
                # lib/verify_anchor_texture.py for the calibration and for
                # the c053 annotation that prompted it.
                cut["annotations"] = screen_anchors(
                    cut["id"], pslot["path"], spec["annotations"], notes)
            else:
                # The picture moved, so run #1's annotated_still type, its
                # backgroundImage and its anchor coordinates are all stale --
                # anchors were measured on a frame this slot no longer shows.
                if cut.get("type") == "annotated_still":
                    cut.pop("type", None)
                for k in ("backgroundImage", "annotations", "parallax"):
                    cut.pop(k, None)
            for k in ("actNumber", "actTitle", "sceneIndex"):
                if k in spec:
                    cut[k] = spec[k]
            cap = pslot.get("caption") or (None if changed else spec.get("caption"))
            if cap:
                cut["caption"] = cap
            else:
                cut.pop("caption", None)
            line = spec.get("source") if not changed else None
            if pslot.get("artist") or pslot.get("licence"):
                line = " · ".join(x for x in (pslot.get("artist"), pslot.get("licence")) if x)
            if line:
                cut["sourceLine"] = line
            resolved += 1

    for cut in ed["cuts"]:
        if str(cut.get("source", "")).startswith("authored:"):
            problems.append(f"{cut['id']} ({slot_id(cut)}): still marked authored")

    ed.setdefault("metadata", {})["authored_slots_applied"] = {
        "graphics": authored,
        "resolved_photographic": resolved,
        "note": (
            "Graphic slots carry component props from lib/authored/. The 40 slots "
            "that reached the edit as `authored:<description>` were photographic "
            "subjects with no asset; they are re-pointed at verified assets in "
            "lib/authored/resolved_sourced.py, with captions describing what is "
            "actually on screen."
        ),
    }

    # The scene_plan is what the gate reads, so the same props are written
    # back onto its slots. A plan that cannot be built must fail at its own
    # gate, not three stages later.
    sp_path = os.path.join(ART, "scene_plan.json")
    sp = json.load(open(sp_path, encoding="utf-8"))
    cut_by_slot = {}
    for cut in ed["cuts"]:
        sid = slot_id(cut)
        if sid:
            cut_by_slot.setdefault(sid, cut)
    for slot in sp["metadata"]["slots"]:
        cut = cut_by_slot.get(slot["slot_id"])
        if not cut:
            continue
        if cut.get("type"):
            slot["treatment"] = "graphic"
            slot["component"] = cut["type"]
            skip = {"id", "in_seconds", "out_seconds", "layer", "transition_in",
                    "transition_duration", "reason", "source", "type",
                    "claim_refs", "reused_from", "backgroundImage"}
            props = {k: v for k, v in cut.items() if k not in skip}
            if cut["type"] == "annotated_still":
                props["image"] = cut.get("backgroundImage") or cut.get("source")
            slot["props"] = props
            slot.pop("path", None)
        else:
            # A sourced slot that the plan still calls a graphic would be read
            # as an unbuilt authored slot. Three slots were mislabelled that
            # way; the treatment follows the asset that actually fills them.
            slot["path"] = cut.get("source")
            if slot.get("treatment") == "graphic":
                asset = by_scene.get(slot["slot_id"])
                slot["treatment"] = "footage" if (asset or {}).get("type") == "video" else "still"
            slot.pop("component", None)
            slot.pop("props", None)
    json.dump(sp, open(sp_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    out = os.path.join(ART, "edit_decisions.json")
    json.dump(ed, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"authored graphics: {authored}")
    print(f"resolved photographic: {resolved}")
    print(f"missing reuse targets: {missing}")
    if notes:
        print(f"anchor texture (MIN_SD 15, proofs in reports/anchor_texture/):")
        for n in notes:
            print("  -", n)
    for p in problems[:20]:
        print("  -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""The reuse rule: one film, one use of each asset.

Run #1 put 182 slots on 80 distinct files. Nothing in the pipeline objected,
because nothing was looking. These are the rules, in one place, used both by
the planner when it assigns assets and by the scene-plan gate when it checks
the result — so the planner cannot satisfy a rule the gate does not enforce,
or the reverse.

  1. An asset id appears at most once in the film.
  2. Two framings of the same parent may both appear only if they are at least
     240 s apart and neither sits on an act boundary adjacent to the other's.
  3. No two consecutive slots share a parent.
  4. Authored graphics: no two slots with identical component + props.
     Reusing a template is the point; reusing a configuration is a repeat.
  5. A Pixabay texture clip appears at most once. If the bank runs short,
     author texture rather than repeat a clip.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

MIN_PARENT_SEPARATION_S = 240.0


def _props_key(slot: dict) -> str:
    props = slot.get("props") or {}
    skip = {"actNumber", "actTitle", "sceneIndex", "coords", "caption", "source"}
    return json.dumps({"c": slot.get("component"),
                       "p": {k: v for k, v in props.items() if k not in skip}},
                      sort_keys=True)


def check(slots: list[dict]) -> list[str]:
    """Return a list of violations. Empty means the plan obeys the rules."""
    v: list[str] = []
    ordered = sorted(slots, key=lambda s: s.get("start_seconds", 0))

    # A plan whose media slots carry no asset_id would pass every rule below
    # by having nothing to check. That is not a pass, it is an untested plan,
    # and it is how the reuse problem survived run #1 in the first place.
    # An authored slot draws its own picture and has no asset by design. It is
    # exempt only if it actually carries a component AND props -- "authored"
    # must not become a way to be invisible to the rule.
    media_like = [s for s in ordered
                  if (s.get("path") or s.get("treatment") in ("still", "footage", "texture"))
                  and not (s.get("component") and s.get("props"))]
    unidentified = [s["slot_id"] for s in media_like if not s.get("asset_id")]
    if unidentified:
        v.append(f"{len(unidentified)} media slots carry no asset_id, so the reuse "
                 f"rule cannot see them: {', '.join(unidentified[:6])}"
                 + (" ..." if len(unidentified) > 6 else ""))
        return v

    # 1 — asset id at most once
    ids = [s["asset_id"] for s in ordered if s.get("asset_id")]
    for aid, n in Counter(ids).items():
        if n > 1:
            where = [s["slot_id"] for s in ordered if s.get("asset_id") == aid]
            v.append(f"asset {aid} used {n} times: {', '.join(where)}")

    # 2 — framings of one parent, far apart only
    by_parent: dict[str, list[dict]] = defaultdict(list)
    for s in ordered:
        p = s.get("parent_id") or s.get("asset_id")
        if p:
            by_parent[p].append(s)
    for parent, group in by_parent.items():
        if len(group) < 2:
            continue
        if len(group) > 2:
            v.append(f"parent {parent} used {len(group)} times "
                     f"({', '.join(g['slot_id'] for g in group)}); at most two framings")
        for a, b in zip(group, group[1:]):
            gap = b.get("start_seconds", 0) - a.get("end_seconds", 0)
            if gap < MIN_PARENT_SEPARATION_S:
                v.append(f"parent {parent}: {a['slot_id']} and {b['slot_id']} are "
                         f"{gap:.0f}s apart, minimum {MIN_PARENT_SEPARATION_S:.0f}s")
            if a.get("script_section_id") != b.get("script_section_id") and gap < MIN_PARENT_SEPARATION_S:
                v.append(f"parent {parent}: {a['slot_id']} and {b['slot_id']} straddle "
                         f"an act boundary too closely")

    # 3 — no two consecutive slots on one parent
    for a, b in zip(ordered, ordered[1:]):
        pa = a.get("parent_id") or a.get("asset_id")
        pb = b.get("parent_id") or b.get("asset_id")
        if pa and pa == pb:
            v.append(f"consecutive slots {a['slot_id']} and {b['slot_id']} share parent {pa}")

    # 4 — authored graphics must differ in configuration
    #
    # Keyed on the component, NOT on treatment. The authored textures carry
    # treatment "texture", so a treatment == "graphic" filter skipped all
    # fourteen of them -- fourteen slots that could have held one identical
    # configuration and passed, which is precisely the defect being fixed.
    authored = [s for s in ordered if s.get("component") and s.get("props")]
    for key, n in Counter(_props_key(s) for s in authored).items():
        if n > 1:
            comp = json.loads(key)["c"]
            where = [s["slot_id"] for s in authored if _props_key(s) == key]
            v.append(f"identical authored configuration ({comp}) in {n} slots: "
                     f"{', '.join(where)}")

    # 5 — texture clips once each
    tex = [s for s in ordered if s.get("treatment") == "texture" and s.get("asset_id")]
    for aid, n in Counter(s["asset_id"] for s in tex).items():
        if n > 1:
            v.append(f"texture clip {aid} used {n} times; author texture instead")
    return v


def metrics(slots: list[dict]) -> dict:
    ids = [s["asset_id"] for s in slots if s.get("asset_id")]
    parents = [s.get("parent_id") or s.get("asset_id") for s in slots if s.get("asset_id")]
    cid = Counter(ids)
    cpar = Counter(parents)
    return {
        "media_backed_slots": len(ids),
        "unique_assets": len(cid),
        "max_appearances_of_any_asset": max(cid.values()) if cid else 0,
        "unique_parents": len(cpar),
        "max_appearances_of_any_parent": max(cpar.values()) if cpar else 0,
        "assets_used_more_than_once": sum(1 for n in cid.values() if n > 1),
    }


if __name__ == "__main__":
    import sys
    plan = json.load(open(sys.argv[1]))
    slots = plan["metadata"]["slots"]
    viol = check(slots)
    print(json.dumps(metrics(slots), indent=1))
    if viol:
        print(f"\nREUSE RULE: FAIL ({len(viol)} violations)")
        for x in viol[:40]:
            print("  -", x)
        sys.exit(1)
    print("\nREUSE RULE: PASS")

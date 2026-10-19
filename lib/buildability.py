"""Buildability check for authored scene-plan slots.

WHY THIS EXISTS
---------------
Run #1 of the narrated-documentary pipeline reached the compose stage with 79
of 183 slots naming graphics that had no component behind them — "cross_section
— the pyramid in section", "map — the Orcadian sea route". They were
*descriptions*, not scenes. Every gate passed, because nothing checked that an
authored slot could actually be rendered. The render would have silently fallen
back to text cards for 43% of the film.

The scene_plan gate now fails if any authored slot names a component that does
not exist in the composer, or supplies props that do not satisfy that
component's contract.
"""
from __future__ import annotations

import json
import os
from typing import Any

CONTRACT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "remotion-composer",
    "component-contract.json",
)


def load_contract(path: str | None = None) -> dict[str, Any]:
    with open(path or CONTRACT_PATH, encoding="utf-8") as fh:
        return json.load(fh)["components"]


def check_slot(slot: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    """Return a list of problems for one slot. Empty list means buildable."""
    problems: list[str] = []
    sid = slot.get("slot_id", "<no id>")

    # Only authored slots need a component; sourced slots need a real file.
    treatment = slot.get("treatment")
    if treatment != "graphic":
        path = slot.get("path")
        if not path:
            problems.append(f"{sid}: sourced slot has no asset path")
        elif not os.path.exists(path):
            problems.append(f"{sid}: asset path does not exist on disk: {path}")
        return problems

    comp = slot.get("component")
    if not comp:
        problems.append(
            f"{sid}: authored slot names NO component "
            f"(authored_kind={slot.get('authored_kind', '')!r:.70}) — "
            f"a description is not a scene"
        )
        return problems

    spec = contract.get(comp)
    if not spec:
        problems.append(
            f"{sid}: component {comp!r} does not exist in the composer "
            f"(known: {', '.join(sorted(contract))})"
        )
        return problems

    props = slot.get("props") or {}
    for key in spec.get("required", []):
        if key not in props or props[key] in (None, "", [], {}):
            problems.append(f"{sid}: {comp} requires prop {key!r}")

    for arr, keys in (spec.get("array_item_required") or {}).items():
        items = props.get(arr)
        if items is None:
            continue
        if not isinstance(items, list):
            problems.append(f"{sid}: {comp}.{arr} must be a list")
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                problems.append(f"{sid}: {comp}.{arr}[{i}] must be an object")
                continue
            for k in keys:
                if k not in item:
                    problems.append(f"{sid}: {comp}.{arr}[{i}] missing {k!r}")

    for dotted, allowed in (spec.get("enums") or {}).items():
        if "." in dotted:
            arr, field = dotted.split(".", 1)
            for i, item in enumerate(props.get(arr) or []):
                v = (item or {}).get(field)
                if v is not None and v not in allowed:
                    problems.append(
                        f"{sid}: {comp}.{arr}[{i}].{field}={v!r} not in {allowed}"
                    )
        else:
            v = props.get(dotted)
            if v is not None and v not in allowed:
                problems.append(f"{sid}: {comp}.{dotted}={v!r} not in {allowed}")

    # An image-backed component must point at a file that exists.
    if comp == "annotated_still":
        img = props.get("image")
        if img and not img.startswith(("http://", "https://", "staticFile:")):
            local = img
            if not os.path.exists(local):
                problems.append(f"{sid}: annotated_still image not found on disk: {img}")

    return problems


def check_scene_plan(slots: list[dict[str, Any]], contract: dict[str, Any] | None = None):
    """Check every slot. Returns (ok, problems, summary)."""
    contract = contract or load_contract()
    problems: list[str] = []
    counts = {"authored": 0, "sourced": 0, "unbuildable": 0}
    for slot in slots:
        p = check_slot(slot, contract)
        if slot.get("treatment") == "graphic":
            counts["authored"] += 1
        else:
            counts["sourced"] += 1
        if p:
            counts["unbuildable"] += 1
            problems.extend(p)
    return (not problems), problems, counts


if __name__ == "__main__":
    import sys

    src = sys.argv[1] if len(sys.argv) > 1 else None
    if not src:
        print("usage: buildability.py <slots.json>")
        raise SystemExit(2)
    data = json.load(open(src, encoding="utf-8"))
    slots = data if isinstance(data, list) else data.get("metadata", {}).get("slots", [])
    ok, problems, counts = check_scene_plan(slots)
    print(f"slots: {len(slots)}  authored {counts['authored']}  sourced {counts['sourced']}")
    print(f"unbuildable slots: {counts['unbuildable']}")
    for p in problems[:40]:
        print("  -", p)
    if len(problems) > 40:
        print(f"  ... and {len(problems)-40} more")
    print("BUILDABILITY:", "PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)

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
import math
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

    # SLOT-LEVEL FIELDS THE COMPONENT DECLARES, which are not props and are
    # never passed to it. `map_route` declares `claim_id`: the ledger claim
    # the route illustrates, whose date decides whether the route is drawn
    # on a historical chart or on terrain.
    #
    # The planner must say. Inferring it from the slot's one-line
    # description does not work and fails unsafely -- measured on
    # easter-island it dated the birdman swim to an 1868 ship's visit and
    # matched "the small statue's route" to a 1914 expedition on the word
    # "small" -- and a wrong year silently picks a wrong chart.
    #
    # A claim that resolves to NO DATE is not a failure; that route gets
    # terrain with the reason recorded. Only a MISSING claim_id fails.
    for key in (contract.get(comp, {}) or {}).get("slot_required", []):
        if slot.get(key):
            continue
        if key == "claim_id":
            problems.append(
                f"{sid}: {comp} names no claim_id — the planner must say "
                f"which ledger claim this scene illustrates, because the "
                f"claim's date decides whether the route is drawn on a "
                f"historical chart or on terrain, and it cannot be inferred "
                f"from the description")
        elif key == "prompt":
            problems.append(
                f"{sid}: {comp} names no prompt — `subject` is the short "
                f"label the viewer reads and cannot also be the record of "
                f"what the picture is of. A generated asset with no prompt "
                f"cannot be licence-checked after the fact")
        else:
            problems.append(f"{sid}: {comp} requires slot field {key!r}")

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
    """Check every slot, then the reuse rule. Returns (ok, problems, summary)."""
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
    # Reuse is a buildability question too: a plan that repeats an asset is
    # not a plan the film can be cut from, it is the same film twice.
    try:
        from .reuse_rules import check as reuse_check, metrics as reuse_metrics
    except ImportError:
        from reuse_rules import check as reuse_check, metrics as reuse_metrics
    reuse_problems = reuse_check(slots)
    problems.extend(reuse_problems)
    counts["reuse_violations"] = len(reuse_problems)
    counts.update(reuse_metrics(slots))

    return (not problems), problems, counts


# ---------------------------------------------------------------------------
# The timeline, frame by frame
# ---------------------------------------------------------------------------

#: How the composition turns a cut's seconds into frames.
#:
#: This mirrors `frameSpan` in `remotion-composer/src/Explainer.tsx` and has
#: to keep mirroring it: the whole point is to read the same timeline the
#: renderer will lay out, from the props, before anything is rendered.
def js_round(x: float) -> int:
    """`Math.round`, which is NOT Python's `round`.

    The composition lays the timeline out in JavaScript, and the two
    languages disagree on exactly the values this check exists to find.
    JavaScript rounds a half UP; Python rounds it to EVEN. A cut at 807.35s
    lands on frame 24220.5, which JavaScript puts at 24221 and Python at
    24220 — a one-frame disagreement about where a cut begins, in a check
    whose whole job is to find one-frame holes.

    Measured: counting they-said-it-couldnt-be-built's holes with Python's
    rounding gives 21 and with JavaScript's gives 27. The film has 27. The
    six it missed include three of the five flashes visible in the published
    file. A check that models the composition must round the way the
    composition rounds.
    """
    return math.floor(x + 0.5)


def frame_span(element: dict[str, Any], fps: int = 30) -> tuple[int, int]:
    """(first frame, last frame) inclusive, both edges rounded from the timeline."""
    first = js_round(float(element["in_seconds"]) * fps)
    last = js_round(float(element["out_seconds"]) * fps) - 1
    return first, max(first, last)


def check_timeline_coverage(cuts: list[dict[str, Any]], fps: int = 30
                            ) -> tuple[list[str], dict[str, Any]]:
    """Every frame of the film is covered by exactly one cut.

    WHY THIS IS BLOCKING
    --------------------
    A frame no cut covers is not a missing frame. It is a frame the
    composition paints with its bare background — no scene, no chrome —
    while the type pass goes on laying captions over it. It looks like a
    flash, and it survives every delivery gate there is:

      - frame count:  the frame is present
      - frame motion: one frame is not a freeze
      - frame order:  the delivered film is compared against the PLATE, and
                      the gap is in the plate, so the two agree perfectly
      - plate purity, type lock, delivery audio: not their question

    Film #1 shipped with eight of these. It was published before anything
    looked at a histogram of single-frame differences, and the only reason
    they were ever found is that a splice went looking for something else.

    Counted on the props of the four films made so far, under the old
    arithmetic (start rounded from the timeline, duration rounded from
    `out - in`): they-said-it-couldnt-be-built 21, king-tut 13,
    easter-island 0, noah 0.

    OVERLAPS FAIL TOO. Two cuts over one frame is the same class of defect
    read from the other side — the later cut wins and the earlier one is a
    frame shorter than its own edit says, which is exactly the arithmetic
    that produced the gaps.
    """
    problems: list[str] = []
    if not cuts:
        return ["the props carry no cuts at all"], {"cuts": 0}

    spans = sorted((frame_span(c, fps), c.get("id", "<no id>")) for c in cuts)
    total = max(last for (_, last), _ in spans) + 1

    gaps: list[dict[str, Any]] = []
    overlaps: list[dict[str, Any]] = []
    for ((a1, b1), id1), ((a2, b2), id2) in zip(spans, spans[1:]):
        if a2 > b1 + 1:
            gaps.append({"first": b1 + 1, "last": a2 - 1,
                         "after": id1, "before": id2})
        elif a2 <= b1:
            overlaps.append({"first": a2, "last": min(b1, b2),
                             "cuts": [id1, id2]})

    first_frame = spans[0][0][0]
    if first_frame != 0:
        problems.append(
            f"the film starts at frame {first_frame}, not 0 — "
            f"{first_frame} frame(s) before {spans[0][1]} are covered by "
            f"nothing")
    for gap in gaps:
        span = (f"frame {gap['first']}" if gap["first"] == gap["last"]
                else f"frames {gap['first']}-{gap['last']}")
        problems.append(
            f"{span} ({gap['first'] / fps:.3f}s) "
            f"is covered by no cut — it falls between {gap['after']} and "
            f"{gap['before']}, so the composition paints its bare background "
            f"there: no scene, no chrome")
    for over in overlaps:
        span = (f"frame {over['first']}" if over["first"] == over["last"]
                else f"frames {over['first']}-{over['last']}")
        problems.append(
            f"{span} ({over['first'] / fps:.3f}s) is covered by "
            f"{' and '.join(over['cuts'])} at once — the later cut paints "
            f"over the earlier one, which is a frame shorter than its edit")

    return problems, {"cuts": len(cuts), "frames": total,
                      "gap_frames": sum(g["last"] - g["first"] + 1 for g in gaps),
                      "gaps": gaps[:40],
                      "overlap_frames": sum(o["last"] - o["first"] + 1
                                            for o in overlaps),
                      "overlaps": overlaps[:40]}


def flatten_scene(cuts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A copy of the cuts with `scene` folded onto each, as the renderer sees
    them.

    `lib/build_render_props.py` does this once, on the way to
    `render_props.json`. Doing it on a COPY here is the point: an edit-time
    check must not quietly rewrite the artifact it is checking.
    """
    flat: list[dict[str, Any]] = []
    for cut in cuts:
        copy = dict(cut)
        scene = copy.pop("scene", None)
        if isinstance(scene, dict):
            for key, value in scene.items():
                copy.setdefault(key, value)
        flat.append(copy)
    return flat


def check_cut_props(cuts: list[dict[str, Any]], root: str | None = None
                    ) -> tuple[bool, list[str], dict[str, Any]]:
    """The composer's own zod schemas over an EDIT, before any render.

    WHY HERE AND NOT ONLY IN THE PROPS BUILDER
    ------------------------------------------
    The props gate added on 2026-11-22 runs at the last free moment — the
    write of `render_props.json`. That is the right place for a blocking
    refusal, and it is the WRONG place to learn about it: the stage that can
    fix a cut is the edit stage, and by then it has exited. Four cuts of
    every film from #1 to #6 carried `density: 0.4`, which is
    `Math.round(0.4)` = 0 elements and a texture beat that draws nothing;
    six carried `basemap: "terrain"`, which is a request and not a tile. All
    of it was authored in a stage that was never told.

    So the same schemas run here, over `edit_decisions.json`, where the
    answer still costs nothing and the cut can still be rewritten. There is
    no normalising: a fractional density is reported with the cut named, and
    the value is fixed where it was written.
    """
    from importlib import import_module

    props_builder = import_module("build_render_props")
    report = props_builder.scene_prop_report(
        {"cuts": flatten_scene(cuts), "overlays": []}, root)
    failures = report.get("failures") or []
    problems = [f"{f['id']} ({f['type']}): {f['field']} — {f['rule']}"
                for f in failures]
    counts = {"checked": report.get("checked", 0),
              "failures": len(failures),
              "unchecked": report.get("unchecked", {})}
    return (not failures), problems, counts


if __name__ == "__main__":
    import sys

    src = sys.argv[1] if len(sys.argv) > 1 else None
    if not src:
        print("usage: buildability.py <slots.json>")
        raise SystemExit(2)
    data = json.load(open(src, encoding="utf-8"))

    # An edit, not a scene plan. `edit_decisions.json` carries `cuts`, and
    # what is worth checking about it is whether the composer can draw the
    # props — the question that killed two renders in two nights in
    # November 2026 and was only ever asked after the edit stage had gone.
    if isinstance(data, dict) and data.get("cuts"):
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        ok, problems, counts = check_cut_props(data["cuts"])
        print(f"cuts: {counts['checked']} checked against the composer's "
              f"zod schemas")
        unchecked = counts.get("unchecked") or {}
        if unchecked:
            print("  no schema for: "
                  + ", ".join(f"{k} x{v}" for k, v in sorted(unchecked.items())))
        for problem in problems[:40]:
            print("  -", problem)
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more")
        print("CUT PROPS:", "PASS" if ok else "FAIL")
        if not ok:
            print("Fix these where they were written. Nothing downstream "
                  "normalises them: a fractional density is zero elements "
                  "at render time and a string basemap is no basemap.")
        raise SystemExit(0 if ok else 1)

    slots = data if isinstance(data, list) else data.get("metadata", {}).get("slots", [])
    ok, problems, counts = check_scene_plan(slots)
    print(f"slots: {len(slots)}  authored {counts['authored']}  sourced {counts['sourced']}")
    print(f"unbuildable slots: {counts['unbuildable']}")
    print(f"unique assets {counts.get('unique_assets')} across "
          f"{counts.get('media_backed_slots')} media-backed slots; "
          f"max reuse {counts.get('max_appearances_of_any_asset')} "
          f"(parent-level {counts.get('max_appearances_of_any_parent')})")
    print(f"reuse violations: {counts.get('reuse_violations')}")
    for p in problems[:40]:
        print("  -", p)
    if len(problems) > 40:
        print(f"  ... and {len(problems)-40} more")
    print("BUILDABILITY:", "PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)

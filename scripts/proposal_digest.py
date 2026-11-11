#!/usr/bin/env python3
"""The proposal, as much of it as the script stage needs and no more.

WHY A DIGEST AND NOT THE PACKET
-------------------------------
Research, proposal and script became three separate `claude -p` calls on
2026-11-11, each from an empty context. That is the fix for a 60-turn cap
being spent on research before a word of script existed — but it means the
script stage can no longer remember what the proposal decided. It has to
read it.

`proposal_packet.json` is 31 KB on a real film and most of it is addressed
to somebody else: provider rankings, a cost estimate, three alternative
paths not taken, six stage descriptions, and a metadata block. Read whole on
turn one, it is carried on every turn after.

So this prints the decision: which concept was chosen and why, the act
structure it implies, the register, the duration, and the claim ids the
concept rests on. The fields it drops are the fields the script stage has no
business re-deciding.

A DIGEST IS GENERATED, NEVER COPIED, so it cannot drift from the packet —
the same argument as scripts/brief_digest.py and
scripts/playbook_digest.py. If the script stage needs something this leaves
out, that is a bug HERE, and the stage is told to say so in its report
rather than reading the packet whole.

    python3 scripts/proposal_digest.py --project king-tut
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Printed from the chosen concept. Everything else in a concept is written
#: for the proposal reviewer, not for the writer.
CONCEPT_FIELDS = ("title", "hook", "core_message", "cta", "tone",
                  "narrative_structure", "key_points", "visual_approach",
                  "target_duration_seconds", "grounded_in")

#: Printed from the production plan. `stages`, `provider_rankings`,
#: `alternative_paths`, `quality_tradeoffs` and `cost_estimate` are the
#: producer's record and not an instruction to the writer.
PLAN_FIELDS = ("playbook", "composition_mode", "art_direction",
               "delivery_promise", "voice_selection", "render_runtime")


def wrap(text: str, width: int = 76, indent: str = "  ") -> str:
    import textwrap
    return "\n".join(textwrap.wrap(str(text), width,
                                   initial_indent=indent,
                                   subsequent_indent=indent)) or indent


def render(packet: dict) -> str:
    out: list[str] = ["PROPOSAL DIGEST — the decision, not the packet", ""]

    chosen_id = (packet.get("selected_concept") or {}).get("concept_id")
    concepts = packet.get("concept_options") or []
    concept = next((c for c in concepts if c.get("id") == chosen_id), None)
    if concept is None and concepts:
        concept = concepts[0]
        out.append(f"(no concept matches selected id {chosen_id!r} — showing "
                   f"the first, and THIS IS A BUG worth reporting)")
        out.append("")

    rationale = (packet.get("selected_concept") or {}).get("rationale")
    out.append(f"CHOSEN: {chosen_id}  of {len(concepts)} considered")
    if rationale:
        out.append("why:")
        out.append(wrap(rationale))
    out.append("")

    if concept:
        for field in CONCEPT_FIELDS:
            if field not in concept:
                continue
            value = concept[field]
            if isinstance(value, list):
                out.append(f"{field}:")
                for item in value:
                    out.append(wrap(f"- {item}"))
            else:
                out.append(f"{field}:")
                out.append(wrap(value))
        out.append("")

    plan = packet.get("production_plan") or {}
    out.append("PRODUCTION PLAN — the parts that bind the script")
    for field in PLAN_FIELDS:
        if field not in plan:
            continue
        value = plan[field]
        if isinstance(value, dict):
            out.append(f"{field}:")
            for k, v in value.items():
                if v in (None, "", [], {}):
                    continue
                out.append(wrap(f"{k}: {v}", indent="    "))
        else:
            out.append(f"{field}:")
            out.append(wrap(value))
    out.append("")

    out.append("WHAT THIS DIGEST LEAVES OUT, DELIBERATELY: the cost "
               "estimate, the provider rankings, the alternative paths not "
               "taken, the stage list and the metadata. If you need one of "
               "them, say so in your closing report rather than reading the "
               "packet whole — it is 31 KB and you would carry it on every "
               "turn.")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--packet", default=None)
    args = ap.parse_args()

    path = (Path(args.packet) if args.packet else
            ROOT / "projects" / args.project / "artifacts" /
            "proposal_packet.json")
    if not path.exists():
        print(f"no proposal packet at {path}", file=sys.stderr)
        return 1
    sys.stdout.write(render(json.loads(path.read_text())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

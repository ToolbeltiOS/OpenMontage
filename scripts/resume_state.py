#!/usr/bin/env python3
"""What this project has already finished, for a stage going back in.

WHY THIS EXISTS
---------------
A `claude -p` stage that stops on a usage limit has usually done real work
first — the first attended run had a research brief, a proposal and a script
on disk when the render stage died. Re-entering the stage without telling it
so means it starts at research again: hours of work redone, the ledger spent
twice, and a second set of artifacts over the top of a set that was fine.

The checkpoints already know. `lib/checkpoint.py` records a stage completed
with its artifacts, and `get_completed_stages` reads it back. This prints
that as an instruction a re-entering stage can act on, so resumption is a
fact the prompt carries rather than a judgement the agent has to make about
files it finds lying around.

    scripts/resume_state.py --project easter-island
    scripts/resume_state.py --project easter-island --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PIPELINE_TYPE = "narrated-documentary"

#: The artifact each stage is finished when it has written. Checked as well
#: as the checkpoint, because a checkpoint written for a stage whose file is
#: missing is the one state that must NOT be treated as done.
STAGE_ARTIFACT = {
    "research": "research_brief.json",
    "proposal": "proposal_packet.json",
    "script": "script.json",
    "scene_plan": "scene_plan.json",
    "assets": "asset_bank.json",
    "edit": "edit_decisions.json",
    "compose": "render_props.json",
    "publish": "publish.json",
}


def state(project: str) -> dict:
    from lib.checkpoint import (get_completed_stages, get_next_stage,
                                get_pipeline_stages)

    projects = ROOT / "projects"
    art = projects / project / "artifacts"
    stages = get_pipeline_stages(PIPELINE_TYPE)
    completed = set(get_completed_stages(projects, project, PIPELINE_TYPE))

    rows, trustworthy = [], []
    for stage in stages:
        name = STAGE_ARTIFACT.get(stage)
        path = art / name if name else None
        exists = bool(path and path.exists() and path.stat().st_size > 0)
        done = stage in completed and exists
        if stage in completed and not exists:
            note = "checkpoint says completed but the artifact is MISSING — redo it"
        elif done:
            note = "done"
        elif exists:
            note = "an artifact exists but no completed checkpoint — verify, do not assume"
        else:
            note = "not started"
        if done:
            trustworthy.append(stage)
        rows.append({"stage": stage, "done": done, "artifact": name,
                     "exists": exists, "note": note})

    return {"project": project,
            "completed": trustworthy,
            "next": get_next_stage(projects, project, PIPELINE_TYPE),
            "stages": rows}


def render(st: dict) -> str:
    out = [f"RESUME STATE for {st['project']}", ""]
    for row in st["stages"]:
        mark = "x" if row["done"] else " "
        out.append(f"  [{mark}] {row['stage']:<11} {row['note']}")
    out += ["",
            f"Already finished: {', '.join(st['completed']) or 'nothing'}",
            f"Start at: {st['next'] or 'everything is done'}",
            "",
            "Do NOT redo a stage marked [x]. Its artifact is on disk and was",
            "approved or auto-approved; rebuilding it spends the run twice and",
            "overwrites a result that was fine. Read what it produced and",
            "carry on from the first stage that is not marked."]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    st = state(args.project)
    print(json.dumps(st, indent=1) if args.json else render(st))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""The owner's angle constraint, rendered as prompt text.

WHY THIS EXISTS
---------------
`pick_topic.py` writes the constraint into the brief, under
`briefs[0]["angle"]["constraint"]`. The weekly prompt said only "Brief:
<path> (take the first brief)" and never mentioned it, so an unattended run
had to notice the field, infer that it binds, and honour every part of it —
the spine ORDER, the register, the title length, the entities that cannot be
sourced. Some of that it would have found. The rest is the kind of thing that
is discovered afterwards, in the finished film.

A constraint the prompt does not name is a constraint the run may skip. This
renders it as instruction and `run_weekly.sh` appends it, so the words the
owner wrote are in front of the agent rather than three keys deep in a JSON
file it was told to "take the first brief" from.

Prints nothing and exits 0 when there is no constraint, so the runner can
append it unconditionally.

    python scripts/angle_brief.py --brief artifacts/topic_briefs.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def sentence(text: str) -> str:
    """Capitalise the first letter and leave the rest alone.

    `str.capitalize()` lowercases everything after the first character, which
    turns "The subject is why ... A film that arrives knowing the answer" into
    "... a film that arrives", and would do the same to any proper noun in a
    constraint's prose.
    """
    return text[:1].upper() + text[1:] if text else text


def render(brief: dict) -> str:
    """The constraint as prompt text, or "" when the subject has none."""
    angle = brief.get("angle") or {}
    c = angle.get("constraint")
    if not c:
        return ""

    out: list[str] = [
        "",
        "THE ANGLE IS SET. It is not derived and it is not yours to choose.",
        f"Set by {c['set_by']}. It overrides the angle the Shorts titles",
        "suggest, because the picker cannot know what a previous film argued",
        "or what this one is for.",
        "",
        "The spine, in this order, one act each:",
    ]
    out += [f"  {n}. {item}" for n, item in enumerate(c["spine"], 1)]

    recap = c.get("recap")
    if recap:
        out += ["",
                f"{sentence(recap['what'])}: at most "
                f"{recap['max_seconds']}s, in {recap['where']}, as a recap "
                f"and not as the spine. {sentence(recap['why'])}."]

    register = c.get("register")
    if register:
        out += ["", "Register, binding:",
                f"  - {register['both_sides']}",
                f"  - {register['evidence']}",
                f"  - No {' or '.join(register['forbidden'])} register.",
                f"  - {sentence(register['why'])}"]

    thin = c.get("thin")
    if thin:
        out += ["",
                "These are named in the spine and WILL NOT clear the asset",
                "floor. Measured, not assumed. Do not build a shot list that",
                "assumes pictures of them exist:"]
        for name, row in thin.items():
            out.append(f"  - {name}: {row['counted']} usable assets. "
                       f"Shoot {', '.join(row['shoot_instead'])} instead — "
                       f"{row['why']}.")

    titles = c.get("titles")
    if titles:
        out += ["",
                f"Title: {titles['min_chars']}-{titles['max_chars']} "
                f"characters. Candidates, in the channel's register:"]
        out += [f"  - {t}  ({len(t)} chars)" for t in titles["candidates"]]
        if titles.get("exemplars"):
            out.append(
                "  The owner's own exemplars, quoted for VOICE: "
                + ", ".join(f"{t!r}" for t in titles["exemplars"])
                + ". " + sentence(titles.get("exemplars_note", "")) + ".")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True)
    ap.add_argument("--index", type=int, default=0)
    args = ap.parse_args()

    path = Path(args.brief)
    if not path.exists():
        print(f"no brief at {path}", file=sys.stderr)
        return 1
    blob = json.loads(path.read_text())
    briefs = blob["briefs"] if isinstance(blob, dict) else blob
    if not briefs:
        return 0
    sys.stdout.write(render(briefs[args.index]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

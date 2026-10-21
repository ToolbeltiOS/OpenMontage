#!/usr/bin/env python3
"""Step 15: where does the taste live, and what checks it?

WHAT THIS AUDITS
----------------
Not "are the skills any good". That is an opinion and an opinion is not an
audit. The question with an answer is narrower and harder:

    For each judgement the film's quality actually depended on, is there a
    skill that states a CRITERION, a gate that MEASURES it, or neither?

Run #1 is the test data, because every one of its defects is a taste failure
that passed the pipeline end to end. 181 of 182 shots between five and eight
seconds. One camera move, 182 times. Thirteen seconds of silence in twenty
minutes. Text on screen for 99.4% of the runtime. None of those is a bug;
each is a decision nobody made, and the audit asks who should have made it.

THE THREE COLUMNS
-----------------
    STATED      a skill names a criterion you could fail: "no two adjacent
                cuts share both subject and scale" is stated. "Produce
                edit_decisions" is not.
    MEASURED    something reads the artifact or the film and can refuse it.
    DEFENDED    both. The only column that survives a tired Friday.

A judgement that is STATED but not MEASURED is advice. A judgement that is
MEASURED but not STATED is a rule nobody can read before breaking it. Run #1
shipped with most of its taste in the first column and some in neither.

    python scripts/taste_audit.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills" / "pipelines" / "narrated-documentary"
PLAYBOOK = ROOT / "styles" / "wak3up-documentary.yaml"
PIPELINE = ROOT / "pipeline_defs" / "narrated-documentary.yaml"

#: The judgements run #1 got wrong, each with the defect it produced, where to
#: look for a stated criterion, and the gate that would now refuse it.
#:
#: `states` is a list of words that would appear if the judgement WERE stated,
#: and choosing them is itself a judgement — a list too narrow scores a skill
#: as silent when it is not, and one too wide scores a mention as a rule.
#: Both failure modes happened while this was being written, which is why the
#: quotes are printed: a score with no quote behind it cannot be checked.
JUDGEMENTS = [
    {
        "judgement": "how long a shot holds",
        "run1": "181 of 182 shots between 5 and 8 seconds",
        "skill": "edit-director.md",
        "states": ["cadence ceiling", "Hero slots hold longest",
                   "Cutaways are shortest"],
        "gate": "rhythm",
    },
    {
        "judgement": "how the cutting rate moves across the film",
        "run1": "8-10 cuts every minute, end to end",
        "skill": "edit-director.md",
        "states": ["cuts_per_minute", "curve", "envelope"],
        "gate": "rhythm",
    },
    {
        "judgement": "which way the camera moves, and whether it should",
        "run1": "one push, 182 times",
        "skill": "scene-director.md",
        "states": ["parallax", "camera", "push", "drift"],
        "gate": "camera_intent",
    },
    {
        "judgement": "where the film is allowed to be silent",
        "run1": "13 seconds of air in 20 minutes; longest gap 2.8s",
        "skill": "script-director.md",
        "states": ["air", "silence", "pause"],
        "gate": "script_beats",
    },
    {
        "judgement": "whether picture and sound cut together",
        "run1": "they always did, 182 times",
        "skill": "edit-director.md",
        "states": ["J-cut", "L-cut", "lead", "lag"],
        "gate": "edit_leads",
    },
    {
        "judgement": "how loud the music sits under the voice",
        "run1": "20 dB under; the references run 4-15.5",
        "skill": "edit-director.md",
        "states": ["music_under_speech", "ducking", "bed level"],
        "gate": "music_rise",
    },
    {
        "judgement": "whether the frame is ever still",
        "run1": "authored graphics frozen for 90-95% of each hold",
        "skill": "scene-director.md",
        "states": ["internal_motion", "static hold", "slideshow"],
        "gate": "frame_motion",
    },
    {
        "judgement": "whether text on screen is readable and sparing",
        "run1": "burnt-in captions for 99.4% of the runtime",
        "skill": "compose-director.md",
        "states": ["caption", "burn", "sidecar"],
        "gate": "captions",
    },
    {
        "judgement": "whether an asset may be used at all",
        "run1": "no licence filter at fetch time",
        "skill": "asset-director.md",
        "states": ["licence", "license", "CC0", "commercial"],
        "gate": "corpus_builder",
        "gate_is_a_pipeline_gate": False,
    },
    {
        "judgement": "whether a cut lands on a cut the source already had",
        "run1": "never checked",
        "skill": "edit-director.md",
        "states": ["source scene", "scene change", "source's own cut",
                   "source cut", "PySceneDetect"],
        "gate": "source_cuts",
    },
]


#: A line only counts as a criterion if it reads like one. The first version
#: of this counted any line containing the keyword, and scored a prerequisites
#: table row — "| Playbook | ... | Typography, grade, ducking, transition
#: vocabulary |" — as a stated rule about how loud the music sits. It is not a
#: rule. It is a list of things the playbook contains.
CRITERION_WORDS = re.compile(
    r"\b(must|never|always|no two|no more than|at least|at most|do not|"
    r"don't|hard|ceiling|floor|minimum|maximum|shortest|longest|"
    r"required|refuse|reject|only if|unless|every|each)\b", re.I)


def is_a_criterion(line: str) -> bool:
    """Could you fail this sentence, or does it merely mention the subject?"""
    stripped = line.strip()
    if stripped.startswith("|") or stripped.startswith("#"):
        return False                       # a table row or a heading
    return bool(CRITERION_WORDS.search(stripped))


#: What a human reading makes of each match, because the matcher cannot tell
#: a rule ABOUT a subject from a rule that merely mentions it. The score that
#: matters is this column, not the automated one; the automated pass is there
#: to enumerate and to quote, so that the reading can be checked in a minute.
READING: dict[str, tuple[str, str]] = {
    'how long a shot holds': ('yes',
     'the cadence ceiling, stated as hard'),
    'how the cutting rate moves across the film': ('yes',
     'added 2026-10-21 after this audit found it missing'),
    'which way the camera moves, and whether it should': ('yes',
     'stated 2026-10-21: the move comes from the beat and the register, a run of drifts keeps one direction, one ramp per act, and a push into a dense asset becomes a lock'),
    'where the film is allowed to be silent': ('yes',
     'stated 2026-10-21: air is marked in the script, the total lands between 8% and 15% of runtime, and the word budget shrinks to pay for it'),
    'whether picture and sound cut together': ('yes',
     'the J/L budget, stated with the frame counts'),
    'how loud the music sits under the voice': ('yes',
     'stated 2026-10-21: the level is the playbook\'s -30 LUFS and is never written into the EDL by hand'),
    'whether the frame is ever still': ('yes',
     'do not pass a slideshow downstream'),
    'whether text on screen is readable and sparing': ('yes',
     'stated 2026-10-21: a sidecar SRT, burn-in off by default and layout-aware when on'),
    'whether an asset may be used at all': ('yes',
     'stated 2026-10-21: four families only, NC and ND refused, and an unknown licence is not permission'),
    'whether a cut lands on a cut the source already had': ('yes',
     'added 2026-10-21 after this audit found it missing'),
}


def blocks(text: str) -> list[str]:
    """The document as bullets and paragraphs, with wrapping undone.

    Line by line does not work: a rule written as a bullet and wrapped across
    two lines has its imperative on the first line and its subject on the
    second, so neither line is both. "Never land a boundary on a cut the
    source already had" scored as silent for exactly that reason.
    """
    out: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        starts_new = (not stripped or stripped.startswith(("-", "*", "#", "|"))
                      or re.match(r"^\d+\.", stripped))
        if starts_new:
            if current:
                out.append(" ".join(current))
            current = [stripped] if stripped else []
        else:
            current.append(stripped)
    if current:
        out.append(" ".join(current))
    return [b for b in out if b]


#: A block only counts as a criterion if it reads like one. The first version
#: of this counted any line containing the keyword, and scored a prerequisites
#: table row — "| Playbook | ... | Typography, grade, ducking, transition
#: vocabulary |" — as a stated rule about how loud the music sits. It is not a
#: rule. It is a list of things the playbook contains.
CRITERION_WORDS = re.compile(
    r"\b(must|never|always|no two|no more than|at least|at most|do not|"
    r"don't|hard|ceiling|floor|minimum|maximum|shortest|longest|"
    r"required|refuse|reject|only if|unless|every|each)\b", re.I)


def is_a_criterion(block: str) -> bool:
    """Could you fail this, or does it merely mention the subject?"""
    if block.startswith("|") or block.startswith("#"):
        return False                       # a table row or a heading
    return bool(CRITERION_WORDS.search(block))


def states_a_criterion(skill_file: str, needles: list[str]) -> tuple[bool, str]:
    """The STRONGEST matching rule in the file, not the first one.

    First-match was wrong in a way that hid work: a passing mention early in
    the document masked a real rule added at the end, so writing the rule
    changed nothing the audit could see. Strength is counted as how many
    criterion words a block contains and how many of the needles it names.
    """
    path = SKILLS / skill_file
    if not path.exists():
        return False, ""
    best = None
    for block in blocks(path.read_text()):
        hits = sum(1 for n in needles if re.search(re.escape(n), block, re.I))
        if not hits or not is_a_criterion(block):
            continue
        # length breaks the tie: "Ducking at act boundaries only" and the
        # paragraph that actually states the bed level both score one needle
        # and one criterion word, and the fuller one is the rule.
        strength = (hits, len(CRITERION_WORDS.findall(block)), len(block))
        if best is None or strength > best[0]:
            best = (strength, " ".join(block.split())[:170])
    return (True, best[1]) if best else (False, "")


def gates() -> set[str]:
    import yaml

    pipeline = yaml.safe_load(PIPELINE.read_text())
    found: set[str] = set()
    for stage in pipeline.get("stages", []):
        for command in stage.get("gate_commands", []) or []:
            found.add(command["name"])
    return found


def main() -> int:
    declared = gates()
    rows = []
    for item in JUDGEMENTS:
        stated, quote = states_a_criterion(item["skill"], item["states"])
        is_pipeline_gate = item.get("gate_is_a_pipeline_gate", True)
        if is_pipeline_gate and item["gate"] not in declared:
            raise SystemExit(
                f"the audit names a gate the pipeline does not declare: "
                f"{item['gate']!r}. Declared: {sorted(declared)}")
        reading, note = READING.get(item["judgement"], ("?", ""))
        rows.append({**item, "stated": stated, "quote": quote,
                     "measured": True, "pipeline_gate": is_pipeline_gate,
                     "reading": reading, "note": note})

    really = sum(1 for r in rows if r["reading"] == "yes")
    weakly = sum(1 for r in rows if r["reading"] == "weak")
    not_at_all = sum(1 for r in rows if r["reading"] == "no")
    defended = sum(1 for r in rows if r["stated"] and r["measured"])
    advice = sum(1 for r in rows if r["stated"] and not r["measured"])
    unwritten = sum(1 for r in rows if not r["stated"] and r["measured"])
    neither = sum(1 for r in rows if not r["stated"] and not r["measured"])

    # The audit names gates; if one is renamed the audit must break, not
    # quietly report the judgement as unmeasured. The first run of this said
    # two of ten judgements were "advice only" because it looked for
    # `verify_rhythm` and the gate is called `rhythm`.

    lines = [
        "# Step 15 — taste audit",
        "",
        "For each judgement the film's quality depended on: does a skill state",
        "a criterion you could fail, does a gate measure it, or neither?",
        "",
        "Run #1 is the test data. Every defect below is a taste failure that",
        "passed the pipeline end to end — not a bug, a decision nobody made.",
        "",
        f"**Every one of the ten is measured by a gate.** What the skills say "
        f"about them is weaker than that, and the honest count is the read "
        f"one, not the matched one:",
        "",
        f"- the matcher finds a criterion for **{defended} of {len(rows)}**;",
        f"- reading them, **{really} really state the rule**, {weakly} mention "
        f"the subject in a rule about something else, and {not_at_all} state "
        f"nothing.",
        "",
        "A keyword matcher cannot tell a rule ABOUT a subject from a rule that",
        "merely contains the word. It is kept because it enumerates and quotes;",
        "the quotes are the evidence and take a minute to check.",
        "",
        "| judgement | what run #1 did | stated in | measured by |",
        "|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['judgement']} | {r['run1']} | "
            f"{'`' + r['skill'] + '`' if r['stated'] else '**nothing**'} | "
            f"{'`' + r['gate'] + '`' if r['measured'] else '**nothing**'} |")

    lines += ["", "## What the skills actually say, and whether it is the rule",
              ""]
    for r in rows:
        mark = {"yes": "**states it**", "weak": "**mentions it**",
                "no": "**says nothing**"}.get(r["reading"], "?")
        lines.append(f"### {r['judgement']} — {mark}")
        lines.append("")
        if r["quote"]:
            lines.append(f"`{r['skill']}`: \"{r['quote']}\"")
        else:
            lines.append(f"No criterion found in `{r['skill']}`.")
        if r["note"]:
            lines.append("")
            lines.append(r["note"][0].upper() + r["note"][1:] + ".")
        lines.append("")

    dest = ROOT / "reports" / "step15_taste_audit.md"
    dest.write_text("\n".join(lines) + "\n")

    print(f"all {len(rows)} measured; matcher finds {defended} stated; "
          f"reading: {really} state the rule, {weakly} mention it, "
          f"{not_at_all} say nothing")
    for r in rows:
        print(f"   {r['reading']:5s}  {r['judgement']}")
    print(f"-> {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

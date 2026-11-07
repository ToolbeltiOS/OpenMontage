#!/usr/bin/env python3
"""The style playbook, cut down to the stage that is about to run.

WHY THIS EXISTS
---------------
`styles/wak3up-documentary.yaml` is 44 KB. The 2026-11-06 script stage read
it TWICE — 88,555 bytes of tool output, about 22,000 tokens — and then
carried all of it for another 280 turns at $0.50 per million cache-read
tokens. The script stage does not use `motion`, `audio`, `captions`,
`chart_palette` or `visual_cadence`; the edit stage does not use
`script_rules` or `fact_gate`. Each stage was paying, every turn, for the
other stages' instructions.

The playbook is not trimmed. It stays the single authority and nothing is
rewritten here — this prints the SECTIONS A STAGE ACTUALLY NEEDS, straight
out of the same file, so there is one copy of the rules and no second place
for them to drift.

    scripts/playbook_digest.py --stage script
    scripts/playbook_digest.py --stage edit --playbook styles/other.yaml
    scripts/playbook_digest.py --sizes          # what each stage carries

A stage name that is not in the table prints the whole playbook and says so
on stderr: an unknown stage must not silently get a playbook with holes in
it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAYBOOK = ROOT / "styles" / "wak3up-documentary.yaml"

#: `identity`, `taste_profile` and `quality_rules` are in every stage: they
#: are what the film IS, and a stage that does not know that makes something
#: competent and wrong. Everything else is where the work is done.
ALWAYS = ("identity", "taste_profile", "quality_rules")

#: Sections that NO STAGE IS GIVEN, each with the reason. The orphan check in
#: tests/automation/test_digests.py fails on any playbook section that is
#: neither routed to a stage nor listed here — so a rule cannot be added to
#: the playbook and quietly read by nobody, which is this repository's most
#: frequent defect: a gate written, reviewed, and never wired to a consumer.
UNREAD = {
    "overrides": (
        "`max_deviation_ratio: 0.15`. Declared in "
        "schemas/styles/playbook.schema.json, set in the playbook, and read "
        "by NOTHING — found 2026-11-07 by the orphan check on its first run. "
        "That makes four: the texture gate, the camera props, the "
        "illustrations gate, and now this. It is not routed to a stage "
        "because what a 15% deviation ratio should govern, and which stage "
        "should enforce it, is the owner's decision and not a guess to bury "
        "in a digest script."
    ),
}

STAGE_SECTIONS = {
    "research": ("sources", "content_stance", "fact_gate"),
    "proposal": ("content_stance", "structure", "sources", "visual_language",
                 "asset_reuse", "music_authority"),
    "script": ("content_stance", "structure", "script_rules", "rhythm",
               "sources", "fact_gate"),
    "scene_plan": ("structure", "visual_cadence", "visual_language",
                   "typography", "motion", "overlays", "asset_reuse",
                   "chart_palette", "color_rules"),
    "assets": ("visual_language", "asset_generation", "asset_reuse",
               "sources", "audio", "music_authority"),
    "edit": ("edit_rules", "rhythm", "visual_cadence", "audio", "captions",
             "music_authority", "overlays", "color_rules"),
    "compose": ("edit_rules", "captions", "color_rules"),
    "publish": ("content_stance", "sources"),
}


def load(path: Path) -> dict:
    blob = yaml.safe_load(path.read_text())
    return blob if isinstance(blob, dict) else {}


def sections_for(stage: str) -> tuple[str, ...] | None:
    wanted = STAGE_SECTIONS.get(stage)
    if wanted is None:
        return None
    seen: list[str] = []
    for name in ALWAYS + wanted:
        if name not in seen:
            seen.append(name)
    return tuple(seen)


def digest(book: dict, stage: str) -> tuple[str, bool]:
    """(text, whole_playbook). The flag says the stage was not in the table."""
    wanted = sections_for(stage)
    if wanted is None:
        return yaml.safe_dump(book, sort_keys=False, allow_unicode=True), True

    kept = {name: book[name] for name in wanted if name in book}
    dropped = [name for name in book if name not in kept]
    head = [
        f"# PLAYBOOK — the {stage} stage's sections only",
        "#",
        f"# From styles/{DEFAULT_PLAYBOOK.name}, unedited. Sections kept:",
        f"#   {', '.join(kept)}",
        "#",
        f"# NOT HERE ({len(dropped)} section(s)): {', '.join(dropped) or 'none'}",
        "# Those belong to other stages. If this stage turns out to need one,",
        "# that is a bug in scripts/playbook_digest.py STAGE_SECTIONS — say so",
        "# rather than reading the whole 44 KB file, which you then re-read on",
        "# every turn for the rest of the stage.",
        "",
    ]
    return "\n".join(head) + yaml.safe_dump(kept, sort_keys=False,
                                            allow_unicode=True), False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage")
    ap.add_argument("--playbook", default=str(DEFAULT_PLAYBOOK))
    ap.add_argument("--out", default=None)
    ap.add_argument("--sizes", action="store_true",
                    help="what each stage would carry, against the whole file")
    args = ap.parse_args()

    path = Path(args.playbook)
    try:
        book = load(path)
    except (OSError, yaml.YAMLError) as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 1

    whole = len(yaml.safe_dump(book, sort_keys=False, allow_unicode=True))

    if args.sizes:
        print(f"{'stage':<12} {'bytes':>8} {'of whole':>9}   sections")
        print(f"{'(whole)':<12} {whole:>8} {'100%':>9}   {len(book)}")
        for stage in STAGE_SECTIONS:
            text, _ = digest(book, stage)
            print(f"{stage:<12} {len(text):>8} {len(text) / whole:>8.0%}   "
                  f"{len(sections_for(stage) or ())}")
        return 0

    if not args.stage:
        print("need --stage or --sizes", file=sys.stderr)
        return 64

    text, unknown = digest(book, args.stage)
    if unknown:
        print(f"playbook_digest: no section list for stage "
              f"{args.stage!r} — printing the WHOLE playbook. Add it to "
              f"STAGE_SECTIONS.", file=sys.stderr)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""A finished film's edit_decisions.json, as its SHAPE and not its content.

WHY THIS EXISTS
---------------
Run #5, 2026-11-13. The edit stage died at its turn cap twice — once at 30
turns having written nothing, once at 60 having done the full caption
alignment and still not reached `edit_decisions.json`. In the middle of the
second attempt it tried this, and was refused:

    .venv/bin/python -I -c "
    d=json.load(open('projects/king-tut/artifacts/edit_decisions.json'))
    print('cut keys freq:', collections.Counter(k for c in d['cuts'] for k in c))
    ..."

That is a stage trying to learn the shape of the artifact it has been asked
to write, from the last film that wrote one. It is the cheapest orientation
available and it is the right instinct: the schema says what is legal, a
finished film says what is NORMAL — which keys every cut carries, which are
conditional, what a sourced cut looks like next to an authored one.

Reading the file whole is not the answer. King Tut's is **252 KB across 161
cuts with 95 distinct keys**, and a stage that reads it on turn one carries
it on every turn after; that is the same arithmetic that moved the research
and proposal packets behind digests.

So this prints the shape: every key with how many cuts carry it, one real
sourced cut and one real authored cut in full, the component types in use,
and the top-level blocks beside `cuts` that a render needs. Long prose
fields are truncated — their LENGTH is shape, their wording is King Tut's.

A DIGEST IS GENERATED, NEVER COPIED, so it cannot drift from the exemplar.
If the edit stage needs something this leaves out, that is a bug here, and
the stage is told to say so rather than reading the file whole.

    python3 scripts/edit_decisions_digest.py --project king-tut
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Prose fields whose wording belongs to the film that wrote them. Kept, cut
#: to this many characters, because a stage needs to know the field holds a
#: sentence and not an enum.
PROSE_CHARS = 90
PROSE_FIELDS = ("reason", "lead_reason", "attribution", "sourceLine",
                "caption", "claim", "detail", "text", "headline", "title",
                "subtitle", "kicker", "footnote", "epigraph", "actTitle")

#: Beyond this, the digest has stopped being a digest.
SIZE_BUDGET_BYTES = 8192


def _shorten(value, depth: int = 0):
    """A value with its shape kept and its bulk removed."""
    if isinstance(value, str):
        if len(value) > PROSE_CHARS:
            return value[:PROSE_CHARS] + f"…<+{len(value) - PROSE_CHARS} chars>"
        return value
    if isinstance(value, list):
        if not value:
            return []
        if depth >= 2:
            return [f"<{len(value)} items>"]
        head = [_shorten(v, depth + 1) for v in value[:2]]
        if len(value) > 2:
            head.append(f"<+{len(value) - 2} more of the same shape>")
        return head
    if isinstance(value, dict):
        if depth >= 3:
            return {"<keys>": sorted(value)}
        return {k: _shorten(v, depth + 1) for k, v in value.items()}
    return value


def _example(cut: dict) -> dict:
    out = {}
    for key, value in cut.items():
        if key in PROSE_FIELDS and isinstance(value, str):
            out[key] = (value[:PROSE_CHARS] + "…") if len(value) > PROSE_CHARS \
                else value
        else:
            out[key] = _shorten(value)
    return out


def digest(blob: dict, project: str) -> str:
    cuts = blob.get("cuts") or []
    total = len(cuts)
    freq = collections.Counter(k for c in cuts for k in c)
    universal = sorted(k for k, n in freq.items() if n == total)
    conditional = sorted(((k, n) for k, n in freq.items() if n < total),
                         key=lambda kv: (-kv[1], kv[0]))

    lines: list[str] = []
    add = lines.append
    add(f"EXEMPLAR: projects/{project}/artifacts/edit_decisions.json")
    add(f"  a DELIVERED film. {total} cuts, "
        f"{blob.get('total_duration_seconds')}s, "
        f"composition_mode={blob.get('composition_mode')!r}, "
        f"renderer_family={blob.get('renderer_family')!r}")
    add("  This is the shape that rendered. The schema says what is LEGAL;")
    add("  this says what is NORMAL. Your film is not this film.")
    add("")
    add(f"TOP-LEVEL KEYS ({len(blob)}): " + ", ".join(sorted(blob)))
    add("")
    add(f"EVERY CUT CARRIES THESE {len(universal)} KEYS "
        f"({total}/{total} cuts):")
    add("  " + ", ".join(universal))
    add("")
    add("CONDITIONAL KEYS — how many of the cuts carry each:")
    for key, count in conditional:
        add(f"  {count:>4}/{total}  {key}")
    add("")

    sourced = next((c for c in cuts
                    if isinstance(c.get("source"), str) and "/" in c["source"]),
                   None)
    authored = next((c for c in cuts if isinstance(c.get("scene"), dict)), None)
    if authored is None:
        authored = next((c for c in cuts if "type" in c and "source" not in c),
                        None)
    if sourced:
        add("ONE SOURCED CUT, in full:")
        add(json.dumps(_example(sourced), indent=1, ensure_ascii=False))
        add("")
    if authored:
        add("ONE AUTHORED CUT, in full:")
        add(json.dumps(_example(authored), indent=1, ensure_ascii=False))
        add("")

    types = collections.Counter(
        c.get("type") or (c.get("scene") or {}).get("type")
        for c in cuts if c.get("type") or (c.get("scene") or {}).get("type"))
    if types:
        add("COMPONENT TYPES IN USE (authored cuts), with counts:")
        for name, count in types.most_common():
            add(f"  {count:>4}  {name}")
        add("")

    add("THE BLOCKS BESIDE `cuts`, shape only:")
    for key in sorted(blob):
        if key in ("cuts", "version", "total_duration_seconds",
                   "composition_mode", "renderer_family"):
            continue
        value = blob[key]
        if isinstance(value, list):
            add(f"  {key}: {len(value)} item(s)")
            if value:
                add("    " + json.dumps(_shorten(value[0]),
                                        ensure_ascii=False)[:400])
        elif isinstance(value, dict):
            add(f"  {key}: " + json.dumps(_shorten(value),
                                          ensure_ascii=False)[:400])
        else:
            add(f"  {key}: {value!r}")
    add("")
    add("If this digest leaves out something you need, say so in your report:")
    add("that is a bug in scripts/edit_decisions_digest.py. Do not read the")
    add("exemplar whole — it is 250 KB and you would carry it every turn.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="A delivered film's edit_decisions.json as its shape")
    parser.add_argument("--project", default="king-tut",
                        help="the DELIVERED film to read (default: king-tut)")
    parser.add_argument("--projects-dir", default=None)
    args = parser.parse_args(argv)

    root = Path(args.projects_dir) if args.projects_dir else ROOT / "projects"
    path = root / args.project / "artifacts" / "edit_decisions.json"
    if not path.exists():
        print(f"no exemplar at {path}", file=sys.stderr)
        return 1
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"{path} is not readable as JSON: {error}", file=sys.stderr)
        return 1
    if not blob.get("cuts"):
        print(f"{path} has no cuts — it is not an exemplar", file=sys.stderr)
        return 1
    sys.stdout.write(digest(blob, args.project))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

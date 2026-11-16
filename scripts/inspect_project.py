#!/usr/bin/env python3
"""Look at a film's artifacts without reading them whole.

WHY A TOOL AND NOT `cat`
------------------------
A stage needs to see a DELIVERED film to know what normal looks like — the
edit director says so in as many words, and the schema says what is legal
while an exemplar says what is usual. But the artifacts are 329 KB of
scene_plan, 288 KB of edit_decisions and 425 KB of render_props on a real
film, and a stage that reads one whole pays 80–110 K tokens for it on every
later turn. So the contract tells stages to read a SLICE, with python, never
`cat` — and then every stage invents its own slicing one-liner, each of
which is a new shape of Bash call for the guard to judge.

The allow list grew one entry per incident that way. This is the entry
point instead: three questions, one name, already covered by
`Bash(scripts/:*)`, so looking at a prior film needs no new permission and
no improvised program.

    inspect_project.py artifacts <project>
        what this film has, with sizes and the shape of each

    inspect_project.py show <project> <artifact> [--path k.k.k] [--limit N]
        one slice of one artifact, truncated on purpose

    inspect_project.py scenes <project>
        how many scenes, cuts and act spans, and the runtime they imply

Nothing here writes. It is the read half of a stage's curiosity.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: How much of a slice to print. A stage that wants more should ask a
#: narrower question — the point of this tool is to not carry a quarter of a
#: megabyte on every later turn.
DEFAULT_LIMIT = 4000


def artifacts_dir(project: str, root: Path) -> Path:
    path = root / "projects" / project / "artifacts"
    if not path.is_dir():
        raise SystemExit(
            f"no artifacts for {project!r} at {path}. "
            f"`inspect_project.py artifacts <project>` on a film that exists "
            f"will list what is there.")
    return path


def shape(blob: Any, depth: int = 0) -> str:
    """One line saying what a thing IS, without printing it."""
    if isinstance(blob, dict):
        keys = list(blob)
        inner = ", ".join(keys[:8]) + (", …" if len(keys) > 8 else "")
        return f"object({len(keys)}) {{{inner}}}"
    if isinstance(blob, list):
        if not blob:
            return "list(0)"
        return f"list({len(blob)}) of {shape(blob[0], depth + 1)}"
    if isinstance(blob, str):
        return f"string({len(blob)})"
    return type(blob).__name__


def cmd_artifacts(args, root: Path) -> int:
    where = artifacts_dir(args.project, root)
    rows = sorted(where.glob("*.json"))
    if not rows:
        print(f"{args.project}: no artifacts yet")
        return 0
    print(f"{args.project}: {len(rows)} artifact(s) in {where.relative_to(root)}")
    for path in rows:
        size = path.stat().st_size
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
            detail = shape(blob)
        except Exception as error:                            # noqa: BLE001
            detail = f"UNREADABLE ({type(error).__name__})"
        print(f"  {size:>9,}  {path.stem:<22}  {detail}")
    return 0


def dig(blob: Any, path: str) -> Any:
    """`a.b.3.c` through dicts and lists, saying where it gave up."""
    here: Any = blob
    for step in [p for p in path.split(".") if p]:
        if isinstance(here, list):
            if not step.lstrip("-").isdigit():
                raise SystemExit(
                    f"{step!r} is not an index, and this is a "
                    f"list({len(here)})")
            here = here[int(step)]
        elif isinstance(here, dict):
            if step not in here:
                near = ", ".join(list(here)[:10])
                raise SystemExit(
                    f"no {step!r} here. What is: {near}")
            here = here[step]
        else:
            raise SystemExit(f"cannot go into a {type(here).__name__} "
                             f"looking for {step!r}")
    return here


def cmd_show(args, root: Path) -> int:
    where = artifacts_dir(args.project, root)
    path = where / f"{args.artifact}.json"
    if not path.exists():
        names = ", ".join(sorted(p.stem for p in where.glob("*.json")))
        raise SystemExit(f"no {args.artifact}.json for {args.project}. "
                         f"It has: {names}")
    blob = json.loads(path.read_text(encoding="utf-8"))
    chosen = dig(blob, args.path) if args.path else blob
    print(f"{args.project}/{args.artifact}"
          + (f" at {args.path}" if args.path else "")
          + f" — {shape(chosen)}")
    text = json.dumps(chosen, indent=1, ensure_ascii=False)
    if len(text) > args.limit:
        print(text[:args.limit])
        print(f"… truncated at {args.limit} of {len(text)} characters. "
              f"Ask a narrower --path rather than raising --limit: a stage "
              f"that reads a whole artifact carries it on every later turn.")
    else:
        print(text)
    return 0


def cmd_scenes(args, root: Path) -> int:
    where = artifacts_dir(args.project, root)

    def load(name: str) -> dict | None:
        path = where / f"{name}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:                                     # noqa: BLE001
            return None

    print(f"{args.project}:")
    plan = load("scene_plan")
    if plan is not None:
        scenes = plan.get("scenes") or []
        print(f"  scene_plan     {len(scenes)} scene(s)")
        if scenes:
            last = scenes[-1]
            end = last.get("out_seconds") or last.get("end_seconds")
            if isinstance(end, (int, float)):
                print(f"                 ends at {end:.1f}s "
                      f"({end / 60:.1f} min)")

    for name in ("edit_decisions", "render_props"):
        blob = load(name)
        if blob is None:
            continue
        cuts = blob.get("cuts") or []
        kinds: dict[str, int] = {}
        for cut in cuts:
            kind = cut.get("type") or (cut.get("scene") or {}).get("type") \
                or ("authored" if cut.get("scene") else "sourced")
            kinds[str(kind)] = kinds.get(str(kind), 0) + 1
        print(f"  {name:<14} {len(cuts)} cut(s), "
              f"{len(kinds)} kind(s)")
        for kind, n in sorted(kinds.items(), key=lambda kv: -kv[1])[:12]:
            print(f"                 {n:>4}  {kind}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=None,
                    help="the tree the project lives under (default: here)")
    sub = ap.add_subparsers(dest="command", required=True)

    one = sub.add_parser("artifacts", help="what a film has")
    one.add_argument("project")

    two = sub.add_parser("show", help="one slice of one artifact")
    two.add_argument("project")
    two.add_argument("artifact")
    two.add_argument("--path", default="",
                     help="dotted path, e.g. cuts.0 or music.beds")
    two.add_argument("--limit", type=int, default=DEFAULT_LIMIT)

    three = sub.add_parser("scenes", help="how many scenes and cuts")
    three.add_argument("project")

    args = ap.parse_args(argv)
    root = Path(args.root) if args.root else ROOT
    return {"artifacts": cmd_artifacts, "show": cmd_show,
            "scenes": cmd_scenes}[args.command](args, root)


if __name__ == "__main__":
    raise SystemExit(main())

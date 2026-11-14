#!/usr/bin/env python3
"""The CLI the runner calls after a stage ends. See lib/checkpoint_reconcile.

    .venv/bin/python scripts/reconcile_checkpoint.py \
        --project king-tut --stage scene_plan

Exit 0: the artifact validates and a checkpoint matching it is on disk —
written or rewritten here if it had to be. The run carries on.
Exit 1: the artifact is missing or invalid, or the stage is one this step is
not entitled to touch. The run stops, and stdout says why.

Nothing here decides whether a stage OVERRAN. That is the runner's business.
This only answers: is there a valid artifact, and does the bookkeeping match
it? Which is the question that should have cancelled or saved run #5, and
did neither.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# ROOT, not ROOT/lib: lib/checkpoint.py imports `schemas`, which only
# resolves from the repository root. Same as scripts/write_checkpoint.py.
sys.path.insert(0, str(ROOT))

from lib import checkpoint_reconcile as R  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile a stage's checkpoint with its artifact")
    parser.add_argument("--project", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--projects-dir", default=None)
    parser.add_argument("--quiet", action="store_true",
                        help="print the verdict word only")
    args = parser.parse_args(argv)

    projects_dir = Path(args.projects_dir) if args.projects_dir \
        else ROOT / "projects"
    rc, verdict, lines = R.reconcile(projects_dir, args.project, args.stage)
    if args.quiet:
        print(verdict)
    else:
        print(f"reconcile: {verdict}")
        for line in lines:
            print(f"  {line}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Write a stage's checkpoint. The command every stage is told to run.

WHY THIS EXISTS
---------------
`lib/checkpoint.py` had no command line. It is a library — `init_project`,
`write_checkpoint`, `validate_checkpoint` — and nothing in the production
path called `init_project` at all; only the Backlot simulation scripts did.

Meanwhile `run_weekly.sh`'s stage preamble instructs every stage to "write
your checkpoint `completed` with human_approved=True", and a stage that does
not leave a checkpoint is a stage the next one rebuilds.

So each stage had to reach for the library itself, and a library call is a
program. The 2026-11-11 rehearsal shows what that costs: the research stage
finished its brief at transcript turn 44 of 62 — 33 data points, every one
with an id and a source_url — and then spent turns 46 to 62, 27% of the
stage, failing to write a checkpoint. It tried
`cat > /tmp/wrck_$$.py <<'PYEOF'` (denied), then authored
`projects/<slug>/write_checkpoint_once.py`, then hit its cap having never
written one.

It was not breaking the rules. `docs/STAGE_CONTRACT.md` says a throwaway
script in `projects/<slug>/` is acceptable WHEN NOTHING FITS, and nothing
did. This is what fits.

WHAT IT DOES THAT A STAGE SHOULD NOT HAVE TO
--------------------------------------------
Initialises the project if `project.json` is missing, because the first
stage of every run would otherwise have to call `init_project` itself; it is
idempotent, so later stages pay nothing. Resolves an artifact NAME to the
file the pipeline already writes it to. Adds the stage's canonical artifact
when it exists and was not named, because forgetting it is a validation
error the stage would then have to read and understand. Validates, and
REFUSES with the validator's own message rather than writing something the
next stage cannot read.

    .venv/bin/python scripts/write_checkpoint.py --project king-tut \
        --stage research --artifact research_brief --human-approved

    .venv/bin/python scripts/write_checkpoint.py --project king-tut \
        --stage proposal --artifact proposal_packet --artifact decision_log \
        --human-approved
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.checkpoint import (  # noqa: E402
    CANONICAL_STAGE_ARTIFACTS, CheckpointValidationError, init_project,
    write_checkpoint)

DEFAULT_PIPELINE = "narrated-documentary"
DEFAULT_PLAYBOOK = "wak3up-documentary"


def artifact_path(project_dir: Path, spec: str) -> tuple[str, Path]:
    """`name` or `name=path`. A bare name is where the pipeline puts it."""
    if "=" in spec:
        name, _, raw = spec.partition("=")
        return name.strip(), Path(raw.strip())
    name = spec.strip()
    return name, project_dir / "artifacts" / f"{name}.json"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Write a stage checkpoint (the CLI for lib/checkpoint.py)")
    ap.add_argument("--project", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--artifact", action="append", default=[],
                    metavar="NAME[=PATH]",
                    help="repeatable; a bare NAME resolves to "
                         "projects/<project>/artifacts/NAME.json")
    ap.add_argument("--status", default="completed",
                    choices=["completed", "awaiting_human", "failed",
                             "in_progress"])
    ap.add_argument("--human-approved", action="store_true",
                    help="the ONLY human gate is the script gate and it is "
                         "handled outside the stage, so a stage writing its "
                         "own checkpoint passes this")
    ap.add_argument("--human-approval-required", action="store_true")
    ap.add_argument("--error", default=None)
    ap.add_argument("--title", default=None,
                    help="only used when project.json does not exist yet")
    ap.add_argument("--pipeline-type", default=None)
    ap.add_argument("--style-playbook", default=None)
    ap.add_argument("--projects-dir", default=None)
    args = ap.parse_args()

    projects_dir = Path(args.projects_dir) if args.projects_dir \
        else ROOT / "projects"
    project_dir = projects_dir / args.project
    marker = project_dir / "project.json"

    # ── the project itself, if nobody has made it ────────────────────────
    existing = json.loads(marker.read_text()) if marker.exists() else {}
    pipeline_type = (args.pipeline_type or existing.get("pipeline_type")
                     or DEFAULT_PIPELINE)
    if not marker.exists():
        title = args.title or args.project.replace("-", " ").title()
        init_project(args.project, title=title, pipeline_type=pipeline_type,
                     pipeline_dir=projects_dir,
                     style_playbook=args.style_playbook or DEFAULT_PLAYBOOK)
        print(f"initialised projects/{args.project} ({title!r})")

    # ── the artifacts ────────────────────────────────────────────────────
    specs = list(args.artifact)
    canonical = CANONICAL_STAGE_ARTIFACTS.get(args.stage)
    named = {artifact_path(project_dir, s)[0] for s in specs}
    if (canonical and canonical not in named
            and args.status in {"completed", "awaiting_human"}):
        # Forgetting it is a validation error the stage would have to read
        # and work out. If the file is there, it was meant.
        if (project_dir / "artifacts" / f"{canonical}.json").exists():
            specs.append(canonical)
            print(f"adding the canonical artifact for {args.stage!r}: "
                  f"{canonical}")

    artifacts: dict[str, object] = {}
    for spec in specs:
        name, path = artifact_path(project_dir, spec)
        if not path.exists():
            print(f"REFUSED: no artifact {name!r} at {path}", file=sys.stderr)
            return 2
        try:
            artifacts[name] = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            print(f"REFUSED: {path} is not valid JSON: {exc}", file=sys.stderr)
            return 2

    # ── write it, or refuse with the validator's own words ───────────────
    try:
        out = write_checkpoint(
            projects_dir, args.project, args.stage, args.status, artifacts,
            pipeline_type=pipeline_type,
            style_playbook=args.style_playbook or existing.get(
                "style_playbook") or DEFAULT_PLAYBOOK,
            human_approval_required=args.human_approval_required,
            human_approved=args.human_approved,
            error=args.error)
    except CheckpointValidationError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        print("Nothing was written. Fix the artifact and run this again — a "
              "checkpoint the next stage cannot read is worse than none.",
              file=sys.stderr)
        return 1
    except Exception as exc:                                   # noqa: BLE001
        print(f"REFUSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    rel = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"{args.stage}: {args.status}  ->  {rel}")
    print(f"  artifacts: {', '.join(sorted(artifacts)) or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

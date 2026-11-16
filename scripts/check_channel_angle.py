#!/usr/bin/env python3
"""The channel's angle, checked at whichever stage just finished.

    scripts/check_channel_angle.py --project <id> --stage research
    scripts/check_channel_angle.py --project <id> --stage proposal
    scripts/check_channel_angle.py --project <id> --stage script

Exit 0: this stage holds the angle.
Exit 1: it does not, and stdout says how.
Exit 3: RESEARCH ONLY — this TOPIC has no angle to find. Distinct because
        the runner's answer to it is different: not "fix the stage" but
        "take the next topic", and a shell cannot tell those apart from a
        message. See lib/verify_channel_angle.MIN_DISPUTED.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

from lib import verify_channel_angle as A  # noqa: E402

#: The research failure the runner must treat as a topic problem rather than
#: a stage problem.
NO_ANGLE_IN_THE_TOPIC = 3


def load(project: str, name: str, root: Path = ROOT) -> dict:
    path = root / "projects" / project / "artifacts" / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"no {name}.json for {project} at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--stage", required=True,
                    choices=("research", "proposal", "script"))
    ap.add_argument("--backend", default="capitalisation",
                    help="proper-noun backend for the script lint; spacy is "
                         "better and slower")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default=None,
                    help="the tree the project lives under (default: this "
                         "repo), so a dev checkout can read the runner's")
    args = ap.parse_args(argv)

    root = Path(args.root) if args.root else ROOT
    brief = load(args.project, "research_brief", root)
    if args.stage == "research":
        problems, measured = A.check_brief(brief)
    elif args.stage == "proposal":
        problems, measured = A.check_proposal(
            load(args.project, "proposal_packet", root), brief)
    else:
        problems, measured = A.check_script(
            load(args.project, "script", root), brief, args.backend)

    if args.json:
        print(json.dumps({"stage": args.stage, "problems": problems,
                          "measured": measured}, indent=1))
    else:
        print(f"channel angle, {args.stage}: "
              f"{'PASS' if not problems else 'FAIL'}")
        for key, value in measured.items():
            if key != "per_section":
                print(f"  {key}: {value}")
        for problem in problems:
            print(f"  FAIL: {problem}")

    if not problems:
        return 0
    if args.stage == "research" and measured.get("topic_has_no_angle"):
        # Only this one is worth a new topic. A brief that HOLDS contested
        # claims and fails to name them is a stage that did not finish, and
        # the next topic would not fix it.
        print(f"\nthis is a TOPIC problem, not a stage problem: "
              f"{measured.get('contested_claims')} contested claim(s) in the "
              f"whole brief against {A.MIN_DISPUTED}. Take the next topic.")
        return NO_ANGLE_IN_THE_TOPIC
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Does this act read like speech? Run it AS THE ACT IS WRITTEN.

The companion to `scripts/check_claims.py`: that one asks whether the act's
facts hold up, this one asks whether a voice can say it. They are separate
because they fail for different reasons and are fixed by different edits,
and because the fact gate is deliberately left alone — a sourcing check
that also had opinions about sentence length would be two gates in a coat.

See `lib/script_cadence.py` for what the three numbers are and why they are
a floor rather than a target.

    python3 scripts/check_cadence.py --project king-tut --section act1
    python3 scripts/check_cadence.py --project king-tut
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import script_cadence as SC  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--section", action="append", default=[],
                    help="only these section ids (default: all)")
    ap.add_argument("--script", default=None,
                    help="default: projects/<film>/artifacts/script.json")
    args = ap.parse_args()

    path = (Path(args.script) if args.script
            else ROOT / "projects" / args.project / "artifacts" / "script.json")
    script = json.loads(path.read_text())

    problems, rows = SC.check_script(script, args.section or None)
    if not rows:
        print("no sections selected", file=sys.stderr)
        return 2

    print(f"{'section':22s} {'sents':>5s} {'mean':>6s} {'<8w':>6s} "
          f"{'long':>5s}  {'?':>2s} {'—':>2s}")
    for m in rows:
        flag = "" if m["sentences"] else "  (no narration)"
        enforced = "" if m.get("short_fraction_enforced", True) else "*"
        print(f"{m['id']:22s} {m['sentences']:5d} {m['mean']:6.2f} "
              f"{m['short_fraction']:5.0%}{enforced} {m['longest']:5d} "
              f"{m['questions']:2d} {m['dashes']:2d}{flag}")
    if any(not m.get("short_fraction_enforced", True) for m in rows):
        print(f"  * fewer than {SC.MIN_SENTENCES} sentences — the "
              f"short-sentence fraction is reported, not enforced")

    said = sum(m["sentences"] for m in rows)
    if said:
        total_mean = sum(m["mean"] * m["sentences"] for m in rows) / said
        print(f"\nwhole script: {said} sentences, mean {total_mean:.2f} words")

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print(f"  · {p}")
        return 1
    print("\ncadence ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

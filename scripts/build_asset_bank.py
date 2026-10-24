#!/usr/bin/env python3
"""Build a project's Wikimedia asset bank from its bank_subjects spec.

A thin, auditable front door on `lib/asset_bank.build`, which is already
parameterised by subjects / out_dir / bank_path but was only ever called from
an ad-hoc `python -c` during run #1. The bank is the backbone of the amended
visual mix — measured Commons holdings for this subject are stills, not
footage — so the call that produces it belongs in the repository.

Throttled at one API call every three seconds by lib/asset_bank; a ten-subject
build is tens of minutes, not seconds. Errors are surfaced by that module
rather than absorbed, so a category that comes back empty comes back loudly.

    .venv/bin/python scripts/build_asset_bank.py --project easter-island --top-n 12
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

from asset_bank import build  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--top-n", type=int, default=8,
                    help="assets kept per subject (a larger pool is downloaded)")
    ap.add_argument("--spec", default=None,
                    help="defaults to the project's artifacts/bank_subjects.json")
    ap.add_argument("--out-dir", default=None,
                    help="defaults to the project's assets/images/bank")
    ap.add_argument("--subjects", nargs="*",
                    help="only these subjects from the spec")
    ap.add_argument("--bank", default=None,
                    help="bank json to write; defaults to artifacts/asset_bank.json")
    ap.add_argument("--pool-n", type=int, default=None,
                    help="candidates downloaded per subject before selection; "
                         "top-n cannot exceed it")
    ap.add_argument("--max-per-series", type=int, default=None,
                    help="files one upload session may contribute. The default "
                         "of 3 keeps a bank from being one photographer's "
                         "afternoon; a subject with few contributors needs it "
                         "raised or it comes back short.")
    ap.add_argument("--min-long-edge", type=int, default=None,
                    help="override lib/asset_bank's bankable size floor. The "
                         "3000px default assumes a push and a derived crop are "
                         "both wanted. A century-old plate has no larger "
                         "version anywhere, so for archival subjects the floor "
                         "is lowered to what fills the 1920px canvas and those "
                         "slots take a lock or a small move instead.")
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    spec = Path(args.spec) if args.spec else project / "artifacts" / "bank_subjects.json"
    out_dir = (Path(args.out_dir).resolve() if args.out_dir
               else project / "assets" / "images" / "bank")
    bank_path = (Path(args.bank).resolve() if args.bank
                 else project / "artifacts" / "asset_bank.json")

    # A spec may carry comment keys. `_why` next to ten subjects is where the
    # reason for an unusual pass belongs, and build() iterates every key.
    subjects = {k: v for k, v in json.loads(spec.read_text()).items()
                if not k.startswith("_")}
    if args.subjects:
        subjects = {k: v for k, v in subjects.items() if k in args.subjects}
        if not subjects:
            raise SystemExit(f"none of {args.subjects} are in {spec}")
    import asset_bank
    if args.min_long_edge:
        print(f"size floor lowered from {asset_bank.MIN_BANK_LONG_EDGE} to "
              f"{args.min_long_edge} for this pass")
        asset_bank.MIN_BANK_LONG_EDGE = args.min_long_edge
    if args.pool_n:
        print(f"candidate pool raised from {asset_bank.POOL_N} to {args.pool_n}")
        asset_bank.POOL_N = args.pool_n
    if args.max_per_series:
        print(f"per-upload-session cap raised from {asset_bank.MAX_PER_SERIES} "
              f"to {args.max_per_series}")
        asset_bank.MAX_PER_SERIES = args.max_per_series
    print(f"{args.project}: {len(subjects)} subjects, top {args.top_n} each "
          f"-> {out_dir.relative_to(ROOT)}", flush=True)
    bank = build(subjects, str(out_dir), str(bank_path), top_n=args.top_n)
    kept = bank.get("assets") or bank.get("bank") or []
    print(f"\nBANK: {len(kept)} assets -> {bank_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Count what a Commons category actually holds before committing a bank build.

The bank build is throttled at one API call every three seconds, so a category
name that turns out to be a redirect, a disambiguation or empty costs real
minutes to discover inside the build. This asks first.

Prints one line per candidate: the category, how many files one level of
descent reaches, and how many of those filenames carry a subject term.

    .venv/bin/python scripts/probe_bank_categories.py --spec <subjects.json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

from asset_bank import category_files, filename_has_term  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text())
    for subject, cfg in spec.items():
        total = kept = 0
        for category in cfg["categories"]:
            files = category_files(category)
            hits = [f for f in files
                    if filename_has_term(f, cfg["terms"], cfg.get("exclude"))]
            print(f"  {category:52} {len(files):5} files  {len(hits):5} on-term",
                  flush=True)
            total += len(files)
            kept += len(hits)
        print(f"{subject}: {total} files, {kept} on-term\n", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

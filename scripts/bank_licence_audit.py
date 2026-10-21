#!/usr/bin/env python3
"""What the bank holds, and what the licence filter makes of it.

The filter is enforced at fetch time now, for every source. This reads it
backwards: every asset ALREADY in the bank, classified by the same rules, so
the cost of the rule is a number rather than an expectation.

    python scripts/bank_licence_audit.py --project <id>
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.video.stock_sources.licences import (PERMITTED, PERMITTED_EXTRA,  # noqa: E402
                                                classify)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    bank = json.loads((project / "artifacts" / "asset_bank.json").read_text())

    rows = []
    for subject, entry in bank.get("subjects", {}).items():
        for asset in entry.get("assets", []):
            raw = str(asset.get("licence") or asset.get("license") or "")
            rows.append((subject, raw, classify(raw)))

    per: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for subject, _, licence in rows:
        per[subject][0] += 1
        per[subject][1] += 1 if licence.permitted else 0

    families = Counter(licence.code for _, _, licence in rows)
    refused = Counter(raw for _, raw, licence in rows if not licence.permitted)
    kept = sum(k for _, k in per.values())

    lines = [
        f"# Bank licence audit — {args.project}",
        "",
        f"{len(rows)} assets, {kept} of them usable under the filter as it "
        f"stands. Permitted families: {', '.join(PERMITTED)}"
        + (f"; also permitted: {', '.join(PERMITTED_EXTRA)}" if PERMITTED_EXTRA else ""),
        "",
        "## By licence family", "",
        "| family | assets | permitted |",
        "|---|---|---|",
    ]
    for code, n in families.most_common():
        ok = code in PERMITTED or code in PERMITTED_EXTRA
        lines.append(f"| {code} | {n} | {'yes' if ok else '**no**'} |")

    lines += ["", "## Per subject, before and after the filter", "",
              "| subject | in the bank | usable | lost |", "|---|---|---|---|"]
    for subject, (before, after) in sorted(per.items(), key=lambda kv: -kv[1][0]):
        lost = before - after
        lines.append(f"| {subject} | {before} | {after} | "
                     f"{'**' + str(lost) + '**' if lost else '0'} |")

    if refused:
        lines += ["", "## Refused, by the string that was refused", "",
                  "| assets | licence as the source stated it | read as |",
                  "|---|---|---|"]
        for raw, n in refused.most_common():
            lines.append(f"| {n} | `{raw[:70] or '(empty)'}` | {classify(raw).code} |")

    dest = ROOT / "reports" / f"bank_licence_audit_{args.project}.md"
    dest.write_text("\n".join(lines) + "\n")

    print(f"{len(rows)} assets, {kept} usable, {len(rows) - kept} refused")
    for code, n in families.most_common():
        print(f"   {n:4d}  {code}"
              + ("" if code in PERMITTED or code in PERMITTED_EXTRA else "   REFUSED"))
    print(f"-> {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

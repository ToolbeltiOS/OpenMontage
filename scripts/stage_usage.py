#!/usr/bin/env python3
"""What a stage of the weekly film cost, from `claude -p --output-format json`.

A film's cost was invisible: the run log said a stage started and finished
and nothing about what it spent. With the turns and the wall clock in the
log, a week that takes four times as long as the one before is a question
somebody can ask on Saturday morning instead of discovering at the next
usage limit.

Also pulls out the agent's own closing report — the `result` field — so the
readable stage log survives the move to JSON output. The log was the most
useful artifact of the first attended run and switching output formats must
not cost it.

    scripts/stage_usage.py <result.json> --stage script --seconds 3380
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> dict:
    try:
        blob = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return blob if isinstance(blob, dict) else {}


def hms(seconds: float) -> str:
    seconds = int(seconds)
    if seconds >= 3600:
        return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"
    if seconds >= 60:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds}s"


def summarise(blob: dict, stage: str, seconds: float, attempt: int) -> dict:
    usage = blob.get("usage") or {}
    return {
        "stage": stage,
        "attempt": attempt,
        "wall_seconds": round(seconds, 1),
        "wall": hms(seconds),
        "turns": blob.get("num_turns"),
        "api_seconds": round((blob.get("duration_api_ms") or 0) / 1000.0, 1),
        "cost_usd": blob.get("total_cost_usd"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_read_tokens": usage.get("cache_read_input_tokens"),
        "cache_write_tokens": usage.get("cache_creation_input_tokens"),
        "is_error": blob.get("is_error"),
        "subtype": blob.get("subtype"),
        "session_id": blob.get("session_id"),
        # A stage that quietly could not run a command is the defect that
        # cost the first attended run; it is worth a column of its own.
        "permission_denials": len(blob.get("permission_denials") or []),
    }


def line(row: dict) -> str:
    bits = [f"{row['stage']}"]
    if row["attempt"] > 1:
        bits.append(f"attempt {row['attempt']}")
    bits.append(f"{row['wall']} wall")
    if row["turns"] is not None:
        bits.append(f"{row['turns']} turns")
    if row["cost_usd"] is not None:
        bits.append(f"${row['cost_usd']:.2f}")
    if row["output_tokens"] is not None:
        bits.append(f"{row['output_tokens']:,} out")
    if row["permission_denials"]:
        bits.append(f"{row['permission_denials']} DENIED")
    if row["is_error"]:
        bits.append(f"ERROR ({row.get('subtype')})")
    return "usage: " + ", ".join(bits)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("result")
    ap.add_argument("--stage", required=True)
    ap.add_argument("--seconds", type=float, required=True)
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--ledger", default=None,
                    help="JSON lines file to append the row to")
    ap.add_argument("--report", default=None,
                    help="write the agent's own closing message here")
    args = ap.parse_args()

    blob = load(Path(args.result))
    row = summarise(blob, args.stage, args.seconds, args.attempt)
    print(line(row))

    if args.ledger:
        with open(args.ledger, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    if args.report:
        text = blob.get("result")
        if isinstance(text, str) and text.strip():
            Path(args.report).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

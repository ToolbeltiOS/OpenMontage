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

WHY IT READ `modelUsage` AND NOT `usage`
----------------------------------------
The 2026-11-06 render stage was recorded as

    usage: render, 2h45m wall, 1 turns, $212.43, 0 out, ERROR (success)

Three of those numbers were wrong and all three for one reason. On a result
record that ends in an api_error, `usage` and `num_turns` describe the LAST
EXCHANGE — the one that got the 429 and did nothing — while `modelUsage`
holds the session. The session was 1,222 turns, 404K output tokens and
388,077,078 cache-read tokens, which is where the $212.43 went: 91% of the
bill was re-reading the conversation. "1 turns, 0 out" made the single most
expensive stage ever run look like a no-op, and "ERROR (success)" put the
word success next to it because `subtype` stayed "success" while `is_error`
went true.

So: session totals from `modelUsage`, and CACHE READS ARE PRINTED. The cost
of this pipeline is the context re-read per turn times the number of turns,
and neither number was in the log.

    scripts/stage_usage.py <result.json> --stage script --seconds 3380
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

#: Opus 5 list price per million tokens, for the cache-read share. Used only
#: to say WHERE the money went in the printed line; the authority on what was
#: spent is `total_cost_usd`, which the vendor computes.
PER_MTOK = {"input": 5.0, "output": 25.0, "cache_read": 0.50, "cache_write_1h": 10.0}

#: Where the CLI keeps its transcripts. The result record's `num_turns` is
#: not the session's turn count when the session ended in an api_error, and
#: the turn count is the number that explains the bill — so it is counted
#: from the transcript when the transcript can be found.
TRANSCRIPTS = Path.home() / ".claude" / "projects"


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


def big(n: float | None) -> str:
    """388077078 -> '388M'. A number this size is unreadable in full."""
    if n is None:
        return "?"
    n = int(n)
    for cut, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(n) >= cut:
            return f"{n / cut:.0f}{suffix}"
    return str(n)


def model_totals(blob: dict) -> dict:
    """Session token totals, summed over every model the stage used."""
    per_model = blob.get("modelUsage")
    out = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
           "thinking": 0, "models": []}
    if not isinstance(per_model, dict):
        return out
    for name, row in per_model.items():
        if not isinstance(row, dict):
            continue
        out["models"].append(name)
        out["input"] += row.get("inputTokens") or 0
        out["output"] += row.get("outputTokens") or 0
        out["cache_read"] += row.get("cacheReadInputTokens") or 0
        out["cache_write"] += row.get("cacheCreationInputTokens") or 0
        out["thinking"] += row.get("thinkingTokens") or 0
    return out


def transcript_turns(session_id: str | None) -> int | None:
    """How many assistant turns the session really had.

    Best effort: the transcript is the CLI's own file and may be absent,
    pruned or somewhere else. A missing count prints as the result record's
    own number rather than stopping a film.
    """
    if not session_id:
        return None
    try:
        matches = list(TRANSCRIPTS.glob(f"*/{session_id}.jsonl"))
    except OSError:
        return None
    if not matches:
        return None
    turns = 0
    try:
        with matches[0].open(errors="replace") as fh:
            for line in fh:
                if '"type":"assistant"' not in line and '"type": "assistant"' not in line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("type") == "assistant" and (row.get("message") or {}).get("usage"):
                    turns += 1
    except OSError:
        return None
    return turns or None


def summarise(blob: dict, stage: str, seconds: float, attempt: int) -> dict:
    # `usage` on a result record that ended in an api_error describes the
    # failed exchange, not the session. modelUsage is the session.
    usage = blob.get("usage") or {}
    totals = model_totals(blob)
    reported = blob.get("num_turns")
    counted = transcript_turns(blob.get("session_id"))

    def pick(key: str, fallback: str) -> int | None:
        value = totals.get(key)
        return value if value else usage.get(fallback)

    cache_read = pick("cache_read", "cache_read_input_tokens") or 0
    cost = blob.get("total_cost_usd")
    return {
        "stage": stage,
        "attempt": attempt,
        "wall_seconds": round(seconds, 1),
        "wall": hms(seconds),
        # The number that explains the bill, and the number the CLI reported,
        # kept apart: they disagreed by a factor of 1,222 once.
        "turns": counted or reported,
        "turns_reported": reported,
        "api_seconds": round((blob.get("duration_api_ms") or 0) / 1000.0, 1),
        "cost_usd": cost,
        "input_tokens": pick("input", "input_tokens"),
        "output_tokens": pick("output", "output_tokens"),
        "cache_read_tokens": cache_read,
        "cache_write_tokens": pick("cache_write", "cache_creation_input_tokens"),
        "thinking_tokens": totals.get("thinking") or None,
        # Of the money, how much was spent re-reading the conversation. This
        # is the pipeline's dominant cost and had never been written down.
        "cache_read_usd": round(cache_read / 1e6 * PER_MTOK["cache_read"], 2),
        "context_per_turn": (int(cache_read / (counted or reported))
                             if (counted or reported) else None),
        "is_error": blob.get("is_error"),
        "subtype": blob.get("subtype"),
        # `subtype` stayed "success" on a 429, which is how the log came to
        # read "ERROR (success)". The error's own name is the useful one.
        "api_error": blob.get("api_error"),
        "terminal_reason": blob.get("terminal_reason"),
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
        bits.append(f"{big(row['output_tokens'])} out")
    if row["cache_read_tokens"]:
        bits.append(f"{big(row['cache_read_tokens'])} cache-read "
                    f"(${row['cache_read_usd']:.2f})")
    if row["context_per_turn"]:
        bits.append(f"{big(row['context_per_turn'])}/turn")
    if row["permission_denials"]:
        bits.append(f"{row['permission_denials']} DENIED")
    if row["is_error"]:
        bits.append(f"ERROR ({row.get('api_error') or row.get('subtype')})")
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

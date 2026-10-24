#!/usr/bin/env python3
"""Did this `claude -p` stage stop because the usage limit was reached?

WHY THIS EXISTS
---------------
The first attended run's render stage died at 23:30 with one line:

    You've hit your session limit · resets 12am (America/Toronto)

Nothing in the pipeline was wrong. The run stalled until credits returned
and was resumed by hand. Unattended, that is a lost week — so the runner has
to tell this apart from a stage that genuinely failed, wait exactly as long
as the message says, and go back in.

Telling them apart is the whole job. A stage that failed for a real reason
must NOT be slept on and retried six times; that buries the reason under six
more logs, which is the same mistake the runner already refuses to make with
renders.

    scripts/usage_limit.py <file> [<file> ...]
      exit 0  -> a usage limit. prints SECONDS=<n> and RESETS=<text>
      exit 1  -> not a usage limit; the caller should fail the stage
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

#: What the limit actually says. Matched case-insensitively against both the
#: JSON result and whatever landed on stderr, because which one carries it
#: depends on how far the CLI got before it stopped.
LIMIT_PATTERNS = (
    r"hit your (?:session|usage|rate) limit",
    r"(?:session|usage|rate)[- ]limit (?:reached|exceeded)",
    r"you(?:'| ha)ve (?:reached|hit) your limit",
    r"out of (?:credits|usage)",
    r"\bupgrade to increase your usage limit\b",
)

#: "resets 12am (America/Toronto)", "resets at 3:30pm", "resets 09:00"
RESET_RE = re.compile(
    r"resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)?"
    r"(?:\s*\(([A-Za-z_]+/[A-Za-z_]+)\))?",
    re.I)

#: With no time in the message, wait this long. Long enough that a retry is
#: not a hot loop, short enough that an hour-long window is not wasted.
DEFAULT_WAIT_SECONDS = 60 * 60

#: Never sleep longer than this, whatever a message claims. A parse that goes
#: wrong should cost an hour of a Friday night, not a weekend.
MAX_WAIT_SECONDS = 6 * 60 * 60

#: Go back in slightly after the window opens, not on the exact second.
GRACE_SECONDS = 60


def text_of(path: Path) -> str:
    """Everything legible in the file, JSON result included."""
    try:
        raw = path.read_text(errors="replace")
    except OSError:
        return ""
    parts = [raw]
    try:
        blob = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    if isinstance(blob, dict):
        for key in ("result", "error", "message", "subtype", "api_error_status"):
            value = blob.get(key)
            if isinstance(value, str):
                parts.append(value)
    return "\n".join(parts)


def is_usage_limit(text: str) -> bool:
    return any(re.search(p, text, re.I) for p in LIMIT_PATTERNS)


def seconds_until_reset(text: str, now: datetime | None = None) -> tuple[int, str]:
    """How long to wait, and the human text it came from.

    A reset time with no date is the NEXT time that clock reads it, which is
    the one case worth being careful about: at 23:30 a message saying
    "resets 12am" means thirty minutes away, not twenty-three and a half
    hours ago.
    """
    match = RESET_RE.search(text)
    if not match:
        return DEFAULT_WAIT_SECONDS, "no reset time in the message"

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").lower()
    zone_name = match.group(4)

    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return DEFAULT_WAIT_SECONDS, f"unreadable reset time {match.group(0)!r}"

    zone = None
    if zone_name:
        try:
            zone = ZoneInfo(zone_name)
        except Exception:
            zone = None
    now = now or datetime.now(zone)
    if now.tzinfo is None and zone is not None:
        now = now.replace(tzinfo=zone)
    elif zone is not None:
        now = now.astimezone(zone)

    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)

    wait = int((target - now).total_seconds()) + GRACE_SECONDS
    return min(max(wait, 0), MAX_WAIT_SECONDS), match.group(0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()

    text = "\n".join(text_of(Path(f)) for f in args.files)
    if not is_usage_limit(text):
        return 1
    seconds, source = seconds_until_reset(text)
    print(f"SECONDS={seconds}")
    print(f"RESETS={source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

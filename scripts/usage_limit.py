#!/usr/bin/env python3
"""Why did this `claude -p` stage stop — a usage limit, a turn cap, or a fault?

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

WHY IT STOPPED WORKING
----------------------
On 2026-11-06 the render stage stopped with

    You've hit your 5-hour limit · resets 2:20am (America/Toronto)

and this script said "not a usage limit", so the runner failed the run
instead of sleeping 167 minutes and going back in. The reset time was
sitting in the message and parsed correctly. Every pattern missed for one
reason: they all assumed the word `session`, `usage` or `rate` sat directly
against `limit`, and the window is named after its LENGTH now. The JSON also
said `"api_error": "usage_limit_reached"` in as many words — with
underscores, which `[- ]` does not match.

So the STRUCTURED FIELDS ARE READ FIRST and the prose is the fallback. A
sentence is a thing a vendor rewords; `api_error` is a thing a vendor
changes deliberately. Reading the sentence first is how a 167-minute pause
became a dead week.

    scripts/usage_limit.py <file> [<file> ...]
      exit 0  -> a usage limit. prints SECONDS=<n> and RESETS=<text>
      exit 1  -> not a usage limit; the caller should fail the stage

    scripts/usage_limit.py --classify <file> [<file> ...]
      always exit 0, prints KIND=ok|usage_limit|max_turns|error
      plus SECONDS=/RESETS= when the kind is usage_limit
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

#: `api_error` values that mean "come back later", not "this is broken".
LIMIT_ERRORS = {"usage_limit_reached", "rate_limit_error", "rate_limit_exceeded"}

#: What the limit actually says, when all we have is prose. Matched
#: case-insensitively against both the JSON result and whatever landed on
#: stderr, because which one carries it depends on how far the CLI got.
#:
#: The first pattern is deliberately loose about what sits between "your"
#: and "limit": that slot has held `session`, `5-hour` and `weekly`, and the
#: next word for it has not been invented yet. Everything it could wrongly
#: match ("hit your stride limit"?) is not a sentence anything emits, and the
#: cost of being wrong in this direction is one hour of a Friday night, while
#: the cost of being wrong in the other is the week's film.
LIMIT_PATTERNS = (
    r"hit your\b[^.\n]{0,40}?\blimit\b",
    r"reached your\b[^.\n]{0,40}?\blimit\b",
    r"\busage[-_ ]limit[-_ ](?:reached|exceeded)\b",
    r"(?:session|usage|rate)[- ]limit (?:reached|exceeded)",
    r"you(?:'| ha)ve (?:reached|hit) your limit",
    r"out of (?:credits|usage)",
    r"\bupgrade to increase your usage limit\b",
    r"\b\d+\s*-?\s*hours?\s+limit\b",
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


def blob_of(path: Path) -> dict:
    """The parsed result record, or {} if this file is not one."""
    try:
        parsed = json.loads(path.read_text(errors="replace"))
    except (OSError, ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def text_of(path: Path) -> str:
    """Everything legible in the file, JSON result included."""
    try:
        raw = path.read_text(errors="replace")
    except OSError:
        return ""
    parts = [raw]
    blob = blob_of(path)
    for key in ("result", "error", "message", "subtype", "api_error",
                "terminal_reason"):
        value = blob.get(key)
        if isinstance(value, str):
            parts.append(value)
    return "\n".join(parts)


def structured_limit(blob: dict) -> bool:
    """Does the result record SAY it was a usage limit, in a field?

    Preferred over the prose for the reason in the module docstring. A bare
    429 is not enough on its own — it is also what a burst of requests gets
    — so the status has to come with an error name or a limit sentence.
    """
    if not blob:
        return False
    if str(blob.get("api_error") or "") in LIMIT_ERRORS:
        return True
    if blob.get("api_error_status") == 429:
        name = str(blob.get("api_error") or "")
        if "limit" in name.lower():
            return True
        result = blob.get("result")
        if isinstance(result, str) and is_usage_limit(result):
            return True
    return False


def structured_max_turns(blob: dict) -> bool:
    """Did the stage stop because it ran out of its turn allowance?

    This is NOT sleepable and NOT retryable: the stage was given a budget
    and spent it. Sleeping on it would re-enter a stage that is about to
    spend the same budget again, which is how a cap becomes a loop.
    """
    if not blob:
        return False
    if str(blob.get("subtype") or "") == "error_max_turns":
        return True
    for key in ("result", "error", "terminal_reason"):
        value = blob.get(key)
        if isinstance(value, str) and re.search(
                r"max(?:imum)?[-_ ]turns?\b|\bturn limit\b", value, re.I):
            return True
    return False


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


def classify(paths: list[Path]) -> tuple[str, str]:
    """(kind, text) for a stage's result files, worst-news-first.

    A usage limit outranks a turn cap: a stage that spent its cap AND hit
    the window should be slept on, because its next entry gets a fresh cap
    but not fresh credits.
    """
    blobs = [blob_of(p) for p in paths]
    text = "\n".join(text_of(p) for p in paths)

    if any(structured_limit(b) for b in blobs) or is_usage_limit(text):
        return "usage_limit", text
    if any(structured_max_turns(b) for b in blobs):
        return "max_turns", text
    if any(b.get("is_error") for b in blobs if b):
        return "error", text
    return "ok", text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--classify", action="store_true",
                    help="print KIND= and always exit 0")
    args = ap.parse_args()

    paths = [Path(f) for f in args.files]
    kind, text = classify(paths)

    if kind == "usage_limit":
        seconds, source = seconds_until_reset(text)

    if args.classify:
        print(f"KIND={kind}")
        if kind == "usage_limit":
            print(f"SECONDS={seconds}")
            print(f"RESETS={source}")
        return 0

    if kind != "usage_limit":
        return 1
    print(f"SECONDS={seconds}")
    print(f"RESETS={source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

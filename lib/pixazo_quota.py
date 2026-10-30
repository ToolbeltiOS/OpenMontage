#!/usr/bin/env python3
"""The Pixazo free tier, and the fact that it is not ours alone.

THE QUOTA IS SHARED, AND NOTHING ELSE KNOWS THAT
-------------------------------------------------
Pixazo's free tier is an allowance on the ACCOUNT and is shared across every
API key on it. The Shorts pipeline in ~/Desktop/wak3up draws on the same
account through the same endpoint. Two pipelines, one bucket.

The Shorts poster is paused today, so the bucket is effectively ours. That
is a fact about this week, not a property of the system, and the moment
posting resumes the two will be spending the same 750 images. This file is
where that is written down, and the ledger below is deliberately shared: it
counts what THIS pipeline spent, and it cannot see what the other one spent,
which is stated in every report it produces rather than quietly assumed to
be zero.

THE NUMBERS
-----------
From Pixazo's own free-tier page (effective 20 September 2026) and its API
FAQ, read 2026-10-30:

  750 images per month, resetting on the 1st
  shared across all API keys on the account
  60 requests per minute per API on free balance
  $0.0012/image once the free allowance is gone

Older Pixazo blog posts cite about 10 requests per minute instead of 60. The
lower figure is used here: being wrong about a rate limit costs a 429 and a
retry, and being wrong in the cautious direction costs nothing.

Refusal is at 80% of each, as instructed.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Images a month on the free tier, across the whole account.
MONTHLY_FREE_IMAGES = 750

#: Requests a minute. The cautious of the two published figures.
RATE_PER_MINUTE = 10

#: Refuse past this share of either limit.
CEILING = 0.80

#: Where this pipeline's spend is counted. NOT the account's spend -- see
#: the module docstring.
LEDGER = ROOT / "reports" / "pixazo_usage.json"


def month_key(when: dt.date | None = None) -> str:
    d = when or dt.date.today()
    return f"{d.year:04d}-{d.month:02d}"


def load() -> dict:
    if not LEDGER.exists():
        return {"months": {}}
    return json.loads(LEDGER.read_text())


def used_this_month() -> int:
    return int(load().get("months", {}).get(month_key(), 0))


def record(n: int) -> int:
    blob = load()
    key = month_key()
    blob.setdefault("months", {})
    blob["months"][key] = int(blob["months"].get(key, 0)) + n
    blob["note"] = ("Counts only what OpenMontage generated. The Pixazo free "
                    "tier is shared with the Shorts pipeline in "
                    "~/Desktop/wak3up, whose usage is NOT counted here and "
                    "is not visible from this machine.")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(blob, indent=1) + "\n")
    return blob["months"][key]


def check(n: int) -> tuple[bool, str]:
    """May this pipeline generate `n` more images this month?"""
    used = used_this_month()
    limit = int(MONTHLY_FREE_IMAGES * CEILING)
    if used + n > limit:
        return False, (
            f"{used} image(s) already generated this month by OpenMontage "
            f"and {n} more would reach {used + n}, over the "
            f"{int(CEILING * 100)}% ceiling of {limit} on a free tier of "
            f"{MONTHLY_FREE_IMAGES}. AND THAT COUNT IS AN UNDERCOUNT: the "
            f"Shorts pipeline shares this account's allowance and its usage "
            f"is not visible from here.")
    return True, (
        f"{used} used by OpenMontage this month, {n} more reaches "
        f"{used + n} of a {limit} ceiling ({MONTHLY_FREE_IMAGES} free, "
        f"{int(CEILING * 100)}%). Shared with the Shorts pipeline, whose "
        f"usage is not counted here.")


def spacing_seconds() -> float:
    """Seconds to leave between calls to stay under 80% of the rate limit."""
    return 60.0 / (RATE_PER_MINUTE * CEILING)

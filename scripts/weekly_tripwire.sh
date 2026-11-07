#!/usr/bin/env bash
# Sunday noon: did a film actually get made?
#
# A run that dies quietly is the failure mode this catches. The runner reports
# its own errors, but a runner that never started — a Mac asleep, a launchd
# agent unloaded, a lock file left by a crash — reports nothing at all, and
# the first anyone would know is a Monday with no video.
#
# So this asks the only question that matters: is there a published.json entry
# newer than Friday? If not, it pages.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO/.venv/bin/python"

REPO="$REPO" "$PY" - <<'PYEOF'
import json, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0]
import os
ROOT = Path(os.environ.get("REPO", ".")).resolve()
sys.path.insert(0, str(ROOT / "lib"))
import telegram

# The shared ledger, outside every worktree — see lib/shared_state.py. The
# tripwire reads it with allow_missing because a missing ledger must PAGE,
# which is what an empty films list does three lines down, rather than raise
# inside a Sunday-noon cron nobody is watching.
import shared_state

ledger = shared_state.published_path()
films = shared_state.published_films(allow_missing=True)
cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).date()

recent = [f for f in films
          if f.get("published") and
          datetime.fromisoformat(f["published"]).date() >= cutoff]

if recent:
    print(f"ok: {len(recent)} film(s) since {cutoff}")
    sys.exit(0)

logs = sorted((ROOT / "logs").glob("*/run.log"))
tail = ""
if logs:
    tail = "\n".join(logs[-1].read_text().splitlines()[-6:])
telegram.send(
    "<b>Tripwire: no film this week</b>\n"
    f"Nothing in {ledger} since {cutoff}. "
    f"The Friday run either never started or died without saying so.\n\n"
    + (f"<pre>{tail[:900]}</pre>" if tail else "No run log at all."))
print("TRIPWIRE: nothing published")
sys.exit(1)
PYEOF

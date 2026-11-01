#!/usr/bin/env bash
#
# Start the full-film render so that it OUTLIVES WHOEVER STARTED IT.
#
# WHY THIS EXISTS. The Noah plate was started three times as a background
# task of the agent driving the render stage. A background task here has a
# two-hour ceiling, and a 35,561-frame film needs four passes and several
# hours, so the harness stopped the task every time — the third at 33,055 of
# 35,561 frames. Killing the task kills its process group, so the renderer
# went with it: no output file, no error line, no exit status. Three attempts,
# six hours, nothing on disk.
#
# A render must therefore not be a child of the thing that is waiting for it.
# This script is launched with `setsid` so the renderer sits in its own
# session, and it returns as soon as the render is under way. Whoever wants
# to know how it went reads render_status.json; whoever wants to watch reads
# the log. Both outlive the caller too.
#
# Usage:  setsid nohup scripts/render_detached.sh <project> [render_film args...] &
#
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="${1:?usage: render_detached.sh <project> [args...]}"
shift
DIR="$REPO/projects/$PROJECT"
PIDFILE="$DIR/render.pid"
STATUS="$DIR/render_status.json"
STAMP="$(date +%Y%m%dT%H%M%S)"
ATTEMPT="$DIR/render_$STAMP.log"
CUMULATIVE="$DIR/render.log"

mkdir -p "$DIR"

# macOS ships no setsid(1), and a render that stays in its caller's process
# group dies when that group is killed — which is exactly how three attempts
# were lost. So the script puts ITSELF in a new session on first entry and
# re-execs: the caller gets control back at once and the render is nobody's
# child.
if [[ "${RENDER_DETACHED_SESSION:-}" != "1" ]]; then
  export RENDER_DETACHED_SESSION=1
  exec "$REPO/.venv/bin/python" -c '
import os, sys
if os.fork():                      # the caller returns immediately
    os._exit(0)
os.setsid()                        # the render leads its own session
fd = os.open(os.devnull, os.O_RDWR)
for stream in (0, 1, 2):
    os.dup2(fd, stream)
os.execv("/bin/bash", ["/bin/bash"] + sys.argv[1:])
' "$0" "$PROJECT" "$@"
fi

# One render at a time. Two renders on one Mac write the same plate.mp4 and
# neither is the film.
if [[ -f "$PIDFILE" ]]; then
  OLD="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ -n "$OLD" ]] && kill -0 "$OLD" 2>/dev/null; then
    echo "render already running (pid $OLD) — refusing to start a second" >&2
    exit 3
  fi
fi
echo $$ > "$PIDFILE"

finish() {
  local rc=$?
  cat > "$STATUS" <<JSON
{
  "project": "$PROJECT",
  "attempt_log": "$ATTEMPT",
  "started": "$STAMP",
  "finished": "$(date +%Y%m%dT%H%M%S)",
  "exit_code": $rc,
  "outcome": "$( ((rc == 0)) && echo delivered || echo failed )"
}
JSON
  rm -f "$PIDFILE"
  # The last lines are what a reader wants first, so put them where the
  # status is rather than making them go and find the log.
  tail -25 "$ATTEMPT" >> "$STATUS.tail" 2>/dev/null || true
}
trap finish EXIT

# The render is hours long and a sleeping Mac is a dead render. This
# caffeinate is a child of this script, so it goes when the render goes.
caffeinate -dimsu -w $$ &

{
  echo
  echo "=== attempt $STAMP  (pid $$, $(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null)@$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null)) ==="
  echo "=== $*"
} | tee -a "$CUMULATIVE" >> "$ATTEMPT"

# PYTHONUNBUFFERED, or the watchdog's own lines sit in a buffer and the log
# looks stalled while the render is fine.
PYTHONUNBUFFERED=1 "$REPO/.venv/bin/python" "$REPO/scripts/render_film.py" \
    --project "$PROJECT" "$@" 2>&1 | tee -a "$CUMULATIVE" >> "$ATTEMPT"
exit "${PIPESTATUS[0]}"

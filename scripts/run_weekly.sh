#!/usr/bin/env bash
# The weekly documentary, end to end, unattended except for one approval.
#
# WHAT THIS IS
#   Friday 22:00 a launchd agent runs this. It picks a topic, hands the brief
#   to `claude -p` against this repository, and waits at the script gate for a
#   human. Everything after the gate is mechanical and already gated by a
#   measurement, so it runs through the night and schedules Monday 09:00.
#
# WHAT IT WILL NOT DO
#   Retry a render. A render that failed failed for a reason, and a second
#   twenty-minute attempt at 4am buries the reason under another log. It
#   fails, says so on Telegram, and stops.
#
#   Run twice. A lock file holds the whole run; a second invocation exits
#   rather than queueing, because two renders on one Mac is neither.
#
#   Continue past a stage error. Every stage's exit code is checked.
#
# USAGE
#   scripts/run_weekly.sh                 # pick a topic and run
#   scripts/run_weekly.sh --brief <path>  # use this brief instead
#   scripts/run_weekly.sh --dry-run       # prove the hand-offs, render nothing
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO/.venv/bin/python"
DATE="$(date +%Y-%m-%d)"
LOGDIR="$REPO/logs/$DATE"
LOCK="$REPO/.weekly.lock"
BRIEF=""
DRY_RUN=0
GATE_HOURS="${GATE_HOURS:-12}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --brief) BRIEF="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --gate-hours) GATE_HOURS="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done

mkdir -p "$LOGDIR"
"$REPO/scripts/rotate_logs.sh" >/dev/null 2>&1 || true
exec > >(tee -a "$LOGDIR/run.log") 2>&1

say() { printf '\n== %s == %s\n' "$(date +%H:%M:%S)" "$*"; }

notify() {  # best effort; a notifier that raises must not stop a render
  "$PY" "$REPO/lib/telegram.py" --send "$1" >/dev/null 2>&1 || true
}

fail() {
  say "FAILED at $1"
  notify "<b>Weekly run failed</b>
stage: $1
$2

log: $LOGDIR/run.log"
  exit 1
}

# ── one run at a time ────────────────────────────────────────────────────
if ! mkdir "$LOCK" 2>/dev/null; then
  owner="$(cat "$LOCK/pid" 2>/dev/null || echo unknown)"
  if kill -0 "$owner" 2>/dev/null; then
    say "a run is already going (pid $owner) — exiting"
    exit 0
  fi
  say "stale lock from pid $owner — taking it"
  rm -rf "$LOCK" && mkdir "$LOCK"
fi
echo $$ > "$LOCK/pid"
cleanup() { rm -rf "$LOCK"; }
trap cleanup EXIT

# ── keep the Mac awake for the whole thing ───────────────────────────────
caffeinate -dimsu -w $$ &
CAFFEINE=$!
say "awake (caffeinate $CAFFEINE)"

# ── 1. the topic ─────────────────────────────────────────────────────────
if [[ -z "$BRIEF" ]]; then
  say "picking a topic"
  "$PY" "$REPO/scripts/pick_topic.py" --top 3 --candidates 14 \
    > "$LOGDIR/pick_topic.log" 2>&1 \
    || fail "topic picker" "$(tail -5 "$LOGDIR/pick_topic.log")"
  BRIEF="$REPO/artifacts/topic_briefs.json"
fi
TOPIC="$("$PY" -c "
import json,sys
b=json.load(open('$BRIEF'))
briefs=b['briefs'] if isinstance(b,dict) else b
print(briefs[0]['entity'] if briefs else '')
")"
[[ -n "$TOPIC" ]] || fail "topic picker" "no eligible topic"
SLUG="$(printf '%s' "$TOPIC" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-')"
say "topic: $TOPIC  (project $SLUG)"
notify "<b>Weekly run started</b>
topic: $TOPIC
log: $LOGDIR"

# ── 2. the film, up to the script ────────────────────────────────────────
PROMPT="$LOGDIR/prompt.txt"
cat > "$PROMPT" <<PROMPTEOF
Make this week's documentary.

Pipeline:  pipeline_defs/narrated-documentary.yaml
Playbook:  styles/wak3up-documentary.yaml
Project:   $SLUG
Brief:     $BRIEF  (take the first brief)

Run the pipeline from research through to the script artifact and stop there.
Every gate in the pipeline is auto-approved EXCEPT the script gate, which is a
human one and is handled outside this process — do not wait for it and do not
approve it yourself.

Write the script to projects/$SLUG/artifacts/script.json and the hero style
frames to projects/$SLUG/renders/style/. Do not render the film.
PROMPTEOF

if [[ "$DRY_RUN" == "1" ]]; then
  say "dry run: skipping claude -p"
else
  say "writing the script (claude -p)"
  claude -p "$(cat "$PROMPT")" --permission-mode acceptEdits \
    > "$LOGDIR/script_stage.log" 2>&1 \
    || fail "script stage" "$(tail -20 "$LOGDIR/script_stage.log")"
fi

# ── 3. the human ─────────────────────────────────────────────────────────
if [[ "$DRY_RUN" == "1" ]]; then
  say "dry run: skipping the script gate (there is no script to approve)"
  say "         scripts/dry_run.py is what exercises the gate"
else
say "script gate (up to ${GATE_HOURS}h)"
ATTEMPT=1
while true; do
  "$PY" "$REPO/scripts/telegram_gate.py" \
    --project "$SLUG" \
    --script "$REPO/projects/$SLUG/artifacts/script.json" \
    --frames "$REPO/projects/$SLUG/renders/style" \
    --hours "$GATE_HOURS" --attempt "$ATTEMPT"
  GATE=$?
  case "$GATE" in
    0)  say "approved"; break ;;
    2)  say "aborted by reply"; exit 0 ;;
    3)  say "aborted: no reply"; exit 0 ;;
    4)  say "aborted: second round of notes"; exit 0 ;;
    10) say "notes received — applying"
        ATTEMPT=2
        if [[ "$DRY_RUN" != "1" ]]; then
          claude -p "Apply the notes in projects/$SLUG/artifacts/script_notes.txt
to projects/$SLUG/artifacts/script.json. Change nothing else." \
            --permission-mode acceptEdits \
            >> "$LOGDIR/script_stage.log" 2>&1 \
            || fail "applying notes" "$(tail -20 "$LOGDIR/script_stage.log")"
        fi
        ;;
    5)  fail "script gate" "the script stage produced no script.json" ;;
    *)  fail "script gate" "unexpected exit $GATE" ;;
  esac
done
fi

# ── 4. the render ────────────────────────────────────────────────────────
if [[ "$DRY_RUN" == "1" ]]; then
  say "dry run: skipping the render"
else
  say "rendering (no retries)"
  claude -p "Continue the pipeline for project $SLUG from the approved script
through to a delivered film. Auto-approve every gate. Render with
scripts/render_film.py, which is the only full-film render path." \
    --permission-mode acceptEdits \
    > "$LOGDIR/render_stage.log" 2>&1 \
    || fail "render" "$(tail -20 "$LOGDIR/render_stage.log")"
fi

# ── 5. publish ───────────────────────────────────────────────────────────
if [[ "$DRY_RUN" == "1" && ! -f "$REPO/projects/$SLUG/artifacts/listing.json" ]]; then
  say "dry run: no listing for $SLUG, so there is nothing to publish"
  say "         scripts/dry_run.py is what exercises the publisher"
  say "done (dry run: topic and hand-offs only)"
  exit 0
fi
say "publishing"
PUBLISH_ARGS=(--project "$SLUG")
[[ "$DRY_RUN" == "1" ]] && PUBLISH_ARGS+=(--dry-run)
"$PY" "$REPO/scripts/publish_doc.py" "${PUBLISH_ARGS[@]}" \
  > "$LOGDIR/publish.log" 2>&1 \
  || fail "publish" "$(tail -10 "$LOGDIR/publish.log")"

say "done"
notify "<b>Weekly run finished</b>
topic: $TOPIC
$(tail -3 "$LOGDIR/publish.log")"

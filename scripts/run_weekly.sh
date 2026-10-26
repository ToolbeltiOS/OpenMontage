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
#   RUN_WEEKLY_SMOKE=1 scripts/run_weekly.sh
#                                         # prove the LAUNCHD path, spend nothing
#
# SMOKE MODE
#   --dry-run proves the hand-offs between the stages. It does not prove the
#   thing that actually goes wrong with a scheduled job: whether launchd runs
#   the script at all, with the right environment, writing where it should.
#   The agent's plist pointed at a file that did not exist for three days and
#   nothing noticed, because nothing had ever made launchd try.
#
#   RUN_WEEKLY_SMOKE=1 runs the real path — the launchd entry, the lock file,
#   the log rotation, the topic pick, Telegram — and stops at the script gate
#   without calling `claude -p` and without rendering. It costs nothing and it
#   is the only thing that exercises the plist.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO/.venv/bin/python"
DATE="$(date +%Y-%m-%d)"
LOGDIR="$REPO/logs/$DATE"
LOCK="$REPO/.weekly.lock"
BRIEF=""
DRY_RUN=0
GATE_HOURS="${GATE_HOURS:-12}"
SMOKE="${RUN_WEEKLY_SMOKE:-0}"

#: How many times a stage may be resumed after a usage limit before the run
#: fails loudly. The owner's number, 2026-10-24.
#:
#: IT WAS NEVER DEFINED. `claude_stage` used it four times and nothing set it.
#:
#: Measured, under `set -u` an unbound name in `(( ))` ABORTS THE SHELL: the
#: error prints, neither branch of the `if` runs, nothing after it runs — and
#: the exit status is 0. So the first usage limit would have killed the whole
#: weekly run, with no `fail()`, no Telegram, no "giving up", and a launchd
#: job that looks like it succeeded. Silent, and indistinguishable from a
#: clean finish.
#:
#: Every part of that was written and reviewed; none of it had ever run. The
#: test that was supposed to hold the cap asserted only that the STRING
#: "MAX_RESUMES" appeared in the file.
MAX_RESUMES="${MAX_RESUMES:-6}"

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

# ── a claude -p stage, resumable ────────────────────────────────────
#
# Output is JSON so the turns and the cost can be recorded; the agent's own
# closing report is pulled back out into <stage>.log, because that report was
# the most useful artifact of the first attended run and switching formats
# must not cost it.
#
# $1 stage name   $2 log basename   $3 prompt
claude_stage() {
  local name="$1" base="$2" prompt="$3"
  local attempt=1 resumes=0 rc t0 t1 limit secs resets back
  while true; do
    t0=$(date +%s)
    claude -p "$prompt" --permission-mode acceptEdits --output-format json \
      > "$base.json" 2> "$base.err"
    rc=$?
    t1=$(date +%s)

    "$PY" "$REPO/scripts/stage_usage.py" "$base.json" \
      --stage "$name" --seconds $((t1 - t0)) --attempt "$attempt" \
      --ledger "$LOGDIR/usage.jsonl" --report "$base.log" || true

    [[ $rc -eq 0 ]] && return 0

    # A usage limit, or a real failure? Only the first is slept on.
    if limit="$("$PY" "$REPO/scripts/usage_limit.py" "$base.json" "$base.err")"; then
      resumes=$((resumes + 1))
      if (( resumes > MAX_RESUMES )); then
        say "$name: usage limit again after $MAX_RESUMES resumes — giving up"
        return "$rc"
      fi
      secs="$(printf '%s' "$limit" | sed -n 's/^SECONDS=//p')"
      resets="$(printf '%s' "$limit" | sed -n 's/^RESETS=//p')"
      back="$(date -v +"${secs}"S +%H:%M 2>/dev/null || date -d "+${secs} seconds" +%H:%M)"
      say "$name: usage limit ($resets) — sleeping ${secs}s, back at $back (resume $resumes/$MAX_RESUMES)"
      notify "<b>paused: usage limit, resuming at $back</b>
stage: $name
$resets
resume $resumes of $MAX_RESUMES"
      sleep "$secs"
      attempt=$((attempt + 1))
      continue
    fi
    return "$rc"
  done
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

FIRST, before anything else, run this and obey what it says:

    .venv/bin/python scripts/resume_state.py --project $SLUG

This stage can be RE-ENTERED after a usage limit, and when it is, the work
already on disk is finished work. Do not rebuild a stage it marks [x]: read
that stage's artifact and carry on from the first one it does not mark.
Rebuilding spends the run twice and overwrites a result that was fine.

Run the pipeline from research through to the script artifact and stop there.
Every gate in the pipeline is auto-approved EXCEPT the script gate, which is a
human one and is handled outside this process — do not wait for it and do not
approve it yourself.

Write the script to projects/$SLUG/artifacts/script.json and the hero style
frames to projects/$SLUG/renders/style/. Do not render the film.
PROMPTEOF

# The owner's angle constraint, if this subject has one, as instruction rather
# than as a field three keys deep in a file the prompt said to "take the first
# brief" from. Prints nothing when there is no constraint.
"$PY" "$REPO/scripts/angle_brief.py" --brief "$BRIEF" >> "$PROMPT" 2>/dev/null || true

if [[ "$SMOKE" == "1" ]]; then
  say "smoke: not calling claude -p"
elif [[ "$DRY_RUN" == "1" ]]; then
  say "dry run: skipping claude -p"
else
  say "writing the script (claude -p)"
  claude_stage "script" "$LOGDIR/script_stage" "$(cat "$PROMPT")" \
    || fail "script stage" "$(tail -20 "$LOGDIR/script_stage.log" 2>/dev/null \
                             || tail -20 "$LOGDIR/script_stage.err")"
fi

# ── 3. the human ─────────────────────────────────────────────────────────
#
# The smoke run stops HERE, at the gate, because everything before it is the
# part a schedule can get wrong unattended and everything after it needs a
# human anyway.
if [[ "$SMOKE" == "1" ]]; then
  say "smoke run reached the gate"
  notify "<b>smoke run reached the gate</b>
topic: $TOPIC
log: $LOGDIR/run.log
launchd ran the script, took the lock, rotated the logs and picked a topic.
No model calls, no render, nothing published."
  say "done (smoke)"
  exit 0
fi
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
          claude_stage "notes" "$LOGDIR/notes_stage" \
            "Apply the notes in projects/$SLUG/artifacts/script_notes.txt
to projects/$SLUG/artifacts/script.json. Change nothing else." \
            || fail "applying notes" "$(tail -20 "$LOGDIR/notes_stage.log" 2>/dev/null \
                                       || tail -20 "$LOGDIR/notes_stage.err")"
        fi
        ;;
    5)  fail "script gate" "the script stage produced no script.json" ;;
    6)  fail "script gate" "the gate cannot read this chat — another process is
polling the same bot token, or a webhook is set. The documentary needs its own
bot; see the README." ;;
    *)  fail "script gate" "unexpected exit $GATE" ;;
  esac
done
fi

# ── 4. the render ────────────────────────────────────────────────────────
if [[ "$DRY_RUN" == "1" ]]; then
  say "dry run: skipping the render"
else
  say "rendering (no render retries; usage limits are resumed)"
  claude_stage "render" "$LOGDIR/render_stage" \
    "FIRST, before anything else, run this and obey what it says:

    .venv/bin/python scripts/resume_state.py --project $SLUG

This stage can be RE-ENTERED after a usage limit. Everything it marks [x] is
finished — read the artifact and carry on from the first stage it does not
mark. Do not rebuild the script; it is approved.

Continue the pipeline for project $SLUG from the approved script through to a
delivered film. Auto-approve every gate. Render with scripts/render_film.py,
which is the only full-film render path.

If the picture is already rendered and only a gate or the audio needs
rebuilding, say so and do that rather than rendering 36,000 frames again." \
    || fail "render" "$(tail -20 "$LOGDIR/render_stage.log" 2>/dev/null \
                       || tail -20 "$LOGDIR/render_stage.err")"
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

# ── what the film cost ───────────────────────────────────────
# Against the plan, on Saturday morning, rather than at the next usage limit.
COST=""
if [[ -s "$LOGDIR/usage.jsonl" ]]; then
  say "what this film cost"
  COST="$("$PY" - "$LOGDIR/usage.jsonl" <<'"'"'COSTEOF'"'"'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
wall = sum(r.get("wall_seconds") or 0 for r in rows)
cost = sum(r.get("cost_usd") or 0 for r in rows)
turns = sum(r.get("turns") or 0 for r in rows)
resumes = sum(1 for r in rows if (r.get("attempt") or 1) > 1)
for r in rows:
    print(f"  {r['stage']:<8} attempt {r.get('attempt',1)}  "
          f"{r.get('wall','?'):>7}  {r.get('turns','?')} turns  "
          f"${r.get('cost_usd') or 0:.2f}")
print(f"  {'TOTAL':<8}            {int(wall)//3600}h{(int(wall)%3600)//60:02d}m  "
      f"{turns} turns  ${cost:.2f}"
      + (f"  ({resumes} resumed after a usage limit)" if resumes else ""))
COSTEOF
)"
  printf '%s\n' "$COST"
fi

say "done"
notify "<b>Weekly run finished</b>
topic: $TOPIC
$(tail -3 "$LOGDIR/publish.log")

<b>cost</b>
<pre>$COST</pre>"

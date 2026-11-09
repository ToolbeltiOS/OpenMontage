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
#   Hold a model open while a render runs. The 2026-11-06 render stage was
#   one `claude -p` agent told to start the render detached and then poll
#   for it. It polled for 2h45m across 1,222 turns, re-read 388 million
#   cache tokens and cost $212.43 — $194 of that re-reading its own
#   conversation — to move 745 KB of tool output, and then hit the five-hour
#   usage window one minute after the audio mix finished. Nothing in those
#   turns needed a language model: it ran `ls -lt`, tailed a log and waited.
#   The compose stage now has NO AGENT: scripts/await_render.py starts the
#   render and waits, and scripts/render_film.py runs the gates itself.
#
#   Abandon a half-made film. A run that dies after the human script gate
#   has spent the only scarce thing in this pipeline, which is a person's
#   attention. An unfinished film is finished before a new one is started —
#   and because the topic picker excludes any subject with a directory under
#   projects/, re-firing without this would have picked a NEW topic and left
#   the approved King Tut film unmade.
#
#   Run twice. A lock file holds the whole run; a second invocation exits
#   rather than queueing, because two renders on one Mac is neither.
#
#   Continue past a stage error. Every stage's exit code is checked.
#
# USAGE
#   scripts/run_weekly.sh                 # finish an unfinished film, else
#                                         # pick a topic and run
#   scripts/run_weekly.sh --resume <slug> # finish this film, from its
#                                         # checkpoints
#   scripts/run_weekly.sh --new           # start a new film even if one is
#                                         # unfinished
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
RESUME=""
NEW_FILM=0
DRY_RUN=0
GATE_HOURS="${GATE_HOURS:-12}"
SMOKE="${RUN_WEEKLY_SMOKE:-0}"

#: The fact gate's proper-noun detector. spaCy + en_core_web_sm, installed
#: 2026-10-26. The `capitalisation` substitute remains in the gate for a
#: machine without the model, but nothing reaches for it by default any more.
FACT_BACKEND="${FACT_BACKEND:-spacy}"

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

#: HOW MANY TURNS EACH MODEL STAGE MAY TAKE. A `claude -p` stage pays for
#: its whole context on every turn, so its cost is the context size times
#: the turn count — quadratic in turns, not linear. Measured on the
#: 2026-11-06 render stage: 1,222 turns, context grown to 842,269 tokens,
#: 388M cache-read tokens, $212.43. The same work in four capped stages
#: starts each one from an empty context, so the quadratic restarts four
#: times instead of running once to 1,222.
#:
#: A stage that hits its cap FAILS and is not resumed: a stage given a
#: budget will spend it again. It says which cap it hit and how to raise it,
#: so a cap set too tight is a one-line fix and not a dead week.
#:
#: For reference, what the uncapped 2026-11-06 stage actually spent (tool
#: calls, scaled to turns at the measured 1.68 turns per call): scene plan
#: ~275, audio ~203, edit decisions ~113, asset bank ~99. These caps are
#: deliberately tighter than that, because most of those turns were a loop
#: — 48 edits to one agent-authored build_scene_plan.py, read back 13 times
#: — and docs/STAGE_CONTRACT.md now tells the stage not to author programs.
TURNS_SCRIPT="${TURNS_SCRIPT:-60}"
TURNS_SCENE_PLAN="${TURNS_SCENE_PLAN:-40}"
TURNS_ASSETS="${TURNS_ASSETS:-30}"
TURNS_EDIT="${TURNS_EDIT:-30}"
TURNS_NOTES="${TURNS_NOTES:-15}"

#: How long the non-agent waiter gives the picture before it reports that
#: the render is still going. It does NOT kill it: a render killed near the
#: end leaves no file and no error, which is how three Noah attempts and six
#: hours were lost.
RENDER_TIMEOUT_HOURS="${RENDER_TIMEOUT_HOURS:-8}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --brief) BRIEF="$2"; shift 2 ;;
    --resume) RESUME="$2"; shift 2 ;;
    --new) NEW_FILM=1; shift ;;
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

# ── did a stage edit the code the film is traced to? ─────────────────────
#
# CHECKED AT THE END OF EVERY STAGE, not only at the start of the run.
#
# The start-of-run guard proves the film can be traced to a commit. It cannot
# notice a stage dirtying the tree WHILE the run is going, and on 2026-11-06
# both `claude -p` stages did exactly that: seven files under schemas/, lib/,
# scripts/ and remotion-composer/src/, between 20:00 and 22:48. Nothing said
# so until the NEXT run refused to start at 10:10 the following morning with
# "REFUSED: 7 uncommitted change(s) to code" — twelve hours later, by which
# time the only signal was a refusal with no author and no reason.
#
# `.claude/settings.json` denies Edit and Write under those directories in
# this worktree, which is the first line of defence and not the guarantee: a
# stage must be able to run arbitrary commands to make a film, so `sed -i`,
# `cat >` and a python script all remain. THIS is the guarantee, because it
# asks git rather than trusting a tool boundary.
#
# It does NOT revert anything. All seven of those edits were real fixes with
# real causes and were committed as 86e057c; a guard that had discarded them
# would have destroyed good work and hidden three live defects.
code_dirty() {
  git -C "$REPO" status --porcelain -- "${RUN_CODE[@]}" 2>/dev/null
}

assert_code_clean() {
  local stage="$1" dirty
  dirty="$(code_dirty)"
  [[ -z "$dirty" ]] && return 0
  say "$stage: THIS STAGE EDITED THE CODE TREE"
  printf '%s\n' "$dirty" | sed 's/^/         /'
  fail "$stage (edited the code)" "The $stage stage modified code the film is
traced to:

$dirty

Nothing has been reverted. Read the diff: the last stage to do this made
seven edits and all seven were real defects worth committing. Commit or
revert them, then re-fire — the run picks this film back up where it stopped.

docs/STAGE_CONTRACT.md tells a stage to report a defect in shared code rather
than fix it, and .claude/settings.json denies Edit and Write there."
}


# ── power ────────────────────────────────────────────────────────────────
#
# A RUN TAKES HOURS AND A CLAMSHELL MAC ON BATTERY SLEEPS THROUGH THEM.
# Measured on the 2026-10-30 run: on battery with the lid shut, the machine
# slept 75 times across two model stages and 19.5 hours of the 41 were sleep,
# each wake returning "Connection lost while your computer was asleep" — 36
# in the script stage (9.10 h) and 39 in the render stage (10.43 h). Then the
# battery ran down. `caffeinate -dimsu` runs throughout and cannot help: it
# does not hold a clamshell awake on battery.
#
# So battery at the start is a REFUSAL, not a warning. "Late beats none" does
# not apply, because late is not what happens — the film never arrives.
# Mid-run it is a PAUSE instead: by then there is a script, a scene plan and
# an asset bank on disk, and those are worth waiting for power to finish.
power_source() { pmset -g batt 2>/dev/null | sed -n "1s/.*drawing from '\([^']*\)'.*/\1/p"; }
power_charge() { pmset -g batt 2>/dev/null | sed -n '2s/.*	\([0-9]*%\);.*/\1/p'; }
on_battery()   { [[ "$(power_source)" == *Battery* ]]; }

POWER_WAIT_HOURS="${POWER_WAIT_HOURS:-6}"
POWER_POLL="${POWER_POLL:-120}"

# Pause here until the mains come back. $1 names where we are, so the
# notification says what is waiting rather than just that something is.
require_power() {
  local where="$1" waited=0 told=0 limit=$((POWER_WAIT_HOURS * 3600))
  # A dry run or a smoke run is minutes, not hours. Power is not its problem.
  [[ "${DRY_RUN:-0}" == "1" || "${SMOKE:-0}" == "1" ]] && return 0
  while on_battery; do
    if (( told == 0 )); then
      say "PAUSED before $where: on battery ($(power_charge))"
      notify "<b>Weekly run paused: on battery</b>
before: $where
charge: $(power_charge)

The work so far is on disk and will be picked up where it stopped. Plug in
and open the lid; the run carries on by itself within $((POWER_POLL / 60)) minutes.
It gives up after ${POWER_WAIT_HOURS}h on battery."
      told=1
    fi
    if (( waited >= limit )); then
      fail "$where" "on battery for ${POWER_WAIT_HOURS}h with no mains — stopped before $where"
    fi
    sleep "$POWER_POLL"
    waited=$((waited + POWER_POLL))
  done
  if (( told )); then
    say "power back ($(power_source)) — carrying on with $where"
    notify "<b>Weekly run resumed</b>
power: $(power_source) $(power_charge)
carrying on with: $where"
  fi
}


# ── which code is about to run ───────────────────────────────────────────
#
# THE RUNNER EXECUTES THE WORKING TREE, NOT A BRANCH. On 2026-10-30 that
# produced a full film from the unmerged `asset-library` branch, because a
# development checkout had been left there after a push to `automation`.
# Pushing a branch does nothing if the runner reads a different one.
#
# Two defences, and the first is the real one:
#
#   1. The plist points at a DEDICATED WORKTREE pinned to RUN_BRANCH
#      (~/Developer/wak3up-docs/runner), which no development checkout can
#      reach.
#   2. This check, which refuses to start if the tree it is in is not on
#      RUN_BRANCH or is not clean. A guard is worth having even behind a
#      worktree, because worktrees can be switched too.
#
# The branch and commit go in the log header and the start notice, so a run
# can always be traced to the code that made it.
RUN_BRANCH="${RUN_BRANCH:-automation}"
RUN_HEAD="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)"
RUN_ON="$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"

# The dirty check is about CODE, not about what the runner itself writes.
# pick_topic.py writes artifacts/topic_briefs.json and reports/briefs/*.md
# into this very tree, so a tree that has ever run is dirty for ever — and a
# guard that refuses on that refuses every run after the first. Measured: the
# runner worktree was created clean at 09:25:52 on 2026-10-31 and was dirty
# with four generated files by 09:37:03. The guard exists so the film can be
# traced to the code that made it, so it is the code that must be committed.
RUN_CODE=(lib scripts schemas styles remotion-composer/src config.yaml)
RUN_DIRTY="$(git -C "$REPO" status --porcelain -- "${RUN_CODE[@]}" 2>/dev/null | wc -l | tr -d ' ')"
RUN_DIRTY_ALL="$(git -C "$REPO" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"

# A render is hours long and a sleeping Mac is a stopped render. Measured on
# the 2026-10-30 run: the machine was on battery with the lid shut, slept 75
# times across two stages, and 19.5 hours of a 41-hour run were sleep — each
# wake costing an API round trip that came back "Connection lost while your
# computer was asleep". caffeinate cannot hold a clamshell awake on battery.
RUN_POWER="$(pmset -g batt 2>/dev/null | sed -n "1s/.*drawing from '\([^']*\)'.*/\1/p")"
RUN_CHARGE="$(pmset -g batt 2>/dev/null | sed -n '2s/.*	\([0-9]*%\);.*/\1/p')"

say "code: $RUN_ON @ $RUN_HEAD  (expected $RUN_BRANCH, $RUN_DIRTY uncommitted in code, $RUN_DIRTY_ALL in all)"
say "power: ${RUN_POWER:-unknown} ${RUN_CHARGE:-}"

if [[ "$RUN_ON" != "$RUN_BRANCH" ]]; then
  notify "<b>Weekly run refused to start</b>
The checkout at $REPO is on <b>$RUN_ON</b>, not <b>$RUN_BRANCH</b>.

A run from the wrong branch makes a film out of code that has not been
merged, and the gates it passes are not the gates anyone agreed to. Put the
tree back on $RUN_BRANCH, or set RUN_BRANCH if this is deliberate."
  say "REFUSED: on $RUN_ON, expected $RUN_BRANCH"
  exit 7
fi

if [[ "$RUN_DIRTY" != "0" ]]; then
  notify "<b>Weekly run refused to start</b>
$REPO is on $RUN_BRANCH but has <b>$RUN_DIRTY uncommitted change(s) to code</b>
(${RUN_CODE[*]}).

The film would be made from code that is in no commit, so nothing could be
traced back to it afterwards. Commit or stash, then re-run."
  say "REFUSED: $RUN_DIRTY uncommitted change(s) to code on $RUN_BRANCH"
  exit 7
fi

if [[ "$RUN_POWER" == *Battery* ]]; then
  notify "<b>not running: on battery / lid closed</b>
plug in, open the lid, re-fire with
<code>launchctl kickstart -k gui/$(id -u)/com.wak3up.docs.weekly</code>

charge: ${RUN_CHARGE:-?}. A run takes hours; a clamshell Mac on battery
sleeps through them and the battery runs out before the film is made."
  say "REFUSED: on battery (${RUN_CHARGE:-?}) — plug in, open the lid, re-fire"
  exit 7
fi

# ── a claude -p stage, resumable ────────────────────────────────────
#
# Output is JSON so the turns and the cost can be recorded; the agent's own
# closing report is pulled back out into <stage>.log, because that report was
# the most useful artifact of the first attended run and switching formats
# must not cost it.
#
# $1 stage name   $2 log basename   $3 prompt   $4 turn cap (0 = uncapped)
claude_stage() {
  local name="$1" base="$2" prompt="$3" cap="${4:-0}"
  local attempt=1 resumes=0 rc t0 t1 classified kind secs resets back
  local -a args
  while true; do
    args=(-p "$prompt" --permission-mode acceptEdits --output-format json)
    (( cap > 0 )) && args+=(--max-turns "$cap")
    t0=$(date +%s)
    claude "${args[@]}" > "$base.json" 2> "$base.err"
    rc=$?
    t1=$(date +%s)

    "$PY" "$REPO/scripts/stage_usage.py" "$base.json" \
      --stage "$name" --seconds $((t1 - t0)) --attempt "$attempt" \
      --ledger "$LOGDIR/usage.jsonl" --report "$base.log" || true

    # WHAT KIND OF STOP WAS IT. Asked before the exit code is trusted,
    # because a stage that spends its turn cap may still exit 0, and a stage
    # treated as finished when it ran out of turns hands a half-written
    # artifact to the next stage as if it were done.
    #
    # The classifier reads the result record's STRUCTURED fields first. On
    # 2026-11-06 this was a prose match only, and the limit said "You've hit
    # your 5-hour limit" — the window is named after its length now, and
    # every pattern assumed the word session, usage or rate against "limit".
    # The JSON said "api_error": "usage_limit_reached" in as many words. The
    # reset time parsed fine. The run failed instead of sleeping 2h47m and
    # going back in at 02:21, and that cost the film.
    # Before the exit code is read: a stage that dirtied the code stops the
    # run whether it thinks it succeeded or not. A usage limit is not a
    # reason to resume into a tree somebody now has to reconcile by hand.
    assert_code_clean "$name"

    classified="$("$PY" "$REPO/scripts/usage_limit.py" --classify \
                  "$base.json" "$base.err" 2>/dev/null || echo KIND=error)"
    kind="$(printf '%s' "$classified" | sed -n 's/^KIND=//p')"

    # A WEEKLY CAP IS NOT SLEPT ON. Owner's ruling, 2026-11-07: a Friday run
    # blocked until Monday cannot make Monday's film anyway, and six hourly
    # retries — which is what the old one-hour fallback produced for every
    # weekly-shaped message — is the worst of the three options. There is no
    # API key to fall back to on a subscription, so the honest move is to
    # say when it comes back and stop.
    if [[ "$kind" == "weekly_limit" ]]; then
      resets="$(printf '%s' "$classified" | sed -n 's/^RESETS=//p')"
      say "$name: WEEKLY usage limit ($resets) — failing now, not sleeping"
      notify "<b>weekly usage limit — the run has stopped</b>
stage: $name
$resets

Not slept on: a weekly cap is days, not hours, and a run that waits that
long cannot make the week's film anyway. Nothing is lost — every finished
stage is checkpointed, so re-firing after the reset picks this film up where
it stopped:

<code>launchctl kickstart -k gui/$(id -u)/com.wak3up.docs.weekly</code>"
      return 10
    fi

    if [[ "$kind" == "max_turns" ]]; then
      say "$name: hit the ${cap}-turn cap — FAILING, not resuming"
      notify "<b>stage hit its turn cap</b>
stage: $name
cap: $cap turns

A stage given a budget will spend it again, so this is not resumed. Either
the stage is looping — read $base.log for what it was doing — or the cap is
too tight for this film. Raise it and re-fire:

<code>TURNS_$(printf '%s' "$name" | tr '[:lower:]' '[:upper:]')=$((cap * 2)) scripts/run_weekly.sh --resume $SLUG</code>"
      return 9
    fi

    [[ $rc -eq 0 ]] && return 0

    # A usage limit, or a real failure? Only the first is slept on.
    if [[ "$kind" == "usage_limit" ]]; then
      resumes=$((resumes + 1))
      if (( resumes > MAX_RESUMES )); then
        say "$name: usage limit again after $MAX_RESUMES resumes — giving up"
        return "$rc"
      fi
      secs="$(printf '%s' "$classified" | sed -n 's/^SECONDS=//p')"
      resets="$(printf '%s' "$classified" | sed -n 's/^RESETS=//p')"
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

# Has this project already finished this stage? Used to skip a stage on a
# resume rather than paying a model to read resume_state.py and be told
# there was nothing to do.
stage_done() {
  "$PY" "$REPO/scripts/resume_state.py" --project "$SLUG" --is-done "$1" \
    >/dev/null 2>&1
}

# ── the renderer's own dependencies ──────────────────────────────────────
#
# WHY THIS IS A START CHECK AND NOT A COMMENT.
#
# `runner/remotion-composer/node_modules` was a SYMLINK into the dev
# checkout at OpenMontage/remotion-composer/node_modules — 733 MB shared
# between two worktrees on two different branches. Every render the runner
# has ever done used whatever happened to be installed over there, which
# means the pinned `package-lock.json` in this tree described one thing and
# the renderer ran another. An `npm install` in the dev checkout, a branch
# switch, or deleting that directory to free disk would have changed the
# runner's renderer without touching the runner.
#
# It is checked at the START, because the alternative is discovering it
# four hours in: the plate pass is the first thing that needs the renderer
# and the first thing that would fail.
COMPOSER_MODULES="$REPO/remotion-composer/node_modules"
if [[ -L "$COMPOSER_MODULES" ]]; then
  fail "node_modules" "$COMPOSER_MODULES is a SYMLINK to $(readlink "$COMPOSER_MODULES").
The renderer would run whatever is installed in that tree, not what this
tree's package-lock.json pins. Fix: rm the link, then npm ci in
$REPO/remotion-composer."
fi
if [[ ! -d "$COMPOSER_MODULES" ]]; then
  fail "node_modules" "$COMPOSER_MODULES is missing.
Fix: npm ci in $REPO/remotion-composer (npm ci, not npm install — the
lockfile is what pins the renderer)."
fi
if [[ ! -x "$REPO/remotion-composer/node_modules/.bin/remotion" ]]; then
  fail "node_modules" "$COMPOSER_MODULES exists but has no remotion binary.
A partial install renders nothing. Fix: npm ci in $REPO/remotion-composer."
fi
say "node_modules: real directory, remotion present"

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

# ── 1. which film ────────────────────────────────────────────────────────
#
# AN UNFINISHED FILM IS FINISHED BEFORE A NEW ONE IS STARTED, and this is
# not a convenience. The topic picker excludes any subject that already has
# a directory under projects/ — a second line of defence added on
# 2026-11-06 so a published film could not be re-made. That defence means a
# re-fire after a mid-run death does NOT pick the film back up: it sees
# projects/king-tut, rules King Tut out, and starts a different film from
# research. The approved script, the scene plan, the asset bank, the edit
# decisions and a 235 MB finished audio mix would all have been left on
# disk, and the human's approval spent for nothing.
if [[ -z "$RESUME" && -z "$BRIEF" && "$NEW_FILM" != "1" ]]; then
  RESUME="$("$PY" "$REPO/scripts/unfinished_film.py" 2>/dev/null || true)"
fi

if [[ -n "$RESUME" ]]; then
  SLUG="$RESUME"
  [[ -d "$REPO/projects/$SLUG" ]] \
    || fail "resume" "no project at projects/$SLUG — nothing to resume"
  TOPIC="$("$PY" -c "
import json, sys
try:
    print(json.load(open('$REPO/projects/$SLUG/project.json'))['title'])
except Exception:
    print('$SLUG')
")"
  say "resuming the unfinished film: $SLUG  ($TOPIC)"
  say "         pass --new to start a different film instead"
  "$PY" "$REPO/scripts/resume_state.py" --project "$SLUG" 2>&1 | sed 's/^/         /'
  notify "<b>Weekly run resuming an unfinished film</b>
film: $TOPIC
project: <code>$SLUG</code>
code: <code>$RUN_ON @ $RUN_HEAD</code>
power: ${RUN_POWER:-unknown} ${RUN_CHARGE:-}

Finished stages are not rebuilt. The script is already approved; it will not
be rewritten and you will not be asked to approve it again.

log: $LOGDIR"
else
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
code: <code>$RUN_ON @ $RUN_HEAD</code>
power: ${RUN_POWER:-unknown} ${RUN_CHARGE:-}
log: $LOGDIR"
fi

# ── 2. the film, up to the script ────────────────────────────────────────
require_power "the script stage"
PROMPT="$LOGDIR/prompt.txt"
cat > "$PROMPT" <<PROMPTEOF
Make this week's documentary, from research through to the script, and stop.

Pipeline:  pipeline_defs/narrated-documentary.yaml  (read YOUR stages only)
Project:   $SLUG
Brief:     $BRIEF  (take the first brief)

YOUR CONTRACT IS docs/STAGE_CONTRACT.md. Read it first, and read it INSTEAD
OF AGENT_GUIDE.md — that file is 48 KB written for an agent driving a
production conversationally with a human present, and you pay for every byte
of it again on every turn. The 2026-11-06 script stage read it once at turn
20 and carried it for 288 more.

THEN run this and obey what it says:

    .venv/bin/python scripts/resume_state.py --project $SLUG

This stage can be RE-ENTERED after a usage limit, and when it is, the work
already on disk is finished work. Do not rebuild a stage it marks [x]: read
that stage's artifact and carry on from the first one it does not mark.
Rebuilding spends the run twice and overwrites a result that was fine.

YOU HAVE $TURNS_SCRIPT TURNS. At the cap the stage fails and is not resumed.
If you are going to run out, stop and write what you have with a note of
what is missing — a partial artifact can be re-entered, a stage that dies
mid-thought leaves nothing.

INSTEAD OF THE TWO BIGGEST FILES, read their digests. The playbook is 44 KB
and the script stage uses nine of its twenty-three sections; the research
brief is 72 KB and most of each data point is a URL you never read:

    .venv/bin/python scripts/playbook_digest.py --stage script
    .venv/bin/python scripts/brief_digest.py --project $SLUG

The digests are generated from those files, not copies of them, so they
cannot drift. The fact gate reads the REAL brief, so a digest can never let
an unsourced sentence through. If a digest is missing something this stage
needs, that is a bug in the digest script — say so in your closing report.

Every gate in the pipeline is auto-approved EXCEPT the script gate, which is
a human one and is handled outside this process — do not wait for it and do
not approve it yourself.

Write the script to projects/$SLUG/artifacts/script.json and the hero style
frames to projects/$SLUG/renders/style/. Do not render the film.

EVERY FACTUAL SENTENCE MUST BE ATTRIBUTED, and this is checked before the
human sees the script. A sentence carrying a date, a number, a proper noun or
a quotation needs a claim id in its PARAGRAPH's claims list, and that claim
must exist in the research brief's data_points with a source_url.

Write the script's sections with a \`paragraphs\` list, each entry
{"text": "...", "claims": ["c07", "c12"]}, and give every data point in the
research brief an explicit \`id\`. A section-level \`source_ref\` naming a bag
of ids DOES NOT COVER ANYTHING any more: it attributes a whole act to a list,
so it cannot say which sentence rests on which claim, and one resolving id in
it used to carry thirty sentences.

AFTER EACH ACT, BEFORE WRITING THE NEXT ONE, run:

    .venv/bin/python scripts/check_claims.py --project $SLUG --section <act>

and fix what it reports before continuing. It is the same two checks the gate
makes, scoped to one act and cheap enough to run six times. Running it at the
end instead means composing an act around a claim that was never in the brief
and finding out when the whole script is done.

A sentence that counts or signposts the FILM's own structure rather than
saying anything about the world — "Four questions", "The bones first" — takes
a \`[framing]\` marker inline at the head of the sentence. The gate cannot
infer it: it cannot tell "four questions", meaning the film's four acts, from
"four tablets", which is a fact. You write it, and it is reviewable at the
script gate like any other sentence you wrote.

A marker is not a licence. A [framing] sentence is skipped only if it carries
no proper noun, no number of ten or more, and no date; one that names or
counts something real is checked like any other. No more than 5% of the
film's sentences may be framing.

Do not invent a claim id, and do not renumber one to something that happens
to exist. If a sentence needs a source the brief does not have, either
research it and add the data point — with a source_url — or cut the sentence.
easter-island shipped citing fifty-four ids against a fifteen-claim ledger;
forty-two of them had never existed.
PROMPTEOF

# The owner's angle constraint, if this subject has one, as instruction rather
# than as a field three keys deep in a file the prompt said to "take the first
# brief" from. Prints nothing when there is no constraint.
"$PY" "$REPO/scripts/angle_brief.py" --brief "$BRIEF" >> "$PROMPT" 2>/dev/null || true

if stage_done script; then
  say "script: approved and on disk already — not rewriting it"
elif [[ "$SMOKE" == "1" ]]; then
  say "smoke: not calling claude -p"
elif [[ "$DRY_RUN" == "1" ]]; then
  say "dry run: skipping claude -p"
else
  say "writing the script (claude -p, $TURNS_SCRIPT turns)"
  claude_stage "script" "$LOGDIR/script_stage" "$(cat "$PROMPT")" "$TURNS_SCRIPT" \
    || fail "script stage" "$(tail -20 "$LOGDIR/script_stage.log" 2>/dev/null \
                             || tail -20 "$LOGDIR/script_stage.err")"
fi

# ── 2b. is every factual sentence attributed? ────────────────────────────
require_power "the fact gate"
#
# BEFORE the human gate, not after: the gate asks a person to approve a
# script, and a script whose claims do not resolve to a sourced ledger entry
# is not a script to put in front of them.
#
# This found that easter-island's act 4 cites fourteen claim ids and that
# none of them exist — the whole act, twenty-eight factual sentences, with an
# attribution chain that pointed past the end of a fifteen-entry ledger.
if stage_done script && [[ -n "$RESUME" ]]; then
  say "fact coverage: the approved script already passed it — skipping"
elif [[ "$SMOKE" != "1" && "$DRY_RUN" != "1" ]]; then
  say "fact coverage ($FACT_BACKEND)"
  "$PY" "$REPO/lib/verify_fact_coverage.py" --project "$SLUG" \
    --backend "$FACT_BACKEND" --report "$LOGDIR/fact_coverage.md" \
    > "$LOGDIR/fact_coverage.log" 2>&1 \
    || fail "fact coverage" "$(tail -12 "$LOGDIR/fact_coverage.log")"
fi

# ── 3. the human ─────────────────────────────────────────────────────────
require_power "the script gate"
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
if stage_done script && [[ -n "$RESUME" ]]; then
  # checkpoint_script.json carries human_approved=True, and lib/checkpoint.py
  # refuses to write a gated stage completed without it. So the approval is a
  # fact on disk, not a flag this script is trusting itself about. Asking
  # again would wake someone at 10am to re-approve what they approved at
  # 20:48.
  say "script gate: already approved (checkpoint_script.json) — not asking again"
elif [[ "$DRY_RUN" == "1" ]]; then
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
to projects/$SLUG/artifacts/script.json. Change nothing else.

Read docs/STAGE_CONTRACT.md, not AGENT_GUIDE.md. You have $TURNS_NOTES turns:
this is an edit to one file, not a stage." "$TURNS_NOTES" \
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

# ── 4. the film, one capped stage at a time ──────────────────────────────
#
# WHY FOUR STAGES AND NOT ONE. This was a single `claude -p` call told to go
# from the approved script to a delivered film. On 2026-11-06 that call ran
# 1,222 turns over 2h45m, grew its context to 842,269 tokens, read 388
# million cache tokens and cost $212.43 — and then hit the five-hour usage
# window one minute after the audio mix finished, with the picture never
# started.
#
# A `claude -p` stage re-reads its whole conversation on every turn, so the
# bill is the context size times the turn count: QUADRATIC IN TURNS. Of that
# $212.43, $194.04 was cache reads. The information the stage actually moved
# was 745 KB of tool output, about 190,000 tokens. It paid 388 million for
# 190 thousand.
#
# Four stages, each starting from an empty context, restart that quadratic
# four times instead of running it once to 1,222. Each has a turn cap, each
# ends by writing its artifact and stopping, and the hand-off between them
# is a file on disk — which is also what makes a mid-run death resumable.
#
# And the picture itself has NO MODEL AT ALL. scripts/render_film.py renders
# the plate, the look pass and the type pass, delivers the file AND RUNS THE
# GATES. There was never a decision in the compose stage; there was a loop
# with a sleep in it, and 65 of the render stage's tool calls were that loop.

# What a stage is told before its own instructions. Everything here is about
# NOT carrying what the other stages need.
stage_preamble() {
  local stage="$1" cap="$2" skill="$3"
  cat <<PRE
You are the $stage stage of projects/$SLUG, and nothing else.

YOUR CONTRACT IS docs/STAGE_CONTRACT.md. Read it, and read it INSTEAD of
AGENT_GUIDE.md: that file is 48 KB written for an agent driving a whole
production conversationally, and a single stage pays for every byte of it
again on every turn.

FIRST, before anything else, run this and obey what it says:

    .venv/bin/python scripts/resume_state.py --project $SLUG

A stage it marks [x] is FINISHED. Read its artifact and carry on. Do not
rebuild it.

YOU HAVE $cap TURNS. At the cap this stage FAILS and is not resumed. If you
are going to run out, stop and write what you have with a note of what is
missing: a partial artifact can be re-entered, a stage that dies mid-thought
leaves nothing. Spending turns on a loop is what the cap is for — the stage
this replaced edited one file it had written itself 48 times and read it
back 13 times.

READ THESE, AND NOT MORE:

    .venv/bin/python scripts/playbook_digest.py --stage $stage
    skills/pipelines/narrated-documentary/$skill

The playbook is 44 KB of twenty-three sections and this stage uses a
handful; the digest is generated from the same file so it cannot drift. Read
a SLICE of a large artifact with python, never \`cat\`: scene_plan.json is
329 KB, edit_decisions.json 288 KB and render_props.json 425 KB on a real
film, and reading one whole costs you 80–110 K tokens on every later turn.

DO NOT edit lib/, scripts/, schemas/, styles/, remotion-composer/src/ or
config.yaml. The runner refuses to start when they are dirty, so an edit
here stops next week's run — the 2026-11-06 stages left seven such files
modified and the next run refused. If shared code is wrong, and twice now it
genuinely has been, SAY SO IN YOUR CLOSING REPORT with the file, the line
and the cause, and work around it.

AUTO-APPROVE YOUR OWN GATE. pipeline_defs/narrated-documentary.yaml marks
scene_plan and assets human_approval_default: true, and lib/checkpoint.py
refuses to write a gated stage \`completed\` without human_approved=True. The
ONLY human gate in this pipeline is the script gate, and it is handled
outside this process and is already past. So write your checkpoint
\`completed\` with human_approved=True and say in your closing report what a
reviewer would have wanted to look at. A checkpoint left \`awaiting_human\`
stops the film: the next stage reads resume_state.py, does not see yours as
finished, and builds it again.

DO NOT render the film and do not wait for a render. That is not a stage.
PRE
}

# $1 stage  $2 cap  $3 director skill  $4 what this stage must produce
pipeline_stage() {
  local stage="$1" cap="$2" skill="$3" body="$4"
  if stage_done "$stage"; then
    say "$stage: already finished — skipping"
    return 0
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    say "dry run: skipping the $stage stage"
    return 0
  fi
  require_power "the $stage stage"
  say "$stage (claude -p, $cap turns)"
  claude_stage "$stage" "$LOGDIR/${stage}_stage" \
    "$(stage_preamble "$stage" "$cap" "$skill")

$body" "$cap" \
    || fail "$stage stage" "$(tail -20 "$LOGDIR/${stage}_stage.log" 2>/dev/null \
                             || tail -20 "$LOGDIR/${stage}_stage.err")"
}

pipeline_stage scene_plan "$TURNS_SCENE_PLAN" scene-director.md \
"Produce projects/$SLUG/artifacts/scene_plan.json from the APPROVED script at
projects/$SLUG/artifacts/script.json.

Validate it against schemas/artifacts/scene_plan.schema.json and check every
authored slot with lib/buildability.py, which validates against
remotion-composer/component-contract.json — required props, required keys on
every array item, and enum ranges per component. A slot that passes
buildability and renders with no picture is a defect worth reporting: the
contract calls a plate \`image\` and the renderer used to read only
\`backgroundImage\`.

Write the checkpoint and STOP. Do not generate or acquire a single asset."

pipeline_stage assets "$TURNS_ASSETS" asset-director.md \
"Produce the asset bank and the asset manifest for every slot the scene plan
asks for: projects/$SLUG/artifacts/asset_bank.json and asset_manifest.json,
plus the narration audio.

Use the scripts that exist rather than writing programs:
scripts/build_asset_bank.py builds the Wikimedia bank from bank_subjects,
lib/reuse_rules.py holds the one-film-one-use rule,
scripts/synthesize_narration.py synthesises the narration one segment per
beat and bakes the written air, scripts/measure_music.py measures the music
library against the playbook's bed criteria.

Write the checkpoint and STOP. Do not build the edit."

pipeline_stage edit "$TURNS_EDIT" edit-director.md \
"Produce projects/$SLUG/artifacts/edit_decisions.json, the Remotion props at
artifacts/render_props.json, and the finished audio mix at
renders/mix_final.wav with its renders/mix_report.json.

lib/build_render_props.py turns edit_decisions into the props Remotion
renders; lib/verify_rhythm.py says whether the edit has a rhythm or only an
average. An authored cut carries its component's props flat beside
\`type\` and needs no \`source\`.

Those three files are the whole hand-off: the next stage is NOT an agent, it
is scripts/await_render.py, which starts the render and waits with no model
open. Write the checkpoint and STOP."

# ── 4b. the picture: no model, no context, no usage limit ────────────────
require_power "the render"
if [[ "$DRY_RUN" == "1" ]]; then
  say "dry run: skipping the render"
else
  # Checked here, cheaply, rather than discovered by render_film.py after
  # the waiter has already started: "no mix at ..." is the right error but
  # the wrong place for it.
  MISSING=""
  for needed in "artifacts/render_props.json" "renders/mix_final.wav"; do
    [[ -s "$REPO/projects/$SLUG/$needed" ]] || MISSING="$MISSING $needed"
  done
  if [[ -n "$MISSING" ]]; then
    fail "render" "the edit stage did not leave:$MISSING
A render needs the props and the mix. Re-run the edit stage."
  fi
  # No `stage_done compose` test: compose has no agent now, so nothing
  # writes its checkpoint. await_render.py answers the question itself —
  # it returns 0 immediately when render_status.json says delivered and the
  # file is there — and it costs nothing to ask.
  say "rendering (no model open; the waiter makes no API calls)"
  "$PY" "$REPO/scripts/await_render.py" --project "$SLUG" \
    --timeout-hours "$RENDER_TIMEOUT_HOURS"
  RENDER_RC=$?
  case "$RENDER_RC" in
    0) say "the film is delivered and the gates passed" ;;
    2) fail "render" "still rendering after ${RENDER_TIMEOUT_HOURS}h. The
render is STILL GOING and was deliberately not killed — a render killed near
the end leaves no file and no error. Watch
projects/$SLUG/render.log, then re-fire: the run picks this film back up.
No model was open for any of it, so nothing was spent waiting." ;;
    *) assert_code_clean "render"
       fail "render" "$(tail -20 "$REPO/projects/$SLUG/render_status.json.tail" \
                        2>/dev/null || tail -20 "$REPO/projects/$SLUG/render.log" \
                        2>/dev/null || echo "the render failed and left no log")" ;;
  esac
fi

# ── 5. publish ───────────────────────────────────────────────────────────
require_power "publishing"
if [[ "$DRY_RUN" == "1" && ! -f "$REPO/projects/$SLUG/artifacts/listing.json" ]]; then
  say "dry run: no listing for $SLUG, so there is nothing to publish"
  say "         scripts/dry_run.py is what exercises the publisher"
  say "done (dry run: topic and hand-offs only)"
  exit 0
fi
assert_code_clean "the render"

# ── 5a. the credits page, BEFORE the upload ──────────────────────────────
# The description links to it, so it has to be live before the description
# is. See scripts/publish_credits_page.sh for why the push lives in a shell
# step rather than in the publisher.
say "credits page"
if ! "$REPO/scripts/publish_credits_page.sh" "$SLUG" \
      > "$LOGDIR/credits_page.log" 2>&1; then
  fail "credits page" "$(tail -5 "$LOGDIR/credits_page.log")"
fi
say "$(tail -1 "$LOGDIR/credits_page.log")"

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

assert_code_clean "publish"
say "done"
notify "<b>Weekly run finished</b>
topic: $TOPIC
$(tail -3 "$LOGDIR/publish.log")

<b>cost</b>
<pre>$COST</pre>"

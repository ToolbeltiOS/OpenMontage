# One stage of the weekly film

You were started by `scripts/run_weekly.sh` to run **one stage** of
`pipeline_defs/narrated-documentary.yaml` and then stop. This file is your
contract. **Read this instead of `AGENT_GUIDE.md`** — that file is 50 KB
written for an agent that drives a whole production conversationally, and
you are not that agent.

## Why this file is short

You pay for your context on every turn. The 2026-11-06 render stage ran
1,222 turns with a context that grew to 842,269 tokens, re-read 388 million
cache tokens, and cost $212.43 — of which $194 was re-reading the
conversation. It moved 745 KB of actual information. The five biggest files
it opened came to 258 KB and it carried every byte of them for the rest of
its life.

So the rule behind every rule below: **anything you read or write once, you
then re-read on every remaining turn.** A 44 KB playbook read at turn 20 of
300 costs 11,000 tokens × 280 turns. Reading it twice, which the script
stage did, costs that twice.

## Your turn budget is real

The runner passes `--max-turns`. When you hit it the stage FAILS — it is not
resumed, because a stage that spent its budget will spend it again. The caps
are: script 60, scene_plan 40, assets 30, edit 30.

If you are going to run out, **stop and write what you have** with a clear
note of what is missing. A stage that lands an honest partial artifact can be
re-entered. A stage that dies mid-thought at the cap leaves nothing.

## Start here, every time

```
.venv/bin/python scripts/resume_state.py --project <slug>
```

Obey it. A stage it marks `[x]` is finished: its artifact is on disk and was
approved or auto-approved. **Read that artifact and carry on.** Rebuilding it
spends the run twice and overwrites a result that was fine.

## Read these, and not more

| Instead of | Read |
|---|---|
| `AGENT_GUIDE.md` (50 KB) | this file |
| `styles/wak3up-documentary.yaml` (44 KB) | `scripts/playbook_digest.py --stage <stage>` |
| `artifacts/research_brief.json` (72 KB) | `scripts/brief_digest.py --project <slug>` |
| the whole pipeline manifest (27 KB) | your stage's entry — read it with python, not `cat` |
| `scripts/run_weekly.sh` | nothing. It started you; it is not your business |

Your stage's director skill (`skills/pipelines/narrated-documentary/<stage>-director.md`)
is 5–13 KB and **is** worth reading, once. Do not read the other stages'.

Read a **slice** of a large JSON artifact with python, never `cat`:

```bash
.venv/bin/python -c "
import json; d=json.load(open('projects/<slug>/artifacts/scene_plan.json'))
print(len(d['scenes']), [s['id'] for s in d['scenes'][:5]])"
```

`scene_plan.json` is 329 KB, `edit_decisions.json` 288 KB and
`render_props.json` 425 KB on a real film. Reading one whole is 80–110 K
tokens that you then carry for every remaining turn.

## Do not author programs

The 2026-11-06 render stage wrote **thirty Python files** into
`projects/king-tut/` and edited `build_scene_plan.py` **48 times**, reading
it back 13 times. It also emitted 793,389 output tokens — every one of which
it then re-read on every later turn, so authoring a program inside a stage
is paid for twice: $25 per million to write it, then $0.50 per million for
each turn it stays in context.

The deterministic work is already written. Call it:

| What you want | Call |
|---|---|
| are this act's citations real? | `scripts/check_claims.py --project <slug> --section <act>` |
| does every factual sentence carry a sourced claim? | `lib/verify_fact_coverage.py --project <slug>` |
| beats and written air out of the prose | `lib/script_beats.py` |
| is this authored slot buildable? | `lib/buildability.py` |
| build the Wikimedia asset bank | `scripts/build_asset_bank.py` |
| one film, one use of each asset | `lib/reuse_rules.py` |
| measure music against the bed criteria | `scripts/measure_music.py` |
| synthesise narration, one segment per beat | `scripts/synthesize_narration.py` |
| align narration to the script | `scripts/align_narration.py` |
| edit_decisions → Remotion props | `lib/build_render_props.py` |
| has the edit a rhythm or only an average? | `lib/verify_rhythm.py` |
| where did the film leave the playbook? | `scripts/critic_pass.py` |

If one of these is missing something you need, **say so in your closing
report** and do the smallest thing that gets this film made. A throwaway
script in `projects/<slug>/` is acceptable when nothing fits; forty-eight
edits to one is not — that is a program being developed, and a stage is not
the place to develop a program. Promote it to `scripts/` in a commit, later,
with a human looking.

## Never edit shared code

`lib/`, `scripts/`, `schemas/`, `styles/`, `remotion-composer/src/` and
`config.yaml` are the code the film is traced to. The runner **refuses to
start** when they are dirty, so an edit you make here stops next week's run.
The 2026-11-06 stages left seven such files modified and the 2026-11-07 run
refused with `7 uncommitted change(s) to code`.

If shared code is genuinely wrong — and twice now it genuinely has been —
**say so in your closing report with the file, the line and the cause.** Do
not fix it. A human commits it with its reason, which is what turns a defect
into a thing that stays fixed.

## Never wait for a render

A render takes hours. You do not watch it. You do not start one as a
background task of your own: a background task is stopped at two hours, and
the Noah plate was killed that way three times, the last at 33,055 of 35,561
frames, leaving no file and no error.

The compose stage has **no agent at all**. `scripts/await_render.py` starts
`scripts/render_detached.sh` and waits, with no model open, and
`scripts/render_film.py` runs the gates itself. If your stage's artifact is
done and the next thing is a render, **your stage is over**.

## Finish the stage, then stop

1. Write your canonical artifact to `projects/<slug>/artifacts/`.
2. Validate it against `schemas/artifacts/<artifact>.schema.json`.
3. Write the checkpoint (`lib/checkpoint.py`). A stage the manifest gates
   can only be `completed` with `human_approved=True` — the runner handles
   the human gates outside your process, so do not wait for one and do not
   approve one yourself.
4. Append any decision you made to `artifacts/decision_log.json`, reusing
   the same `(category, subject)` pair when you revise an earlier one.
5. **End your turn.** Say what you produced, what you had to work around,
   and anything you found wrong in shared code.

Doing the next stage's work in the same process is the thing this split
exists to prevent.

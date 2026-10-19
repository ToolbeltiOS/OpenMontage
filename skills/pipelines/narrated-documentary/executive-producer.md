# Executive Producer — Narrated Documentary Pipeline

## When To Use

You are orchestrating a narrated long-form documentary (12–25 minutes) through
`pipeline_defs/narrated-documentary.yaml`. This skill is the orchestration
contract: it tells you the stage order, what each gate costs, and the handful of
rules that are specific to long-form narrated work rather than to any one stage.

Read `AGENT_GUIDE.md` first. Nothing here overrides it.

## Stage Order

```
research → proposal → script → scene_plan → assets → edit → compose → publish
```

Five stages gate on human approval: **proposal, script, scene_plan, assets,
publish**. `research`, `edit` and `compose` auto-proceed. The manifest value is
binding — never re-judge it, and never write a gated stage `completed` without
`human_approved=True`.

Call `checkpoint.get_next_stage()` to find where to resume. Read the stage's
director skill before doing any work in that stage.

## What Makes This Pipeline Different

This pipeline exists because no ancestor could do all three of the following at
once. Hold all three or the piece fails:

1. **Citation-bound.** The `research_brief` is not background reading — it is a
   claim ledger. The script may not state a date, name or figure that is absent
   from it. This is checked at the script gate.
2. **Narration is the spine.** Narration is required, not optional. Every visual
   decision downstream is placed against a narration timestamp, not against a
   music beat. A montage with narration sprinkled on top is the wrong shape.
3. **Retrieval-first, keyless-first.** Visuals are found, not generated. Search
   the keyless public archives before any keyed provider, and never substitute a
   generated image for footage you failed to find — flag the gap instead.

## Duration Discipline

Long-form is where pipelines quietly fail. Two numbers govern everything:

- **Narrated word budget** — the playbook sets it. At ~150 wpm, a 20-minute
  piece is ~3,000 narrated words. Count words; do not estimate.
- **Measured narration runtime** — after the assets stage you have real audio.
  Measure it with `ffprobe`. If measured runtime is more than 10% off the target,
  send the script back rather than stretching or trimming visuals to hide it.

Never report a duration you have not measured.

## Budget

`budget_default_usd: 0.00`. This pipeline is designed to run at zero marginal
cost: keyless archives, a local TTS voice, a user-supplied music library, and
local composition. If any stage wants to spend money, that is a change of plan —
announce it, price it, and get approval per AGENT_GUIDE's decision contract
before calling anything paid.

## Wall Time

`max_wall_time_minutes: 90`. A 20-minute render is the single longest operation
in the pipeline and can consume most of that budget on its own. Do not spend the
allowance on speculative re-renders: get the storyboard approved at the assets
gate, then render once.

## Send-Backs

`max_send_backs: 2`. The two failures worth sending back for:

- **A padded act.** An act that restates an earlier one is a script defect, not
  an editing problem. Send it back to `script`.
- **A slideshow.** If the scene plan's visual mix drifts past the playbook's
  stills budget, send it back to `scene_plan`. Do not try to rescue it in `edit`.

Anything else: fix forward and note it in the review.

## Reviewer

Self-review after every stage using `skills/meta/reviewer.md`, loading the
`review_focus` items for the current stage from the manifest. Maximum two rounds.
Treat the playbook's `quality_rules` as constraints, not suggestions.

## Common Pitfalls

- Letting the script run long because the visuals are ready — the script is the
  contract, not the footage.
- Treating the research brief as done once prose starts; new claims appear during
  drafting and must be added to the ledger with a source or cut.
- Rendering before the storyboard is approved, then discovering the pacing
  problem 80 minutes later.
- Reporting an estimated duration, resolution or loudness instead of a measured one.

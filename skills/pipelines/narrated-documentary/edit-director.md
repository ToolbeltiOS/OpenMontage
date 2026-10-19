# Edit Director — Narrated Documentary Pipeline

Adapted from `skills/pipelines/hybrid/edit-director.md`. Hybrid locks an anchor
cut from source footage and layers support on top. Here the anchor is not
footage — it is **the narration track**.

## When To Use

Assets are approved. You now produce `edit_decisions`: the concrete timeline of
cuts, overlays, captions and music that the compose stage renders.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | `asset_manifest`, `scene_plan`, `script` | Assets, slot intent, narration timing |
| Prior artifact | `proposal_packet` | The locked `render_runtime` |
| Playbook | Active style playbook | Typography, grade, ducking, transition vocabulary |

## Carry The Runtime Forward Unchanged

Read `proposal_packet.production_plan.render_runtime` and write the identical
value into `edit_decisions.render_runtime`. This field is **locked at proposal**
and carried through here untouched. If the runtime now looks wrong, that is a
conversation with the user and a new `render_runtime_selection` decision — not a
quiet edit. A silent swap is a CRITICAL governance violation.

## Process

### 1. Lay The Narration First

The narration track is the spine. Place it at t=0 and let its **measured**
timings define the timeline. Every cut is then positioned against a narration
timestamp, never against a music bar or a round number.

If narration runtime and planned slot holds disagree, the narration wins — adjust
holds, and if the drift is structural, say so rather than compressing forty cuts
by 4% each.

### 2. Place Cuts On Meaning

Walk the slots in order and assign each a real in-point and duration against the
narration. Rules that hold across the piece:

- **Honour the cadence ceiling.** The playbook's maximum hold is hard.
- **Hero slots hold longest.** The biggest claim gets the longest look.
- **Cutaways are shortest.** Mid-sequence punctuation should feel like
  punctuation.
- **Cut on the sentence, not through it.** Land cuts at clause or sentence
  boundaries. A cut mid-phrase reads as a mistake unless it is deliberately
  jarring.

### 3. Vary Adjacency

No two adjacent cuts share both subject and scale. Check the whole sequence, not
just pairs you happened to plan together — adjacency problems appear when two
independently sensible acts meet at a boundary.

### 4. Keep The Transition Vocabulary Small

At most four distinct transition types in the whole piece. A documentary that
uses nine transitions looks like a template demo. Pick a default (usually a hard
cut), one soft option for act boundaries, and at most two special-purpose moves.

### 5. Layer Support In Priority Order

Narration is placed; now add, in this order:

1. **Captions** — word-level, per the playbook's style.
2. **Lower-thirds** — names, places, dates. On first mention only.
3. **Maps and timelines** — the orienting graphics.
4. **Document reveals** — scans and artefacts, pushed into.
5. **Any remaining overlay.**

Protect readability: never stack captions, a lower-third and a chart in the same
window. If three layers collide, something moves or something goes.

### 6. Duck The Music

Music runs continuously unless the proposal says otherwise, ducked under
narration by the playbook's amount. Duck against the narration envelope rather
than at fixed act boundaries, so the bed lifts in the gaps between sentences —
that is what makes a bed feel scored rather than pasted under.

Crossfade at act boundaries; do not hard-cut music.

### 7. Give Every Cut A Reason

Each cut carries a short `reason`. This is not ceremony — it is what makes the
timeline reviewable and what catches the cut that exists only because a clip was
available.

### 8. Reserve The Ending

Nothing essential in the last 20 seconds. The outro CTA is 10 seconds maximum.

### 9. Quality Gate

- `render_runtime` equals the proposal's value exactly.
- Every cut has an in-point against narration, a duration and a reason.
- No adjacent cut shares subject and scale.
- At most four transition types.
- Music present and ducked; crossfades at act boundaries.
- Word-level caption track present.
- `total_duration_seconds` equals the sum of cut durations.

## Common Pitfalls

- Building the timeline against the script's *estimated* timings instead of the
  measured narration.
- Cutting on a metronome, which no amount of good footage rescues.
- Rescuing a thin scene plan with more overlays — it reads as clutter, not depth.
- Ducking at act boundaries only, so the bed fights every sentence.
- A cut whose only reason is that the clip was already downloaded.

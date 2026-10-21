# Scene Director — Narrated Documentary Pipeline

Adapted from `skills/pipelines/documentary-montage/scene-director.md` (slot and
query discipline) and `skills/pipelines/explainer/scene-director.md` (script-led
beats). The montage original plans slots against music; this version plans them
against **narration timestamps**.

## When To Use

The script is approved. You now turn narration into a slot list: an ordered set
of visual holds, each with a description, search queries, a source preference and
a treatment. The asset director fills these slots; it does not invent them.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/scene_plan.schema.json` | Artifact validation |
| Prior artifact | `state.artifacts["script"]["script"]` | Narration text and timings |
| Prior artifact | `state.artifacts["proposal"]["proposal_packet"]` | Visual approach, runtime, cadence |
| Playbook | Active style playbook | Cut cadence, stills budget, palette, typography |
| Optional tools | `frame_sampler`, `scene_detect` | Inspecting any supplied footage |

## Mental Model

A slot is a **promise about what the viewer sees while a specific sentence is
spoken**. That makes three things true:

1. **Slots are derived from narration, not from available footage.** Write the
   slot the sentence needs, then go find it. Writing slots around footage you
   already have is how a documentary becomes a stock-footage reel.
2. **Every slot has a timestamp.** It opens at a narration time and holds for a
   duration. The sum must track the script.
3. **A slot is one shot.** If you need two images to serve a sentence, that is
   two slots.

## Process

### 1. Take The Shot Band From The Beat, Not From One Cadence

Work act by act. Place a cut where the *meaning* changes — a new subject, a new
place, a new claim — never on a metronome.

**The script says which beat each paragraph is, and the beat sets the band.**
Copy the beat onto every slot it covers (`beat` on the slot, carried through to
`edit_decisions.cuts[].beat`) and take the hold from `rhythm.targets` in the
playbook:

| beat | `target_hold_seconds` | cuts/min through that passage |
|---|---|---|
| `reveal` | 12–25, **one shot** | 2–4 |
| `exposition` | 6–10 | 6–9 |
| `landing` | 4–8, and no cut lands inside the air | 0–2 |
| `transition` | 1.5–3.5, as a burst of 8–15s | 15–25 momentarily |

A reveal may only hold past the stills cap when the shot **moves inside the
frame** — an authored graphic with timed reveals, real footage, a parallax
across an oversized frame, or a push of more than 4% total. Set
`internal_motion: true` on the slot when it does. A twelve-second hold on a
static photograph is the slideshow the cap was written against, and the beat
label does not change that; the edit gate checks it.

There is one cadence band left in the playbook, `visual_cadence.cut_interval_seconds`,
and it is the exposition band — what a slot gets when no beat reaches it.

**Why this replaced a single band.** Run #1 had one band for the whole film.
181 of its 182 shots came out between 5 and 8 seconds, p10 5.89s and p90 7.47s,
with 8 to 10 cuts in every single minute. The playbook said "cut on meaning,
never on a fixed interval" the whole time — nothing implemented it. Every
reference film measured for run #2 swings by a factor of three to seven inside
one film (`reports/reference_pacing.md`).

### 1b. Hold The Picture Through The Air

Where the script wrote `[air N.Ns]`, no cut lands inside the silence. The shot
that carries the landing line carries the gap after it too. A cut inside the air
spends the silence on a new picture, which is the one thing it was written to
avoid.

### 2. Write Slot Descriptions In Concrete Nouns

The description is what a human would have to see. Concrete noun plus adjective,
no abstractions.

- Good: `"limestone staircase descending into dark rock-cut shaft, handheld torchlight"`
- Bad: `"the mystery of the discovery"`

A slot you cannot describe in concrete nouns is a slot you cannot search for, and
it will come back as something unrelated.

### 3. Give Every Slot 2–3 Short Queries

Short, literal, provider-facing. Vary the vocabulary across the set so you are
not asking the same question three times:

```json
{
  "slot_id": "a1_s04",
  "description": "limestone staircase descending into dark rock-cut shaft",
  "queries": ["stone staircase descending underground",
              "rock cut tomb entrance shaft",
              "archaeology excavation stairs dark"],
  "preferred_sources": ["archive_org", "wikimedia", "nara", "pixabay_video"],
  "treatment": "footage",
  "target_hold_seconds": 6.5,
  "narration_start_seconds": 41.2,
  "hero": false
}
```

### 4. Order `preferred_sources` Keyless-First

Follow the playbook's strict tier order. For this pipeline that is:

1. **Keyless archives** — `archive_org`, `nasa`, `esa`, `wikimedia`, `loc`, `nara`
2. **Pixabay video** — `pixabay_video`
3. **Free stock scrapers** — `mixkit`, `dareful`
4. **Unsplash stills** — `unsplash`

**`pexels` is excluded outright.** Pexels paused new key issuance on 2026-09-30,
`PEXELS_API_KEY` is intentionally unset, and the adapter must not appear in any
`preferred_sources` list — a retrieval that lists it stalls on a missing key.

Match the source to the subject rather than listing all of them: space material
goes to NASA/ESA/JAXA, mid-century and institutional material to Archive.org and
NARA, document scans and artefact stills to Wikimedia and the Library of
Congress, and contemporary generic coverage to the keyed providers.

### 5. Assign A Treatment To Every Slot

Three treatments, and the mix is governed by the playbook:

- **`footage`** — real moving footage. This should be the majority.
- **`motion_graphic`** — must name a concrete Remotion scene type and what it
  shows. A map tracing a route, a timeline placing an event, a document reveal
  pushing in on a scan, a lower-third naming a person. "A graphic here" is not a
  slot; name the type and the content.
- **`still`** — a photograph or scan. **Capped by the playbook** (typically 20%).
  Every still must name its motion treatment — a parallax/2.5D push, a slow drift
  across a larger frame. A still with no movement is a dead hold.

### 6. Compute The Visual Mix And State Slideshow Risk

Count the slots by treatment and record real percentages in
`metadata.visual_mix`. Then assess slideshow risk honestly:

**Risk is high if any of these is true** — stills exceed the playbook cap; any
run of three consecutive slots is all stills; the mean hold exceeds the cadence
ceiling; or more than a third of slots lack a confirmed source family.

If risk is not low, fix the plan here. Do not pass a slideshow downstream with a
note saying it is a slideshow — the edit stage cannot rescue it.

### 7. Check Adjacency

No two adjacent slots should share both subject and scale. Two consecutive wide
shots of the same ruin read as one long shot with a glitch. Vary scale
deliberately: wide establishes, medium carries, detail punctuates.

### 8. Mark Hero Slots

At least two per piece, and at least one per act. A hero slot is where the
narration makes its biggest claim; it gets the longest hold, the best candidate,
and the most search effort.

### 9. Quality Gate

- Every slot has a concrete description, 2–3 queries, keyless-first sources, a
  treatment and a narration timestamp.
- Every act has at least one hero slot.
- Stills within the playbook cap, each with a motion treatment.
- Motion graphics name a concrete scene type.
- `visual_mix` recorded; slideshow risk assessed as low.
- Sum of holds within 10% of the script duration.
- `lib/buildability.py` exits 0 — zero unbuildable slots.

### 10. Run The Buildability Check (Blocking)

```
python3 lib/buildability.py projects/<slug>/artifacts/scene_plan.json
```

It must exit 0 before you checkpoint. The check enforces two things:

- **An authored slot names a component that exists** in
  `remotion-composer/component-contract.json`, and supplies props that satisfy
  that component's contract — required props, required keys on every array
  item, and every enum value in range.
- **A sourced slot points at a file that is on disk.**

`"cross_section — the pyramid in section"` is a description, not a scene. It
will pass every other criterion on this page and then render as a text card.

If the check fails, you have two honest moves and no third: author the slot
properly against a real component, or re-treat it as a sourced slot and give it
queries. Do not weaken the contract to make a slot pass.

If a slot genuinely needs a scene type that does not exist, build the component
first — Zod schema in `src/schemas/docComponents.ts`, entry in
`component-contract.json`, dispatch branch in `src/Explainer.tsx`, demo
composition — and only then author against it. Both contract files must be
updated together or the check and the render will disagree.

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). Checkpoint
`awaiting_human`, present the slot list, the visual mix **and the buildability
result**, and **END YOUR TURN**. Do not present a plan whose buildability check
has not been run.

## Common Pitfalls

- Slot descriptions written as themes rather than as images.
- Listing every provider on every slot, so the search has no preference at all.
- A stills budget met on average but violated in one long stretch.
- "Motion graphic" as a placeholder with no named type — it becomes a text card.
- Treating the buildability check as advisory. It is the only thing between a
  described slot and a silent text-card fallback at compose.
- Planning cuts on a metronome, which reads as mechanical however good the footage.

## Every Still Names Its Move, And The Asset May Refuse It

The move comes from the beat and the register, not from habit. The playbook's
mood table gives a move, a speed, a transition family, a hold multiplier and
whether the music may rise for each `beat × register`, and `lib/camera_intent.py`
is the gate. Two rules are about consecutive shots rather than single ones: a
run of drifting stills must keep one direction, or the eye is thrown back where
it came from; and there is at most one speed ramp per act, into a hard cut.

The asset has exactly one veto. A push into a **dense** frame becomes a lock,
because a frame that is already full reads as a zoom on a photograph rather
than an approach to a subject. Asset classes are assigned by
`lib/asset_classifier.py` and must be on the cut before the move is chosen.

Run #1 gave every still the same push, 182 times, and nothing recorded a
choice because nothing asked for one.

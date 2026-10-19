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

### 1. Walk The Script And Cut On Meaning

Work act by act. Place a cut where the *meaning* changes — a new subject, a new
place, a new claim — not on a metronome. The playbook sets the cadence band
(typically a cut every 5–8 seconds); treat the ceiling as hard and the floor as a
default. Holding one image past the ceiling is the fastest way to lose a viewer.

Two cadence exceptions worth using deliberately:

- **The reveal hold.** On the single biggest claim in the piece, hold longer than
  the ceiling on one strong image and let the narration land. Mark it `hero`.
- **The burst.** Through a dense list or a montage of consequences, run 2–3
  second cuts for 10–15 seconds, then return to the normal cadence.

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

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). Checkpoint
`awaiting_human`, present the slot list and the visual mix, and **END YOUR TURN**.

## Common Pitfalls

- Slot descriptions written as themes rather than as images.
- Listing every provider on every slot, so the search has no preference at all.
- A stills budget met on average but violated in one long stretch.
- "Motion graphic" as a placeholder with no named type — it becomes a text card.
- Planning cuts on a metronome, which reads as mechanical however good the footage.

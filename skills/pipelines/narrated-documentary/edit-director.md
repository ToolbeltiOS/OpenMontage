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
- **Shape the cutting rate across the film, not just within a shot.** The
  playbook names an envelope for cuts per minute and a minimum spread, and a
  flat curve fails the `rhythm` gate however defensible each individual hold
  is. Run #1 passed every per-shot rule and ran 8-10 cuts a minute from the
  first frame to the last: every minute was reasonable and the film had no
  shape. Decide where the film is fast and where it is slow before placing
  cuts, and let the per-minute count follow that decision.
- **Never land a boundary on a cut the source already had.** A clip is rarely
  one take. Cutting away twelve frames or less from the source's own cut gives
  the viewer two cuts a quarter of a second apart, and they read the second as
  a mistake. `lib/verify_source_cuts.py` finds the source's cuts and the
  `source_cuts` gate refuses a boundary inside that window; a step in a
  timelapse is not a cut and is exempt.

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

### 6b. Give Every Cut A Camera Move

The move comes from the beat, not from habit:

| beat | move | why |
|---|---|---|
| `reveal` | **push** | the frame closes on what is being revealed |
| `exposition` | **pull** | context arrives as the frame opens |
| `landing` | **lock** | the picture stops with the voice and holds the air |
| `transition` | **drift** | lateral movement carries the eye to the next subject |

Two rules about neighbours rather than single shots:

- a run of consecutive stills keeps **one direction** — two drifts going
  opposite ways throw the eye back where it came from;
- **one speed ramp per act**, and only into a hard cut.

Write `camera: {move, speed_pct_per_second, direction, reason}` on the cut.
`lib/camera_intent.py` fills it from the beat if you leave it empty, and a move
you choose by hand outranks the table. The reason is not decoration: a move
without one is the default under another name, which is how run #1 ended up
giving the same push to 182 shots.

### 6c. Let Sound And Picture Change At Different Moments

Run #1 cut picture and narration together 182 times. Every boundary was square,
and a square boundary tells the viewer twice, at the same instant, that
something changed.

Set `audio_lead_frames` on the cut:

- **+12 to +18 frames** at an act boundary and into a reveal — the next
  section is already speaking while the previous image is still up (a J-cut);
- **down to −10 frames** at an exposition cut — the picture arrives before the
  sentence that explains it (an L-cut), and only on roughly every third
  exposition cut, because a lead on every cut is a style rather than
  punctuation;
- **0 at a landing.** The picture is holding through written air; moving that
  boundary is the cut the air exists to prevent.

Every non-zero lead carries a `lead_reason`. The leads are applied in
`lib/build_render_props.py`, which moves the boundary and takes the frames from
the neighbour, so the film's length never changes.

### 7. Give Every Cut A Reason

Each cut carries a short `reason`. This is not ceremony — it is what makes the
timeline reviewable and what catches the cut that exists only because a clip was
available.

### 7b. Where An Authored Cut's Props Go

**A cut object is a closed set of EDITORIAL decisions** — where the boundary
is, how the camera moves, whether the sound leads it. An authored scene also
needs a component name and that component's props, which are a different
kind of thing and vary per component. Those go under `scene`, never flat on
the cut.

This is not style. `schemas/artifacts/edit_decisions.schema.json` closes the
cut object, so a cut carrying component props flat fails its own schema and
**the stage cannot be checkpointed at all** — the edit is lost at the end of
the stage that made it.

`source` is required on every cut. For an authored cut it is the SLOT ID,
not a file path. `lib/build_render_props.py` flattens `scene` onto the cut
before the renderer sees it, so the composition is unchanged.

```json
{
  "id": "c017",
  "in_seconds": 0.0,
  "out_seconds": 9.067,
  "layer": "primary",
  "source": "act1_s010",
  "transition_in": "cut",
  "transition_duration": 0.0,
  "reason": "meaning_change | act1_s010 | straight cut on meaning change",
  "beat": "exposition",
  "register": "quiet",
  "internal_motion": true,
  "scene": {
    "type": "evidence_card",
    "treatment": "graphic",
    "act": "act1",
    "actNumber": "01",
    "claim": "The claim this card states, in one sentence.",
    "attribution": "Who said it",
    "status": "claim"
  }
}
```

`layer` is a STRING — `primary`, `overlay` or `background`. Two earlier
films wrote it as an integer and their artifacts no longer match the schema.

### 7c. An Illustration Cut Carries Its Subject

An `illustration` cut is a scene nobody photographed, and the scene planner
has already decided which slots get one. Your job is to carry both of its
required props through, because losing either turns a labelled drawing into
an unlabelled one:

```json
{
  "id": "c041",
  "in_seconds": 182.4,
  "out_seconds": 190.933,
  "layer": "primary",
  "source": "act2_s014",
  "transition_in": "dissolve",
  "transition_duration": 0.5,
  "reason": "meaning_change | act2_s014 | the archive holds nothing of this",
  "beat": "exposition",
  "register": "quiet",
  "internal_motion": true,
  "scene": {
    "type": "illustration",
    "treatment": "graphic",
    "act": "act2",
    "actNumber": "02",
    "image": "assets/library/illustrations/ark-build.png",
    "subject": "Ark under construction",
    "parallax": true
  }
}
```

**`subject` is the label, not the description.** At most 40 characters,
title case — the scene plan already chose it, and you carry it through. The
component renders `ILLUSTRATION — <subject>` across the whole hold at 20px,
`nowrap`, with an ellipsis, so a long line is cut off mid-word on screen;
the full description is the slot's `prompt` and does not belong here. A cut
that drops the subject renders an illustration the viewer may read as a
photograph, and `Explainer.tsx` will not save you: it falls back to `title`
and then to an empty string rather than failing.

**Do not retime it shorter than the label can be read.** The strip is up for
the whole cut, so the cut has to be long enough to read it — treat the
subject line like a lower third, not like a caption.

**Do not promote a cut to `illustration` yourself.** The scene planner owns
that decision, the owner approves each one at the script gate, and
`build_render_props.py` demotes any cut whose subject is not in
`approved.json` back to `annotated_still` or `text_card`. Authoring the type
on a slot that was never approved produces a cut that silently becomes
something else.

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

## Gate Commands (Blocking)

```bash
.venv/bin/python lib/verify_rhythm.py  {artifacts}/edit_decisions.json
.venv/bin/python lib/camera_intent.py  {artifacts}/edit_decisions.json
.venv/bin/python lib/edit_leads.py     {artifacts}/edit_decisions.json
```

## Common Pitfalls

- Building the timeline against the script's *estimated* timings instead of the
  measured narration.
- Cutting on a metronome, which no amount of good footage rescues.
- Rescuing a thin scene plan with more overlays — it reads as clutter, not depth.
- Ducking at act boundaries only, so the bed fights every sentence.
- A cut whose only reason is that the clip was already downloaded.

## The Bed Level Comes From The Playbook

Never write a music level into the EDL by hand. `audio.music_under_speech_lufs`
in the playbook is the decision — **−30 LUFS under speech**, chosen by ear on
the act 2 demo with the sound design present — and `lib/mix_audio.py` reads it
from there. An EDL may state its own level only when a specific film has a
reason, and then the reason belongs in the decision log.

The references run their beds 4–15.5 dB under the voice. Run #1 ran 20 and
every loudness check still passed, because the FILM was −14 LUFS integrated
and nothing measured the music on its own.

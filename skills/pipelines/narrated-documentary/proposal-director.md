# Proposal Director — Narrated Documentary Pipeline

Adapted from `skills/pipelines/explainer/proposal-director.md`, with the
long-form act structure, the mandatory music plan, and the composition-runtime
contract carried over intact.

## When To Use

The `research_brief` exists. You now turn it into a `proposal_packet` the user
approves before a word of script is written. This is the first human gate and the
most important one: it locks the angle, the act structure, the voice, the music
and the render runtime.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/proposal_packet.schema.json` | Artifact validation |
| Prior artifact | `state.artifacts["research"]["research_brief"]` | Angles + claim ledger |
| Playbook | Candidate style playbooks | Visual language |
| Meta skill | `skills/meta/taste-direction.md` | Design read for hero work |
| Registry | Tool availability from preflight | Honest production plan |

## Process

### 1. Present At Least 3 Concepts

Each concept must differ in **angle**, not merely in title. Each must name the
ledger entries that carry it (`grounded_in`), and each must state the act
structure that gets it to the target duration.

For each concept give: title candidates, the cold-open hook, the act list with a
one-line promise per act, the core question, and an honest read on whether the
ledger supports the full runtime.

### 2. Lock The Act Structure

Long-form dies of structural vagueness. Each act needs:

- a one-sentence promise,
- the ledger entries it spends,
- a target duration,
- and **new information** — an act that re-states an earlier act is cut here, not
  discovered at the script gate.

Four to five acts is the band that works for 20 minutes. Fewer and acts sprawl
past attention; more and the piece fragments.

### 3. Narration Plan (MANDATORY)

Narration is **required** on this pipeline — it is the spine, not a garnish. The
plan must name:

- the TTS route and the specific voice,
- the target words-per-minute and the resulting word budget,
- whether word-level caption timings come from the TTS provider or from a
  transcription pass afterwards,
- and the fallback if the user rejects the voice after act 1.

Discover the real routes rather than assuming:

```python
registry.get_by_capability("tts")
```

Announce the provider and voice before synthesizing anything, and log it as a
`voice_selection` decision. If the voice changes later, **append** a new
`decision_log` entry reusing the same `category` and `subject` — never edit the
old one.

### 4. Music Plan (MANDATORY)

Surface music now, not at the asset stage where a failure is expensive. Check all
three sources and present what actually exists:

```python
registry.get_by_capability("music_library")
registry.get_by_capability("music_search")
registry.get_by_capability("music_generation")
```

Then offer the user explicit choices: use a track from their library (name which
ones and their durations), drop in a different track, generate one (name the
provider and the cost), or proceed without music. Record the decision in the
proposal artifact so the asset director knows what to do.

For a long-form piece also decide the **bed strategy**: one continuous track, or
one track per act with crossfades at the boundaries. Record the ducking amount
the playbook specifies.

### 5. Composition Runtime — Present Both (HARD RULE)

Check what the machine actually has:

```python
registry._tools["video_compose"].get_info()["render_engines"]
```

When both Remotion and HyperFrames are available you **MUST present both** to the
user before locking `render_runtime`. You may recommend one with reasoning, but
silently picking a default is forbidden even if this skill or the manifest
suggests one.

For each runtime give one sentence on what it is best at *for this brief* and one
honest sentence on why it might be wrong here:

- **Remotion** (`render_runtime="remotion"`) — React composition. Best here when
  the support layer is the stock scene stack: maps, timelines, stat cards,
  lower-thirds, document reveals, and word-level caption burn over archive
  footage in one pass. Tradeoff: the component catalogue is a frozen look, so a
  templated build can read as generic.
- **HyperFrames** (`render_runtime="hyperframes"`) — HTML/CSS/GSAP composition.
  Best here when the support layer is kinetic typography or registry-block
  scenes authored per piece. Tradeoff: you give up much of the Remotion scene
  stack, including its caption burn, and archive footage integration is less
  direct. See `skills/core/hyperframes.md` for the full decision matrix.
- **FFmpeg** (`render_runtime="ffmpeg"`) — cuts, concat, grade and subtitle burn
  with no designed support layer. Honest option only if the piece is pure
  footage with captions.

Then wait for explicit approval. Record the full shortlist — **both** runtimes
plus the ffmpeg option — as `options_considered` in a `render_runtime_selection`
entry in `decision_log`. A `render_runtime_selection` with only one runtime
considered when both were available is a CRITICAL reviewer finding.

If only one runtime is available, proceed with it but say so explicitly, and
still record the unavailable one as
`rejected_because: "runtime not available on this machine"`.

`render_runtime` is locked here and carried through `edit_decisions` unchanged.
A silent swap at compose time is a governance violation.

### 6. Composition Authoring Mode

Orthogonal to runtime: **templated** (assemble stock `cut.type` scene types) or
**atelier** (hand-author the composition). Present it as its own decision and log
it under `category: "composition_mode"`.

For a flagship documentary, atelier is the honest recommendation — a frozen
scene catalogue is exactly what makes long-form look like everyone else's. Say
plainly that atelier costs more tokens and iteration so the user opts in
knowingly. If they choose atelier, route through `skills/meta/taste-direction.md`
then `skills/meta/bespoke-composition.md`.

### 7. Visual Approach And Slideshow Risk

State the intended mix of real footage, motion graphics and stills, and the cut
cadence. If the plan leans on stills, say so now and name the parallax treatment —
"we will animate the stills" is the promise that most often quietly breaks.

### 8. Cost Estimate

Itemize it. A zero-cost plan is credible only if it names the free paths carrying
each line: keyless archives for footage, a local voice for narration, the user's
library for music, local composition for render. If any line is not free, price it
and flag it before the gate.

### 9. Quality Gate

- 3+ genuinely different concepts, each grounded in the ledger.
- Act structure concrete and duration-feasible.
- Narration plan names provider and voice.
- Music plan present, covering all three capabilities.
- `render_runtime_selection` logged with both runtimes in `options_considered`.
- `composition_mode` logged.
- Cost itemized.

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review
passes: checkpoint with `status="awaiting_human"`, present the artifact summary,
review findings and cost snapshot, and **END YOUR TURN**. Doing further pipeline
work in the same response is a gate violation. Approval is per-gate — an earlier
"go ahead" never covers this one.

## Common Pitfalls

- Three concepts that are one concept with three titles.
- An act structure with no new information in act 4.
- Deferring music to the asset stage.
- Recommending a runtime without presenting the other.
- A zero-cost estimate that does not say what makes it free.

# Asset Director — Narrated Documentary Pipeline

Adapted from `skills/pipelines/documentary-montage/asset-director.md`. The
retrieval discipline is carried over as-is; what is added is **narration
production** (this pipeline must render ~20 minutes of speech) and a hard
**keyless-first acquisition order**.

## When To Use

The scene plan exists. You now acquire everything the render needs: one visual
per slot, narration audio per act, a music bed, and a caption track.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifact | `state.artifacts["scene_plan"]["scene_plan"]` | Slots, queries, sources, treatments |
| Prior artifact | `state.artifacts["script"]["script"]` | Narration text and delivery cues |
| Prior artifact | `state.artifacts["proposal"]["proposal_packet"]` | Voice, music plan, runtime |
| Required tools | `direct_clip_search`, `tts_selector` | Footage acquisition, narration |
| Optional tools | `corpus_builder`, `clip_search`, `subtitle_gen`, `music_gen`, `audio_enhance`, `image_selector`, `video_selector` | Semantic retrieval, captions, music, polish |

## Acquisition Order (Binding)

**Keyless archives first, keyed providers second.** Always. For each slot, run
its queries against the keyless set before touching a keyed provider, and only
fall through for slots the archives could not fill.

This is not only about cost. Archive material is what gives a documentary its
texture; keyed stock is clean, modern and generic, and a piece built primarily
from it looks like an advertisement. Use keyed stock to fill gaps, not to set the
look.

Record which pass filled each slot so the gate can see the ratio.

## Run Order (parallelise)

Narration is the long pole and footage search is network-bound, so start both
early:

1. Fire `direct_clip_search` for act 1's slots **in the background**.
2. While it downloads, synthesize act 1 narration.
3. Inspect act 1 thumbnails, pick per slot.
4. Repeat per act, reusing earlier downloads first (see Cross-Act Reuse).
5. Music and captions last, once narration runtime is measured.

## Process — Footage

### F1. Search Keyless, Per Act

```python
direct_clip_search.execute({
    "output_dir": "projects/<project-id>/assets/video/raw_act1",
    "queries": [
        {"query": "stone staircase descending underground", "slot_id": "a1_s04"},
        {"query": "rock cut tomb entrance shaft",           "slot_id": "a1_s04"},
        # ... one entry per query per slot
    ],
    "sources": ["archive_org", "wikimedia", "nara", "loc", "nasa"],
    "clips_per_query": 3,
    "filters": {
        "min_duration": 3,
        "max_duration": 40,
        "orientation": "landscape",
        "min_width": 1280,
    },
})
```

`clips_per_query: 3` is the sweet spot. Keep `skip_existing: true` so retries are
cheap. Note that `orientation: landscape` and `min_width: 1280` matter on this
pipeline — the deliverable is 1920×1080 and an upscaled or pillarboxed clip will
be visible.

### F2. Second Pass — Keyed Providers For Unfilled Slots Only

Fall through the remaining tiers in order, for unfilled slots only:

```python
# tier 2
{"sources": ["pixabay_video"]}
# tier 3
{"sources": ["mixkit", "dareful"]}
# tier 4 — stills only
{"sources": ["unsplash"], "filters": {"kind": "image"}}
```

**Never include `pexels`.** Key issuance has been paused by Pexels since
2026-09-30 and `PEXELS_API_KEY` is intentionally unset; listing the adapter
stalls the retrieval on a missing key rather than degrading gracefully.

### F3. Inspect Thumbnails, Pick Per Slot

Browse `<output_dir>/thumbnails/` and confirm each pick visually against the slot
description. Do not pick on filename or on search rank. One clip per slot, and no
`clip_id` used twice — use `exclude_ids` to enforce it.

### F4. Cross-Act Reuse

Before searching for a later act, check what earlier acts already downloaded.
Thematic overlap is heavy in documentary work — excavation, laboratory, archive,
landscape and sky material recurs. Reusing a clip in a *different act* is fine;
reusing it in an adjacent slot is not.

### F5. Fill Gaps Honestly

If a slot has no good match: rewrite the query with more concrete nouns and
different vocabulary, then re-search. Two rewrites. If it is still empty, you
have three legitimate moves — convert the slot to a `motion_graphic`, convert it
to a sourced `still` with a parallax treatment, or **flag it to the user**.

What you may not do is drop in a loosely related clip and move on. One
unrelated shot is what makes a viewer stop trusting the piece.

`corpus_builder` + `clip_search` remain available as a fallback for stubborn
slots if the semantic-retrieval dependencies are installed; they are optional on
this pipeline and the fast path is the default.

## Process — Narration

### N1. Synthesize Act By Act

Never synthesize twenty minutes in one call. Per act, feed the act's sections
with their `delivery_cues` through `tts_selector`, writing to
`projects/<project-id>/assets/audio/narration_act<N>.wav`.

Act-level files are what make a re-record cheap: a script change in act 3 should
cost one act, not the whole piece.

### N2. Measure, Never Estimate

Run `ffprobe` on every act file and record real durations. Sum them for the
narration runtime. Compare against the script's target:

- Within 10% — proceed.
- Over by more than 10% — this is a script problem. Report it with the measured
  numbers and recommend a send-back rather than speeding up the voice.

The measured narration runtime, not the script estimate, is the timeline the edit
stage builds against.

### N3. Voice Approval After Act 1

Present act 1 audio before synthesizing the rest. If the user rejects the voice,
stop — do not render acts 2–5 in a voice that is going to be replaced. A
user-supplied pre-rendered narration WAV is a legitimate input here: if one is
provided, skip synthesis, probe it for duration, and record its provenance as
`user_supplied`.

### N4. Captions

Word-level timings. If the TTS route returns word timestamps, use them. If not,
run a transcription pass over the rendered narration to recover them, then align
to the script text — the script is the authority for spelling, the transcript for
timing.

## Process — Music

Resolve the music plan from the proposal. Prefer the user's library; check it
with `registry.get_by_capability("music_library")`. Record for every track:
title, path, duration and **licence**. For library tracks the licence is whatever
the user's source grants — record it rather than assuming.

Match bed length to the measured narration runtime. For a continuous bed, loop or
crossfade to cover; for per-act beds, note the crossfade points at act
boundaries.

## Asset Manifest

One entry per asset, and provenance on every single one:

```json
{
  "slot_id": "a1_s04",
  "asset_type": "video",
  "path": "projects/<id>/assets/video/raw_act1/archive_org_18823.mp4",
  "provider": "archive_org",
  "original_url": "https://archive.org/details/...",
  "licence": "public_domain",
  "source_tool": "direct_clip_search",
  "acquisition_pass": "keyless",
  "treatment": "footage",
  "picked_because": "matches the descending-shaft description; torchlight reads as period"
}
```

An asset with no `licence` and no `original_url` cannot ship. This is the record
that lets the piece be published without a rights question later.

## Quality Gate

- Keyless pass ran before any keyed pass, and the ratio is recorded.
- Every slot has exactly one asset; no `clip_id` reused in adjacent slots.
- Provenance and licence on every asset.
- Narration exists per act with **measured** durations; total within 10% of target.
- Captions carry word-level timings.
- Music bed selected, licence recorded, length matched to measured narration.
- Stills carry a parallax treatment.
- Unfilled slots flagged, not papered over.

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). Refresh
`metadata.partial_progress` as each act completes so the board shows live
progress. Then checkpoint `awaiting_human`, present the filmstrip and the
measured narration runtime, and **END YOUR TURN**.

## Common Pitfalls

- Going to Pixabay first because it returns the most hits fastest — and ending up
  with a corporate-looking documentary.
- Estimating narration length from word count after the audio already exists.
- Synthesizing all acts before the user has heard the voice.
- A clip reused in adjacent slots, which reads as a mistake rather than a motif.
- Recording a provider but not a licence.

## What May Be Used At All

The channel is monetised and the films are re-cut and re-graded, so only four
licence families may be fetched: **CC0, public domain, CC BY and CC BY-SA**.
NonCommercial and NoDerivatives are refused, and so is anything unreadable —
**an unknown licence is not permission**. A substring check for "CC BY" accepts
every NC and ND variant, which is why `tools/video/stock_sources/licences.py`
exists and why the refusal happens at fetch time, inside the corpus builder,
for every source rather than for the ones that remember to ask.

An asset that was never downloaded cannot end up in a film by accident.

# Compose Director — Narrated Documentary Pipeline

Adapted from `skills/pipelines/hybrid/compose-director.md`, with long-form
render discipline and a measured self-review added.

## When To Use

`edit_decisions` is written. You now render the deliverable and verify it against
what was promised.

## Runtime Routing (MANDATORY first step)

Read `edit_decisions.render_runtime` and route on it. Do not infer the runtime
from the assets or from what rendered last time.

- **`render_runtime="remotion"`** — the usual choice here. Archive footage via
  `<OffthreadVideo>`, maps/timelines/lower-thirds/document reveals as React
  scenes, and word-level caption burn, all in one pass.
- **`render_runtime="hyperframes"`** — only when the proposal locked it because
  the support layer is HTML/GSAP-native. Note that HyperFrames does not give you
  the Remotion caption-burn stack, so captions must be handled explicitly; verify
  the runtime with `hyperframes_compose` `operation="doctor"` before committing a
  20-minute render to it.
- **`render_runtime="ffmpeg"`** — cuts, grade, concat and subtitle burn with no
  designed support layer. Legitimate only if the approved treatment has no
  motion-graphic slots.

**Pass `proposal_packet` to `video_compose.execute()`** so the in-tool
swap-detection check runs against the proposal instead of being skipped.

If the locked runtime is unavailable, that is a blocker. Surface it with the
structured escalation from AGENT_GUIDE.md — what was attempted, what failed,
whether it is auth/access/tool/design, the options, your recommendation — and
wait. Do not substitute another runtime and do not quietly fall back to stills.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `edit_decisions`, `asset_manifest`, `scene_plan`, `script` | Timeline, assets, intent |
| Required tools | `video_compose`, `audio_mixer` | Assembly and mix |
| Optional tools | `video_stitch`, `video_trimmer`, `color_grade`, `audio_enhance`, `subtitle_gen`, `remotion_caption_burn` | Polish |
| Profile | `youtube_landscape` (1920×1080) | Output canvas |

## Process

### 1. Render Once, Deliberately

A 20-minute render is the longest operation in the pipeline and can take the
better part of the wall-time allowance. Before starting:

- confirm the storyboard was approved at the assets gate,
- confirm every asset path in the manifest exists on disk,
- confirm the output path is under `projects/<project-id>/renders/`.

A missing asset discovered at minute 60 of a render is an avoidable loss.

### 2. Grade Across Mixed Eras

Archive material arrives in wildly different stocks, gammas and white balances.
Apply a uniform grade across the whole timeline so 1920s nitrate, 1960s 16mm and
modern 4K read as one piece. Without this, the cuts announce themselves as
sourced from different places — which is the single clearest tell of an
assembled-from-stock documentary.

### 3. Mix For Intelligibility

Narration must be intelligible at every point. After mixing, check the quiet
passages, not the loud ones — ducking failures hide under a dense bed. Target the
playbook's integrated loudness and keep a limiter on the final mix.

### 4. Burn Or Deliver Captions

Per the playbook. If burning, check legibility over the brightest footage in the
piece, not over a mid-grey frame.

### 5. Post-Render Self-Review (measured, not estimated)

Run `ffprobe` on the output and report every one of these as a **measured**
value:

| Check | Source | Pass condition |
|---|---|---|
| Duration | `ffprobe` format duration | within 2s of planned |
| Resolution / fps | `ffprobe` stream | 1920×1080, playbook fps |
| Shot count | count of cuts in `edit_decisions` | matches timeline |
| Visual mix % | asset manifest treatments | matches approved mix; stills within cap |
| Audio levels | measured integrated loudness and true peak | near playbook target |
| Caption presence | burned frames or sidecar file | present |
| Codec | `ffprobe` | h264 + aac unless specified |

Then answer the two questions the numbers do not answer:

- **Does it read as a documentary or as a slideshow?** Sample frames across the
  piece. If stills cluster anywhere, say so plainly.
- **Did the promise survive?** Compare the output against the approved visual
  approach. A motion-led promise delivered as stills is a failure even if every
  number passes.

If a check fails, report it with the measured number. Do not round a 23-second
overrun into "roughly on target".

### 6. Record The Render Report

Include the measured values above, the runtime used, total render wall time, peak
memory if available, and any substitution made along the way. Substitutions are
recorded, never hidden.

## Common Pitfalls

- Routing on the assets present rather than on `render_runtime`.
- Skipping the uniform grade, so every era change reads as a seam.
- Checking the mix only where the music is loud.
- Reporting planned numbers as if measured.
- Re-rendering repeatedly to fix a pacing problem that belongs in the scene plan.

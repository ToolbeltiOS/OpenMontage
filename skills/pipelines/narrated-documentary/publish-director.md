# Publish Director — Narrated Documentary Pipeline

Adapted from `skills/pipelines/hybrid/publish-director.md`. The hybrid version
packages a hero cut plus derivatives. This version packages a single long-form
deliverable **plus its provenance record**.

## When To Use

The render passed its self-review. You now assemble the local export package.

## Uploading Is Not Part Of This Stage

This stage produces a **local** export package. It does not upload. Publishing to
a platform requires an explicit, current instruction from the user naming the
destination — an approval of this gate is not that instruction.

Record in `publish_log` whether an upload occurred and to where. For a local-only
run, that field says so explicitly. This is what makes it possible to tell later
whether a piece ever shipped.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/publish_log.schema.json` | Artifact validation |
| Prior artifacts | `render_report`, `final_review` | The deliverable and its verification |
| Prior artifacts | `script`, `research_brief`, `proposal_packet` | Metadata and provenance |

## Process

### 1. Assemble The Package

```
<export-dir>/
├── <slug>.mp4              # the deliverable
├── <slug>-thumbnail.png    # thumbnail
├── metadata.json           # title, description, tags, chapters
├── research_brief.json     # the claim ledger — ships with the video
└── render_report.json      # measured verification
```

The research brief ships with the video. It is the record of where every claim
came from, and it is the thing you will want if a factual challenge arrives six
months later.

### 2. Write Metadata That Matches The Content

- **Title** — from the approved concept's candidates. No claim the piece does not
  make.
- **Description** — opens with the question the piece actually asks. Every
  factual statement in it traces to the research brief, exactly as the narration
  does. A description is not a place where unsourced claims become acceptable.
- **Tags** — drawn from the real subject matter.
- **Chapters** — timestamps at the **real** act boundaries, read from
  `edit_decisions`, not guessed from the act plan. A chapter marker that lands
  mid-sentence is worse than no chapters.

### 3. Attribute The Sources

Archive material is usually public domain but often carries an attribution
request, and library music frequently requires credit. Walk the asset manifest's
licence fields and build the credit block the licences actually require. Put it
in the description, not only in a file nobody reads.

A piece built from free sources is only legitimately free if its attributions are
honoured.

### 4. Quality Gate

- Package contains video, thumbnail, metadata JSON and research brief.
- Chapter timestamps match real act boundaries.
- Every factual claim in the description traces to the brief.
- Attribution block covers every licence that requires credit.
- `publish_log` records the upload status truthfully.

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review
passes: checkpoint with `status="awaiting_human"`, present the package contents,
and **END YOUR TURN**. Do not upload in the same response as the approval request.
Approval is per-gate — an earlier "go ahead" does not cover this gate, and it
never covers an upload.

## Common Pitfalls

- Treating gate approval as upload approval.
- Chapter timestamps taken from the plan rather than the finished timeline.
- A description that asserts more than the narration does.
- Dropping the attribution block because the sources were "public domain".
- Shipping the video without the brief, leaving no provenance trail.

## Caption Track (Binding)

The film is no longer rendered with its narration burnt into the picture, so
the caption track is a separate deliverable and it ships at publish.

```bash
.venv/bin/python lib/captions_srt.py projects/<id>/artifacts/render_props.json \
    projects/<id>/artifacts/captions.en.srt \
    output/<id>/<id>.mp4
```

Then upload it with the `youtube_captions` tool (`captions.insert`), language
`en`, name "English", `is_draft: false`. Run it with `dry_run: true` first —
the dry run deliberately needs no token, so a publish can be rehearsed before
anyone authorises a write scope on the channel.

`captions.insert` needs the `youtube.force-ssl` scope. An upload-only token
authenticates and then fails with an insufficient-permission error; the tool
checks the scope up front and says so rather than retrying.

Two things this buys that the burn did not:

- a caption can be corrected without re-rendering a twenty-minute film;
- the viewer can switch it off, restyle it, or auto-translate it.

Record the caption id in the publish log beside the video id.

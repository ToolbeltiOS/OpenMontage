# Merging `asset-library` — the plan

Written 2026-11-09, merge-week item 6. **Not yet executed.** The merge was
opened, measured, and aborted; the tree is clean.

    253 files touched · 15 conflicts · 33 hunks

Most of the 253 is the asset library itself (SVG glyphs, licences) and
auto-merges cleanly. The work is the 33 hunks.

---

## 0. THE DECISION THAT GATES EVERYTHING ELSE

Two coherent designs collide here, and the merge cannot be resolved until
someone picks one. This is not a stale branch versus a current one.

**Design A — on `automation`, from `86e057c` (2026-11-07).** The cut object
is OPEN (`additionalProperties: true`) and `source` is not required. The
schema records its own reasoning in three keys:

  * `_why_source_is_not_required` — an authored cut has no source file: it
    names a component and draws its picture, and the narrated-documentary
    films run 60% of their cuts that way.
  * `_why_additional_properties` — authored props sit FLAT beside `type`
    because that is the shape `remotion-composer/src/Explainer.tsx` reads
    and `lib/build_render_props.py` passes through. They are not unchecked:
    `lib/buildability.py` validates every one against the component
    contract, which is stricter than an enumeration here, and enumerating
    them again "would be a copy that drifts".
  * `_found_by` — the king-tut run, the first to checkpoint the edit stage.

**Design B — on `asset-library`, in WIP `894da43`.** The cut object is
CLOSED (`additionalProperties: false`), `source` is required (the SLOT ID
for an authored cut), and component props live under a `scene` sub-object
that `build_render_props` flattens before the renderer sees it.

**Evidence for each.** noah was authored under B and validates clean, all
159 cuts. king-tut was authored under A. Design A's objection to item 8 —
that a schema enumeration duplicates `buildability` and drifts — is NOT
answered by design B, because B does not enumerate: it puts the open set
under one key. That is the strongest argument for B, and it is compatible
with A's objection rather than contradicting it.

**What is already done for B**, and must be REVERTED if A is chosen:

  * `b17f841` documents the `scene` sub-object in
    `docs/STAGE_CONTRACT.md` and
    `skills/pipelines/narrated-documentary/edit-director.md`, with
    `tests/automation/test_authored_cut_shape.py` validating the example
    out of the instructions. Three of its tests skip until the closed
    schema lands.
  * `9159da5` proves all four films still load and flatten safely, with no
    migration. This holds under EITHER design.

**Item 8 depends on this.** "edit_decisions additionalProperties back to
strict once buildability enumerates props per component" is design B's
goal by a route design A has already argued against.

---

## 1. Group MINE — automation's version wins

`asset-library` is simply older for these. Take `--ours` and verify.

| file | what would be lost by taking theirs |
|---|---|
| `lib/film_render.py` (9 hunks) | the `plate-dropout` gate, the loudness-reference requirement, the three-state SKIPPED verdict |
| `scripts/render_film.py` (3) | the thumbnail gate, the real-film check, the timeline-coverage check |
| `scripts/publish_doc.py` (1) | the scheduled-film credits change |
| `launchd/com.wak3up.docs.metrics.plist` (1) | Tuesday 09:00 and the runner worktree |
| `launchd/com.wak3up.docs.tripwire.plist` (1) | Sunday 12:00 and the runner worktree |
| `lib/buildability.py` (1) | `js_round`, `frame_span`, `check_timeline_coverage` |
| `lib/verify_frame_order.py` (1) | `js_round` on cut edges, and its sibling-import fix |
| `lib/mix_audio.py` (1) | nothing — already cherry-picked as `9e14a31`; the same change arriving by another road |
| `.gitignore` (1) | the ledger rule; KEEP BOTH sides, as in the visual-quality merge |

## 2. Group THEIRS — asset-library's version wins

The illustration feature and the library. These auto-merge except where
listed in group 3.

  * `lib/illustration_spec.py` — 9 KB, absent from automation. `build_
    render_props.py`'s `demote_unapproved()` call depends on it, so the two
    cannot be separated.
  * `assets/library/**` — glyphs, `LICENCE.md`, `.gitattributes`.
  * everything else that auto-merged.

## 3. Group RECONCILE — automation's content PLUS the WIP's structure

Neither side wins. Resolve by hand, preserving `86e057c` in every case.

  * `schemas/artifacts/edit_decisions.schema.json` (2 hunks) — gated on
    section 0.
  * `schemas/artifacts/research_brief.schema.json` (1)
  * `scripts/check_claims.py` (3)
  * `remotion-composer/component-contract.json` (2)
  * `remotion-composer/src/Explainer.tsx` (3)
  * `tests/automation/test_topic_exclusion.py` (4)

`schemas/artifacts/script.schema.json` did not conflict but the WIP is
behind it too — check it by hand before trusting the auto-merge.

---

## 4. The `86e057c` keys to re-check AFTER resolving

The WIP predates `86e057c`, so taking any of these files wholesale REVERTS
it. Proved before the merge: `closest_available` is absent from the WIP's
`research_brief.schema.json`. After resolving, every key below must still
be present.

**`research_brief.schema.json`** — `closest_available`, `confidence`,
`contested`, `gaps`, `id`, `kind`, `looked_for`, `notes`, `pattern`,
`provenance_repair`, `repairs_sentence`, `sources`, `supports`,
`why_it_matters`

**`script.schema.json`** — `air_after_seconds`, `beat`, `claims`,
`paragraphs`, `register`, `text`

**`edit_decisions.schema.json`** — `_found_by`,
`_why_additional_properties`, `_why_source_is_not_required`, `source`,
`total_duration_seconds` (the three underscore keys are design A's recorded
reasoning; if design B is chosen they must be REWRITTEN, not deleted — the
next person needs to know why it changed twice)

Check with:

    python3 - <<'PY'
    import json
    KEYS = {"schemas/artifacts/research_brief.schema.json": [...],
            "schemas/artifacts/script.schema.json": [...],
            "schemas/artifacts/edit_decisions.schema.json": [...]}
    for path, keys in KEYS.items():
        blob = open(path).read()
        missing = [k for k in keys if f'"{k}"' not in blob]
        print(path, "MISSING:" + ", ".join(missing) if missing else "ok")
    PY

---

## 5. The gate, before it lands on `automation`

Both, and neither is optional.

1. **Full suite green.** `.venv/bin/python -m pytest tests -q` — the
   baseline on 2026-11-09 was 3,319 passed, 0 failed.
2. **A 2-minute King Tut slice through the real chain**, 7/7 gates with
   `plate-dropout` included:

       scripts/slice_check.py --project king-tut --seconds 120

   The reference tables are in `9cc1d7e`. `delivery audio` reports SKIPPED
   on a slice — that is correct and is not a failure; the other six must
   read PASS and `plate-dropout` must be one of them.

If either fails, the merge does not land. A silent revert of a delivery
gate is the exact failure this week existed to remove, and it would not
announce itself.

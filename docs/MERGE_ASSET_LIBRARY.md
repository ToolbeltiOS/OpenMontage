# Merging `asset-library` — the plan

Written 2026-11-09, merge-week item 6. **EXECUTED 2026-11-09** onto
`fix/render-finalise`, with the group-1 correction recorded in section 1a.
Sections 0 and 2–5 were followed as written.

    253 files touched · 15 conflicts · 34 hunks

(The summary line said 33; the per-file counts in sections 1 and 3 sum to
34 and the merge produced 34. The per-file numbers were right.)

Most of the 253 is the asset library itself (SVG glyphs, licences) and
auto-merges cleanly. The work is the 33 hunks.

---

## 0. THE DECISION — **B, taken 2026-11-09**

**Chosen: the cut object is CLOSED, component props live under the single
`scene` key, and those props are validated by `lib/buildability.py` against
the component contract.**

The two designs below collided, and this resolves them rather than picking
a winner between them: B closes the cut WITHOUT enumerating component props
in the schema, which is the thing design A objected to. The schema gains
one key whose value is open; `buildability` keeps doing the checking it
already does, against the component contract, which is stricter than an
enumeration here could be and cannot drift from it because there is only
one copy. A's objection stands and B does not trip it.

What follows from the decision:

  * `b17f841` STANDS — the instructions in `docs/STAGE_CONTRACT.md` and
    `skills/pipelines/narrated-documentary/edit-director.md` already
    describe the `scene` sub-object, and the three skipped tests in
    `tests/automation/test_authored_cut_shape.py` go live when the schema
    lands, including the control that a flattened cut is refused.
  * The three underscore keys are **REWRITTEN, NOT DELETED**. They are
    design A's recorded reasoning and it is still true about props being
    open-ended and checked by `buildability`; what changes is where they
    sit. `_why_source_is_not_required` becomes an explanation of why
    `source` carries the SLOT ID for an authored cut. The next person has
    to be able to see that this changed twice and why.
  * `9159da5` holds unchanged: the four published films are NOT migrated,
    they load, and the flattening is safe on all of them.
  * **Item 8 is largely satisfied by this.** Its task — "additionalProperties
    back to strict once buildability enumerates props per component" — is
    met without the enumeration: strict comes from the closed cut, and
    `buildability` already validates the props. Item 8 becomes verification
    rather than construction.

The two designs, recorded because the merge still has to reconcile them
file by file:

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

**What is already done for B** (all of it stands, now that B is chosen):

  * `b17f841` documents the `scene` sub-object in
    `docs/STAGE_CONTRACT.md` and
    `skills/pipelines/narrated-documentary/edit-director.md`, with
    `tests/automation/test_authored_cut_shape.py` validating the example
    out of the instructions. Three of its tests skip until the closed
    schema lands.
  * `9159da5` proves all four films still load and flatten safely, with no
    migration. This holds under EITHER design.

**Item 8 depended on this**, and is answered above.

---

## 1. Group MINE — automation's version wins

`asset-library` is simply older for these. Take `--ours` and verify.

**Read section 1a before acting on this.** For four of these nine files the
premise above is false, and `--ours` reverts work that only ever existed on
`asset-library`.

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

## 1a. The correction — four of group 1 are RECONCILE, not `--ours`

Recorded 2026-11-09, during the merge. **Ruling: where theirs carries a fix
automation never had, the resolution is ADDITIVE.** That is what "preserve
`86e057c`" meant in section 3, applied in the other direction: the point was
never that one branch wins a file, it was that no fix is lost to the
resolution of a file it happens to share.

The table above is right about what OURS carries. It is wrong about theirs,
because it was written from the assumption that `asset-library` branched and
stopped. It did not: it took commits until 2026-11-01 (`6c479ca`, `6f3da99`,
`42ac750`) and a WIP on 2026-11-09, and `--ours` silently reverts them.
Measured, not read off the diff:

| file | what `--ours` ALSO drops | how it showed |
|---|---|---|
| `lib/film_render.py` | the three-signal watchdog — `WATCH_FINALISE`, `_file_size`, `_tree_cpu_seconds` (`6c479ca`) | **6 errors** in `tests/lib/test_run_watched.py`, which arrives with the merge |
| `lib/film_render.py` | the `approved asset use` gate | `lib/verify_approved_use.py` lands with **no caller** — the fourth gate-without-consumer, in the file written to end them |
| `scripts/render_film.py` | `project=` into `gates()` | the caller side of the line above |
| `lib/verify_frame_order.py` | `_coalesce` (`6f3da99`) | the mid-shot threshold crossing FAILS on ours. The incoming test does not catch it: it puts the flicker on a cut edge, where ours' older exemption already applies |
| `scripts/publish_doc.py` | `COMMENT_LIMIT` / `split_comment` (`42ac750`) | ours moved the long credits block to `post_pending_credits.py`, which posts it as ONE comment with no length check — 400 `commentTextTooLong` at 11,636 chars, and noah's block is 12,502 |

So those four were resolved by hand, ours' content plus theirs', and each
side's features were then re-proved by test rather than by reading the diff.
The other five stand exactly as the table says, and two of those were
checked rather than assumed: `lib/buildability.py`'s only conflict is two
phrasings of one comment, and `lib/mix_audio.py`'s `fit_to_length` really is
`9e14a31` by another road.

**What was deliberately NOT carried over.** `PUBLISH_HOLD` and `held()` in
`scripts/publish_doc.py`. They auto-merged in with the rest of theirs;
`.publish-hold` was deleted on purpose and no gate was wanted, so the
sentinel was removed again. That is a decision reversed, not a fix lost,
which is the distinction section 1a turns on.

**Still owed, and out of scope here.** `split_comment` now lives in
`publish_doc.py`, but the script that posts the long block today is
`scripts/post_pending_credits.py` and it does not call it. Carrying the
function is a merge; changing which script splits is a behaviour change.

### The noah row of the approved-use table is stale

`reports/asset_library_branch.md` says "On `noah` as it stands it reads
**FAIL**, naming all three files. That is correct and is left standing."
That was true when written and stopped being true the same day:
`assets/library/illustrations/approved.json` is `{"approved": []}`, revoked
at 2026-11-01T15:35:52, so this gate "passes by being TRUE and not by being
excused" — `projects/noah/artifacts/illustration_approvals.json` carries the
reasoning. There is therefore no expected-FAIL on noah to keep, and
asserting one would be the waiver that record explicitly refuses.

`tests/lib/test_approved_use.py` is the control instead: the report's six
cases on synthetic fixtures, the FAIL direction among them, plus three tests
on the real committed files asserting the REVOCATION — that `approved.json`
is empty, that the three pictures kept their provenance, and that the gate
is green on noah by being true. A control on a synthetic project cannot be
satisfied by re-approving illustrations and cannot go stale when a film
changes.

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

  * `schemas/artifacts/edit_decisions.schema.json` (2 hunks) — take the
    WIP's closed-cut structure per section 0, keeping `86e057c`'s `source`
    and `total_duration_seconds`, and REWRITING the three underscore keys
    rather than dropping them.
  * `schemas/artifacts/research_brief.schema.json` (1)
  * `scripts/check_claims.py` (3)
  * `remotion-composer/component-contract.json` (2)
  * `remotion-composer/src/Explainer.tsx` (3)
  * `tests/automation/test_topic_exclusion.py` (4)

`schemas/artifacts/script.schema.json` did not conflict but the WIP is
behind it too — check it by hand before trusting the auto-merge.

**This warning paid for itself.** The auto-merge of that file produced
DUPLICATE JSON KEYS — `paragraphs` and `claims` twice each — because both
sides inserted near the same place and git took both. It parses: `json.load`
keeps the last of a duplicate pair silently, so the schema would have
validated against half of itself. Ours is a strict superset of theirs here
(proved by comparing key paths, not by reading), so ours was taken whole.

Every JSON file the merge touched was then swept for duplicate keys and for
parse failure; `script.schema.json` was the only casualty.

The same superset check cleared `research_brief.schema.json`: theirs has
nothing ours lacks, so its one conflict is ours.

`tests/automation/test_topic_exclusion.py` is also ours, and not as a
preference — theirs' two unique tests both assert things that are now false.
`test_king_tut_survives_all_three` says king-tut is not excluded, and
king-tut published on 2026-11-08; `test_the_noah_project_is_visible_from_the_runner_tree`
asserts `projects/noah` does NOT exist in the tree it runs from, which is
false in the development worktree. Ours replaced both.

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

**Result, 2026-11-09: all 25 keys present** — 14 / 6 / 5.

The three key NAMES were kept and only their values rewritten, because
section 4 asks for these names and section 0 asks for rewritten values. Two
of the names are now historical — `source` IS required, and
`additionalProperties` on the cut IS false — so each value opens by saying
so. The name is the question that was asked on 2026-11-07; the value is the
answer that reversed it on 2026-11-09. Renaming them would satisfy section 0
and silently fail this check.

The WIP's copy of this file is reformatted to one-space indent. That is an
artifact of whatever wrote the WIP, not a convention — no sibling schema on
either branch is indented that way — so the resolution keeps the repo's
formatting and applies only the WIP's STRUCTURE, which is what section 3
asks for. The resolved file was then compared to the WIP key path by key
path: identical, plus `total_duration_seconds` and the three underscore
keys.

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

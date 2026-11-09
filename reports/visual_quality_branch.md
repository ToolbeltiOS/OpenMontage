# `visual-quality` — what is on it, and what merges it

Complete and **deliberately unmerged through Friday**. Only one commit from
this work has reached `automation`: `db20713`, the AnnotatedStill
camera-props fix, cherry-picked on its own so Friday's run inherits a bug fix
without the 2.5D work.

## What is on the branch

| | gate beside it |
|---|---|
| 2.5D push, pull and drift via DepthFlow | [`reports/depth_parallax.md`](depth_parallax.md) |
| the two-twin parallax gate | both injections read exactly 0.000 |
| drift pan calibration | 24/24 cuts, travel error 0.4–7.2% against 10% |
| anchor tracking on a 2.5D plate | [`reports/anchor_tracking_25d.md`](anchor_tracking_25d.md) |
| bank quality floor | [`reports/bank_quality_floor.md`](bank_quality_floor.md) |
| anchor-texture authoring rule | `reports/anchor_texture/*.png` |
| text-bearing guard + derivation inheritance | 5 cuts refused, 49 eligible |

Assessed and rejected: Real-ESRGAN and RIFE — see
[`reports/realesrgan_assessment.md`](realesrgan_assessment.md) and the
README. Do not re-try without new evidence.

## What merges it, next week

In order. The branch does not go onto `automation` until every step is green.

1. **A 2-minute easter-island slice renders end to end through
   `scripts/render_film.py`** — not a bare Remotion render. This matters:
   the slice rendered during the camera-props work was a single flat
   Explainer pass, and the gates are written for the look+type composite
   `deliver()` builds. `plate_is_clean` was handed a render containing the
   type it looks for, and `check_motion` a picture with no grain, so held
   frames read as duplicates. Only the before/after comparison was
   meaningful there. Through `render_film.py` the absolute numbers mean
   something.
2. **Every gate green on that slice**, with the output recorded beside the
   claim — the README may not say otherwise.
3. **Merge `visual-quality` onto `automation`.**
4. **Re-run the Run #2 checklist as the Run #3 checklist.**

## Two numbers that are thin, and should be watched rather than trusted

- **`MIN_WORDS = 14`** in `lib/text_bearing.py` rests on four positives: 36,
  20 and 18 words (three documents) against 8 (a photograph of a museum case
  with legible exhibit labels). Revisit when more documents are banked.
- **`MIN_SD = 15`** in `lib/verify_anchor_texture.py` separates verified
  anchors (15.06–68.27) from the one unverifiable anchor (8.61), but c143
  clears it by **0.06**. The rule will sometimes move an anchor that would
  have verified. That is the safe direction; 12 would sit mid-gap.

The drift gate's tightest cuts are `c023` (travel error 7.2%) and `c117`
(frozen twin 1.352) — both short cuts with small pans, and both the first
things that would move if anything drifts.

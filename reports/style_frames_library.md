# Style frames with the house library

8 style frames, not 10. Six use the library; the two that do not —
`01_title_sequence` and `02_act_title_card` — are the controls.

Before/after pairs and a stacked sheet: `~/Downloads/style-frames/`.

## What changed

| frame | treatment | mean abs diff |
|---|---|---|
| 01 title_sequence | **control** | **0.000** |
| 02 act_title_card | **control** | **0.000** |
| 03 map_route | plate | 0.000 — see below |
| 04 timeline | glyphs | 0.063 |
| 05 schematic | stone | 18.084 |
| 06 document_reveal | parchment | 147.800 |
| 07 evidence_card | parchment | 148.279 |
| 08 scale_comparison | glyphs | 2.302 |

Both controls are byte-identical, which is the point of having them: nothing
moved that should not have.

`map_route` is unchanged because its historical plate needs a `claim_id` on
the scene, and the planner does not write one yet — so the route correctly
falls to terrain. Consistent with the rule, not a failure of it.

The glyph diffs are small because a glyph is a small mark: 0.063 across a
whole frame is five 34px marks on a 1920x1080 field.

## Gates: identical before and after

At the gate's own `SHIFT_TOLERANCE_PX = 0.65`:

| | before | after |
|---|---|---|
| plate purity | 1 frame | 1 frame |
| type lock | 4 frames | 4 frames |

Per frame, the type-lock count is the same or **lower** after the library:
`07_evidence_card` improves from 3 moved words to 1 (worst 0.718 → 0.669).
No frame gets worse. **The library introduces no type movement.**

The single plate-purity finding is on `03_map_route`, before and after, and
it is a **false positive**: the "word" is `|` at (570, 99) — OCR reading a
hairline rule in the map as a pipe character.

**A caveat about the type-lock numbers.** This harness samples frame `f0`
and `f0 + 30` and compares every OCR box. The real gate samples *past the
last declared animation time in the cut*; this one does not, so words still
animating in are counted as having moved. The 0.67–0.76px figures are
therefore an upper bound and partly measure reveals in progress. What the
comparison is good for is the before/after difference, which is zero or
favourable.

## Two defects found doing this

- **`cut.texture` was never forwarded.** The components defaulted to
  parchment and stone whatever the props said, so the documented `null`
  escape was unreachable and the first before/after came back
  byte-identical on four of six frames — both sides were the "after". The
  same props-the-renderer-never-read trap as the camera props, in new code.
- **`texture` was already taken.** A `texture_field` cut uses it for a media
  path; a library texture is a name. The field is `plate_texture`, because
  one key meaning a file in one scene and a palette entry in another is a
  collision waiting for whoever reads it next.

`SlotPreview` now honours `layer_mode`, without which a style frame could
not produce a plate pass and could not be gated at all.

# Anchor tracking on a 2.5D plate

`scripts/check_anchor_tracking.py`, on easter-island cuts given a depth
plate. The 2D run is in [`anchor_tracking.md`](anchor_tracking.md).

A 2.5D plate is not a rigid transform of the photograph, so every stage of
this gate had to be rebuilt. All four problems below were found by measuring,
and three of them were faults in the GATE reporting a fault in the render.

| cut | annotation | off | if locked | match | by |
|---|---|---|---|---|---|
| c053 | every land bird on the island | **1.15px** | 55.32px | 0.996 | ecc-affine |
| c143 | 3.9 hectares of land | **0.99px** | 10.12px | 0.887 | ecc-affine |
| c154 | added after the statue was finished | **0.66px** | 14.98px | 0.982 | ecc-affine |
| c154 | two birdmen, facing each other | **0.60px** | 11.65px | 0.991 | ecc-affine |
| c154 | a sooty tern above them | **0.72px** | 11.53px | 0.972 | ecc-affine |
| c154 | ceremonial paddles | **0.83px** | 13.64px | 0.983 | ecc-affine |
| c154 | the statue religion on the front of the stone | **3.72px** | 34.98px | 0.992 | ecc-affine |
| c053 | twenty-one tree species | — | — | 0.476 | **not verifiable** |

Type lock passes on all three cuts: 0 scenes with a word in a different
place, worst 0.0px.

## The four things that were wrong

**1. The matcher assumed a rigid plate.** A CSS scale moves a patch rigidly;
a depth displacement warps it. The 2D cuts matched at 0.906–0.985 and c053's
2.5D patches at 0.604. Now: template match to find it, affine ECC to refine,
SIFT and a homography if ECC will not converge, and the score is the
correlation after the warp either way, so one floor covers all three. ECC's
capture range is small — on a synthetic 11px shift it will not converge from
identity at all, and reaches cc=0.9996 from a seed 2px out — so the template
match does the finding and ECC only polishes.

**2. The score was never checked.** A 0.604 match was allowed to report the
feature 385px away and condemn the render. A match under 0.8 is now reported
as a failed measurement, with the patch's contrast, so the two cases are
distinguishable: c053's remaining failure sits on grey sd **6.17 of 255**,
where no matcher can locate anything and the anchor is unverifiable from the
picture — which is where the annotation was placed, not a fault in the
render.

**3. The patch was taken at the authored position.** `isometric` is 0.30 from
the first frame, so the shader has already displaced every point before the
move begins: the authored (x, y) is where the point is in the PHOTOGRAPH, not
where it appears in frame 0. The gate was tracking whatever happened to sit
there and comparing it against a dot following the intended point. The error
was exactly that displacement, anchor for anchor:

| cut | frame-0 offsets | errors it produced |
|---|---|---|
| c154 | 8.6, 8.4, 7.2, 11.5, 3.7 | 7.8, 8.3, 7.5, 10.3 |
| c053 | 2.5, 1.2 | 3.9 |
| c143 | 1.9 | 1.4 |

**4. The dot was looked for in grey.** The accent is ochre and weathered grey
stone has nearly the same luma: c154's fifth anchor reads BGR (59,132,184)
against (117,132,141), which in grey is 139.2 against 133.0 — a difference of
**6.2**, under any usable threshold. The dot was drawn exactly where the
track said and the gate reported "no anchor dot found". Summed across
channels the same pixel differs by 101. Colour is safe for a difference,
unlike for detection by hue, because the only thing that can account for it
is the annotation.

## Two things that were measured and were NOT the cause

Worth recording, because both were plausible and both were wrong.

- **Track quantisation.** 8-bit luma over 1920px is 7.5px per level, and the
  c154 track resolved one anchor to 5 distinct positions across 649 frames.
  A fine triangle ramp was added (`FINE_CYCLES`, four passes instead of two)
  and the offsets did not move. The quantisation was in taking the MEDIAN OF
  A BINARY MASK of integer pixel coordinates, which can only shift when a
  whole pixel enters the set; a Newton step on the decoded mapping's local
  Jacobian fixed the resolution (c053: 207 distinct positions in 280 frames,
  from 145). Both changes are kept — the ruler is better — but neither was
  the error.
- **Frame mapping.** `duration_seconds` is 22.133 on c154 against an
  `out − in` of 21.633, the difference being the transition. The composer
  uses `out − in`, which matches the track exactly, so the mapping was never
  wrong.

The four ramp passes need their own processes: four long renders in one
exhaust the GL resources here and fail in two different places, while two
passes never do and a 2s four-pass run does not either.

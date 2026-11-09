# Is the 2.5D render actually 2.5D?

`lib/verify_depth_parallax.py`, on every 2.5D render.

The gate exists because the answer was no twice and nothing noticed. A depth
map DepthFlow silently dropped, and then a move that scaled about a pinned
depth plane, both produced plausible video that passed the tearing gate —
it passed them *because* there was no parallax to tear.

## Two checks, because neither number catches both failures

1. **Flat twin.** The same photograph and the same move rendered twice, once
   with the depth map and once with a map of constant depth. The mean
   difference in 8-bit levels IS the depth contribution. Floor 2.0.
2. **Anchor parallax.** Three anchors at the near, middle and far depths the
   picture has, tracked through the render by `scripts/anchor_track.py`. A
   plain zoom about the centre is then fitted to their displacements and
   subtracted; what is left cannot be produced by scaling. Floor 2.5 px.

| case | flat twin | anchor parallax | caught by |
|---|---|---|---|
| moai row | 19.639 | 3.54 px | — pass |
| Tiryns wall | 6.166 | 4.46 px | — pass |
| Sacsayhuamán joint | 16.012 | 5.32 px | — pass |
| INJECT no-relief depth map | **0.000** | **2.03 px** | both checks |
| INJECT zoom-only move | 21.660 | **1.50 px** | **anchors only** |

The last row is the reason there are two checks. A zoom-only push differs
from its flat twin by 21.7 levels — **more than any working render** —
because scaling a static relief changes the picture a great deal without near
and far ever separating. Check 1 is blind to it.

Reproduce the second injection with `OPENMONTAGE_ISOMETRIC_TRAVEL=0.0`, a
test hook in `scripts/render_25d.py` that exists so that proving the gate
works does not require editing the renderer and remembering to change it
back.

## The 4 px floor does not work, and 2.5 px is thin

The 4 px floor was set against a 14.5 px reading from two hand-picked anchors
at the depth extremes under isometric 0.5. The shipping setting is isometric
0.35 with anchors chosen automatically, and at that setting **a good render
measures 3.54 px and a 4 px floor fails it.**

Measured bands: working 3.54–5.32, broken 1.50–2.03. 2.5 px is the only floor
that separates them, by 1.42× above and 1.23× below. That is thin, and it is
the honest number: this gate will not survive a photograph with less depth in
it than these three. Widening the margin means more parallax, which is a look
decision at isometric 0.35 and not the gate's to make.

Raw travel is **not** the measurement, and assuming it was let a flat render
through. On the zoom-only injection the three anchors travel 35.6, 49.6 and
53.7 px — a spread of 18 px on a render with no parallax at all — because a
zoom moves every point in proportion to its distance from the centre. Hence
the fit. On the Tiryns wall the fit recovered a zoom of −0.0787 against the
move's actual amount of 0.080, without being told what the move was.

## The loader rejects what the shader would drop

`as_depth()` in `scripts/render_25d.py` refuses by name, with the dtype in
the message, rather than converting quietly — the whole defect was that an
unusable array was *accepted*.

| dtype | |
|---|---|
| uint16 — the original defect | REJECTED |
| int32 | REJECTED |
| float16 | REJECTED |
| uint8 | accepted → float32 [0.000, 1.000] |
| float32 | accepted → float32 [0.000, 1.000] |

## Two bugs found while testing the gate

Both were found because an injected no-relief map read **31.4 levels** on
check 1 — a loud depth contribution from a map with no depth in it.

- `as_depth()` skipped its normalisation when the depth span was zero and
  returned the **raw** values, so a constant uint8 map reached the shader as
  depth 128.0 — a plane a hundred times past the far limit. A no-relief map
  now normalises to a defined 0.5.
- `--flat-depth` built the twin with `np.full_like(depth, 0.5)`, which
  truncates to **0** on a uint8 map: the twin was a plane at the near limit
  instead of the middle. Now mid-grey for the dtype.

Neither affects the cached float32 depth maps, so no shipped render was
wrong. They would have made this gate unusable on a uint8 map.

## The px floor cannot be a per-cut gate

Run against the moves the edit stage actually authored on easter-island,
rather than the 0.08 push the floor was calibrated on:

| cut | move | amount | secs | flat twin | anchor parallax | verdict |
|---|---|---|---|---|---|---|
| c061 | drift | +0.0144 | 2.40 | 28.977 | 0.00 | FAIL |
| c051 | drift | −0.0150 | 2.50 | 7.951 | 0.00 | FAIL |
| c117 | drift | +0.0136 | 2.27 | 8.441 | 0.97 | FAIL |
| c003 | drift | +0.0510 | 8.50 | 21.942 | 2.27 | FAIL |
| c154 | push | +0.0600 | 21.63 | 7.498 | 1.65 | FAIL |
| c094 | pull | +0.1542 | 8.57 | 6.908 | 12.96 | **PASS** |
| c053 | push | +0.2427 | 9.33 | 6.334 | 2.46 | FAIL |

**One of seven passes.** The flat-twin column is the thing to read: every one
is between 6.3 and 29.0 against a floor of 2.0, so the depth map is
demonstrably changing all seven renders. They are not flat. The absolute px
floor fails six of them anyway.

Nor is the floor predictable from anything available at build time. Against
the move amount r = +0.51, against the depth map's p5–p95 spread r = +0.28,
against their product r = +0.61, on n = 7 — and c053's 0.24 push reads 2.46 px
while c094's smaller 0.15 pull reads 12.96 px. What the number really depends
on is where the three automatically chosen anchors happen to land, which is a
property of the photograph and not of the render's correctness.

So the absolute floor stays where it is calibrated and means something — as a
regression check on the three reference stills, where it catches both
injected failures — and it is **not** applied per cut. A per-cut gate has to
ask whether the depth map changes *this* render, which is check 1, and that
one passed all seven.

The drift rows are a separate defect, not evidence about the floor: the
authored drift amount does not map onto DepthFlow's `offset` (see the wiring
commit), so those four cuts barely move at all.

## The per-cut gate: two self-comparisons, and why not a model

The expected-parallax model was tried first and does not exist. Fitting
`residual = k · amount · height · |depth − steady|` over 15 tracked anchors
gives a `k` spanning **8×** for drifts and **29×** for pushes, with and
without a radius term. The shader raymarches, so where a point lands depends
on the depth field along its whole ray rather than the depth beneath it.

The percentile anchors are not dependable either. On the Sacsayhuamán joint
the 10th and 50th percentile depths are **both 0.120**, so two of three
anchors land side by side and straddle no depth at all — which is why its
parallax reads 0.69 px on deciles against 5.32 px on the depth extremes.

So the per-cut gate makes no prediction. It changes one thing and measures
what that thing contributed:

1. **Flat twin** — the same move with a constant depth map. Floor 1.0.
2. **Frozen parameter** — the same move with its parallax-carrying parameter
   held still: `isometric` for a push or pull, the lateral offset for a
   drift. Floor 1.0.

| case | flat twin | frozen twin | verdict |
|---|---|---|---|
| moai row (approved) | 19.639 | 9.550 | pass |
| Tiryns wall (approved) | 6.166 | 3.952 | pass |
| Sacsayhuamán (approved) | 16.012 | 11.840 | pass |
| c053 push 0.2427 | 6.334 | 3.326 | pass |
| c154 push 0.0600 | 7.498 | 8.011 | pass |
| c094 pull 0.1542 | 6.908 | 7.223 | pass |
| c117 drift 0.0136 | 8.441 | 3.742 | pass |
| c003 drift 0.0510 | 21.942 | 21.076 | pass |
| INJECT no-relief map | **0.000** | 15.251 | **FAIL** |
| INJECT zoom-only move | 21.660 | **0.000** | **FAIL** |

Each failure reads **exactly 0.000** on the check that sees it, and the worst
working render reads 3.326. There is no band to overlap, which is what the
absolute px floor could never achieve — it had to thread a gap between 2.03
and 3.54.

**One honest limit.** For a *drift* the frozen twin holds the offset at zero,
so it proves the lateral move is happening, not that it is big enough. It
reads 21.076 on c003, whose plate travels only 2.0 px — so this check would
**not** have caught the drift-mapping defect. For a push or a pull it is
exactly the right question, because freezing `isometric` leaves the zoom
untouched and isolates the parallax.

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

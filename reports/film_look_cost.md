# The film look as a shader pass: what it costs

Measured 2026-10-20 on the M1, `--gl=angle`, 1920×1080.

The brief's condition was that the shader pass stay inside **+25%** of the
base render. It does not, and the reason is worth recording because it is not
the one I expected.

## Method

Per-frame cost is the **slope**, not a single render: a one-frame render on
this machine is about 2 seconds of bundling and 0.03 of drawing, so any
measurement that includes startup measures the bundler. Each configuration was
rendered twice, at 60 frames and at 300, back to back in one sweep on an
otherwise idle machine:

```
per_frame = (t300 − t60) / 240
```

An earlier sweep taken while other renders were running disagreed with itself
by 10% and briefly reported the minimal stack as more expensive than the full
one. These numbers are from the clean sweep.

Source is a still, so these are the floor: an `OffthreadVideo` source adds its
own decode on top.

## Numbers

| configuration | per frame | against CSS |
|---|---|---|
| **CSS** — grade wash, radial vignette, flat darken | **24.4 ms** | — |
| shader, `minimal` — grade + vignette + grain | 43.7 ms | **+79%** |
| shader, `lean` — + small-kernel bloom | 42.7 ms | **+75%** |
| shader, `full` — + mipmap bloom + radial chromatic aberration | 48.9 ms | **+100%** |

## What that says

**The effect chain is not the cost.** Going from the minimal stack to the full
one — adding mipmap bloom and a radially modulated chromatic aberration —
costs about 5 ms a frame. Getting a WebGL canvas, a full-frame plane and an
`EffectComposer` running at all costs about 19 ms before a single effect is
configured.

So there is no trimming that reaches +25%. The floor of the approach is +79%,
and the one configuration closest to it is also the one with **no halation in
it**, which was the reason for doing this in a shader rather than in CSS.

Two further notes for the decision:

- On a twenty-minute film at 30fps — 36,000 frames — the full stack adds about
  **15 minutes** of render time over the CSS treatment. That is the real unit,
  not the percentage.
- The pass is a **second** render over finished frames, because a Remotion
  composition is DOM and WebGL cannot sample DOM. That has a compensating
  advantage the CSS version does not have: the look can be changed without
  re-rendering the film.

## What it buys

See `remotion-composer/out/step13/compare_{hero,joint,quarry}.png` — CSS left,
shader right.

The visible differences, in order of how much they matter:

1. **Halation.** The clouds bloom; the stone does not. A CSS layer cannot do
   this at all, because no layer knows which pixels are bright.
2. **Vignette falloff.** The CSS radial gradient darkens evenly and reads as a
   dark ring; the shader's falls off with distance and reads as a lens.
3. **Grain that belongs to the image** rather than a fixed tile sitting on top
   of it.

One thing the frames show that is a tuning gap rather than a property of
either approach: the shader pass currently sits **brighter** than the CSS
treatment, because the grade is applied as `BrightnessContrast` on one side
and a flat darkening wash on the other. Matching exposure is a half-hour's
work and should happen before anyone judges the two on mood.

## The decision

Not mine to make. The options as measured:

- **Keep CSS.** Costs nothing, loses halation.
- **Ship `full` at +100%.** About 15 extra minutes per 20-minute render, and
  the look in the right-hand frames.
- **Ship `full` on hero slots only.** The pass is per-composition, so it can
  run over the reveals and act cards and leave the rest in CSS. Unmeasured,
  but roughly a tenth of the film is hero material.

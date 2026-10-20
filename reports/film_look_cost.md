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

## The decision — taken 2026-10-20

**Budget withdrawn by the owner. The full stack ships on every slot**, and the
shader path is the playbook default; CSS stays as a fallback flag.

## Addendum: matching exposure before comparing looks

The first set of comparison frames was not a comparison. The two paths were
applying the same grade table by different arithmetic — a flat black layer at
0.15 on the CSS side, an additive `BrightnessContrast` on the shader side — so
the shader read 31–36% brighter and that was the only thing anyone would see.

Both paths now run one chain, `gradeOps()` in `design/system.ts`: multiply by
tint × brightness, then saturate, then contrast. CSS does it with a filter and
a multiply-blended layer; the shader does it with the plane's material colour
plus `HueSaturation` and `BrightnessContrast`. The grade's own darkening —
what stops a bright blue-sky JPEG sitting several stops above the authored
scenes — moved into that chain as `BRIGHTNESS_PULL` instead of living on one
side only.

With the grade matched the gap was still +13 to +17%, and it was **not**
halation: rendering with bloom off changed the mean by 0.1%. It was the
vignette, whose two falloffs darken by different amounts overall. The shader's
darkness is set to 0.85, where the means agree:

| plate | CSS | shader | delta |
|---|---|---|---|
| Rapa Nui hero, act 2 | 64.78 | 63.41 | −2.1% |
| Sacsayhuamán joint, act 3 | 84.30 | 84.68 | +0.4% |
| Aswan quarry, act 4 | 80.46 | 79.03 | −1.8% |

The two vignettes still fall off differently. That is the look, and it is now
the thing the frames show.

## Addendum: the texture race, finally

Three versions of the source loader raced and lost, each more subtly than the
last: releasing `delayRender` in the loader callback captured an empty plane;
releasing it in an effect keyed on the texture still lost under load; two
`requestAnimationFrame`s still produced a black frame in three of six renders.
An intermittent black frame is worse than a slow one — it looks like a look
rather than a bug, and it had already polluted one set of measurements.

Remotion already blocks a frame until an `<Img>` has decoded. The pass now
wraps the element Remotion has finished with, rather than fetching the same
file a second time through `THREE.TextureLoader`. One guarantee, and it is the
renderer's own. Three consecutive renders of the same frame now agree to the
decimal.

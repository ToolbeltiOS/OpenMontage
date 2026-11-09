# The unpainted-frame class

**Status: CLOSED 2026-11-09 as cannot-reproduce. Defended in depth, with a
detector in place. Friday's run is the standing reproduction attempt — if
`plate-dropout` catches a hit, REOPEN with that frame as the failing
measurement.**

A frame whose picture never arrived. The frame is present, it is not a
freeze, and the plate and the delivered file agree about it perfectly,
which is why it got past every gate the pipeline had.

## What was observed

they-said-it-couldnt-be-built (published, `CDpzQKwTBsI`) has **eight**
single-frame flashes: luma about 32 against neighbours at about 15, in dark
passages.

**Five are timeline gaps** — 16648, 21715, 24220, 24603, 26725 — caused by
`Math.round(in*fps)` and `Math.round((out-in)*fps)` rounding independently,
so a cut ended one frame before the next began and nothing covered the
frame between. Fixed by `frameSpan` / `frame_span`, and
`check_timeline_coverage` now refuses to render a props file with a gap or
an overlap. That accounts for five of the eight and for all five of
king-tut's first delivery.

**Three are not gaps**: 21332 (c109, its first frame), 32992 (c169, its
first frame) and 27668 (c141, its LAST frame). All three show the bare
Layer 0 with **no chrome at all** — no act number, no scene index, no
caption furniture, no texture. A scene at opacity 0 would still show its
own backdrop and its own chrome, so this is not an entrance envelope. The
subtree was never painted.

## The lead, unproven

A **compositor layer created but not rasterised when the screenshot was
taken**. A promoted layer that has not rasterised composites as nothing,
which is the only mechanism found that matches "the entire subtree is
absent while its sibling Layer 0 paints".

`translateZ(0)` and `will-change: transform` appear in six places,
including `SceneShell`'s drifting plate layer and its locked layer, and
`design/Type.tsx` promotes glyphs deliberately.

If this is the mechanism there is **no async resource to hold**, so "hold
it with `delayRender`" has nothing to attach to. The honest form would be a
paint barrier: take a handle on the scene root and release it after two
animation frames so the compositor has committed. That costs two animation
frames of wait on every one of ~36,800 frames, and it was NOT written,
because there is no failing measurement to test it against.

## Ruled out, with the reason

| candidate | why not |
|---|---|
| fonts not loaded | `@remotion/google-fonts` `loadFont` takes its own `delayRender` with a 60s timeout for all three families. `fontsReady()` is awaited by nobody and is redundant for renders — its docstring says it is for stills. |
| a throw swallowed into an empty subtree | there are **no error boundaries** anywhere in the composer, so a throw fails the render loudly. |
| a component the three cuts share | they share none. c109 is an `ImageScene` inside `dress()` (`Graded` + `FrameLayer` + `SourceCaption`); c141 and c169 are `TextureField` (`Plate` + svg + `FrameLayer`). `FrameLayer` is common but is a CHILD — its absence cannot blank its own parent. |
| the `backgroundImage` race | a different defect, already fixed by `useBackdrop`. None of these three cuts routes an image through the CSS path. |
| concurrency | the earlier race was concurrency-sensitive. This is not: see below. |

## The reproduction attempt that failed

All three frames re-rendered from the film's own props with current code,
at two concurrency settings, five-frame windows:

```
conc=4  21332: 16.63 against 17.57-27.80   clean
conc=4  27668: 16.94 against 13.91-17.06   clean
conc=4  32992: 13.81 against 13.81-13.86   clean
conc=1  21332: 16.63   27668: 16.94   32992: 13.81   clean
```

Byte-identical between the two concurrencies. 32992 read **32.5 against
neighbours at 14** in the published file and now reads 13.81 against
13.81-13.86.

This tests TODAY's code, which is what matters going forward, and today's
code is clean and deterministic on the exact frames that failed. It does
not prove the defect is gone: an intermittent race that does not happen
once has not been shown to be impossible.

## What defends it now

1. **Layer 0 is the documentary's own `SYS.bg`**, not the template's
   violet gradient. A frame that loses its subtree is near-black against
   near-black. The flash is invisible even if the defect recurs — this was
   always the point of that change.
2. **`plate-dropout` blocks on ANY hit.** The class went from invisible to
   caught before delivery. It is the only gate that can see it: frame count
   sees a frame that is present, frame motion sees that one frame is not a
   freeze, and frame order compares the delivery to the plate, where the
   defect is.
3. The timeline gaps that caused five of the eight cannot recur: the
   coverage check runs before the first pass and refuses the render.

## How to reopen

Do not spend 2h45m re-rendering they-said-it to hunt it. **Every Friday
run is already a 36,000-frame reproduction attempt** with a detector on the
end of it. If `plate-dropout` fails a delivery, that frame is the failing
measurement this was missing: keep the plate, keep the stills, and trace
from a case that exists.

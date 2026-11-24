# The scene-props gate

Written 2026-11-22, after the second render in two nights was killed by a
prop the composer could not draw. The four rulings below were carried out
on 2026-11-24 and the gate went to the runner with them; what each one
actually did is recorded under its own heading.

---

## What it does

`lib/build_render_props.py:check_scene_props` runs the composer's own zod
schemas over every cut, on the finished props, immediately before
`render_props.json` is written — the same boundary as `check_callout_types`
and the last point at which the answer is free. It refuses with the cut,
the field and the rule.

The schemas are TypeScript because `docComponents.ts` is: a Python
restatement would be a second source of truth, which is the bug class the
gate exists to catch. `validate_cut_props_cli.ts` is bundled with the
composer's own esbuild and run under node.

## Why the schemas had no consumer for months

Two reasons, and the second is the interesting one.

1. Nothing imported `docComponents.ts`. It was written for a scene-plan
   buildability check that never wired up — the fourth gate in this
   pipeline found defining a rule nobody enforced.

2. **Pointed at cuts, it cried wolf.** The schemas describe what a
   COMPONENT receives. A cut is not that: `Explainer` maps one onto the
   other, supplying some props and dropping others. On 2026-11-22 the Pearl
   Harbor film scored 85 failures while rendering perfectly well — 75 of
   them because `AnnotatedStill` is handed
   `image={cut.backgroundImage ?? cut.image}` and no cut carries `image`.

   A check that cries wolf is a check nobody can turn on. `DOC_CUT_SCHEMAS`
   states the cut contract separately and **declares every divergence from
   the component contract next to the call site that justifies it**, so the
   difference is visible rather than assumed. Three divergences exist today
   and each names its reason in the source.

## The 16 failures it inherited

Real, long-standing, and none of them fatal — these values would have
failed on films #1–#4 too. The gate surfaces debt; it did not create it.

| class | cuts | what it does today |
|---|---|---|
| `basemap: "terrain"` where a tile object is required | 6 | silently dropped — `Explainer` never passes it |
| `basemap_drift: 1.3` against a `0.08` ceiling | 6 | dropped with it; 16× the ceiling if ever wired |
| `density: 0.4` → `Math.round` → 0 elements | 4 | the texture beat draws nothing at all |

The four density cuts have drawn nothing on every film so far. Film #5
shipped as-is on that basis.

## The four rulings, and what came of them

Rulings of 2026-11-22, carried out 2026-11-24. **The gate stayed strict** —
none of them loosened a rule, and the one schema that did change got
STRICTER in one place and more honest in another.

1. **Basemap wiring.** Pass `basemap` and `basemap_drift` through to
   `MapRoute` (terrain is what the edit asked for), clamp the drift to the
   schema ceiling with the `1.3 → 0.08` cases listed, and re-render those
   six cuts for the NEXT film's benefit, not film #5's. Clears 12 of 16.

2. **Density.** The schema is the authority: an element count, not a
   fraction. Fix it in the stage that writes — the edit director states
   `density` is an integer count with the schema's range, and
   check_timeline/buildability refuses a fractional density at edit time
   with the cut named. **No normalising in the props builder.** Clears 4.

3. **The exemplar digest.** The edit stage's exemplar (king-tut) carries
   these same legacy values, so it is teaching the defect. Rebuild the
   digest from a cut set that passes the gate, and add a test that the
   exemplar itself validates — an exemplar that fails the gate it is meant
   to teach is worse than none.

4. **The inherited baseline.** Run the gate over films #1–#5's
   `edit_decisions.json` and record the counts in the gate's docstring, so
   nobody reads next Friday's zero as a regression check that never ran.

## What the 16 became

Measured end to end through the composer's own schemas on 2026-11-24:
the six published map cuts fail on `basemap` and `basemap_drift` (12), and
`resolve_basemaps.py` clears all 12. The four `density: 0.4` cuts are
refused at edit time with the cut named instead of drawing nothing. The
film the gate was written against goes from 16 failures to 0.

## What it found that nobody was looking for

Four things, all of them in delivered films:

1. **Six map shots of film #6 author no `scale` at all**, so each was drawn
   at d3's default of 1400 — 78.6 degrees of longitude for routes of 17 to
   594 km. Every other film authors one.
2. **Film #5 shows "NaN" where six timeline cards' years should be**, with
   all five labels stacked at the left edge of the frame. Six `timeline`
   cuts carry `year` as a string ("27 Jul", "after"), and `Math.abs("27
   Jul")` is NaN. It was published that way.
3. **king-tut prints "AD 1922.84"** — the fractional year that places an
   event five months into a one-year span was being rendered as the label.
   The schema was wrong to forbid the fraction and the component was wrong
   to print it; both are fixed.
4. **Every film's `document_reveal` credit line is lost.** The edit authors
   it as prose in `source` ("Ledger c33 — contested") and
   `apply_authored_slots` overwrites that with the slot id, while the
   component reads `sourceLine`. Film #5 carries no `sourceLine` on any of
   its 158 cuts. NOT FIXED — recorded here because it is the same shape as
   the basemap drop and wants its own look.

## Coverage

636 of 991 cuts across the six films are checkable. `broll` (74),
`text_card` (9) and `comparison` (2) have no schema at all; they are
reported in `unchecked` and never counted as passing.

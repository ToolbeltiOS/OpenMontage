# The scene-props gate

Written 2026-11-22, after the second render in two nights was killed by a
prop the composer could not draw. **Not live in the runner**: it lands with
Monday's merge, and items 1–3 below must land WITH it or it refuses a film.

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

## Owed Monday, with the merge

Rulings of 2026-11-22. **The gate stays strict** — none of these is a
reason to loosen a rule.

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

## Sequencing

Items 1 and 2 clear all 16. Merging the gate without them refuses the next
film at the props build — in about a second, with the cut, field and rule,
rather than 18 minutes into a render, but it refuses.

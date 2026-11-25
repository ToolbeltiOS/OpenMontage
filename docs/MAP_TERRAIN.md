# Terrain under a map

Written 2026-11-25, when film #6's six map shots were re-resolved for its
replacement and every tile the resolver cut turned out to be unusable.

## What happened

The six `map_route` cuts of the Pearl Harbor film author no `scale`, so
each was drawn at d3's default of 1400 — 78.6 degrees of longitude for
routes of 17 to 594 km. The extent is computed from the route now, which
brought them to 1.00–7.94 degrees. That is the defect that was visible in
the frames.

Resolving the basemaps for those new extents cut five tiles. All five are
unusable, and `good_enough` passed every one of them:

| cut | extent | tile | source px per frame px |
|---|---|---|---|
| c006 | 1.00° | 60 × 32 | 0.03 |
| c094 | 1.00° | 60 × 32 | 0.03 |
| c121 | 1.00° | 60 × 32 | 0.03 |
| c112 | 3.29° | 476 × 247 (shared) | 0.10 |
| c043 | 4.84° | 291 × 151 | 0.15 |
| c070 | 7.94° | 476 × 247 | 0.25 |

Looked at upscaled to frame width, c006 is a pastel smear with JPEG
blocking and no legible coastline; c070 draws the Hawaiian islands as
lumps on a blank white ocean with a stray green square sitting in open
water.

`good_enough` bounded a tile that was too WIDE — four times the frame is a
quarter of the detail — and had no bound in the other direction at all. A
check written to protect detail passed the five coarsest tiles the
pipeline has produced.

## The rule

`MIN_SOURCE_PX_PER_FRAME_PX = 0.5` in `scripts/resolve_basemaps.py`: a
tile must supply at least one source pixel for every two drawn, which is a
2x upscale and what shaded relief survives. Below it there is no terrain
to draw and the map draws as vectors — which is what every published film
already does, because `Explainer` never passed `basemap` through at all.

It is enforced in three places, because a tile reaches the props by three
routes: one found on disk, one the resolver has just cut (the builder will
hand back 60 × 32 for a one-degree frame without complaint), and one
already written into the artifact by an earlier run (that branch used to
return on `isinstance(dict)`, which left the resolver unable to correct
its own output).

## Why Natural Earth cannot do this

Natural Earth 10m is one equirectangular raster at about 60 px per degree.
A tile cut to the frame has `extent × 60` pixels across a 1920-wide frame,
so the detail is `extent / 32` and the floor is met only at **16 degrees
and wider**:

| extent | px per frame px | |
|---|---|---|
| 1.00° | 0.031 | refused |
| 4.84° | 0.151 | refused |
| 7.94° | 0.248 | refused |
| 12.00° | 0.375 | refused |
| 16.00° | 0.500 | the floor |
| 20.00° | 0.625 | passes |

This matters for the plan below: the handover point is 16 degrees, not 5.
c043 at 4.84° and c070 at 7.94° are both above 5° and both still fail on
Natural Earth, so a boundary drawn at 5° would hand them to a source that
cannot serve them and they would stay vector anyway.

## Owed: local-scale terrain (next week, its own item)

Copernicus DEM GLO-30 — 30 m, 1 arc-second, about 3600 samples per degree,
free and public — rendered locally as a hillshade rather than cropped from
a fixed raster. At the same floor it clears from **0.267 degrees** upward:

| extent | px per frame px |
|---|---|
| 0.10° | 0.19 (refused) |
| 0.27° | 0.51 |
| 1.00° | 1.88 |
| 5.00° | 9.38 |
| 16.00° | 30.0 |

So: Copernicus below 16 degrees, Natural Earth at 16 and above. A hillshade
rendered to the frame meets the floor by construction, so the thing to
measure is the DEM's own sampling at the extent asked for, by the same
`source_detail` the tiles go through — not by eye, and not after a film has
shipped on it.

Conditions, in the order they have to hold:

1. The floor is measured on the rendered hillshade with `source_detail`
   before any film uses it, and recorded here next to the table above.
2. Every one of film #6's six extents is checked, including the two
   between 5 and 16 degrees that are the reason this note exists.
3. The tiles are looked at upscaled to frame width. Both faults above were
   caught that way and neither showed up in a number.
4. A DEM is elevation, not a picture: a hillshade has no water mask and no
   land cover, so the sea needs drawing rather than inheriting whatever
   the DEM has at sea level.

Until that is done the maps draw as vectors at the resolved extents, which
is what films #1–#6 have always shipped.

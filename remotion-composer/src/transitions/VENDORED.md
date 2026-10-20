# Vendored transitions

These five transitions and the `core/` helpers they need were **copied**, not
depended on.

| | |
|---|---|
| upstream | https://github.com/GTKottman/remotion-transitions |
| commit | `58df899` |
| copied | 2026-10-20 |
| licence | MIT — see `LICENSE.upstream` |

## Why a copy

There is no npm package: `remotion-transitions` is not on the registry. The
repository was created and last pushed within three minutes of each other on
2026-10-06, and has no stars, forks or issues. A git dependency on a
single-commit repository with no users can change or disappear underneath a
production pipeline, and the total surface we want is about 20 KB — small
enough to read, which is what makes copying it the safe option rather than the
lazy one. The full read is in `reports/vendor_vetting_transitions.md`.

GitHub shows the licence as "Other". That is a false alarm: `LICENSE` is the
standard MIT text with one paragraph appended putting the repository's bundled
Space Grotesk fonts under the SIL OFL, and the exact-match detector refuses it.
We copied no fonts, so the OFL paragraph does not reach us. The MIT notice is
preserved in `LICENSE.upstream` as the licence requires.

## What was taken, and what was not

Taken: `film_dissolve`, `luma_dissolve`, `dip_to_colour`, `light_leak`,
`film_burn`, plus `core/`.

Not taken: everything in the Motion and Distortion families, per the brief.
Nothing from the upstream catalog, schema, CI, preview app or fonts.

## Changes from upstream

The import path in each `index.tsx` was repointed from `../../../../src/core`
to `../core`, which is the only edit. The transition sources are otherwise
byte-identical to commit `58df899`, so a future upstream diff is readable.

## What they need at render time

`light_leak` and `film_burn` are WebGL fragment shaders and need a GL context —
on this machine, `--gl=angle`, the same requirement as the step 13
post-processing pass. The other three are CSS and SVG and render anywhere.

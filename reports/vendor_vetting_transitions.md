# Vetting: GTKottman/remotion-transitions

Read 2026-10-20, at commit `58df899`, before importing anything from it.
This is the read; the import itself is step 14 and is not done yet.

## What it is

An open library of 50 Remotion transitions organised by a taxonomy, with a
catalog.json, a JSON schema per transition, a submission protocol and CI.

## Provenance — read this before trusting it

| | |
|---|---|
| created | 2026-10-06 20:56 UTC |
| last push | 2026-10-06 20:59 UTC — **three minutes later** |
| stars / forks / issues | 0 / 0 / 0 |
| npm package | **none** — `remotion-transitions` is not on the registry |
| GitHub licence badge | "Other" (NOASSERTION) |

The licence badge is a false alarm: `LICENSE` is the standard MIT text,
copyright "2026 GTKottman and contributors", with one appended paragraph
putting the bundled Space Grotesk fonts under the SIL OFL. GitHub's detector
refuses the exact match because of that paragraph. **The licence is MIT and
the five files we want carry no font dependency**, so the OFL paragraph does
not reach us.

Everything else about the provenance is thin: one push, no users, no release,
no published package. That is not a reason to refuse the code — it is a reason
not to take a dependency on the repository.

## The code

All five named transitions were read in full.

| transition | lines | mechanism | risk |
|---|---|---|---|
| `film_dissolve` | 14 | two opacity ramps, `mixBlendMode: plus-lighter` | none |
| `dip_to_colour` | 9 | one `AbsoluteFill` of flat colour, opacity ramp | none |
| `luma_dissolve` | 36 | SVG `feColorMatrix` + `feComposite`, alpha keyed on luma | none |
| `light_leak` | 48 | **WebGL fragment shader**, blobs + fbm noise, screen-blended | needs a GL context |
| `film_burn` | 54 | **WebGL fragment shader**, SDF burn holes with per-frame flicker | needs a GL context |

No network access, no `eval`, no filesystem access, no child processes, no
postinstall script, no analytics. Pure presentational React plus two GLSL
shaders. The whole surface we would take is about 6 KB of transitions plus
roughly 14 KB of `src/core` helpers (`Shader.tsx`, `bridged.tsx`, `clip.ts`,
`math.ts`, `presentation.tsx`, `svg.tsx`, `types.ts`).

`light_leak` and `film_burn` render through WebGL, so on this machine they are
subject to the same `--gl=angle` requirement as the step 13 post-processing
pass. The other three are plain CSS and SVG and will render anywhere.

## Recommendation

**Vendor, do not depend.** Copy the five transitions and the core helpers they
need into `remotion-composer/src/transitions/`, with a `VENDORED.md` recording
the origin URL, the commit SHA, the MIT text and the provenance facts above.

Reasons: there is no npm package to pin; a git dependency on a single-commit
repository with no users can change or disappear under us; and the total
surface is small enough to read, which is exactly what makes vendoring safe
here. The import is 20 KB of code we have read, rather than a moving target.

Nothing from the Motion or Distortion families is imported, per the brief.

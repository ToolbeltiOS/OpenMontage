# vork evaluation — notes before the test

**Status: HELD behind merge week by owner instruction, 2026-11-08.** Step 1
(the licence gate) is DONE and recorded below. Steps 2–4 have not been
started. Nothing is installed on this Mac.

When it runs: branch `vork-test` from `automation`, **nothing merged back**
unless the verdict passes.

---

## 1. Licence — CLEARED, with conditions

`github.com/voyager-so/vork`, **vork Preview License**, © 2026 Nullframe,
Inc. GitHub reports the SPDX id as `NOASSERTION` because it is a custom
licence, **not** because it is restrictive.

The owner's stop condition was "restricts commercial or monetised use". It
does not. Verbatim:

> vork is source-available. **It is free to use during the research preview,
> including for commercial work.** It is not open source.

> You may, free of charge: use vork for **any purpose, including commercial
> work** and use inside a company of any size; **use your AI agents to
> operate vork for you**; modify vork for your own use; share unmodified
> copies of vork with this license and all notices intact.

> **We claim no rights in the scenes, code or media you create with vork.**
> Any assets you use keep their own terms.

> Rendering for your own organization, and **delivering the finished media
> to a client, is allowed** and isn't a hosted service.

So a monetised YouTube film is inside the grant, and so is the unattended
pipeline operating it. **Do not re-derive this.**

### Conditions that bind us

- **No resale, sublicensing, or distributing a modified version.** We don't.
- **No hosted service** where other people submit scenes or jobs to be
  rendered. We don't.
- Rights **end automatically on breach**, restored if cured within 30 days,
  unless already breached before.
- No warranty, no liability.

---

## 2. VERSION PIN — a requirement, not a preference

> **This version only.** This license covers this version of vork only.
> Later versions may come under different terms, **including paid terms**. A
> change in later versions doesn't take away your rights under this license
> to the version you already have.

The weekly run cannot depend on "latest" for something whose terms may
become paid without notice. If vork is adopted:

1. **Pin an exact version** in the pipeline — never a floating tag or an
   install script that fetches latest.
2. **Keep a local copy of the pinned release artefact AND its LICENSE
   file**, in a location the pipeline does not rebuild. The rights attach to
   the version already held; a copy is what makes that provable later.
3. **Record the version in the film's own artifacts** for any film that uses
   it, the way asset licences are recorded, so a published film can say
   which terms its renderer was under.
4. Re-read the LICENSE before moving the pin. Its blob sha at the time of
   this reading is below; a different sha means the terms changed.

### What was read, and when

| what | value |
|---|---|
| read on | 2026-11-08 |
| latest release | `v0.2.0`, published 2026-11-07T20:54:08Z |
| `v0.2.0` commit | `a18cac5d68eae4b6d8d7c0126c44722b02edb897` |
| previous release | `v0.1.0` (`09dbd97a8601dbbd5870dc5a2856aa59d7ea21dd`) |
| default branch | `main` |
| LICENSE blob sha | `3457c10e0eace46984aaa7826f469603599c4e01` (3203 bytes) |
| repo description | "Headless 3D and VFX engine for agents. Research preview." |

**Research preview** is itself a risk worth naming: the project is eight
days from its first release and the pipeline it would sit in runs unattended
once a week.

---

## 3. THE GPL CARVE-OUT — the trap in this licence

> The Blender bridge in `integrations/blender` is a separate component under
> **GPL-3.0-or-later**, and this license does not cover it.

This Mac has Blender tooling available, so reaching for that bridge is a
plausible accident. **The main engine is not GPL; the bridge is.** Using it
pulls GPL-3.0-or-later obligations into whatever links against it. If the
test needs Blender at all, that is a decision to take deliberately and
record, not a convenience to reach for mid-render.

---

## 4. Feasibility, checked while reading (nothing installed)

- Written in **Rust and Slang**, rendering through **Vulkan and Metal**.
- "Rendering requires **Apple Silicon** or an NVIDIA GPU with Vulkan ray
  queries" — this Mac qualifies.
- Scene authoring and `vork help` work with no GPU; scenes are JSON, with
  optional TypeScript or Python authoring through SDKs.
- **Affects the step-2 measurement:** without a fast GPU denoiser, draft and
  final "use 16 and 32 samples undenoised". The seconds-per-frame numbers
  must say which path they took, or they are not comparable to anything.

---

## 5. The test, as specified — steps 2–4, NOT started

2. **One hero.** The Khufu cutaway with the Grand Gallery, Queen's chamber
   and the Big Void as a lit section. 6 s at 1080p30, camera push, playbook
   palette and the film grade applied **after**. Measure **seconds/frame at
   std/previs and std/final, peak memory, compile time**. Compare side by
   side with the current Remotion schematic.
3. **One CC0 Sketchfab scan** (a sarcophagus or a moai) under the Poly Haven
   dusk HDRI, 6 s orbit. Compare with `model_orbit`.
4. **Verdict with numbers.**

### Adoption rule if it passes

A `vork_scene` authored route for **hero slots only, at most 4 per film**.
Output goes through the **film grade** and **every existing gate**.
Everything else stays as it is.

---

## 6. Merge-week items this is held behind

- cut the `node_modules` symlink: `rm`, `npm ci`, and a `run_weekly.sh`
  start check that refuses a symlinked or missing `node_modules`
- the blocking **`plate-dropout`** gate with its injected-frame control, and
  `dropout_scan.py` lifted out of the scratchpad into `lib/`
- **sentence-level caption timing**, so a film ships its own SRT instead of
  falling back to auto-captions (king-tut failed its own readability check:
  47 of 269 cues over the 20-characters-a-second ceiling)
- the **second unpainted path**: narrowed on 2026-11-08 to a scene subtree
  that never painted — no chrome, no backdrop — with composited-layer
  promotion (`translateZ(0)`, `will-change`, `filter:`, `mixBlendMode`) as
  the lead, but not traced to a specific async paint

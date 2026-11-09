# `asset-library` — the house library

Branched from `automation`, and **unmerged until after `visual-quality`
merges next week**.

## Merge order, agreed

1. **`visual-quality`** first.
2. **`asset-library`** second.

Each goes in only after a **2-minute slice renders end to end through
`scripts/render_film.py`** — not a bare Remotion render — **with every gate
green**. The distinction matters: a flat Explainer pass hands
`plate_is_clean` the type it is looking for and `check_motion` a picture
with no grain, so the absolute numbers mean nothing and only a before/after
comparison does. Through `render_film.py` they mean something.

## What went to `automation` early, and why

Two commits, both bug-fix-shaped and both pushed:

- `db20713` — AnnotatedStill never read the authored camera (19 of 20 cuts
  ran the default move).
- `f75c570` — the scene director requires `claim_id` on every `map_route`
  slot, **with the buildability check that enforces it**. The gate was
  ported alongside the skill because the skill states the check fails a
  route without one; on `automation` it did not, and an instruction
  claiming an enforcement that does not exist is the inert-guard failure in
  the one file the planner reads. Those ~20 lines are identical to the ones
  `asset-library` already carries and will merge with it.

## Library of Congress is not reachable from here

`www.loc.gov` answers scripted requests with a Cloudflare interstitial and
**HTTP 403**, including `?fo=json`, with and without a descriptive
User-Agent. Every map plate therefore comes from Wikimedia Commons, which is
enough. Recorded so nobody spends an afternoon rediscovering it; LoC remains
the better source for US-held survey sheets if someone fetches them by hand
from a browser.

Commons itself answers a burst of large downloads with **HTTP 429**. The
plate fetch keeps the asset bank's 3-second floor and backs off.

## `event_year`: the link has to be authored, not inferred

`lib/event_year.py` reads the year from the ledger claim's TEXT — the dated
event — and never from `source_name`, which carries the publication date and
is usually modern.

Finding which claim a cut illustrates is the hard part, and **inferring it
from the scene description does not work.** Measured on easter-island's four
map_route cuts, matching on shared distinctive words:

| cut | description | best inferred match | right? |
|---|---|---|---|
| c140 | "Orongo on the crater rim … with the swim drawn between them" | a claim dated **1868** | no — that is the HMS Topaze visit; the birdman swim is a recurring ritual with no single year |
| c164 | "the small statue's route, off the islet and out" | a claim dated **1914** | no — matched on the word "small", against a Routledge expedition |
| c158 | "the route the statue took off the island" | ties three claims | no — a tie is not an identification |

A wrong year silently selects a wrong plate, which is a confident false
statement about what the mapped people were looking at. So:

- the scene's **authored `claim_id`** is the real link, and is used when
  present;
- the matcher is set to refuse nearly everything (three distinctive words,
  and any tie is a refusal);
- anything unresolved gets terrain with the reason `undated event`.

**All four easter-island routes are currently `undated event`**, which is the
correct and safe answer with the data as it stands. Proved end to end by
giving `act4_s025` a `claim_id` of `r17` by hand: it resolved to **1869**,
and then correctly fell to terrain anyway because no plate covers a route
from Rapa Nui to London. That hand edit was reverted — authoring which claim
a cut illustrates is a content decision for the scene planner.

**Open:** the scene planner does not yet write `claim_id`. Until it does,
every route is terrain.

---

## Merge week, item 1: an approved illustration that no cut uses

Found on 2026-11-01 while diagnosing the Noah render. The three
illustrations generated for Noah were posted to the Telegram script gate and
approved by the owner at `2026-10-31T09:20:42` — and **appear in no cut of
the film**.

`assets/library/illustrations/approved.json` is read by
`scripts/telegram_gate.py`, `lib/illustration_spec.py` and
`scripts/make_illustration.py`. It is read by nothing in the scene planner,
the asset bank or the render path. Measured on the Noah props:

| | |
|---|---|
| approved for `noah` | 3 |
| referenced by a cut in `render_props.json` | **0** |
| planner asset mix | `still 29.6 / graphic 53.5 / texture 17.0` — no illustration class exists |

So the illustration route ends at the gate. The owner approved a decision
that had no effect, and a report could have said the illustrations were in a
film they were not in.

**This is the third gate-without-consumer this project has produced**, after
the `cut.texture` that was never forwarded (first style-frame before/after
came back byte-identical on four of six pairs, both sides being the "after")
and the camera props `AnnotatedStill` never read. The pattern is always the
same: a gate reads what was *authored* and nothing reads what was
*rendered*.

`lib/verify_approved_use.py` makes it a hard failure, in both directions:

- an illustration approved for the project that no cut references;
- a cut referencing an illustration that was not approved for the project,
  which is the standing rule — an illustration not approved at the gate is
  not used, and the slot falls back to a still or an authored graphic.

It matches on **file basename, not path**, because `props_for_layer` stages
assets and `assets/library/illustrations/ark-build.png` in the plan is
`assets_noah/ark-build.png` by the time the renderer sees it. And it
searches the whole props blob as text rather than a known set of fields,
because the two previous faults of this kind were both a field that was
never forwarded: a check that looks only where the asset is *supposed* to be
cannot see it missing.

Blocking, from `gates()` in `lib/film_render.py`. Proved not inert — six
cases, both directions:

| case | verdict |
|---|---|
| approved and used | PASS |
| approved, staged under a different directory | PASS |
| approved and not used | FAIL |
| used but not approved | FAIL |
| two approved, one used | FAIL |
| nothing approved, nothing used | PASS |

On `noah` as it stands it reads **FAIL**, naming all three files. That is
correct and is left standing: the Noah film is wanted as it is, the fault is
known, and the work of giving illustrations a consumer in the scene planner
is this item.

**Still to do, and it is the item itself:** give the planner an illustration
slot class so an approved illustration can be chosen for a cut. The gate
turns a silent omission into a stopped build; it does not supply the
consumer.

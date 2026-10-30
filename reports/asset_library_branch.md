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

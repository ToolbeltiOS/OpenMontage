# `asset-library` — the house library

Branched from `automation`, unmerged until after Friday's run.
`visual-quality` is frozen for its own merge and is untouched.

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

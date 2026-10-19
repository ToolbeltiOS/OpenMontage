# Research Director — Narrated Documentary Pipeline

Adapted from `skills/pipelines/explainer/research-director.md`. The explainer
version researches to find an angle. This version does that **and** builds the
claim ledger that binds the script.

## When To Use

A topic and a rough angle exist. Before any prose is written, you produce a
`research_brief` that is simultaneously:

- the **angle finder** — at least 3 genuinely different ways to tell this story, and
- the **claim ledger** — every date, name, number and quote the script is
  permitted to state, each with a source.

The script director is forbidden from stating a fact that is not in this ledger.
That makes this stage the factual floor of the whole piece: a thin brief produces
either a thin script or an unsourced one.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/research_brief.schema.json` | Artifact validation |
| Prior input | Topic, angle preference, target duration | Scope |
| Playbook | Active style playbook | Register and audience |

## Process

### 1. Map The Landscape

Find at least 3 existing treatments of this topic. For each, record what it
covers and what it misses. You are looking for the gap you can own — the
question everyone raises and nobody answers.

### 2. Pull An Encyclopedia Source For Every Named Entity

**Mandatory.** For every person, place, object, institution or event the piece
will name, pull the Wikipedia/Wikimedia article and record it. This is the
baseline against which spellings, dates and titles are checked. A named entity
with no encyclopedia pull is an incomplete brief.

Wikimedia Commons is also your first stop for public-domain stills and
document scans — note anything visually useful as you go, with its licence. The
asset director will thank you.

### 3. Build The Claim Ledger

Every factual span the script may use becomes a ledger entry:

```json
{
  "claim_id": "c07",
  "claim": "The tomb was opened on 26 November 1922.",
  "kind": "date",
  "sources": ["https://en.wikipedia.org/wiki/...", "https://..."],
  "confidence": "established",
  "surprise_factor": "expected",
  "contested": false,
  "notes": "Carter's own diary gives the 26th; some accounts say the 24th."
}
```

Rules that matter:

- **`kind`** is one of `date`, `name`, `figure`, `quote`, `event`, `claim`.
  Dates, names and figures are exactly what the script gate checks.
- **`confidence`** is `established`, `probable` or `contested`.
- **`contested: true`** is not a defect — it is often the most interesting
  material. But a contested claim must be narrated *as* contested. Never let a
  disputed date be stated flatly.
- **Two sources for anything surprising.** If a figure is the hook, one source is
  not enough.
- **No orphan numbers.** A figure with no unit, date or basis is unusable. "It
  weighed 60,000 tons" needs to say as measured by whom, and when.

Target at least 8 ledger entries for a 20-minute piece; a thin ledger forces the
script to pad.

### 4. Find The Angles

At least 3, each grounded in specific ledger entries via `grounded_in`. An angle
that cannot point at the claims that support it is a vibe, not an angle.

For each angle, state honestly whether the ledger can carry it for the full
target duration. An angle with four good claims cannot carry twenty minutes —
say so here rather than discovering it in act 3.

### 5. Record What You Could Not Find

A dedicated `gaps` list. Things you looked for and could not source are
first-class output: they tell the proposal director which angles are unsafe and
tell the script director which sentences can never be written.

### 6. Quality Gate

- Every named entity has an encyclopedia source.
- At least 8 ledger entries, each sourced with a URL.
- At least 3 angles, each with `grounded_in` references.
- Contested claims are marked, not smoothed over.
- Gaps are recorded.

## Common Pitfalls

- **Researching for colour instead of for claims.** Atmospheric detail you cannot
  source is unusable; the script will be tempted to state it anyway.
- **One source behind a surprising number.** This is how documentaries inherit
  errors from each other.
- **Skipping the Wikimedia pull because you already know the spelling.** The pull
  is the audit trail, not a memory aid.
- **Letting the ledger lag the script.** If drafting surfaces a new claim, it
  comes back here for a source or it does not go in.

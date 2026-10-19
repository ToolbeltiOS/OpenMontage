# Script Director — Narrated Documentary Pipeline

Adapted from `skills/pipelines/explainer/script-director.md`. The explainer
writes a 60–120 second script in one pass. At twenty minutes that approach
produces padding, so this version is **outline-first and act-by-act**, and it is
**bound to the claim ledger**.

## When To Use

The `proposal_packet` is approved. You now write the narration. Everything
downstream — slots, cuts, graphics, captions — is placed against this text, so
the script is the contract for the whole piece.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/script.schema.json` | Artifact validation |
| Prior artifact | `state.artifacts["proposal"]["proposal_packet"]` | Angle, acts, hook, duration, voice |
| Prior artifact | `state.artifacts["research"]["research_brief"]` | **The claim ledger — mandatory, not optional** |
| Playbook | Active style playbook | Word band, act band, cold-open rules |
| Meta skill | `skills/meta/voice-performance-director.md` | TTS delivery cues |

## The Two Hard Rules

### Rule 1 — Never generate the whole script in one call

Write in this order, as separate passes:

1. **Outline pass.** Beat-level outline for the whole piece: every act, every
   beat inside it, the ledger entries each beat spends, and a target word count
   per act. No prose.
2. **Act passes, one at a time.** For each act, draft prose with exactly this
   context: the outline, the previous act's final text, and the ledger entries
   assigned to this act. Not the whole script.

Why: a single-pass long-form script restates its own setup, drifts off the
ledger, and converges on filler phrasing. Act-by-act with the previous act in
context keeps continuity without inviting repetition.

After each act, run the padding check below before starting the next.

### Rule 2 — Never state a fact that is not in the ledger

Every date, name, figure and quote in the narration must trace to a
`research_brief` claim. Carry the reference inline:

```json
{
  "id": "a2_b3",
  "text": "The doorway was sealed twice — and opened on the twenty-sixth of November, 1922.",
  "claim_refs": ["c07", "c11"]
}
```

If drafting needs a fact that is not in the ledger, you have two options: send it
back to research for a source, or cut the sentence. You may not write it and
flag it later. A span with no `claim_refs` must contain no checkable fact.

Contested claims must be narrated as contested. If the ledger marks a date
disputed, the narration says it is disputed.

## Process

### Step 1 — Absorb The Proposal And Ledger

Extract the word budget, the act list with per-act promises, the locked hook, the
voice and the target WPM. Then read the ledger and assign entries to acts. An act
with no assigned entries cannot be written.

### Step 2 — Write The Outline

Beats, not prose. For each beat: what it asserts, which claims it spends, roughly
how many words. Sum the words and check against the budget before writing any
prose. Fixing a structural overrun in the outline is cheap; fixing it in act 4 is
not.

### Step 3 — Cold Open (under 45 seconds)

The cold open carries the approved hook. Rules:

- Under 45 seconds, hard.
- Opens on the most arresting concrete image or claim available — never
  "In this video", never a greeting, never a channel intro.
- Plants the central question and does not answer it.
- If the proposal says to reuse an existing hook, reuse its *language and
  rhythm*, not a transcript lift; it has to sit inside the longer register.

### Step 4 — Act Passes

Per act: the promise, the new information, the ledger spend. Use
"therefore / but" transitions rather than "and then" — each beat should be caused
by the previous one, not merely adjacent to it.

End each act on an open loop that makes the next act necessary.

### Step 5 — The Padding Check (after every act)

Before moving on, answer all four. A no to any one means revise this act now:

1. **New information** — does this act tell the viewer something no earlier act
   told them? Name it in one sentence.
2. **No restatement** — does any paragraph re-explain something already
   established? Cut it; a callback is one clause, not a paragraph.
3. **Earned length** — if this act were 20% shorter, what would be lost? If the
   answer is "nothing", it is 20% too long.
4. **Ledger density** — does it spend at least one ledger entry per ~150 words?
   Prose with no claims under it is filler.

Record the answers in the artifact per act. The reviewer reads them.

### Step 6 — The Ending

An **open question**, not a summary. Do not recap the acts; the viewer just
watched them. Land on the implication the piece has earned and let it stand.

Outro CTA: 10 seconds maximum, and nothing essential in it.

### Step 7 — Delivery Cues

Per section, write `delivery_cues` the TTS can actually implement — pace, energy,
emphasis words, pause lengths. For a documentary register the useful instruction
is usually *slower on the reveal, pause after it*. Add `pronunciation_guides` for
every proper noun the voice is likely to mangle; archaeological and astronomical
names are reliably mangled.

### Step 8 — Word Count

Count the narrated words. Do not estimate. Report the count, the budget and the
implied runtime at the target WPM. If you are more than 10% over, cut — do not
assume the voice will read faster.

## Quality Gate

- Outline existed before prose, and is in the artifact.
- Each act drafted in its own pass with the padding check recorded.
- Every checkable fact carries `claim_refs`.
- Word count inside the playbook band.
- Cold open under 45 seconds and carrying the hook.
- Ending is an open question.
- Acts within the playbook's act band.

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). Checkpoint
`awaiting_human`, present the summary, and **END YOUR TURN**.

## Common Pitfalls

- Writing all five acts in one pass because the outline felt clear.
- A fact that "everyone knows" going in without a ledger entry.
- Act 4 restating act 2 with new adjectives.
- A summary ending, which reliably reads as a shrug.
- Estimating the word count from the character count.

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

### Step 5b — Write For The Voice (after every act)

The padding check asks whether the act earns its length. This asks whether a
voice can say it.

Four rounds of voice A/Bs on 2026-11-10 ended with the plain synthesiser
beating every attempt to improve it. A spectral chain was measured and
rejected. A per-sentence pause model was built and rejected. A second engine
was cloned, verified sentence by sentence, and rejected. The fault was never
in the voice. It was prose written for the **eye**: sentences all of a
length, a subordinate clause hanging off each one, figures as digits,
attribution trailing after the claim, and nothing short to land on. Across
the three delivered scripts — 565 narration sentences — there are **two
questions**.

Rewrite each act against the list below, then run the lint. It blocks the
script gate.

```
.venv/bin/python scripts/check_claims.py --project <slug> --section <act>
```

**Read the verdict from the command's own last two lines.** It prints
`CLAIMS: PASS` or `CLAIMS: FAIL`, then `VOICE: PASS` or `VOICE: FAIL`, and
every violation above them with the sentence that broke it.

**Do not append `; echo "RC=$?"`.** A chained `echo` is a second command and
the permission layer judges it separately from the first, so the whole line
is refused — the 2026-11-11 rehearsal had exactly that denied and spent
turns working out why. The same goes for piping the output into anything.
One command, and read what it says.

For the same reason, do not reach for `python - <<'PY'` to inspect an
artifact. `docs/STAGE_CONTRACT.md` forbids a stage authoring programs, and
a heredoc is a program. Read a slice of a large artifact with a script that
already exists, or with `python -c`.

`scripts/check_cadence.py` prints the same violations with a per-section
table when you want the numbers rather than the gate.

**Length**

| | |
| --- | --- |
| words per sentence | ≤ 20, hard maximum 28 |
| mean across the act | ≤ 15 |
| sentences under 8 words | ≥ 20% |

**One idea per sentence.** No sentence with two subordinate clauses. No
semicolons. No parentheses. A voice cannot say a semicolon — the synthesiser
reads straight through it as a comma — and a bracketed aside arrives as part
of the sentence it interrupts.

**Contractions where they are natural.** `it's`, `that's`, `didn't`,
`wasn't`, `isn't`. Never `could've`, `would've`, `should've`, `there'll`,
`it'll`: those are sayable but not cleanly, and a synthesiser mangles them.

**Everything spoken, nothing written.** Numbers, years, units, currency and
percentages as words. No `%`, `$`, `°`, `&`. No abbreviations except where
the letters are what is spoken — `BBC` is fine, `Dr.` and `e.g.` are not.

**No eye-words.** "The former", "the latter", "respectively",
"aforementioned", and "however" dropped into the middle of a sentence. Each
one asks the listener to look back up a page they cannot see. Name the thing
again instead.

**Attribution leads.** Title or identification before the name on first
mention, then `says` for a living voice or `wrote` for a document. Never a
trailing "said X". On the page the eye has already seen the quotation marks;
spoken, a trailing attribution gives the listener a claim with no owner and
tells them whose it was after they have decided whether to believe it.

**Rhythm.** No three consecutive sentences within three words of each other.
At least one question per act. Each landing line ≤ 8 words.

**Breath.** Commas at the breath points even where the grammar does not
require one. At most two em dashes in a paragraph — each is a turn, and three
is a list.

**The gate is a budget, not a demand for perfection.** A film passes VOICE
with **six or fewer blocking violations across the whole film**, and
**none at all** on a landing line or over the 28-word hard maximum. Those
two are audible on their own; everything else is a tendency, and a budget is
what a tendency deserves.

This is deliberate. You have sixty turns. You can rewrite the worst twenty
sentences in a 176-sentence film; you cannot rewrite every one, and a gate
demanding zero would make you spend the cap trying and then fail on the turn
limit with an act half-edited. Fix the worst, and the rest can stand.

The budget is a **whole-film** number, so a single-act run cannot judge it —
six across a film is not six per act. Run `check_claims.py` without
`--section` for the verdict; with `--section` it still refuses the two
zero-tolerance faults and tells you the budget is owed.

**Contractions are advisory.** They are reported and never counted. Whether
`is not` is emphasis or sloppiness is your judgement and no regular
expression can make it — "The chronology is not the part anyone disputes" is
the line act one turns on.

**The lint is a floor, not the goal.** No measurement hears rhythm. An act
can satisfy every rule above and still read flat, and the only judge of that
is reading it aloud. What the numbers catch is the specific failure the four
A/B rounds were spent on, which no other check in this repo can see.

Two things the rules do not settle, and you decide by ear:

- A run of deliberate fragments — "Arthur Mace. Mervyn Herbert. Richard
  Bethell." — is three sentences within three words of each other and is the
  opposite of flat. The lint allows a run whose every sentence is already
  under 8 words. Longer runs it reports, and you judge.
- `is not` is sometimes the emphasis you want over `isn't`. That is why the
  whole contraction rule is advisory: reported with the sentence, never
  counted against the budget.

The fact gate is unchanged by any of this. `check_claims.py` reports the
sourcing and the voice separately, because they fail for different reasons
and are fixed by different edits.

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

**These are now load-bearing.** A guide used to feed only the YouTube
description. `scripts/build_narration_lexicon.py` is the step that says each
proper noun to the real voice, transcribes it, and respells only the ones a
transcriber actually misheard — and the respelling it writes is derived from
the guide, mechanically: `too-tan-KAH-moon` becomes `tootankahmoon`, which is
the form that measured correct. A name the voice mangles with no guide to
convert is reported unresolved and the step exits non-zero, because there is
nothing safe to invent. Write the guide in dictionary notation as always; do
**not** write IPA, and do not write the letters-only form yourself.

```
.venv/bin/python scripts/build_narration_lexicon.py --project <slug>
```

Run it once the acts are written. It writes `artifacts/lexicon.json` beside
the script, and `scripts/synthesize_narration.py` applies it on top of
`assets/narration/lexicon.json` — so the lexicon changes only what is
**spoken**. The script keeps its real spelling, which is what reaches the
captions, the listing, the alignment text and the fact gate.

### Step 8 — Tag Every Paragraph With A Beat

Put `[beat: <type>]` on its own line above each paragraph. Four types, and the
planner reads them to decide how long a shot may hold:

| beat | what it is | shots run |
|---|---|---|
| `reveal` | the paragraph that turns the act — at most one per act | 12–25s, one shot |
| `landing` | the sentence after a reveal, where the voice stops | 4–8s |
| `transition` | moving between subjects or into a new act | 1.5–3.5s, in a burst |
| `exposition` | everything else, and most of the film | 6–10s |

An untagged paragraph is exposition, which is usually right. Tagging everything
a reveal is the same as tagging nothing: run #1 had no beats at all, the planner
gave every slot one band, and 181 of its 182 shots came out between 5 and 8
seconds long.

### Step 8b — Tag The Register Beside The Beat

`[beat: reveal | awe]` — the beat says what the paragraph is *doing*, the
register says how it *sounds*. Five registers, and only these five: `awe`,
`tension`, `doubt`, `quiet`, `resolution`. The register is optional; the beat
is not.

`lib/script_beats.py` is the authority on the syntax and it is strict. A line
it does not match is not an error — it is prose, so a mistyped marker loses
the beat and adds its own words to the count the gate blocks on. A register
outside the five is rejected there, because the mood table would quietly fall
back to the beat-only row and give the paragraph the same move as every other.

Two reveals in one film can be awe and tension. Tagged only by beat they get the
same push at the same speed, which is how run #1 ended up with one gesture for
182 shots. The playbook's `motion.mood.table` maps (beat × register) onto the
move, its speed, the transition family, a hold multiplier and whether the
music may rise there.

The register is a reading of the paragraph, not of the subject: a quiet
sentence about a catastrophe is `quiet`.

### Step 9 — Write The Air

**Air is written, not found.** Put `[air N.Ns]` on its own line between
paragraphs, using 1.5, 2.5 or 4.0 seconds and nothing else:

```
[beat: reveal]
The granite had been quarried a hundred and forty miles away.
[air 2.5s]

[beat: landing]
Nobody has explained how it got here.
[air 4.0s]
```

Where it goes:

- after a landing line — 1.5s or 2.5s;
- at each act's own climax — 4s, once per act;
- before a reveal the narration has set up and the picture has not yet turned
  — 1.5s;
- somewhere at least every two minutes.

Across the film the air totals 8–15% of the runtime. This is why the word
budget is 2,500–2,700 and not 2,800–3,200: the silence is part of the runtime,
not an overrun on top of it.

Run #1's `pause_policy` asked for "a full beat of silence after each verdict
sentence". The delivered film held thirteen seconds of silence in twenty
minutes and never stopped talking for longer than 2.8 seconds, because the
policy was prose and nothing downstream could read it. A marker can be read.

### Step 10 — Word Count And Duration

Count the narrated words. Do not estimate. The runtime is **speech plus planned
air** — `words / wpm * 60 + sum(air)` — so measure it that way and not by words
alone, or the air will read as an overrun and get cut.

Run the gate; it does the arithmetic and writes the narration plan the
synthesis and mix stages read:

```bash
.venv/bin/python lib/script_beats.py projects/<id>/artifacts/script.json \
    --plan projects/<id>/artifacts/narration_plan.json
```

If you are more than 10% over the duration band, cut words — never air. A film
that needs its silence removed to make length was too long in prose.

## Quality Gate

- Outline existed before prose, and is in the artifact.
- Each act drafted in its own pass with the padding check recorded.
- Every checkable fact carries `claim_refs`.
- Word count inside the playbook band (2,500–2,700).
- Every paragraph carries a beat type.
- Air written as markers, 8–15% of runtime, one 4s gap per act.
- `lib/script_beats.py` exits 0 and the narration plan is written.
- Cold open under 45 seconds and carrying the hook.
- Ending is an open question.
- Acts within the playbook's act band.

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). Checkpoint
`awaiting_human`, present the summary, and **END YOUR TURN**.

## Common Pitfalls

- Writing all five acts in one pass because the outline felt clear.
- Writing a pause policy in prose instead of marking the air. Prose is not a
  number, and no stage downstream can act on it.
- Treating air as slack to be cut when the runtime is long. Cut words.
- A fact that "everyone knows" going in without a ledger entry.
- Act 4 restating act 2 with new adjectives.
- A summary ending, which reliably reads as a shrug.
- Estimating the word count from the character count.

## Air Is Written, Not Found

Silence is a thing you write. Mark it in the script with `[air 1.5s]`,
`[air 2.5s]` or `[air 4.0s]` and the narration synthesiser leaves a real gap
there; `lib/script_beats.py` is the gate and the film's total air must land
between 8% and 15% of its runtime.

Because the air is part of the runtime, the word budget shrinks to account for
it: 2,500–2,700 words for a twenty-minute film, not the 3,000 a wall of speech
would need. Duration is speech **plus planned air**, never speech alone.

Run #1 had 13 seconds of silence in 20 minutes and its longest gap was 2.8
seconds, because every pause was whatever the synthesiser happened to leave.

# Forced-alignment confidence, and where the threshold should sit

Measured 2026-10-20 over run #1's narration, re-aligned with WhisperX
(wav2vec2) against the approved script.

## The rule

A narration paragraph whose mean alignment confidence falls below the
threshold is re-synthesised and re-aligned; still under after two attempts and
the stage fails. Implemented in `lib/alignment_qa.py`, threshold in the
playbook at `audio.alignment_qa.min_mean_confidence`.

## What confidence catches that duration does not

The word-duration gate finds an alignment that **collapsed** — run #1 had an
eight-word sentence occupying 30 milliseconds. It cannot find one that is
confidently placed and wrong, or a synthesis the aligner could barely follow.

Confidence can, and did: the words of that collapsed sentence scored 0.08–0.33
against 0.67–0.96 either side of it. The signal was in the data before anyone
looked at the timings.

## The distribution

54 paragraphs, 2,960 words.

| | mean confidence |
|---|---|
| p10 | 0.356 |
| p25 | 0.395 |
| **p50** | **0.546** |
| p75 | 0.697 |
| p90 | 0.773 |
| range | 0.291 – 0.836 |

Per section: cold open 0.609, act 1 0.547, act 2 0.454, act 3 0.710,
act 4 0.629, outro 0.787.

What a threshold flags:

| threshold | paragraphs | share of film |
|---|---|---|
| 0.35 | 5 | 9% |
| 0.40 | 16 | 30% |
| 0.45 | 20 | 37% |
| **0.50** | **23** | **43%** |
| 0.55 | 27 | 50% |

## The thing I expected to explain it, and did not

The obvious hypothesis was that the aligner loses confidence on proper nouns
and spoken numerals, of which this script has an unusual number — Pumapunku,
Sacsayhuamán, "seven hundred and fifty kilometres".

**Measured, it barely holds.** The correlation between a paragraph's density
of capitalised-mid-sentence and digit-bearing tokens and its mean confidence
is **−0.087**. Paragraphs above 12% density average 0.475 against 0.567 below
it — a gap of 0.09 on a sample of eleven. That is a direction, not an
explanation, and it is not enough to account for a median of 0.55.

The likelier reason is simpler and less testable from here: wav2vec2 was
trained on human speech and this narration is synthesised. A model scoring an
unfamiliar voice marks the whole film down, which moves the median rather than
creating a tail.

## What that means for the threshold

At 0.5 the rule flags 43% of the film — below the median. That is a property
of the measurement, not a defect rate, and re-synthesising half a film on an
uncalibrated number would be a lot of machine time spent on a constant.

The shape of the data suggests the defect lives in the **tail**, not the
middle: 0.35 flags five paragraphs, which is the order of magnitude of
something actually wrong, and it sits well below the collapsed sentence's own
0.08–0.33.

**The threshold stays at 0.5 as specified.** It is a playbook value, the
distribution is recorded here, and the gate reports what it would
re-synthesise rather than doing it, because the synthesiser is not wired in
yet. When run #2's narration exists, re-measure: if its median sits near
0.55 again, 0.5 is measuring the synthesiser and the number should move to
the tail.

## What is not wired up

`audio.alignment_qa.resynth_command` is null. The narration is kokoro driven
through the hyperframes CLI, outside this repo. With no command configured
`--fix` reports that nothing can be re-synthesised automatically rather than
silently passing, and the gate names the paragraphs.

Attempt counts live in `projects/<id>/artifacts/alignment_qa.json`, so the
two-attempt budget survives a re-run.

---

## 2026-11-02: what neither gate catches — local drift

Measured on noah, which shipped without a caption track because of this.

WhisperX placed **every one of 2,687 words**: 0 unplaced, 0 under the 40ms
floor, `WORD TIMINGS: PASS`. The track was still unusable — **39 of 275 cues
over the 20 chars/second ceiling**, worst at 47, in a film averaging 13.6.

The error is local and **it conserves**: 15 further cues run **under 9
chars/s**. Words are held too long exactly where others are rushed, so the
section totals come out right and every whole-film measure looks correct.
Re-running the alignment reproduced it to the word — 2,690 of 2,690 timings
identical — because the aligner is deterministic and was doing what it always
does.

**Both gates look straight at this and see nothing, for the same reason: they
measure a word.**

| gate | what it reported on noah | why it misses drift |
|---|---|---|
| word duration | 0 of 2,687 under 40ms, PASS | `repair_unplaced` spreads unplaced runs and `enforce_floor` pads every word to 41ms, so it reads the REPAIR, not the alignment |
| mean confidence | 0.352 over the ceiling vs 0.590 elsewhere | real but partial — only 1 of the 39 is in the near-zero band, so it narrows the search and does not find the fault |

Confidence still earns its place: it is the only one of the two that moved at
all. But neither is a cue-level instrument, and a cue is what a viewer reads.

**The conclusion for the playbook** (`captions.timing`): word-level forced
alignment on synthetic speech drifts locally, and **the sentence is the
authority for cue timing**. Word timings are a hint inside a sentence, never
the span of a cue.

### The agreed fix, for merge week

1. Detect sentence boundaries from silence — VAD over the narration wav.
2. Match that sequence to the script's sentence sequence.
3. Give each sentence its **measured** span.
4. Distribute each sentence's words inside that span by character count.
5. Build cues from the result.

**Acceptance: A/B on act 2 against the current track. Cues over 20 cps AND
cues under 9 cps must both drop to near zero** — both, because the error
conserves, and fixing only the fast cues would mean the time was moved
somewhere else rather than corrected. If it holds, apply to noah and
easter-island and upload both tracks.

Until then noah serves YouTube's automatic captions, which is better than a
track that overrides them and flashes.

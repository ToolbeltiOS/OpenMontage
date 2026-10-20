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

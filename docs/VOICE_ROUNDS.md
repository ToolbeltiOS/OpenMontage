# The narration voice: four rounds, and what was actually wrong

2026-11-10. Four A/B rounds against the narration of `king-tut` act 1.
Three different ways of changing the **voice** were built and rejected. The
thing at fault was the **prose**, and the fix landed in the script director
as Step 5b with `scripts/check_cadence.py` to measure it.

This file exists so none of it is attempted a second time. Every rejection
below has the measurement that justified building it and the measurement
that killed it.

## What was kept

| | |
| --- | --- |
| Voice | Kokoro `bm_george` via `npx hyperframes tts`, unchanged |
| Lexicon | `assets/narration/lexicon.json`, applied by `scripts/synthesize_narration.py` |
| Lexicon derivation | `scripts/build_narration_lexicon.py` at the script stage |
| Prose rule | script-director Step 5b, measured by `scripts/check_cadence.py` |

## Rejected 1 — the spectral chain

High-pass, mud cut, de-esser, presence lift.

**The measurements that justified it were real.** Sibilant peaks measured
louder than the body of the speech, and presence-band energy sat at 4.2% of
the total. Both true, and the conclusion drawn from them was wrong: the
narration was not dull because of its tone.

Rejected by ear, A preferred. **Not wired.** Do not revisit on the strength
of a spectrum — the spectrum was never the complaint.

## Rejected 2 — the pause model

`lib/voice_cadence.py`, 30 tests, deleted unmerged. A per-sentence model:
rate by sentence kind (landing 0.76, body 0.87, question 0.84, list 0.92,
±2.5% deterministic jitter), silence chosen by what the sentence is
(clause 0.15s to act end 2.0s), generated breaths in front of sentences over
18 words, room tone at −55 dB underneath.

It worked as specified and shaped more silence than the script's own air.
Rejected by ear in rounds 2 and 3, against the plain synthesiser both times.

**The lesson is in where it put the rate.** A model can place pauses
correctly and still not fix flat prose, because the flatness is in sentences
that are all the same shape. Varying the delivery of uniform sentences gives
uniform sentences delivered variously.

## Rejected 3 — Chatterbox

Voice cloning on MPS from a 10-second `bm_george` reference, exaggeration
0.45 then 0.5, `cfg_weight` 0.3. Its own venv, deleted.

Rejected by ear after four rounds, and it was given every advantage:

- **Full act, verified sentence by sentence.** 81 sentences, 81 generations,
  **0 retries and 0 fallbacks** — every sentence passed a per-sentence
  transcript check on the first attempt.
- 315.7s of audio in 33 minutes, about 6× realtime, which extrapolates to
  **~2h08m of synthesis per 20-minute film** against Kokoro's few minutes.
- **No speed control.** Chatterbox has no rate parameter, so a per-sentence
  rate can only be a pitch-preserving stretch applied AFTER generation. A
  slow Kokoro line is spoken slowly; a slow Chatterbox line is spoken and
  then stretched.
- **It mangled names Kokoro says correctly.** Carnarvon came back "canavan",
  "Canavan", "Knavon" and "canavans" in four of six sentences, where Kokoro
  reads it correctly almost everywhere and needs no lexicon entry at all.
  The set of names needing a respelling is engine-specific, so a shared
  lexicon derived from Kokoro under-serves it by construction.

## The round-3 false result, which is the most useful thing here

Round 3 was A (plain Kokoro) against K (Kokoro + lexicon) and E (Chatterbox
+ lexicon) over a full act. **A won, and the result was an artefact of the
lexicon, not a fact about the voices.**

Version 1 of the lexicon respelled 19 proper nouns in dictionary notation —
`kar-NAR-von`, `too-tan-KAH-moon`. Both engines read the notation **out
loud**, mid-sentence. A won because the other two were saying "car. Na-von".

The repair is in `lib/narration_lexicon.py`:

- **Kokoro's phoneme syntax does not work on this pipeline, and that was
  measured.** `hyperframes tts` is kokoro-onnx with an espeak phonemizer,
  not the kokoro/misaki python pipeline, and has no phoneme input at all
  (`--lang` picks a phonemizer language). Handed
  `[Tutankhamun](/tuːtənˈkɑːmən/)` it said *"slash second-restress TU-length
  and T-Schwar, NK letter 251"*. espeak's own `[[tu:t@nkA:'mu:n]]` is read
  just as literally. **Do not reach for either again.**
- What works is a plain lowercase respelling that looks like an ordinary
  word. `tootankahmoon` is said as Tutankhamun. Hence letters-only, enforced
  by `tests/lib/test_narration_lexicon.py`.
- **Respell only names a transcriber actually misheard.** 19 became 6.
  Saqqara → "Sakara" and haematopoietic → "hematopoietic" are *correct*
  readings in a conventional spelling, and respelling them replaces a
  correct reading with a guess.
- **Choose every respelling by measurement.** `guyger` for Geiger looks
  right and Kokoro says *"guide your"*.

## Traps in the verification itself

The checker has its own error rate, and it matters more than the threshold.

1. **Whisper's own floor.** Transcribing known-good Kokoro audio it scored a
   mean WER of 0.048 and a worst of 0.146 — it heard "was 6" for "was sex".
   A threshold at or below that noise floor retries good audio three times
   and then replaces it, reporting a failure that never happened. 0.25 sits
   clear of the floor and under a real failure.
2. **Comparing the respelled text to the original.** The model was handed
   the respelling and scored against the written word. 18 false fallbacks.
3. **Spelled-out numbers against digits.** The script says "nineteen
   twenty-two" and Whisper writes "1922". 5 more false fallbacks, and this
   act is made of figures. A twelve-word map was not enough.
4. **Orthography cannot decide whether a name was misheard.** Measured on
   this evidence, the most distant *correct* reading (Fellowes → "Fellows")
   scores further from its name than the closest *wrong* one (Aspergillus →
   "a spergulus"). No single threshold splits them, which is why
   `lib/narration_lexicon.py` has three answers and reports the middle band
   instead of guessing.
5. **Verify at the grain you synthesise at.** `tootankahmoon` transcribes
   correctly in a carrier sentence and in its own real sentence, but the
   whole-paragraph render of that paragraph came back "two Tenkamun's".

## What the prose problem actually was

Measured across the three delivered scripts — 565 narration sentences:

| film | sentences | mean words | longest | questions |
| --- | --- | --- | --- | --- |
| noah | 178 | 15.38 | 54 | 0 |
| they-said-it-couldnt-be-built | 205 | 14.56 | 56 | 1 |
| easter-island | 182 | 14.81 | 55 | 1 |

Two questions in 565 sentences, a mean within a word of each other in all
three, and a longest sentence over 50 words in every film. That is the
flatness three different synthesisers were asked to fix.

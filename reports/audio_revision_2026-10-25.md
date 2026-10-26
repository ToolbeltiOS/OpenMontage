# Audio revision — easter-island — 2026-10-25

The owner's notes from the first full watch, what was measured against them,
and the six defects the measuring found — five in the audio and one, found on
the way, in the delivered file's length.

**Not delivered by remux in the end.** The remux path was built and works
(`scripts/render_film.py --remux`, `-c:v copy`, tested), and it carried the
first two rounds of this mix. But the sixth defect is fifteen frames missing
from the end of the picture, and a remux copies the stream it is given — it
cannot put back what is not in it. The film was re-composited from the look
and type passes already on disk (`--deliver-only`), which is a fresh
first-generation encode from the same sources rather than a second generation
of the delivered one. The frame-order gate's correlation with the plate reads
0.9963, the same figure to four decimals as the 2026-10-24 delivery, which is
what says the picture did not change.

The new numbers are in `styles/wak3up-documentary.yaml` as the defaults. They
supersede `-30` and the earlier rise amounts.

## What the notes asked for, and what shipped

| asked | shipped | measured |
|---|---|---|
| bed under speech −33 LUFS | −33 | **−33.0 LUFS**, LRA 3.1 |
| gap rises capped at +3 dB | +3, as a cap on the move | envelope peak in a gap **+3.00 dB** |
| 1.5 s ramps in and out | 1.5 s raised cosine, both edges | over 28 raised regions: 10–90% rise **0.68 s median**, 1.28 s slowest; fall 0.68 s median, 0.89 s slowest. A 1.5 s cosine crosses 10–90% in 0.59 of its length, so 0.89 s is the figure to expect and the slowest region is exactly that; shorter regions get clipped ramps, which is why the median is under it |
| act boundary −27, not −22 | −27 | envelope peak at a boundary **+6.00 dB** on a −33 bed |
| 2:1 compressor on each bed, LRA ≤ 6 | 2:1, threshold solved from the material | LRA **3.3 / 4.1 / 2.4 LU** |
| beds within ±1.5 LU of each other | per-bed conditioning before the join | spread **0.1 LU** |
| ducking release 1.2 s | **1.5 s anticipatory ramp instead** — see below | fall 90–10% 0.68 s median |
| centroid and >4 kHz for every bed | all 67 library tracks + the 3 beds | table below |
| swap the cold-open bed for the softest in the approved set | `TORSION` ↔ `Spooked` | 512 Hz → **236 Hz** centroid |
| EQ: HP 120, high shelf −6 from 3.5 k, LP 5 k | `highpass=120 ×2, highshelf=3500:-6:q=0.7, lowpass=5000 ×2` | — |
| gate: no bed over 10% above 4 kHz | `lib/music_brightness.py`, inside the mixer | worst bed **0.14%** |
| ambience −4, risers −8, impacts −8, stings −6 | ambience as asked; **the three one-shots a further −10 as a group** — see below | all 14 events under the bed |
| gate: no SFX event louder than the bed, measured | `lib/verify_sfx_level.py`, inside the mixer | **0 of 14** over; margin −0.8 to −8.6 dB |
| final mix | unchanged spec | **−14.0 LUFS**, −1.5 dBTP, LRA 2.9 |

## Six defects the measuring found

### 1. The envelope was keyed on narration segments, not acts

`gain_envelope`'s second argument was named `offsets` and was given
`build_narration`'s per-**segment** offsets — 73 of them against 6 acts. Every
paragraph start got the act-boundary lift, the loudest level in the mix, under
speech, mid-sentence. **365 seconds of a 1,210-second film: 30% of the runtime
at a level reserved for the fade through black.**

This is "MUSIC LEVEL IRREGULAR", and no existing gate could have found it. The
film's integrated loudness is set by the voice. The bed's integrated loudness
still landed on its target, because 73 brief lifts average out over twenty
minutes. The music-rise gate only examines the cuts the *edit* asked to lift
under. Nothing measured the envelope against the thing it was supposed to be
keyed to.

The name was the whole bug: `offsets` is true of both lists. The parameter is
now `boundaries`, `build_narration` returns the two separately, and
`tests/lib/test_mix_envelope.py` injects the segment list and measures the
share of the film that gets lifted.

### 2. The sound-design layer was ducked twice relative to its reference

`build_sound_design` was handed `bed_ducked`, and the layer it returns is then
multiplied by the same envelope. So every offset was relative to a bed that
had already been lifted, and then lifted again — 3 dB in a gap, 6 dB at a
boundary, which is exactly where the impacts and the stings are placed, and
nowhere else. Measured: the sting at 52 s came out at −32.3 LUFS against a
−38.3 target. +6.0 dB, the boundary boost to the decibel.

### 3. The bed was taken from the middle of each track

With the comment "take from the middle". On this film the middle was the worst
available choice: `Spooked` fades out over its last thirty seconds, and the
middle of a 321-second window inside a 353-second track puts the window's tail
inside that fade — an **18.7 dB hole, landing on the act 2 boundary, where the
sting is.** `steadiest_window` now scores every candidate window on its own
spread and hole depth. Measured on the delivered beds: holes of 5.8, 8.4 and
3.8 dB.

### 4. The offsets and the gate were in different units

The playbook states the sound-design levels as offsets from the bed;
`lib/sound_design.py` applied them as broadband RMS; the new gate asks the
question in K-weighted loudness. On the gate's first run **all fourteen
one-shots came out over the bed while the table said three of them were under
it.** The keys are also named `riser_peak` / `impact_peak` / `sting_peak` and
were being applied to the whole file's average, which for a transient with a
decay sits about 10 dB under its loudest moment.

Both are now in LUFS, and the `_peak` keys refer to the peak.

### 5. A limit that was reported rather than reached

The ambience crest control solved its gain curve once and reported the figure
it had been **asked** for. Asking for 3 dB in a single pass delivered 3.5 to
6.9 dB across this film's five ambience beds — the 200 ms smoothing blunts the
reduction at the sharpest peak — and the worst of them, stone at 6.9 dB, then
failed the SFX gate by 1.2 dB. A gate two modules away catching the
consequence of a claim nobody checked.

It iterates now, re-measuring and re-solving each pass. A second round of the
same mistake was nearly made in the fix: the loop converges on the limit from
*above*, so a break on `crest <= limit` exactly never fires and all five beds
burned every available pass to land on 3.0 dB — the cap was doing the
stopping, which would have let an asset slightly worse than this film's worst
fall out still outside its limit. The break is now on the tolerance the report
states, the loop stops in 2 to 6 passes of 10, and a bed that still cannot be
held **refuses the mix** rather than reporting a number it did not reach.

| bed | crest before | after | passes |
|---|---|---|---|
| room tone | 2.9 dB | 2.9 dB | 0 of 10 |
| sea ambience (cold open) | 11.9 dB | 3.1 dB | 2 of 10 |
| stone ambience (act 1) | 17.0 dB | 3.1 dB | 6 of 10 |
| wind ambience (act 2) | 7.2 dB | 3.1 dB | 5 of 10 |
| stone ambience (act 3) | 17.0 dB | 3.1 dB | 6 of 10 |
| sea ambience (act 4) | 11.8 dB | 3.1 dB | 3 of 10 |

### 6. The delivered film was half a second shorter than its own edit

Found while checking that the remux had not truncated anything. It had not —
but the original delivery had: **36,302 frames in the file against 36,317 the
edit asks for.**

The cut durations and the narration timeline do not come to the same length.
169 cuts each rounded to a frame leaves them 0.486s apart — picture 1210.567s,
mix 1210.081s — and `deliver` passed `-shortest` with the audio the shorter of
the two, so the picture was cut: fifteen frames off the end of the outro, under
the closing title card.

Two things kept it invisible. The report printed the number the **edit** asks
for, taken from the props and never compared with the file. And `frame_count`'s
own docstring claimed that dropping the composition's trailing pad "also makes
the picture and the mix exactly the same length" — false by half a second, and
the reason nobody looked.

The frame-motion gate had the real number the whole time: it decodes the film
and returns `frames`. So the fix adds no decode — `gates` compares the two and
fails on a mismatch, and the report now prints "delivered of asked". `deliver`
and `remux` pad the audio with `apad` before `-shortest`, so the shorter of the
two is the picture.

## Where the brightness actually was

The note said the cold-open bed had audible high content. Measured, it did not
— and the gate the note asked for cannot find what was heard.

| bed | track | centroid | >4 kHz | after the EQ |
|---|---|---|---|---|
| `open_act1` | Spooked - Mini Vandals | 236 Hz | 0.10% | 0.02% |
| `act2_act3` | EBB - Density & Time | 559 Hz | 0.14% | 0.02% |
| `act4_outro` | TORSION - Density & Time | 512 Hz | 0.06% | 0.01% |

`TORSION`, which opened the film, is the **7th darkest of 67 tracks** in the
library at 0.06% above 4 kHz. **No track in the library exceeds 10%**, so that
ceiling passes everything it will ever be shown here. It is kept as a guard
against a future library and the playbook records, beside it, that it did not
find this.

What the measurement did find is in the sound-design layer:
**`ambience_sea.mp3` has a 1,647 Hz centroid and 7.8% of its energy above
4 kHz** — three times the cold-open bed's centroid and 130 times its high-band
share — sitting 6 dB under the bed for the first 52 seconds of the film. The
bright thing in the cold open was never a bed.

The bed was still swapped, because the swap is independently supported: the
approved set (tracks meeting all three movement criteria) has exactly two
members, and measured as the segments actually play, `Spooked` is 353 Hz
against `TORSION`'s 683 and carries 0.73% of its energy above 2 kHz against
1.29%. Both cover their new span unlooped, so the swap costs no loop seam.

## Two places the notes were not followed exactly

**"Ducking release 1.2 s."** The edges are now explicit 1.5 s raised-cosine
ramps and the one-pole is demoted to a 30 ms de-zipper. The note asks for a
1.5 s ramp and a 1.2 s release on what is the same edge, and measured, a
one-pole delivers neither: at 1200 ms it gives a **2.64 s rise and a 0.33 s
fall**, and an authored ramp in front of it barely moves the rise while
dragging the fall out. A one-pole cannot be asked for a ramp length — which is
the same objection this module already makes to using a compressor for the
ducking. The ramp out is anticipatory: it finishes as the voice returns rather
than releasing after it, which offline mixing can do and a reactive ducker
cannot. At 1.5 s it is slower than 1.2 s, so it is the more conservative of
the two against pumping.

**The one-shot offsets.** The note gives a table *and* a gate, and measured,
the table does not satisfy the gate: at ambience −10 / riser −2 / impact +4 /
sting +8, all fourteen one-shots were over the bed, by +4.2 dB (a riser) to
+18.3 dB (a sting). An offset of +8 cannot be under the bed. The gate carries
the reason — "everything below the bed's level in its moment" — so the gate
wins, and the three one-shot offsets are the note's numbers **shifted down by
10 dB as a group**: riser −12, impact −6, sting −2. The spacing between them
is the note's, unchanged — riser 6 dB under impact, impact 4 dB under sting.
Ambience and room tone are the note's numbers untouched.

**If this is too quiet by ear, the thing to relax is the gate, not the levels.
The levels are now derived from it.**

## Per bed

| bed | source LUFS | compressor | LRA | 5–95 spread | hole | in film | window |
|---|---|---|---|---|---|---|---|
| `open_act1` | −12.3 | 1 pass at −12.3 dB | 3.3 | 5.85 | 5.84 | −32.9 | 0.0s (middle 16.1s) |
| `act2_act3` | −18.0 | 5 passes at −30.0 dB | 4.1 | 5.89 | 8.4 | −33.0 | 70.0s (middle 127.8s) |
| `act4_outro` | −15.5 | 1 pass at −15.5 dB | 2.4 | 3.15 | 3.81 | −33.0 | 300.0s (middle 198.6s) |

`act2_act3` is `EBB`, the one bed that missed a selection criterion
(`build_db` 6.57 against a preferred 5). It needed five compressor passes and
is still the widest of the three. It is the next thing to replace, by ear,
when the library grows.

### Why the gate is the 5th-to-95th spread and not LRA

LRA is the metric the note names and it cannot see a hole: it is the 10th-to-
95th percentile of short-term loudness above a relative gate, so a bed can
read **5.7 LU of LRA with a 13 dB drop-out in it**. Both were true of this
film's act 2/3 bed before conditioning. LRA is recorded; the spread is gated.
`tests/lib/test_bed_conditioning.py` injects a bed with a 14 dB hole and
asserts LRA reads under 6 on it.

## Every SFX event against the bed under it

| event | at | design | bed | margin |
|---|---|---|---|---|
| impact | 23.79s | −41.4 | −35.6 | −5.8 |
| riser | 39.06s | −41.6 | −37.1 | −4.5 |
| sting | 45.00s | −34.4 | −32.0 | −2.4 |
| sting | 52.00s | −36.9 | −32.8 | −4.1 |
| impact | 183.84s | −42.6 | −36.5 | −6.1 |
| riser | 202.39s | −40.7 | −34.1 | −6.6 |
| sting | 317.45s | −36.3 | −34.9 | −1.4 |
| impact | 511.00s | −39.9 | −36.3 | −3.7 |
| riser | 529.91s | −42.5 | −33.8 | −8.6 |
| sting | 628.61s | −37.3 | −36.4 | −0.8 |
| impact | 843.79s | −40.6 | −36.2 | −4.4 |
| sting | 937.26s | −33.0 | −30.9 | −2.0 |
| impact | 1082.36s | −39.7 | −36.1 | −3.6 |
| sting | 1197.79s | −32.8 | −31.5 | −1.3 |

Continuous layers (ambience, room tone): **0.0 s over the bed**, against
44.9 s before the ambience crest control. 1.8 s is excluded as a hole in the
bed and counted, so a bed full of drop-outs cannot hide behind the exclusion —
measured against the bed's median less 6 dB, which is the spread the bed gate
permits.

The hole test was the bed's 5th percentile first, which does not work: a hole
big enough to occupy 5% of the film defines its own floor, so the deeper and
longer the drop-out, the less of it is recognised as one. On a fixture with a
hole across 20% of the runtime the percentile version excluded 0.1 s of it.

One other thing had to change for this to pass: the ambience files are not
steady. `ambience_stone.mp3` peaks **17.0 dB over its own median** and
`ambience_sea.mp3` 11.9 dB, so placing them by their median let their peaks
poke through the music. They are now held to a 3 dB crest, iteratively (see
defect 5).

A third change is in the bed and not in this gate. The bed crossfades were
`tri`, which is linear in **amplitude**: at the centre of the fade both sides
sit at 0.5, and two uncorrelated beds at 0.5 sum to 0.707. Measured on two
uncorrelated pink-noise beds, `tri` costs **2.92 dB** at the join centre and
`qsin` costs **0.05 dB** — so there was a 3 dB dip at every act boundary where
two beds meet. That belongs to "the bed must stay in the background the whole
film", not to this gate: placing the one-shots against the bed's level in
their own moment would have compensated for the dip anyway, so `qsin` is not
what made the stings pass. It is what stops the music level changing at a
boundary.

## Rises

The rise set was re-reconciled against the new bed: **10 kept, 11 cleared**
(against 6 and 15 on the old bed). The reconciliation is in the stage that
rebuilds, so the next render reproduces it rather than failing again.

`mix_inputs_hash` now covers the reconciled rise set as well as the music
block and the narration. The rises are an input to the mix, so leaving them
out let `--reuse-audio` hand back a mix built for a rise set that no longer
existed — the same class of defect the hash was added to stop. It converges in
two passes, verified: `bccf8daafa221936` on both.

The hash also proved the remux honest. The mix was rebuilt after a change that
touched only the gate's hole threshold, and came back **byte-identical**
(`bed126607f381d9f2fbab178807eb470`) — which is what established that the
delivered film was carrying exactly the mix the report describes, rather than
an earlier one.

## Gates

`scripts/render_film.py --project easter-island --deliver-only` — see
`reports/film_delivery_final.md`.

| check | measured | verdict |
|---|---|---|
| frame motion | 0.1% duplicate pairs, longest freeze 0.0s, timestamps constant | PASS |
| frame order | 0 frames out of place, 0 isolated black, correlation with the plate 0.9963 | PASS |
| plate purity | 0 words legible in the plate pass | PASS |
| type lock | 143 text-bearing scenes, 0 with a word in a different place, worst 0.58px | PASS |
| frame count | 36,317 delivered of 36,317 asked | PASS |
| delivery audio | −16.9 dBFS mean, −14.01 LUFS against the mix's −14.0 | PASS |

And the four audio gates, run on the delivered file and its layers:

| gate | measured | verdict |
|---|---|---|
| delivery audio | −14.01 LUFS, peak −1.4 dBFS | PASS |
| music rise | 10 asked for, 10 the music supports | PASS |
| music brightness | worst bed 0.14% above 4 kHz | PASS |
| SFX level | 0 of 14 events over the bed, 0.0s of the continuous layers | PASS |
| sound design spec | ambience 5, risers 3, impacts 5, stings 6, room tone yes | PASS |

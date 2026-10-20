# Reference pacing — LEMMiNO, Barely Sociable, Fall of Civilizations

Measured 2026-10-20 for run #2 of *They Said It Couldn't Be Built*.

Sources: `scripts/pick_reference_videos.py` (selection, YouTube Data API,
read-only), `scripts/analyze_reference.py` (measurement),
`reports/reference_handcount.json` (ground truth), and run #1's own
`edit_decisions.json` and `render_props.json` for the comparison column.

---

## 1. What was measured, and what the instrument can carry

| | |
|---|---|
| **LEMMiNO — Cicada 3301: An Internet Mystery** | 17m54s · 42.7M views · 2018 · 60fps |
| **LEMMiNO — Consumed by the Apocalypse** | 26m19s · 7.0M views · 2021 · 60fps |
| **Barely Sociable — The Book Tied To 75,000 Disappearances** | 27m29s · 4.17M views · 2021 · 60fps |
| **Barely Sociable — The Dark Side Of Antarctica** | 24m22s · 2.32M views · 2023 · 60fps |
| **Fall of Civilizations — 8. The Sumerians**, first 20 min | 2h27m49s total · 40.9M views · 2020 · 30fps |
| **Fall of Civilizations — 8. The Sumerians**, final 20 min | same upload |

The first of each channel is its most-viewed upload inside the brief's 10–30
minute window; the second is the most recent datapoint in that window, added
because the window itself dates the sample. All three channels have drifted
long-form — LEMMiNO's post-2021 films run 34–147 minutes, Barely Sociable's
last three are 48m/198m/24m — so anything inside 10–30 minutes is these
channels' 2018–2021 register, not their current one. Fall of Civilizations has
**nothing** in the window: its catalogue jumps from a 1m39s thank-you video to
a 63m30s film, so it enters as two 20-minute windows of its most-viewed film
and is reported separately throughout. It is a long-form reference and its
numbers are never averaged with the other two.

### The cut counts are hand-made, not detected

The automatic cut detector was not good enough to set a target from, and the
way it fails is worth recording because it will come back.

PySceneDetect's `ContentDetector` at its default threshold read **36 shots in
the whole of Cicada 3301** — a mean shot of 30 seconds, which is wrong by any
reading of the film. Dropped to threshold 16 it fired twenty times inside a
single held title card whose only movement was an animated audio waveform. A
confirmation pass — keep a candidate only when the colour distribution
genuinely differs across it — fixed that minute exactly (18 cuts against a
hand count of 18) and survives in the script as the default recipe. It does
not generalise: on Fall of Civilizations' aerial footage the same recipe reads
19 against a hand count of 8, because a detector fires *inside* a moving shot,
and on another LEMMiNO minute it reads 1 against 7, because two photographs
that share a palette do not look like a cut to a histogram.

Both error directions are material-dependent, not random, so no single
correction factor exists. Eight minutes were therefore counted by eye off 1 fps
contact sheets (`reports/reference_handcount.json`); those are the absolute
numbers below. The detector's per-minute curve is still used, but only as the
*shape* between hand-counted points, and it is labelled as such.

Known residual bias: a shot shorter than one second can fall between two
sampled frames, so the hand counts slightly under-count the fastest passages.

---

## 2. Rhythm

Shots per minute, counted by eye:

| reference | sampled minutes | shots/min | mean shot |
|---|---|---|---|
| LEMMiNO | 3 | **3.7** (range 1–7) | 16.2s |
| Barely Sociable | 2 | **9.5** (range 8–11) | 6.3s |
| Fall of Civilizations | 3 | **8.7** (range 4–14) | 6.9s |
| **run #1, ours** | all 20, exact from the EDL | **8.6** (range 8–10) | **6.6s** |

Our average sits inside the reference range. That is not the finding.

The finding is the **range**. Every reference swings by a factor of three to
seven within a single film — LEMMiNO 1 to 7, Fall of Civilizations 4 to 14.
Run #1 swings from 8 to 10, and 181 of its 182 shots are between 5 and 8
seconds long:

```
run #1 shot-length histogram        a reference, for comparison (Cicada, detected)
  5–8s   ███████████████████ 181      0–1s   █████████
  8–12s  ▌ 1                          1–2s   ████
  everything else            0        2–3s   ▌
                                      3–5s   ██
                                      5–8s   ████████
                                      8–12s  ███
                                      12–20s ████
                                      20–30s ██
                                      30–60s ███
                                      60s+   ██████
```

Run #1's p10 is 5.89s and its p90 is 7.47s. Eighty per cent of the film is
inside a 1.6-second band. The playbook already forbids this in words — *"Cut on
meaning, never on a fixed interval"* — and the film does it anyway, because the
plan sets one `target_hold_seconds` band for every slot regardless of what the
narration is doing. A rule that no stage implements is not a rule.

What the references spend their range on, from the sampled minutes:

- **Long holds carry the biggest moments.** A 24-second comet graphic
  (Apocalypse m6), a 40-second single orbit around a ziggurat render
  (Sumerians, final window m12), a minute-long scrolling document (Cicada m11).
  None of these is a slideshow; each is one shot with internal motion.
- **Bursts carry lists and openings.** Fourteen shots in the Sumerians' title
  minute, eleven in a Barely Sociable evidence minute.
- **The slow channel is the biggest one.** LEMMiNO, at 3.7 shots a minute, has
  five times the audience of the other two.

---

## 3. Air — where the narration stops

This is the sharpest difference, and it was not on the brief's list.

| reference | narration coverage | gaps ≥ 0.6s | longest gap |
|---|---|---|---|
| Barely Sociable — Book | 65.9% | 223 | 114.8s |
| Barely Sociable — Antarctica | 63.2% | 183 | 33.8s |
| LEMMiNO — Apocalypse | 73.9%\* | 111 | 30.5s |
| LEMMiNO — Cicada | 84.6%\* | 25 | 28.0s |
| Fall of Civilizations — opening | 95.0%\* | 69 | 24.3s |
| Fall of Civilizations — closing | 97.3%\* | 12 | 7.8s |
| **run #1, ours** | **99.4%** | **11** | **2.8s** |

\* measured from a hand-written subtitle track, whose cues hold a line on screen
through a pause; those four coverage figures are upper bounds and their gap
counts are lower bounds. The two Barely Sociable rows are measured from word
onsets inside an automatic track and are exact to a word.

Run #1 has **thirteen seconds** of air in twenty minutes, and never stops
talking for longer than 2.8 seconds. Measured a second way — acoustically, off
the delivered narration track rather than off the captions — it holds 15.4
seconds in gaps of 1.5s or longer, across 7 gaps, the longest 2.25s. Two
instruments, the same answer. Even Fall of Civilizations, the most
wall-to-wall narrated reference, leaves twice as much. Barely Sociable leaves
five to six minutes.

This is the mechanism behind two separate problems. A reveal cannot land if the
voice is already into the next sentence, and the music has nowhere to come up.

---

## 4. Music against narration

| reference | bed, measured in the gaps | mix under narration | bed sits below |
|---|---|---|---|
| LEMMiNO — Cicada | −23.8 dBFS | −19.5 | **4.3 dB** |
| Barely Sociable — Book | −25.4 | −20.3 | 5.1 dB |
| LEMMiNO — Apocalypse | −29.1 | −20.7 | 8.4 dB |
| Fall of Civilizations — closing | −41.7 | −27.8 | 13.9 dB |
| Fall of Civilizations — opening | −42.8 | −28.0 | 14.7 dB |
| Barely Sociable — Antarctica | −42.4 | −27.0 | 15.5 dB |
| **our playbook** | −26 LUFS in gaps | −16 LUFS narration | **20 dB** under speech (−36) |

Two readings, and they disagree about the bed:

- Every reference runs its bed **closer to the voice than we do** — 4 to 15.5 dB,
  against our 20. The two measurements are not on the same scale (short-time
  RMS against LUFS) so this is not a number to copy, but a 5–16 dB gap in the
  same direction across six films is a signal, not scale noise.
- The **rise** amounts in the playbook are already right. Every reference lifts
  its bed in the gaps, by 3 to 27 dB, several times per film: LEMMiNO eight
  rises, Barely Sociable twelve to sixteen, Fall of Civilizations two to three.
  Our playbook asks for +10 dB in gaps over 1.5s and +14 dB at act boundaries,
  which sits squarely inside that.

So the music plan is not wrong — it has nowhere to happen. With 13 seconds of
air and no gap longer than 2.8s, a rule written for gaps "longer than 1.5s"
fires almost never.

Per the standing rule on this project, **no music level changes on the strength
of a measurement.** The bed level is an ear decision and the recommendation
below is a proposal for an A/B audition, not a change.

---

## 5. Title and thumbnail conventions

Titles, as published:

| | chars | words | shape |
|---|---|---|---|
| Cicada 3301: An Internet Mystery | 32 | 5 | noun phrase + colon subtitle |
| Consumed by the Apocalypse | 26 | 4 | bare noun phrase |
| The Book Tied To 75,000 Disappearances | 38 | 6 | definite article + a hook claim |
| The Dark Side Of Antarctica | 27 | 5 | definite article + place |
| 8. The Sumerians - Fall of the First Cities | 43 | 9 | episode number + series + dash subtitle |
| **ours** — They Said It Couldn't Be Built — The Impossible Stones | 62 | 11 | **sentence + dash subtitle** |

26–43 characters, 4–9 words. No question marks, no second person, no numerals
except inside a claim ("75,000"), no year. Ours is half as long again as the
longest of them.

Thumbnails — all six are 1280×720, and read by eye:

- **Cicada**: one white line-drawn insect centred on near-black, title set
  *behind* the subject in thin red. Two colours.
- **The Book**: one wireframe book on a dark binary field, red/cyan chromatic
  split, **no text at all**.
- **The Sumerians**: one wide photograph of the ziggurat of Ur, desaturated
  warm, three lines of white sans caps stacked lower-left, descending in size.
- None of the six has: a face, an arrow, a circled element, outlined or
  stroked text, or more than two accent colours. Every one has a single
  subject.

Also measured, not asked for: LEMMiNO and Barely Sociable publish at **60fps**;
Fall of Civilizations and run #1 at 30. Chapter counts run 0–15 (ours: 6).

---

## 6. On-screen text density

Tesseract in sparse-text mode, one frame per second, confident words only.

| reference | seconds with any text | with 3+ words | mean area when present |
|---|---|---|---|
| LEMMiNO — Cicada | 70.5% | 54.5% | 4.3% |
| LEMMiNO — Apocalypse | 66.2% | 46.7% | 3.1% |
| Barely Sociable — Book | 66.4% | 56.1% | 7.7% |
| Barely Sociable — Antarctica | 70.4% | 62.1% | 11.5% |
| FoC — opening | 43.1% | 8.2% | 1.3% |
| FoC — closing | 50.1% | 18.7% | 1.3% |

Two registers, cleanly separated. The two mystery channels keep text on screen
about two-thirds of the time, and half the film carries a full phrase: these
are films built on documents, screenshots, headlines and annotated evidence,
and the text *is* the evidence. Fall of Civilizations is the opposite — text
appears for chapter furniture and quotations and almost never as three or more
words, because its evidence is spoken and its pictures are places.

Our register is the second one, and run #1 is closer to neither: it burns
word-level captions for the whole film, so text is on screen for 99.4% of the
runtime, at a size and position that never changes. That is not a text density,
it is a subtitle track rendered into the picture — which is what §8 of the
brief's step 18 removes.

OCR cannot tell a burnt-in caption from a title card, so these figures count
both. For the two Barely Sociable rows the larger mean area is real: its
headline cards are full-frame.

## 7. Graphics / archive / footage ratio

CLIP zero-shot on one frame per shot, crossed with motion measured over a
quarter second in the middle of the shot. A shot classified as footage but not
moving is a photograph held on screen, and is counted as archive.

| reference | graphics | archive | footage | moving shots |
|---|---|---|---|---|
| LEMMiNO — Cicada | 61.0% | 17.1% | 22.0% | 58.5% |
| LEMMiNO — Apocalypse | 52.5% | 7.5% | 40.0% | 100% |
| Barely Sociable — Book | 61.9% | 36.5% | 1.6% | 60.3% |
| Barely Sociable — Antarctica | 41.2% | 52.9% | 5.9% | 38.2% |
| FoC — opening | 7.6% | 35.1% | 57.3% | 68.1% |
| FoC — closing | 5.5% | 30.8% | 63.7% | 78.0% |
| **ours, planned** | 30–40% | 40–45% (stills) | 15–25% | — |

The two channels in our register are **graphics-led**: a little over half of
every film is authored — diagrams, maps, text cards, document reveals — with
archive stills carrying most of the rest and almost no live footage at all.
Barely Sociable's Book film is 1.6% footage. Fall of Civilizations inverts it
completely, because it can afford commissioned art and location filming.

Run #1's amended mix (30–40% graphics, 40–45% stills, 15–25% footage) is
already close to the LEMMiNO/Barely Sociable shape, and the direction of the
remaining gap is toward *more* authored graphics rather than more footage. The
2026-10-18 amendment that cut the footage target from 55–75% to 15–25%, made
because the keyless archives hold stills rather than film, turns out to match
what the comparable channels actually do.

Caveats: CLIP's buckets are coarse, and the shot counts come from the detector
described in §1, so the per-reference *shot counts* carry its error even though
the ratios are stable across it. LEMMiNO's 100% moving figure on Apocalypse is
real — that film is almost entirely animated graphics.

---

## 8. Derived targets

These are proposals for the playbook, in the form the planner and validator
can read. They follow §2–§4 and are expressed as ranges because the underlying
counts are a sample of eight minutes, not a census.

### 8.1 Cuts per minute, by beat type

The point is the spread, not the mean. A film that holds every target below at
the right moments lands near 7–9 cuts a minute overall — close to run #1's
average — while looking nothing like it.

| beat | target shot length | cuts/min inside that passage | evidence |
|---|---|---|---|
| **reveal** | 12–25s, one shot | 2–4 | Apocalypse's 24s comet; Sumerians' 40s orbit; Cicada's minute-long document |
| **exposition** | 6–10s | 6–9 | the ordinary run of all three channels |
| **landing** | 4–8s, and **no cut during the silence** | 0–2 | every reference holds picture through the pause |
| **transition** | 1.5–3.5s for 8–15s of runtime | 15–25 momentarily | Sumerians' title minute (14 shots), Barely Sociable's evidence minute (11) |

Hold caps become beat-aware. The current flat ceiling of 8 seconds is what
produced the 5–8s spike, and it is the single change that most affects how
run #2 reads.

### 8.2 Landing-line hold

- After a landing line: **1.2–2.5s of silence**, picture held, no cut.
- Once per act, on the act's own climax: **3–5s**.
- Film-wide air target: **8–15% of runtime with no narration** (references
  3–37%; run #1 0.6%). For our register, the LEMMiNO/FoC end of that band.
- At least one gap ≥1.5s every two minutes, and at least one gap ≥4s per act.

### 8.3 Music rise points

- A rise may only begin inside a gap of **≥1.5s** — unchanged, and now
  reachable.
- Gap rise **+8 to +12 dB** over the under-speech bed; act boundary **+12 to
  +15 dB**. The playbook's existing +10 / +14 both sit inside the measured
  range and do not need to move.
- Target **6–10 rises across the film** (references: 2–16; the two LEMMiNO
  films, closest to our register, 8 and 15).
- A rise lands *into* the gap, not on the last word before it.

### 8.4 One recommendation that is an ear decision, not a measurement

Every reference runs its bed nearer the voice than our −36 LUFS. The proposal
is to audition **−30 and −28 LUFS under speech** against the current −36, on a
real act with the approved beds, and let the owner choose by ear as before. No
level moves until that happens.

### 8.5 Title, for run #2

Hold the published title to **30–45 characters** and **5–8 words**. Run #1's
62-character two-part title is longer than any reference's.

---

## 9. What this report does not establish

- **Eight minutes of ground truth** across six films is a small sample. The
  per-beat numbers in §8.1 are the right order of magnitude and the right
  *shape*; they are not precise to ±1 cut/min.
- The four hand-written-subtitle references have **upper-bound** narration
  coverage. The gap between run #1 and the references is far larger than that
  bias, but the exact figures for those four are soft.
- Bed-against-voice in §4 compares short-time RMS to the playbook's LUFS
  targets. Direction is sound; the absolute decibel difference is not.
- Nothing here measures **why** a reference holds a shot for 40 seconds. The
  targets say when to hold, not what makes a shot worth holding.

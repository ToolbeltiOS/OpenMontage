# Step 15 — taste audit

For each judgement the film's quality depended on: does a skill state
a criterion you could fail, does a gate measure it, or neither?

Run #1 is the test data. Every defect below is a taste failure that
passed the pipeline end to end — not a bug, a decision nobody made.

**Every one of the ten is measured by a gate.** What the skills say about them is weaker than that, and the honest count is the read one, not the matched one:

- the matcher finds a criterion for **10 of 10**;
- reading them, **10 really state the rule**, 0 mention the subject in a rule about something else, and 0 state nothing.

A keyword matcher cannot tell a rule ABOUT a subject from a rule that
merely contains the word. It is kept because it enumerates and quotes;
the quotes are the evidence and take a minute to check.

**Where this started.** Before this audit the reading was 5 of 10: the
cutting-rate curve and the source-cut rule were stated nowhere at all, and
four more — the camera move, the air budget, the bed level and the licence
families — were enforced by gates while the skills only mentioned the
subject. An agent reading the skills would have discovered those four rules
by failing them. All six were written into the skills on 2026-10-21 and the
quotes below are the result.

| judgement | what run #1 did | stated in | measured by |
|---|---|---|---|
| how long a shot holds | 181 of 182 shots between 5 and 8 seconds | `edit-director.md` | `rhythm` |
| how the cutting rate moves across the film | 8-10 cuts every minute, end to end | `edit-director.md` | `rhythm` |
| which way the camera moves, and whether it should | one push, 182 times | `scene-director.md` | `camera_intent` |
| where the film is allowed to be silent | 13 seconds of air in 20 minutes; longest gap 2.8s | `script-director.md` | `script_beats` |
| whether picture and sound cut together | they always did, 182 times | `edit-director.md` | `edit_leads` |
| how loud the music sits under the voice | 20 dB under; the references run 4-15.5 | `edit-director.md` | `music_rise` |
| whether the frame is ever still | authored graphics frozen for 90-95% of each hold | `scene-director.md` | `frame_motion` |
| whether text on screen is readable and sparing | burnt-in captions for 99.4% of the runtime | `compose-director.md` | `captions` |
| whether an asset may be used at all | no licence filter at fetch time | `asset-director.md` | `corpus_builder` |
| whether a cut lands on a cut the source already had | never checked | `edit-director.md` | `source_cuts` |

## What the skills actually say, and whether it is the rule

### how long a shot holds — **states it**

`edit-director.md`: "- **Honour the cadence ceiling.** The playbook's maximum hold is hard."

The cadence ceiling, stated as hard.

### how the cutting rate moves across the film — **states it**

`edit-director.md`: "- **Shape the cutting rate across the film, not just within a shot.** The playbook names an envelope for cuts per minute and a minimum spread, and a flat curve fails the "

Added 2026-10-21 after this audit found it missing.

### which way the camera moves, and whether it should — **states it**

`scene-director.md`: "- **`still`** — a photograph or scan. **Capped by the playbook** (typically 20%). Every still must name its motion treatment — a parallax/2.5D push, a slow drift across a"

Stated 2026-10-21: the move comes from the beat and the register, a run of drifts keeps one direction, one ramp per act, and a push into a dense asset becomes a lock.

### where the film is allowed to be silent — **states it**

`script-director.md`: "Run #1's `pause_policy` asked for "a full beat of silence after each verdict sentence". The delivered film held thirteen seconds of silence in twenty minutes and never st"

Stated 2026-10-21: air is marked in the script, the total lands between 8% and 15% of runtime, and the word budget shrinks to pay for it.

### whether picture and sound cut together — **states it**

`edit-director.md`: "- **down to −10 frames** at an exposition cut — the picture arrives before the sentence that explains it (an L-cut), and only on roughly every third exposition cut, becau"

The J/L budget, stated with the frame counts.

### how loud the music sits under the voice — **states it**

`edit-director.md`: "Never write a music level into the EDL by hand. `audio.music_under_speech_lufs` in the playbook is the decision — **−30 LUFS under speech**, chosen by ear on the act 2 de"

Stated 2026-10-21: the level is the playbook's -30 LUFS and is never written into the EDL by hand.

### whether the frame is ever still — **states it**

`scene-director.md`: "If risk is not low, fix the plan here. Do not pass a slideshow downstream with a note saying it is a slideshow — the edit stage cannot rescue it."

Do not pass a slideshow downstream.

### whether text on screen is readable and sparing — **states it**

`compose-director.md`: "Captions ship as a **sidecar SRT**, uploaded with `captions.insert`. Burn-in is off by default and must never be switched on without a reason that names the context — a s"

Stated 2026-10-21: a sidecar SRT, burn-in off by default and layout-aware when on.

### whether an asset may be used at all — **states it**

`asset-director.md`: "**an unknown licence is not permission**. A substring check for "CC BY" accepts every NC and ND variant, which is why `tools/video/stock_sources/licences.py` exists and w"

Stated 2026-10-21: four families only, NC and ND refused, and an unknown licence is not permission.

### whether a cut lands on a cut the source already had — **states it**

`edit-director.md`: "- **Never land a boundary on a cut the source already had.** A clip is rarely one take. Cutting away twelve frames or less from the source's own cut gives the viewer two "

Added 2026-10-21 after this audit found it missing.


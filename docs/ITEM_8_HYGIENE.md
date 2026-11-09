# Measurements that do not measure what they are named after

Collected during merge week for **item 8**. Queued deliberately, not done:
both were found while settling the one-shot levels at the `asset-library`
merge, and neither is a reason to hold a merge.

Item 8 started as "`additionalProperties` back to strict once buildability
enumerates props per component" and `MERGE_ASSET_LIBRARY.md` section 0
answered that part: strict came from closing the cut, so that task became
verification rather than construction. What is left under the number is
hygiene of this shape — a reading that is trusted, named after one thing,
and taken from another.

---

## 1. The SFX gate cannot see a riser's level

`lib/verify_sfx_level.py` sites a riser's measurement **0.6 s into a 2.7 s
ramp-in**, where the riser is roughly 20 dB below its own peak. The 400 ms
window there is effectively ambience and room tone, so the figure the gate
reports for a riser is not a measurement of the riser.

**Measured 2026-11-09**, two full mixes of king-tut that differ only in
`riser_peak`, −12 against −14:

| | riser@36.31 placed at | gate's `design_lufs` | gate's `excess_db` |
|---|---|---|---|
| `riser_peak: -12` | −52.0 dB | −45.2 | −6.6 |
| `riser_peak: -14` | −54.0 dB | −45.2 | −6.6 |

`sound_design.build`'s own placement report shows the 2 dB landing. Every
riser row in both `mix_report.json` files is **identical to the decimal**.
The stings and impacts are sited sensibly and did move (sting@51.92
−34.3 → −36.0), so this is specific to risers and to the ramp.

**The fix:** site it at the riser's peak window — the last 0.5 s before the
hit — because that is where a riser is loud and where "does it sit under the
bed" is a real question. A riser ends ON the word it leads to
(`sound_design.py`: `at = at_seconds*SR - len(a)`), so the window is the
0.5 s ending at `at_seconds`.

**The control, and it is the point of the item:** a 2 dB change to
`riser_peak` must move the reported reading by about 2 dB. A gate whose
number does not move when the thing it names moves is the same defect as a
gate with no consumer — it is just harder to see, because it prints a
plausible figure. This project has now found three gates that proved an
intention while nothing checked the render; this is the first one that
checked the render and read the wrong part of it.

**Not to be done quietly:** the −6.6 dB figure appears in delivered mix
reports for four films. Changing where it is measured changes what those
numbers meant, so the fix should say so in the report rather than silently
restating history.

---

## 2. A mix report cannot reproduce its own mix

`renders/mix_report.json` records each span's bed as a **bare filename**:

```json
{"name": "open_act1", "track": "bed_cinematic_quiet.wav", "start": 0.0, "end": 371.39}
```

`lib/music_brightness.py` resolves a span's `track` against the **current
working directory**, and the paths that worked during the real run came from
the music EDL, which is gitignored — see
`project_openmontage_doc`'s note that the by-ear selection is not in git. So
the report names the tracks without being able to find them.

**Measured 2026-11-09:** re-mixing king-tut from its own `mix_report.json`
spans died immediately with

```
subprocess.CalledProcessError: Command '['ffmpeg', ..., 'bed_cinematic_quiet.wav', ...]'
returned non-zero exit status 254
```

The three beds were in `projects/king-tut/assets/music/candidates/trimmed/`
all along. Resolving them there reproduced both mixes.

**The fix:** record repo-relative paths in the report. The report is the
authority for what the mix was made of — `scripts/export_excerpts.py` says
so in as many words — and an authority that cannot be followed back to the
files is a record of names, not of inputs.

**Worth deciding at the same time:** whether the EDL's selection belongs in
git in some form. The gitignore keeps the audio out, which is right; it also
keeps out the ONE fact that cannot be recovered, which is which bed was
chosen for which span and why. The report is where that fact should live,
and repo-relative paths are most of the way there.

---

## Not in this file

`reports/film_delivery_final.md` is a per-film report at a per-film-agnostic
path, which is how king-tut's delivery record came within one fast-forward of
being overwritten by noah's (see commit "The Nov 6 run's own output, which
only the runner worktree had"). That one is not a measurement problem and is
bigger than hygiene: it touches `render_film.py`'s report naming and every
reader of it.

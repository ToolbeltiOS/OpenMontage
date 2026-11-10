# Measurements that do not measure what they are named after

Collected during merge week for **item 8**. Queued deliberately, not done:
both were found while settling the one-shot levels at the `asset-library`
merge, and neither is a reason to hold a merge.

A third item was queued here and then **done immediately instead**, because
it was not a measurement problem: `post_pending_credits.py` posted the whole
credits block as one comment, and that is the path every scheduled film's
credits now take. See the commit "The backup credits path could not carry a
big bank either".

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

**The four delivered reports are NOT to be rewritten.** Ruled 2026-11-09.
The −6.6 dB riser figures in easter-island's, they-said-it's, noah's and
king-tut's mix reports stay exactly as they are: they are what the gate
measured on the day, and a report edited after the fact is no longer a
record of its run. What those numbers measured — ambience and room tone in
the ramp-in, not the riser — is written down here, which is where the
correction belongs.

Instead the fixed gate **adds a line to NEW reports**: `measurement window
changed on <date>`, naming the riser window and why. A reader comparing a
new report against an old one then has the one fact they need, in the new
report, without either report having been altered to agree with the other.

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

**And track the music EDL's JSON in git.** Ruled 2026-11-09, both halves:
repo-relative bed paths in `mix_report.json`, AND the EDL itself under
version control. The audio stays ignored — a bed is tens of megabytes and
regenerable from the candidates — but WHICH BED FOR WHICH SPAN IS A
DECISION, made by ear, and decisions are what this repo keeps. It is the one
fact in the mix that cannot be recovered from anything else: the candidates
are all still on disk, and nothing says which three were chosen or why.

The existing rule is the right shape to copy. `.gitignore` already ignores
`projects/**` and then un-ignores the artifacts that are decisions —
`listing.json` because it is the published record, `script.json` and
`derived_assets.json` because nine tests read a published film's own
provenance. The EDL belongs in that list for the same reason and under the
same `!projects/*/artifacts/` pattern.

---

## Not in this file

`reports/film_delivery_final.md` is a per-film report at a per-film-agnostic
path, which is how king-tut's delivery record came within one fast-forward of
being overwritten by noah's (see commit "The Nov 6 run's own output, which
only the runner worktree had"). That one is not a measurement problem and is
bigger than hygiene: it touches `render_film.py`'s report naming and every
reader of it.

---

## Done 2026-11-10, with two corrections to this file

### Item 1 was already fixed, and the prescribed fix was wrong

The defect — "a 2 dB change to `riser_peak` moves the reported reading by
0.0 dB" — **was resolved by the stems work** that landed with the
asset-library merge, not by the window change prescribed above. An event's
level now comes from its own stem, so `argmax` cannot find the ambience
instead of the riser. `tests/lib/test_sfx_riser_window.py` asserts it: a
2 dB change moves the reading 2 dB, a 6 dB change moves it 6, and the
**counter-control** measures the same audio the old way and shows it not
moving at all and reading 10 dB too loud.

**The prescribed fix would have broken something.** "Site it at the riser's
peak window — the last 0.5 s before the hit" was written before the stems
fix. Narrowing the window narrows the **bed reference** too, and
`sound_design.build` places an element against the bed's loudest window over
the element's OWN extent. Gate and placement would then measure different
instants, `excess_db` would stop equalling the playbook offset, and that is
precisely the bug that once made the layer refuse its own table (see
`sound_design.bed_reference`).

What was actually wrong with the window was smaller and in the other
direction: it ran to `at_seconds + 0.3`, which is 0.3 s **past** the hit, so
the gate could take its bed reference from music the placement never saw.
The fix is that **when a stem is present the bed reference spans the stem**,
which makes the two identical by construction rather than by coincidence. A
test places a bed spike 0.3 s after the hit — inside the old window, outside
the stem, and clear of the 200 ms a 400 ms window straddles — and asserts
the fixed gate does not see it while the old path does.

New reports carry `measurement_window_changed`. The four delivered reports
are untouched, and a test asserts they contain no such key.

### Item 2: the EDL was already un-ignored

"the music EDL, which is gitignored" is **stale**.
`!projects/*/artifacts/edit_decisions.json` has been in `.gitignore` since
`59c42e9` "Track the decision records; keep the bytes out", and the bed
selection lives in that file as `music.beds`. The rule this file asked for
already existed.

What is actually missing is narrower, and measured 2026-11-10:

| film | EDL on disk | in git |
| --- | --- | --- |
| easter-island | yes | **yes** |
| they-said-it-couldnt-be-built | yes | **yes** |
| king-tut | runner worktree only | **yes, normalised 2026-11-10** |
| noah | **nowhere** | no, and **unrecoverable** |

### king-tut: committed, paths normalised, decisions untouched

Ruled by the owner 2026-11-10: *the beds chosen are the decision, the path
spelling isn't, and a worktree-absolute path in shared history is worse than
a normalised copy.*

**There were seventy such paths, not three.** The three bed `path` fields
plus sixty-seven `cuts[].source`, `.image` and `.backgroundSrc` entries, all
carrying the same `/Users/mac/Developer/wak3up-docs/runner/` prefix.
Normalising the three beds and committing sixty-seven worktree-absolute
image paths would have committed the thing the ruling objects to, so the
rule was applied to all seventy.

Only the prefix moved. The normalisation was verified by putting the prefix
back and comparing the result to the original file key for key and value for
value — it round-trips exactly — and
`tests/lib/test_repo_paths.py` asserts the bed names, bed tracks, the three
rejections with their reasons, and the cut count are all unchanged, with no
absolute path and no worktree name left anywhere in the file.

All seventy resolve to a real file in the worktree that holds the assets.
That is what `lib/repo_paths.resolve` is for, and it is wired into
`build_render_props` for cut sources and bed paths as a **fallback only**: it
rewrites a relative path that does not already resolve and leaves everything
else alone, so it can repair a broken path and cannot change a film that
already renders.

### noah: the bed selection is unrecoverable

Recorded 2026-11-10 on the owner's ruling that there is nothing to do.

noah's `edit_decisions.json` **exists on no disk here** — not in the dev
worktree, not in the runner worktree. Its published film carries the mix, so
the beds were chosen and used, but *which bed covered which span* was never
written to a file that survived, and that selection was made by ear.

It cannot be reconstructed. `renders/mix_report.json` records only the bare
basenames the old report format wrote (item 8.2 above), the music candidates
on disk are the whole pool rather than the three picks, and nothing else in
the repo states the mapping. The film can be re-watched; the decision behind
its music cannot be read back.

This is the cost the `.gitignore` rule was added to stop, one film too late.
The rule — `!projects/*/artifacts/edit_decisions.json`, since `59c42e9` —
now holds for every film after noah, and king-tut's is in git as of today.

The report half is done: `mix_audio.report_track` records a bed
repo-relative when it is inside the repo, and absolute **and flagged** when
it is not — easter-island's and they-said-it's beds come from
`/Users/mac/wak3up/assets/ambient_sources/`, so those two films cannot be
re-mixed from a clone however the path is written, and the flag says so.
`music_brightness.resolve` resolves a repo-relative path against the repo
root instead of the working directory, which was the reader's half of the
same defect.

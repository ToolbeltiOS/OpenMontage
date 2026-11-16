#!/usr/bin/env python3
"""Measure a music library against the playbook's bed criteria.

The playbook stopped choosing beds by mood word after run #1 put tunes under
the narration. It states three properties a track either has or does not, and
all three are measurable before anyone listens:

  melodic_movement        frame-to-frame pitch-class distance. A held chord
                          barely moves; a tune does. Prefer < 0.11.
  build_db                p95 - p25 of the loudness envelope across the track.
                          Prefer < 5 dB.
  rhythmic_periodicity    autocorrelation peak of the onset envelope over
                          50-200 BPM. Lower is better.

What this CANNOT do is certify "no melody" — the playbook says so itself, and
asks for a 20-second audition of the shortlist, EQ'd and levelled as it will
sit in the mix, before committing. This ranks candidates for that audition; it
does not replace it.

    .venv/bin/python scripts/measure_music.py --dir "$MUSIC_LIBRARY_DIR" \
        --out projects/<id>/artifacts/music_candidates.json
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
from pathlib import Path

import librosa
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

SR = 22050

#: The span a bed is screened against when nothing says otherwise. A
#: twenty-minute film runs two spans of roughly this length — film #5's were
#: 609.7s and 619.1s — and the span is what decides whether a bed has to
#: loop, which is where holes come from.
DEFAULT_SPAN_SECONDS = 600.0


def digest(path: str) -> str:
    """The file's bytes, for telling two names for one track apart.

    MEASURED 2026-11-15: `bed_ambient_pad` and `bed_sustained_tone` are the
    SAME FILE. Both projects carry both names, at every stage — the source
    mp3s share one hash, the trimmed wavs share another, the 48k screening
    copies a third. So the audition screened one track twice, scored it
    twice, and offered it twice in a shortlist of six.
    """
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def unique(paths: list[str]) -> tuple[list[str], list[dict]]:
    """One path per distinct file, and what was folded into what.

    The kept name is the alphabetically first, so the choice does not depend
    on directory order.
    """
    by_hash: dict[str, list[str]] = {}
    for path in sorted(paths):
        by_hash.setdefault(digest(path), []).append(path)
    kept, folded = [], []
    for sha, group in by_hash.items():
        kept.append(group[0])
        for other in group[1:]:
            folded.append({"track": os.path.basename(other),
                           "same_file_as": os.path.basename(group[0]),
                           "sha256": sha[:16]})
    return sorted(kept), folded


def measure(path: str) -> dict:
    y, sr = librosa.load(path, sr=SR, mono=True)
    seconds = len(y) / sr

    # ── melodic movement ────────────────────────────────────────────────
    # Mean L1 distance between consecutive normalised chroma frames. A
    # sustained pad holds its pitch classes; a melody moves them.
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    norm = chroma / (np.linalg.norm(chroma, ord=1, axis=0, keepdims=True) + 1e-9)
    movement = float(np.mean(np.abs(np.diff(norm, axis=1)).sum(axis=0)) / 2.0)

    # ── build ───────────────────────────────────────────────────────────
    # Spread of the short-term loudness envelope. A track that swells has a
    # wide spread; elevator-quiet has a narrow one.
    rms = librosa.feature.rms(y=y, frame_length=4096, hop_length=2048)[0]
    db = librosa.amplitude_to_db(rms + 1e-9)
    build_db = float(np.percentile(db, 95) - np.percentile(db, 25))

    # ── rhythm ──────────────────────────────────────────────────────────
    # Peak of the onset envelope's autocorrelation inside 50-200 BPM. A pad
    # has no periodic onsets; a percussion loop has a sharp one.
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    hop = 512
    ac = librosa.autocorrelate(onset - onset.mean(), max_size=len(onset))
    ac = ac / (ac[0] + 1e-9)
    frames_per_s = sr / hop
    lo = int(frames_per_s * 60 / 200)      # 200 BPM
    hi = int(frames_per_s * 60 / 50)       # 50 BPM
    window = ac[max(lo, 1):max(hi, 2)]
    periodicity = float(window.max()) if len(window) else 0.0

    return {
        "track": os.path.basename(path),
        "path": path,
        "seconds": round(seconds, 1),
        "melodic_movement": round(movement, 4),
        "build_db": round(build_db, 2),
        "rhythmic_periodicity": round(periodicity, 4),
    }


def verdict(m: dict) -> dict:
    """The playbook's preferences, applied as a score rather than a gate.

    They are stated as "prefer", not as thresholds, and a library that fails
    all three still has a least-bad track in it — so this ranks and records
    which preferences each candidate misses.
    """
    misses = []
    if m["melodic_movement"] >= 0.11:
        misses.append(f"melodic_movement {m['melodic_movement']} >= 0.11")
    if m["build_db"] >= 5.0:
        misses.append(f"build_db {m['build_db']} >= 5")
    if m["rhythmic_periodicity"] >= 0.25:
        misses.append(f"rhythmic_periodicity {m['rhythmic_periodicity']} >= 0.25")
    # Normalised so the three criteria carry comparable weight.
    score = (m["melodic_movement"] / 0.11
             + m["build_db"] / 5.0
             + m["rhythmic_periodicity"] / 0.25)
    return {**m, "misses": misses, "score": round(score, 3),
            "meets_all": not misses}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None,
                    help="the music library (default: the shared one, "
                         "lib/shared_state.music_dir())")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-seconds", type=float, default=60.0,
                    help="a bed shorter than this loops too often to be a span")
    ap.add_argument("--span-seconds", type=float, default=DEFAULT_SPAN_SECONDS,
                    help="the span each shortlisted bed is built against to "
                         "measure its hole")
    ap.add_argument("--no-hole", action="store_true",
                    help="skip the hole measurement (it builds and conditions "
                         "a real span per candidate, which is not quick)")
    args = ap.parse_args()

    from shared_state import music_dir
    library = args.dir or str(music_dir())
    #: An ingested library carries the manifest ingest_bed.py writes. Only
    #: there is a hole over the ceiling a refusal rather than a candidate
    #: nobody has trimmed yet.
    ingested = os.path.exists(os.path.join(library, "MANIFEST.json"))
    print(f"library: {library}"
          + ("  (ingested — the hole is a gate here)" if ingested
             else "  (not ingested — the hole is reported, not enforced)"),
          flush=True)

    found = sorted(
        p for ext in ("mp3", "wav", "m4a", "flac", "ogg")
        for p in glob.glob(os.path.join(library, f"*.{ext}"))
    )
    files, folded = unique(found)
    print(f"{len(found)} file(s) in {library}", flush=True)
    for dupe in folded:
        print(f"  = {dupe['track']} is the same file as "
              f"{dupe['same_file_as']} — screened once", flush=True)
    if folded:
        print(f"{len(files)} distinct track(s) to measure", flush=True)

    rows = []
    for i, path in enumerate(files, 1):
        try:
            m = measure(path)
        except Exception as exc:                      # a bad file is a fact
            print(f"  [{i}/{len(files)}] {os.path.basename(path)}: "
                  f"FAILED {type(exc).__name__}: {exc}", flush=True)
            continue
        if m["seconds"] < args.min_seconds:
            print(f"  [{i}/{len(files)}] {m['track']}: {m['seconds']}s, "
                  f"too short for a bed span", flush=True)
            continue
        row = verdict(m)
        rows.append(row)
        print(f"  [{i}/{len(files)}] {row['score']:6.3f}  "
              f"mov {row['melodic_movement']:.3f}  build {row['build_db']:5.2f}  "
              f"per {row['rhythmic_periodicity']:.3f}  {row['track']}", flush=True)

    rows.sort(key=lambda r: r["score"])

    # ── THE HOLE, ON THE SPAN THE BED WILL ACTUALLY FILL ─────────────────
    #
    # The three criteria above are properties of the FILE. The mixer gates
    # on a property of the BED: `hole_db` against BED_HOLE_MAX_DB, measured
    # after the span has been built and conditioned. A bed shorter than its
    # span is looped, and looping is where holes come from — so the file can
    # be flawless on all three and still be refused after it has won the
    # audition, been EQ'd, levelled and laid under the whole narration.
    #
    # Measured here, on the shortlist only. It builds and conditions a real
    # span per candidate, so it is the expensive step and belongs AFTER the
    # cheap ones have narrowed the field — not instead of them.
    flagged = refused = 0
    if not args.no_hole:
        from mix_audio import span_hole_db

        shortlist = [r for r in rows if r["meets_all"]]
        print(f"\nthe hole each of the {len(shortlist)} shortlisted bed(s) "
              f"would have over a {args.span_seconds:.0f}s span:", flush=True)
        for r in shortlist:
            try:
                hole = span_hole_db(r["path"], args.span_seconds)
            except Exception as exc:                  # a bad file is a fact
                r["hole"] = {"error": f"{type(exc).__name__}: {exc}"}
                print(f"  {r['track']}: FAILED {type(exc).__name__}", flush=True)
                continue
            r["hole"] = hole
            # A TRUE GATE ON AN INGESTED LIBRARY, A REPORT ON ANYTHING ELSE.
            #
            # Looping a RAW candidate measures its silence, not its music.
            # Measured 2026-11-15: candidates/bed_cinematic_quiet.mp3 has
            # near-silence at its edges — median -22.81 LUFS against a
            # minimum of -69.40, a 46.59 dB hole in the FILE — and over film
            # #5's own 622.82s span it conditions out at 28.25 dB, refused.
            # The 117.6s core a hand trim found reads 4.92 dB over the same
            # span, and that is the bed the film actually used. So a refusal
            # read off a raw file would reject every bed whose source fades
            # in, which on that library is all of them.
            #
            # scripts/ingest_bed.py is now that trim, as a rule rather than
            # a hand step, and a library it has written carries a MANIFEST.
            # There, every bed is already loopable and a hole over the
            # ceiling is a real refusal. Elsewhere it is a candidate that
            # has not been ingested yet, and saying so is the useful answer.
            if hole["would_be_refused"]:
                if ingested:
                    r["meets_all"] = False
                    r["misses"] = r["misses"] + [
                        f"hole {hole['hole_db']} dB over a "
                        f"{hole['span_seconds']:.0f}s span, above the "
                        f"{hole['hole_ceiling_db']:.0f} dB the mixer allows"]
                    refused += 1
                else:
                    r["needs_ingest"] = True
                    flagged += 1
            print(f"  {hole['hole_db']:6.2f} dB  "
                  f"{'LOOPED x' + str(hole['reps']) if hole['looped'] else 'window'}"
                  f"  {r['track']}"
                  + ("   fit to be a bed" if not hole["would_be_refused"]
                     else ("   THE MIXER WOULD REFUSE THIS" if ingested
                           else "   NOT INGESTED — run scripts/ingest_bed.py "
                                "on it first")), flush=True)
        rows.sort(key=lambda r: (not r["meets_all"], r["score"]))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "library": library,
        "measured": len(rows),
        "duplicates_folded": folded,
        "span_seconds": None if args.no_hole else args.span_seconds,
        "criteria": {
            "melodic_movement": "< 0.11 preferred",
            "build_db": "< 5 dB preferred",
            "rhythmic_periodicity": "lower is better; 0.25 used as the miss line",
            "hole_db": "measured on the conditioned span the bed would "
                       "fill, not on the file. Above the mixer's ceiling "
                       "means the candidate needs trimming before it can be "
                       "a bed — it is reported, not counted as a miss, "
                       "because a raw file's fade is not the bed's hole",
        },
        "note": "Ranking for an audition, not a substitute for one. The "
                "playbook requires the shortlist to be heard as 20-second "
                "previews, EQ'd and levelled as it will sit in the mix.",
        "candidates": rows,
    }, indent=2) + "\n")

    print(f"\nmeets every criterion: "
          f"{sum(1 for r in rows if r['meets_all'])} of {len(rows)}"
          + (f", {refused} refused on the hole" if refused else "")
          + (f", {flagged} not ingested yet" if flagged else ""))
    print("top 12 by score:")
    for r in rows[:12]:
        print(f"  {r['score']:6.3f}  {r['seconds']:7.1f}s  {r['track']}"
              + ("" if r["meets_all"] else f"   misses: {'; '.join(r['misses'])}"))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

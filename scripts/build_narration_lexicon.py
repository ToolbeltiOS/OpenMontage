#!/usr/bin/env python3
"""Derive this film's pronunciation lexicon by listening to the voice.

RUN THIS AT THE SCRIPT STAGE, not at synthesis. A name the voice mangles is
a script problem with a script fix — a `pronunciation_guide` — and the
cheapest moment to find out is while the act is still being written. Found
at synthesis it is a re-render; found at delivery it is a published film
saying "shooting Cammon's priests" instead of "Tutankhamun's".

WHAT IT DOES
------------
For every proper noun in the narration that the shared lexicon does not
already cover: say it, transcribe it, and compare. A name the transcriber
writes as a spelling variant of the right sound is left alone. A name it
writes as a different word gets a respelling, taken from the script's own
`pronunciation_guide` and then VERIFIED by saying the respelling and
transcribing it again. Anything in between is reported, not guessed.

The output is `projects/<film>/artifacts/lexicon.json`, next to the script
it was derived from, and `scripts/synthesize_narration.py` applies it on top
of `assets/narration/lexicon.json`.

    .venv/bin/python scripts/build_narration_lexicon.py --project king-tut
    .venv/bin/python scripts/build_narration_lexicon.py --project king-tut --sections act1
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import narration_lexicon as NL                                     # noqa: E402
from verify_fact_coverage import BACKENDS, sentences                # noqa: E402

VOICE = "bm_george"
#: The rate the film is actually narrated at. A name probed at a different
#: speed is a name probed on different audio.
PROBE_SPEED = 0.89
HF_PYTHON = str(ROOT / ".venv" / "bin" / "python")
SHARED = ROOT / "assets" / "narration" / "lexicon.json"


def narration_text(script: dict, only: list[str]) -> list[dict]:
    out = []
    for section in script.get("sections", []):
        if only and section.get("id") not in only:
            continue
        out.append(section)
    return out


def proper_nouns(sections: list[dict], backend: str) -> list[str]:
    """Every distinct proper noun the voice will have to say."""
    detect = BACKENDS[backend]
    found: dict[str, str] = {}
    for section in sections:
        for sentence in sentences(section.get("text") or ""):
            for word in detect(sentence):
                clean = word.strip("'’,.;:!?\"")
                # a single letter or an initial is not a name to respell
                if len(clean) < 3 or not clean[:1].isalpha():
                    continue
                found.setdefault(clean.lower(), clean)
    return [found[k] for k in sorted(found)]


def guides(sections: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for section in sections:
        for guide in section.get("pronunciation_guides") or []:
            word = (guide.get("word") or "").strip()
            phonetic = (guide.get("phonetic") or "").strip()
            if word and phonetic:
                out[word] = phonetic
                out[word.lower()] = phonetic
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--sections", nargs="*", default=[])
    ap.add_argument("--backend", default="spacy",
                    help="proper-noun detector: spacy or capitalisation")
    ap.add_argument("--model", default="base.en", help="faster-whisper model")
    ap.add_argument("--out", default=None,
                    help="default: projects/<film>/artifacts/lexicon.json")
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    script = json.loads((project / "artifacts" / "script.json").read_text())
    work = project / "artifacts" / "_lexicon_probe"
    work.mkdir(parents=True, exist_ok=True)

    sections = narration_text(script, args.sections)
    if not sections:
        raise SystemExit("no sections selected")
    names = proper_nouns(sections, args.backend)
    guide_map = guides(sections)

    shared = json.loads(SHARED.read_text()) if SHARED.exists() else {"entries": []}
    already = {e["word"].lower() for e in shared.get("entries", [])}
    todo = [n for n in names if n.lower() not in already]
    skipped = [n for n in names if n.lower() in already]

    print(f"{len(names)} proper nouns, {len(skipped)} already in the shared "
          f"lexicon, {len(todo)} to probe", flush=True)

    from faster_whisper import WhisperModel
    whisper = WhisperModel(args.model, device="cpu", compute_type="int8")
    env = dict(os.environ, HYPERFRAMES_PYTHON=HF_PYTHON)
    heard_cache: dict[str, str] = {}

    def say(text: str, tag: str) -> None:
        dest = work / f"{tag}.wav"
        if not dest.exists():
            proc = subprocess.run(
                ["npx", "hyperframes", "tts", text, "--voice", VOICE,
                 "--speed", f"{PROBE_SPEED:.3f}", "--output", str(dest),
                 "--json"], cwd=ROOT, env=env, capture_output=True, text=True)
            if not dest.exists():
                raise SystemExit(f"tts failed for {tag}: "
                                 f"{proc.stdout[-300:]} {proc.stderr[-300:]}")
        segs, _ = whisper.transcribe(str(dest), language="en", beam_size=1)
        heard_cache[tag] = " ".join(s.text for s in segs).strip()
        print(f"  {tag}: {heard_cache[tag][:70]}", flush=True)

    result = NL.build(todo, guide_map, say, lambda tag: heard_cache[tag])

    problems = NL.validate(result)
    if problems:
        for p in problems:
            print(f"REFUSING: {p}", file=sys.stderr)
        return 2

    out = Path(args.out) if args.out else project / "artifacts" / "lexicon.json"
    payload = {
        "version": 1,
        "project": args.project,
        "note": ("Derived by scripts/build_narration_lexicon.py from this "
                 "film's own script, by saying each proper noun and "
                 "transcribing it. Applied on top of "
                 "assets/narration/lexicon.json at synthesis. Every value is "
                 "letters only, because both engines read hyphens, capitals "
                 "and stress marks ALOUD."),
        "shared_lexicon_covered": sorted(skipped),
        "probe_speed": PROBE_SPEED,
        "whisper_model": args.model,
        "detector": args.backend,
        "thresholds": {"clean_below": NL.CLEAN_BELOW,
                       "misheard_at": NL.MISHEARD_AT},
        "entries": result["entries"],
        "read_correctly": result["clean"],
        "uncertain": result["uncertain"],
        "unresolved": result["unresolved"],
    }
    out.write_text(json.dumps(payload, indent=1) + "\n")

    print(f"\n{out.relative_to(ROOT)}")
    print(f"  {len(result['entries'])} respelled, "
          f"{len(result['clean'])} read correctly, "
          f"{len(result['uncertain'])} uncertain, "
          f"{len(result['unresolved'])} unresolved")
    for row in result["uncertain"]:
        print(f"  UNCERTAIN {row['word']} (ratio {row['ratio']}) "
              f"heard {row['heard'][:50]!r}")
    for row in result["unresolved"]:
        print(f"  UNRESOLVED {row['word']}: {row['why']}")
    # Unresolved is a script problem the writer must act on, and a step that
    # exits 0 on it is a step nobody reads the output of.
    return 1 if result["unresolved"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

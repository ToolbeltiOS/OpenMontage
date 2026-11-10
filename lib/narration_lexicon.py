#!/usr/bin/env python3
"""Which names the voice mangles, and what to spell them as instead.

WHY A RESPELLING AND NOT A PHONEME STRING
-----------------------------------------
The obvious way to fix a mispronunciation is to hand the synthesiser
phonemes. Kokoro's own front end, misaki, has a syntax for exactly that:
`[Tutankhamun](/tuːtənˈkɑːmən/)`. IT DOES NOT WORK ON THIS PIPELINE, and
that was measured rather than assumed. `hyperframes tts` is kokoro-onnx with
an espeak phonemizer, not the kokoro/misaki python pipeline, and it has no
phoneme input at all — `--lang` selects a phonemizer language. Handed the
markdown form it said, aloud: "slash second-restress TU-length and T-Schwar,
NK letter 251". espeak's own `[[tu:t@nkA:'mu:n]]` notation is read out just
as literally.

What does work on this path is a respelling that looks like an ordinary
English word: Kokoro says "tootankahmoon" as Tutankhamun. So every value
here is LETTERS ONLY — no hyphens, no capitals, no stress marks. The first
version of this lexicon used dictionary notation ("kar-NAR-von",
"too-tan-KAH-moon") and both engines read the notation out loud mid
sentence, which lost an A/B against having no lexicon at all.

WHY THE CLASSIFIER HAS THREE ANSWERS AND NOT TWO
------------------------------------------------
"Did the transcriber hear the name correctly" cannot be decided from
orthography alone, and the attempt to do it is the trap this module exists
to avoid. A transcriber writes the sound it heard in whatever spelling it
likes: Saqqara comes back "Sakara" and haematopoietic comes back
"hematopoietic", both of them CORRECT. Meanwhile Aspergillus came back "a
spergulus", which is wrong, and differs from the name by one letter.

Measured on the king-tut evidence, no single threshold separates the two
classes: the most distant CORRECT reading (Fellowes -> "Fellows", 0.143)
scores further than the closest WRONG one (Aspergillus -> "a spergulus",
0.100). A two-way split would therefore have to either invent entries for
names that are fine or silently miss ones that are not.

So there are three answers. Below CLEAN_BELOW the name is left alone. At or
above MISHEARD_AT it gets an entry. In between it is reported as UNCERTAIN
for a person to rule on, and NOTHING IS WRITTEN. On the king-tut data that
is 7 of 9 real mishearings caught automatically, 12 of 13 correct readings
passed over automatically, and the four borderline cases handed up with
their transcripts instead of guessed at.

WHERE THE RESPELLINGS COME FROM
-------------------------------
Not from this module. It has no phonetic knowledge and will not invent any.
The script already carries `pronunciation_guides` — the script director has
asked for them on "every proper noun the voice is likely to mangle" since
long before this existed — and a guide is dictionary notation, which is
mechanically convertible to the letters-only form: "too-tan-KAH-moon"
becomes "tootankahmoon", which is the respelling that actually won.

A name that is misheard and has NO guide is reported unresolved, naming the
guide that would fix it. That is a better outcome than a generated
respelling nobody measured: "guyger" for Geiger looks right and Kokoro says
"guide your".
"""
from __future__ import annotations

import re
import unicodedata
from typing import Callable, Iterable

#: Below this, the reading is a spelling variant of the right sound.
CLEAN_BELOW = 0.10
#: At or above this, the reading is a different word.
MISHEARD_AT = 0.20

#: Spelling differences that do not change the sound. Applied longest-first
#: so "ough" is not eaten by "ou".
_CONSONANT = [("tion", "shn"), ("ough", "of"), ("augh", "af"),
              ("ph", "f"), ("gh", "g"), ("ck", "k"), ("qu", "k"),
              ("x", "ks"), ("z", "s"), ("sh", "s"), ("ch", "k"),
              ("th", "t"), ("wh", "w"), ("q", "k")]
_VOWEL = [("ae", "e"), ("oe", "e"), ("ei", "i"), ("ee", "i"),
          ("ea", "i"), ("ie", "i"), ("ou", "u"), ("oo", "u")]

CARRIER = "The name is {}."


def normalise(word: str) -> str:
    """A word reduced to what a transcriber could not have spelled otherwise.

    Vowels are KEPT. Collapsing them to one class makes Aspergillus and "a
    spergulus" identical, and that difference — gill for gul — is the whole
    mispronunciation.
    """
    word = unicodedata.normalize("NFKD", word.lower())
    word = "".join(c for c in word if c.isalpha())
    for a, b in _CONSONANT:
        word = word.replace(a, b)
    for a, b in _VOWEL:
        word = word.replace(a, b)
    word = word.replace("y", "i")
    return re.sub(r"(.)\1+", r"\1", word)


def _lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def distance_ratio(name: str, heard: str) -> float:
    """How far the best-matching part of `heard` is from `name`.

    The transcriber returns a phrase, and the name may land across two of
    its words ("a spergulus", "two Tenkamun's"), so every window of one,
    two and three words is tried and the closest wins.
    """
    target = normalise(name)
    if not target:
        return 1.0
    words = re.findall(r"[a-zA-Z']+", heard)
    windows = list(words)
    windows += [" ".join(words[i:i + 2]) for i in range(len(words) - 1)]
    windows += [" ".join(words[i:i + 3]) for i in range(len(words) - 2)]
    best = 1.0
    for window in windows or [heard]:
        other = normalise(window)
        if not other:
            continue
        best = min(best, _lev(target, other) / max(len(target), len(other)))
    return best


def classify(name: str, heard: str) -> str:
    """"clean", "uncertain" or "misheard". See the module docstring."""
    ratio = distance_ratio(name, heard)
    if ratio < CLEAN_BELOW:
        return "clean"
    if ratio >= MISHEARD_AT:
        return "misheard"
    return "uncertain"


def is_letters_only(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z]+", value or ""))


def candidates_from_guide(phonetic: str) -> list[str]:
    """A pronunciation guide, stripped of its notation.

    "too-tan-KAH-moon" -> "tootankahmoon". The hyphens are what the
    synthesiser reads as pauses and the capitals as emphasis, so taking
    them out is the whole conversion. A second candidate drops any schwa
    the guide spells "uh", which is the one notation convention that
    reliably adds a syllable Kokoro then pronounces.
    """
    base = re.sub(r"[^a-zA-Z]", "", phonetic or "").lower()
    out = [base]
    if "uh" in base:
        out.append(base.replace("uh", "a"))
    return [c for c in dict.fromkeys(out) if is_letters_only(c)]


def apply(text: str, lexicon: dict) -> str:
    """Swap each respelled name for what the voice should say.

    Whole-word and case-sensitive on the name as written, so "Gouldian" is
    not Gould. The possessive is reached because the boundary falls before
    the apostrophe, and the possessive was the worst mishearing measured.
    """
    for entry in lexicon.get("entries", []):
        if not entry.get("respelled"):
            continue
        text = re.sub(rf"\b{re.escape(entry['word'])}\b", entry["say"], text)
    return text


def merge(*lexicons: dict) -> dict:
    """Later lexicons win on a repeated name.

    The repo's lexicon is the shared baseline; a film's own lexicon,
    derived from its own script, overrides it. Both are letters-only and
    the merge does not re-check that — `load` does.
    """
    by_word: dict[str, dict] = {}
    order: list[str] = []
    for lexicon in lexicons:
        for entry in (lexicon or {}).get("entries", []):
            key = entry["word"].lower()
            if key not in by_word:
                order.append(key)
            by_word[key] = entry
    return {"entries": [by_word[k] for k in order]}


def validate(lexicon: dict) -> list[str]:
    """Every reason this lexicon would be read aloud as notation."""
    problems = []
    for entry in lexicon.get("entries", []):
        say, word = entry.get("say", ""), entry.get("word", "")
        if not entry.get("respelled"):
            continue
        if not is_letters_only(say):
            problems.append(
                f"{word!r} -> {say!r} is not letters only. Both engines read "
                f"hyphens, capitals and stress marks ALOUD.")
        if say.lower() == word.lower():
            problems.append(f"{word!r} respells to itself")
    return problems


def build(names: Iterable[str], guides: dict[str, str],
          say: Callable[[str, str], None],
          transcribe: Callable[[str], str],
          carrier: str = CARRIER) -> dict:
    """Derive a lexicon by listening to the synthesiser.

    `say(text, tag)` renders and `transcribe(tag)` returns what was heard;
    both are injected so this is testable without a model and without
    thirty seconds of audio per name.
    """
    entries, clean, uncertain, unresolved = [], [], [], []
    for name in dict.fromkeys(names):
        say(carrier.format(name), f"probe_{name}")
        heard = transcribe(f"probe_{name}")
        verdict = classify(name, heard)
        if verdict == "clean":
            clean.append({"word": name, "heard": heard})
            continue
        if verdict == "uncertain":
            uncertain.append({
                "word": name, "heard": heard,
                "ratio": round(distance_ratio(name, heard), 3),
                "why": "between the thresholds — rule on it by ear, then "
                       "add a pronunciation_guide or leave it alone"})
            continue

        guide = guides.get(name) or guides.get(name.lower())
        if not guide:
            unresolved.append({
                "word": name, "heard": heard,
                "why": f"misheard, and no pronunciation_guide to respell it "
                       f"from. Add one for {name!r} in the script's "
                       f"pronunciation_guides and re-run this step."})
            continue

        chosen = None
        tried = []
        for cand in candidates_from_guide(guide):
            say(carrier.format(cand), f"cand_{name}_{cand}")
            cand_heard = transcribe(f"cand_{name}_{cand}")
            tried.append({"say": cand, "heard": cand_heard,
                          "verdict": classify(name, cand_heard)})
            if classify(name, cand_heard) == "clean":
                chosen = cand
                break
        if chosen is None:
            unresolved.append({
                "word": name, "heard": heard, "tried": tried,
                "why": f"misheard, and no candidate from the guide "
                       f"{guide!r} read back clean. A human respelling is "
                       f"needed; do not ship a guessed one."})
            continue
        entries.append({
            "word": name, "say": chosen, "respelled": True,
            "misheard_as": heard,
            "why": f"derived from the pronunciation_guide {guide!r}",
            "verified": "carrier sentence, this film's own render"})

    return {"entries": entries, "clean": clean, "uncertain": uncertain,
            "unresolved": unresolved}

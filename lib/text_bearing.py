#!/usr/bin/env python3
"""Is this asset a document rather than a photograph?

WHY IT MATTERS, AND WHY THE EXISTING GUARD DID NOT WORK
--------------------------------------------------------
`scripts/build_25d_cuts.py` refuses a 2.5D treatment for an asset classed
`text_bearing`. Nothing has ever set that class. `lib/asset_classifier.py`
runs two CLIP contests -- scale (vast / intimate) and occupancy (dense /
empty) -- plus a luma split, and has no notion of text, so the guard matched
nothing and every document in the bank was eligible for depth.

Two are already in the film. c005 is a 1786 French chart of Easter Island;
c081 and c124 are an engraved figure captioned "EASTER ISLAND POLITICAL",
and both of those carry an authored push and pull. Estimating depth from
engraved line work gives a surface that is not there, and displacing it
bends the coastline and the lettering. On a map that is not a look, it is a
factual distortion -- the shape of the island is the content.

THE MEASURE
-----------
Tesseract at a 2400px long edge, counting words of two or more characters at
confidence 70 or better. Resolution matters more than it looks: the 1786
chart yields 5 words at 1600px and 36 at 2400, because engraved lettering is
tiny against a large plate. Measured across 47 bank images:

    36  1786 chart of the island          document
    20  engraved "EASTER ISLAND POLITICAL" document
    18  engraved plate, Pyramides de Memphis  document
     8  museum display case                PHOTOGRAPH, with label cards
     5  --
     1  --
     0  x41

The four highest are the three documents and one photograph of a museum
case whose exhibit labels are legible. That photograph is a real 3D scene
and depth suits it, so the floor goes above it rather than below.

MIN_WORDS = 14 is the midpoint of the gap between 8 and 18, AND IT RESTS ON
FOUR POSITIVES. That is a thin basis. It is the safe direction -- a document
wrongly treated as a photograph gets its coastline bent, while a photograph
wrongly treated as a document merely keeps its 2D move -- but the number
should be revisited when more documents are banked.

    python3 lib/text_bearing.py <image> [<image> ...]
"""
from __future__ import annotations

import argparse
from pathlib import Path

#: Words needed before an asset counts as a document. See THE MEASURE.
MIN_WORDS = 14

#: Long edge the page is read at. Engraved lettering disappears below this:
#: the 1786 chart reads 5 words at 1600px and 36 at 2400.
OCR_LONG_EDGE = 2400

#: Tesseract confidence a word must reach to be counted, matching
#: `lib/verify_type_lock.py` so "a legible word" means one thing here.
MIN_CONFIDENCE = 70.0

#: Shortest string that counts. Single characters are mostly noise on a
#: textured photograph.
MIN_WORD_CHARS = 2


def word_count(path: str | Path) -> int:
    """Legible words in the picture, or -1 if it cannot be read."""
    import cv2
    import pytesseract
    from PIL import Image

    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return -1
    h, w = img.shape
    scale = OCR_LONG_EDGE / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_AREA)
    data = pytesseract.image_to_data(Image.fromarray(img),
                                     output_type=pytesseract.Output.DICT)
    n = 0
    for text, conf in zip(data["text"], data["conf"]):
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            continue
        if conf >= MIN_CONFIDENCE and len(text.strip()) >= MIN_WORD_CHARS:
            n += 1
    return n


def is_text_bearing(path: str | Path) -> tuple[bool, int]:
    """Whether this is a document, and the word count behind the answer.

    An unreadable file is NOT called a document. The caller is deciding
    whether to apply a treatment, and failing to read a file is not evidence
    about what is in it -- it is a separate problem that belongs upstream.
    """
    n = word_count(path)
    if n < 0:
        return False, n
    return n >= MIN_WORDS, n


#: A derived still is named `<parent_id>_<framing>.jpg` beside its bank
#: parent. See `inherited`.
DERIVED = __import__("re").compile(r"^(wm_\d+)_[a-z]+$")


def inherited(path: str | Path) -> Path | None:
    """The bank parent of a derived crop, if this is one.

    A CROP OF A DOCUMENT IS STILL A DOCUMENT, and the word count does not
    see it. `wm_348295582_detail.jpg` is cartographic line work -- island
    outline, hatched volcanoes, place names -- and reads FOUR words, because
    OCR does not recognise letter-spaced cartographic lettering like
    "H O T U" at that size. Its parent reads 20.

    So the classification follows the derivation chain rather than being
    taken again on the crop. Any per-asset judgement about what a picture IS
    has to, because a crop keeps the nature of what it was cut from while
    losing the evidence for it.
    """
    path = Path(path)
    m = DERIVED.match(path.stem)
    if not m:
        return None
    for bank in (path.parent.parent / "bank", path.parent):
        cand = bank / f"{m.group(1)}{path.suffix}"
        if cand.exists() and cand != path:
            return cand
    return None


def is_text_bearing_asset(path: str | Path) -> tuple[bool, int, str]:
    """Document or photograph, following the derivation chain.

    Returns the verdict, the word count it rests on, and which file that
    count came from -- "self" or "parent" -- because a crop refused on its
    parent's evidence should say so.
    """
    flag, n = is_text_bearing(path)
    if flag:
        return True, n, "self"
    parent = inherited(path)
    if parent is not None:
        pflag, pn = is_text_bearing(parent)
        if pflag:
            return True, pn, f"parent {Path(parent).name}"
    return False, n, "self"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    args = ap.parse_args()
    found = 0
    for p in args.images:
        flag, n, via = is_text_bearing_asset(p)
        if n < 0 and via == "self":
            print(f"  ?          {Path(p).name:<30} unreadable")
            continue
        print(f"  {'DOCUMENT ' if flag else 'photograph'} "
              f"{Path(p).name:<30} {n} words (floor {MIN_WORDS})"
              + (f", via {via}" if via != "self" else ""))
        found += flag
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())

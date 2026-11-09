#!/usr/bin/env python3
"""What the house library is allowed to contain.

THE SAME RULE AS THE ASSET BANK, WRITTEN DOWN
----------------------------------------------
The bank accepts CC0, public domain, CC BY and CC BY-SA, and rejects
NonCommercial and NoDerivatives at fetch time. The library holds a different
kind of thing -- textures, HDRIs, glyphs, icons -- so the rule is restated
here rather than inferred, and every asset is checked against it before it
is written to disk, not after.

ATTRIBUTION IS PART OF THE LICENCE, NOT A COURTESY. CC BY and CC BY-SA
require it, so an asset under either is refused unless the manifest entry
carries an attribution string. A library that cannot say who made a glyph
cannot ship it, and finding that out at publish time is too late.

SOFTWARE LICENCES ARE ACCEPTED FOR ICON SETS. Lucide is ISC, which is a
permissive software licence rather than a content one; it permits use and
redistribution with the copyright notice kept. The notice travels in the
manifest and in the LICENCE file beside the assets.
"""
from __future__ import annotations

import re

#: Licences the library may hold, as regular expressions matched against a
#: normalised licence string. Anything not matching is refused.
#:
#: ORDER MATTERS AND SHARE-ALIKE COMES FIRST. "CC BY-SA 4.0" satisfies the
#: cc-by pattern too, so with cc-by tested first it was recorded as plain
#: CC BY. Both are allowed, so the decision was right and the RECORD was
#: wrong -- and share-alike is an obligation CC BY does not carry, which the
#: manifest is the only place anyone will look for.
ALLOWED = (
    ("cc0", r"^cc0(\s|-|$)|^creative commons zero"),
    ("public-domain", r"^public domain|^pd(\s|$)"),
    ("cc-by-sa", r"^cc[\s-]?by[\s-]?sa"),
    ("cc-by", r"^cc[\s-]?by(?![\s-]*(nc|nd|sa))"),
    ("isc", r"^isc(\s|$)"),
    ("mit", r"^mit(\s|$)"),
)

#: Refused outright, and checked FIRST. "CC BY-NC 4.0" matches the cc-by
#: pattern on a careless reading, so the refusal runs before the acceptance
#: and the acceptance pattern also excludes them.
REFUSED = {
    "noncommercial": r"\bnc\b|noncommercial|non-commercial",
    "noderivatives": r"\bnd\b|noderiv|no-deriv",
}

#: Licences that oblige us to name the author.
NEEDS_ATTRIBUTION = ("cc-by", "cc-by-sa", "isc", "mit")


def normalise(licence: str) -> str:
    return re.sub(r"\s+", " ", (licence or "").strip().lower())


def classify(licence: str) -> str | None:
    """Which allowed family this licence belongs to, or None if refused."""
    text = normalise(licence)
    if not text:
        return None
    for pattern in REFUSED.values():
        if re.search(pattern, text):
            return None
    for name, pattern in ALLOWED:
        if re.search(pattern, text):
            return name
    return None


def check(entry: dict) -> list[str]:
    """Why this manifest entry may not be stored. Empty means it may."""
    problems = []
    family = classify(entry.get("licence", ""))
    if family is None:
        problems.append(
            f"licence {entry.get('licence')!r} is not one the library may "
            f"hold: CC0, public domain, CC BY, CC BY-SA, ISC or MIT, and "
            f"never NonCommercial or NoDerivatives")
    elif family in NEEDS_ATTRIBUTION and not entry.get("attribution"):
        problems.append(
            f"licence {entry.get('licence')!r} requires attribution and the "
            f"entry carries none — the obligation is part of the licence, "
            f"not a courtesy, and discovering it at publish time is too late")
    if not entry.get("url"):
        problems.append("no source URL: provenance is not reconstructable")
    if not entry.get("provider"):
        problems.append("no provider")
    return problems


if __name__ == "__main__":
    import sys

    for arg in sys.argv[1:]:
        print(f"  {arg!r} -> {classify(arg)}")

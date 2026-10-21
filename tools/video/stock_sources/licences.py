"""What a licence string means, and whether this channel may use it.

WHY THIS IS A MODULE AND NOT A STRING COMPARISON
------------------------------------------------
The channel is monetised, so NonCommercial is not usable, and the films are
re-cut and re-graded, so NoDerivatives is not usable either. Both arrive from
APIs as free text in a dozen spellings: "CC BY-NC-SA 4.0", "Creative Commons
Attribution-NonCommercial", "cc-by-nc", "Public Domain Mark 1.0", "No Known
Copyright Restrictions", "In Copyright - Educational Use Permitted".

A substring check for "CC BY" accepts every one of the NC and ND variants,
because they all contain it. That is the failure this module exists to
prevent, and it is tested in both directions.

UNKNOWN IS NOT PERMISSION
-------------------------
An unrecognised licence string is REJECTED, not accepted. A museum API that
returns an empty rights field is telling us it does not know, and a film that
has to be taken down because an adapter guessed is a worse outcome than a
smaller asset bank. Every rejection records the string it rejected, so a
missing pattern shows up as a rejection to read rather than as silence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#: Families the playbook permits: free to use commercially, and derivable.
#:
#: The list is the brief's, verbatim, and widening it is the owner's call and
#: not an adapter author's. PIXABAY is deliberately NOT in it — see below.
PERMITTED = ("CC0", "PD", "CC-BY", "CC-BY-SA")

#: Named licences that are permissive but outside the four families above.
#:
#: The Pixabay Content License is the live case: free for commercial use, no
#: attribution required, modification allowed — functionally CC0 for this
#: channel's purposes, and not CC0. Adding it to PERMITTED would make 28
#: assets already in the bank usable again; leaving it out loses the whole
#: `elemental_texture` subject. That is a decision about what the channel will
#: stand behind, so it is written here as a switch with the measurement beside
#: it rather than taken quietly either way.
#:
#: What classifying it DOES change, regardless of the switch: a refusal now
#: says "PIXABAY", which is a licence we read and declined, instead of
#: "UNKNOWN", which claims we could not tell.
PERMITTED_EXTRA: tuple[str, ...] = ()


@dataclass(frozen=True)
class Licence:
    code: str
    commercial: bool
    derivatives: bool
    attribution: bool
    share_alike: bool
    raw: str

    @property
    def permitted(self) -> bool:
        return self.code in PERMITTED or self.code in PERMITTED_EXTRA


_UNKNOWN = ("UNKNOWN", False, False, False, False)

# Order matters: the NC and ND patterns are tested BEFORE the plain
# attribution ones, because every NC string also contains "BY".
_PATTERNS: list[tuple[re.Pattern[str], tuple[str, bool, bool, bool, bool]]] = [
    # ── refusals first ────────────────────────────────────────────────────
    (re.compile(r"\bnc\b|non[\s_-]*commercial", re.I),
     ("CC-BY-NC", False, True, True, False)),
    (re.compile(r"\bnd\b|no[\s_-]*deriv", re.I),
     ("CC-BY-ND", True, False, True, False)),
    (re.compile(r"in\s*copyright|all\s+rights\s+reserved|rights[\s_-]*reserved"
                r"|educational\s+use|personal\s+use|editorial\s+use", re.I),
     ("RESTRICTED", False, False, False, False)),
    # ── named, permissive, and not one of the four families ───────────────
    # Tested before CC0 because Pixabay's own text says "free" and "no
    # attribution", which the CC0 pattern would otherwise be asked to judge.
    (re.compile(r"pixabay\s*(content\s*)?licen[cs]e", re.I),
     ("PIXABAY", True, True, False, False)),
    # ── permitted ─────────────────────────────────────────────────────────
    (re.compile(r"cc0|creative\s*commons\s*zero|public\s*domain\s*dedication", re.I),
     ("CC0", True, True, False, False)),
    (re.compile(r"public\s*domain|\bpdm\b|no\s+known\s+copyright"
                r"|no\s+copyright\s*-?\s*united\s+states", re.I),
     ("PD", True, True, False, False)),
    (re.compile(r"(cc[\s_-]*by|attribution)[\s_-]*(sa|share[\s_-]*alike)", re.I),
     ("CC-BY-SA", True, True, True, True)),
    (re.compile(r"cc[\s_-]*by|creative\s*commons\s*attribution", re.I),
     ("CC-BY", True, True, True, False)),
]


def classify(text: str | None) -> Licence:
    """Read a licence out of whatever the API gave us.

    Unrecognised and empty both come back UNKNOWN, which is not permitted.
    """
    raw = (text or "").strip()
    if not raw:
        return Licence(*_UNKNOWN, raw="")
    for pattern, (code, commercial, derivatives, attribution, share_alike) in _PATTERNS:
        if pattern.search(raw):
            return Licence(code, commercial, derivatives, attribution,
                           share_alike, raw)
    return Licence(*_UNKNOWN, raw=raw)


def is_permitted(text: str | None) -> bool:
    """True only for CC0, public domain, CC BY and CC BY-SA."""
    return classify(text).permitted


def filter_candidates(candidates, on_reject=None):
    """Drop everything this channel may not use, at fetch time.

    Filtering here rather than at selection is the point: an asset that was
    never downloaded cannot end up in a film by accident, and the bank's
    licence column cannot drift from what the adapter actually fetched.
    """
    kept = []
    for candidate in candidates:
        licence = classify(getattr(candidate, "license", ""))
        if licence.permitted:
            # Normalise, so the bank records a family rather than a spelling.
            candidate.extra.setdefault("licence_raw", licence.raw)
            candidate.extra["licence_code"] = licence.code
            candidate.extra["share_alike"] = licence.share_alike
            candidate.extra["attribution_required"] = licence.attribution
            kept.append(candidate)
        elif on_reject is not None:
            on_reject(candidate, licence)
    return kept


def summarise(rejections: list[tuple[str, Licence]]) -> dict[str, int]:
    """Rejections by family, so a missing pattern is visible as UNKNOWN."""
    out: dict[str, int] = {}
    for _, licence in rejections:
        out[licence.code] = out.get(licence.code, 0) + 1
    return out

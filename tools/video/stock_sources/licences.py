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
#: not an adapter author's.
PERMITTED = ("CC0", "PD", "CC-BY", "CC-BY-SA")

#: Named licences that are permissive but outside the four families above.
#:
#: PIXABAY, admitted by the owner on 2026-10-21. The Pixabay Content License
#: is free for commercial use, needs no attribution and allows modification —
#: functionally CC0 for this channel's purposes, and not CC0, which is why it
#: is named here rather than folded into that family.
#:
#: IT IS NOT AS WIDE AS CC0, and the difference is recorded in USE_SCOPE
#: below: it permits use WITHIN a produced video and does not permit
#: redistributing the asset on its own. Nothing the pipeline does with an
#: asset breaches that — assets are composited into a film — but an asset
#: pack, a sample reel of unused stills, or shipping the bank itself would.
#:
#: Admitting it restored the whole `elemental_texture` subject: 28 assets,
#: which were the only refusals in a bank of 146.
PERMITTED_EXTRA: tuple[str, ...] = ("PIXABAY",)

#: What a permitted licence actually permits, where that is narrower than
#: "do anything". Keyed by code; absent means no restriction worth recording.
#:
#: This exists because "permitted" is one bit and a licence is not. A future
#: feature that publishes assets rather than films has to be able to ask.
USE_SCOPE: dict[str, dict[str, object]] = {
    "PIXABAY": {
        "in_produced_video": True,
        "commercial": True,
        "standalone_redistribution": False,
        "attribution_required": False,
        "note": "Use within a produced video, commercially. Not for "
                "redistributing the asset on its own — an asset pack, a reel "
                "of unused stills, or shipping the bank would breach it.",
    },
}


def use_scope(code: str) -> dict[str, object]:
    """What this licence allows, beyond the single bit of `permitted`."""
    return dict(USE_SCOPE.get(code, {
        "in_produced_video": True,
        "commercial": True,
        "standalone_redistribution": True,
    }))


#: Copyright expires. A work published before this year is in the public
#: domain in the United States, where the channel publishes, whatever a
#: database does or does not say about it.
PD_BY_PUBLICATION_BEFORE = 1929

#: And a work whose author has been dead this long is in the public domain
#: across the life-plus-70 jurisdictions.
PD_BY_AUTHOR_DEAD_YEARS = 70


@dataclass(frozen=True)
class Licence:
    code: str
    commercial: bool
    derivatives: bool
    attribution: bool
    share_alike: bool
    raw: str
    #: Why this is the answer, when the answer did not come from the string.
    #: Empty for everything read out of a licence statement; filled by the
    #: age rule, so a PD that nobody wrote down can be told from one that
    #: somebody did.
    reason: str = ""

    @property
    def permitted(self) -> bool:
        return self.code in PERMITTED or self.code in PERMITTED_EXTRA


_UNKNOWN = ("UNKNOWN", False, False, False, False)

#: The codes the age rule may overrule.
#:
#: UNKNOWN is an absent or unreadable statement, and UND and CNE are a
#: database saying in so many words that it has not looked. An age fact
#: answers a question those leave open.
#:
#: It does NOT overrule an explicit claim of copyright. A 1883 publication
#: and an "In Copyright" statement contradict each other, and the right
#: outcome is that a person reads the contradiction, not that an adapter
#: picks a side. Those stay refused and the conflict is recorded.
RESOLVABLE_BY_AGE = ("UNKNOWN",)

# Order matters: the NC and ND patterns are tested BEFORE the plain
# attribution ones, because every NC string also contains "BY".
_PATTERNS: list[tuple[re.Pattern[str], tuple[str, bool, bool, bool, bool]]] = [
    # ── before the refusals, the one permission that CONTAINS a refusal ───
    # The Internet Archive states a public-domain determination as
    # "NOT_IN_COPYRIGHT", which contains "IN_COPYRIGHT". Tested first, and
    # the refusal below is widened to catch the underscored form, so the pair
    # cannot be confused in either direction.
    (re.compile(r"\bnot[\s_-]*in[\s_-]*copyright\b", re.I),
     ("PD", True, True, False, False)),
    # rightsstatements.org is a CLOSED vocabulary and Europeana states most of
    # its rights with it. Its twelve codes split cleanly: NoC- (No Copyright)
    # and NKC (No Known Copyright) are determinations that a thing is free;
    # InC- (In Copyright), UND (Undetermined) and CNE (Copyright Not
    # Evaluated) are not. Read rather than left as UNKNOWN, because a
    # rejection log that says "unknown" invites someone to add a pattern that
    # should have been there.
    (re.compile(r"rightsstatements\.org/(vocab|page)/(NoC|NKC)", re.I),
     ("PD", True, True, False, False)),
    (re.compile(r"rightsstatements\.org/(vocab|page)/(InC|UND|CNE)", re.I),
     ("RESTRICTED", False, False, False, False)),
    # ── refusals ──────────────────────────────────────────────────────────
    (re.compile(r"\bnc\b|non[\s_-]*commercial", re.I),
     ("CC-BY-NC", False, True, True, False)),
    (re.compile(r"\bnd\b|no[\s_-]*deriv", re.I),
     ("CC-BY-ND", True, False, True, False)),
    (re.compile(r"in[\s_-]*copyright|all\s+rights\s+reserved|rights[\s_-]*reserved"
                r"|educational\s+use|personal\s+use|editorial\s+use", re.I),
     ("RESTRICTED", False, False, False, False)),
    # ── named, permissive, and not one of the four families ───────────────
    # Tested before CC0 because Pixabay's own text says "free" and "no
    # attribution", which the CC0 pattern would otherwise be asked to judge.
    (re.compile(r"pixabay\s*(content\s*)?licen[cs]e", re.I),
     ("PIXABAY", True, True, False, False)),
    # ── permitted ─────────────────────────────────────────────────────────
    # `publicdomain/zero` is the CC0 deed's own URL, and Europeana states
    # rights as URIs. Without it the deed classified as plain PD — permitted
    # either way, and still a misreading of a licence we can name exactly.
    (re.compile(r"cc0|creative\s*commons\s*zero|public\s*domain\s*dedication"
                r"|publicdomain/zero", re.I),
     ("CC0", True, True, False, False)),
    (re.compile(r"public\s*domain|\bpdm\b|no\s+known\s+copyright"
                r"|no\s+copyright\s*-?\s*united\s+states", re.I),
     ("PD", True, True, False, False)),
    (re.compile(r"(cc[\s_-]*by|attribution)[\s_-]*(sa|share[\s_-]*alike)", re.I),
     ("CC-BY-SA", True, True, True, True)),
    (re.compile(r"cc[\s_-]*by|creative\s*commons\s*attribution", re.I),
     ("CC-BY", True, True, True, False)),
]


def pd_by_age(published: int | None, author_died: int | None,
              today: int | None = None) -> str:
    """Is this old enough to be out of copyright, and which fact says so?

    Returns the reason, or "" if neither fact establishes it. Both are
    checked because they fail in different places: a 1912 photograph by an
    unknown photographer has a publication date and no death date, and a 1935
    drawing by someone who died in 1940 has the reverse.
    """
    import datetime

    year = today or datetime.date.today().year
    if published is not None and published < PD_BY_PUBLICATION_BEFORE:
        return (f"published {published}, before {PD_BY_PUBLICATION_BEFORE}: "
                f"out of copyright in the United States")
    if author_died is not None and year - author_died > PD_BY_AUTHOR_DEAD_YEARS:
        return (f"author died {author_died}, more than "
                f"{PD_BY_AUTHOR_DEAD_YEARS} years ago: out of copyright "
                f"under life plus {PD_BY_AUTHOR_DEAD_YEARS}")
    return ""


def classify(text: str | None, published: int | None = None,
             author_died: int | None = None) -> Licence:
    """Read a licence out of whatever the API gave us.

    Unrecognised and empty both come back UNKNOWN, which is not permitted —
    unless the work is old enough that copyright has expired, in which case
    the age is the answer and the REASON is recorded, so a PD that nobody
    wrote down can be told from one that somebody did.
    """
    raw = (text or "").strip()
    found = None
    if raw:
        for pattern, (code, commercial, derivatives, attribution, share_alike) in _PATTERNS:
            if pattern.search(raw):
                found = Licence(code, commercial, derivatives, attribution,
                                share_alike, raw)
                break
    if found is None:
        found = Licence(*_UNKNOWN, raw=raw)

    if found.permitted or found.code not in RESOLVABLE_BY_AGE:
        reason = pd_by_age(published, author_died)
        if reason and not found.permitted:
            # an explicit claim that the facts contradict: still refused,
            # and the contradiction is the thing worth seeing
            return Licence(found.code, found.commercial, found.derivatives,
                           found.attribution, found.share_alike, raw,
                           reason=f"states {found.code!r} but {reason} — "
                                  f"refused; a person should read this")
        return found

    reason = pd_by_age(published, author_died)
    if reason:
        return Licence("PD", True, True, False, False, raw, reason=reason)
    return found


def is_permitted(text: str | None) -> bool:
    """True only for CC0, public domain, CC BY and CC BY-SA."""
    return classify(text).permitted


def _as_year(value) -> int | None:
    """A year out of whatever a catalogue put in the field."""
    if value is None:
        return None
    text = str(value)
    match = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", text)
    return int(match.group(1)) if match else None


def filter_candidates(candidates, on_reject=None):
    """Drop everything this channel may not use, at fetch time.

    Filtering here rather than at selection is the point: an asset that was
    never downloaded cannot end up in a film by accident, and the bank's
    licence column cannot drift from what the adapter actually fetched.
    """
    kept = []
    for candidate in candidates:
        extra = getattr(candidate, "extra", None) or {}
        licence = classify(
            getattr(candidate, "license", ""),
            published=_as_year(extra.get("published") or extra.get("year")),
            author_died=_as_year(extra.get("author_died")))
        if licence.permitted:
            # Normalise, so the bank records a family rather than a spelling.
            candidate.extra.setdefault("licence_raw", licence.raw)
            candidate.extra["licence_code"] = licence.code
            if licence.reason:
                candidate.extra["licence_reason"] = licence.reason
            candidate.extra["share_alike"] = licence.share_alike
            candidate.extra["attribution_required"] = licence.attribution
            scope = use_scope(licence.code)
            if not scope.get("standalone_redistribution", True):
                # recorded on the asset, so a future step that publishes
                # assets rather than films can see it without re-reading the
                # licence text
                candidate.extra["no_standalone_redistribution"] = True
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

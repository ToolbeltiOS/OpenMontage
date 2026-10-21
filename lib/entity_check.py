"""Is this a thing a documentary can be about?

THE PROBLEM
-----------
Clustering the Shorts ledger by "capitalised phrase" produces topics and it
also produces "Million Years", "Found", "Pond", "Build" and "Heaven". Those
are fragments of titles — a quantity, a verb at the start of a sentence, a
common noun — and three of them passed the source-depth check, because
Wikimedia Commons has a deep category for ponds.

Neither half of the picker can tell them apart. Performance cannot: those
Shorts really did get views. Depth cannot: the pictures really do exist. The
missing question is whether the phrase names something.

THE TEST
--------
A documentary subject is a PLACE, a PERSON, a STRUCTURE or a DATED EVENT.
Wikidata knows which of those a phrase is, keylessly:

    coordinates (P625)          it is somewhere  -> a place or a structure
    date of birth/death (P569/P570)  it is someone
    point in time / start (P585/P580) it happened
    instance of (P31) in the allow-set below

A phrase with none of those is not refused for being uninteresting. It is
refused for not being a thing.

AND A KIND OF THING IS NOT A THING. "Mountain", "Stone", "Pond" and
"Science" all name something, have Wikipedia articles in 38 to 325
languages, and are not subjects: they are CLASSES, and the subjects are
their instances — Everest is a mountain, Petra is a city. Wikidata marks a
class with `subclass of` (P279), and that one property separates them
where neither prominence nor the channel's own corpus could. Shorts titles
are Title Case, so a common noun never appears in lowercase to give itself
away, and a class is usually MORE written about than any of its instances.

WHICH SENSE. A phrase names several things — Petra is a city, a given name,
a Finnish musician and a village in Spain — and asking Wikidata's own search
returns four of those and NOT the city. Wikipedia's title resolution does
know which one people mean: `Petra` is the city, and `King Tut` redirects to
Tutankhamun. So an English Wikipedia article is asked for first and its
Wikidata item is the answer; Wikidata's search is the fallback for a phrase
with no article, ranked by how many language editions write about it.

    python3 lib/entity_check.py "Easter Island" "Pond" "Million Years"
"""
from __future__ import annotations

import json
import re
import sys
import time
from functools import lru_cache
import urllib.parse
import urllib.request
from typing import Any

API = "https://www.wikidata.org/w/api.php"
WIKIPEDIA = "https://en.wikipedia.org/w/api.php"
UA = ("wak3upsociety-documentary/1.0 "
      "(https://github.com/ToolbeltiOS/OpenMontage; topic eligibility)")

MIN_INTERVAL_S = 0.6
_last_call = 0.0

#: Properties that say what KIND of thing this is.
COORDINATES, INSTANCE_OF = "P625", "P31"
BIRTH, DEATH = "P569", "P570"
POINT_IN_TIME, START_TIME = "P585", "P580"

#: Classes worth a documentary that may carry none of the properties above —
#: a text, a myth, a vanished object. Kept short on purpose: this is the
#: escape hatch, not the rule.
ALLOWED_CLASSES = {
    "Q571": "book",
    "Q7725634": "literary work",
    "Q234460": "text",
    "Q2342494": "commemorative plaque",
    "Q4989906": "monument",
    "Q838948": "work of art",
    "Q11042": "culture",
    "Q11514315": "historical period",
    "Q178885": "deity",
    "Q13406463": "list",             # rejected below; named so it is visible
}

#: ...and classes that are never a subject however they are described.
REFUSED_CLASSES = {"Q4167410", "Q13406463", "Q4167836", "Q11266439"}

#: `subclass of`. An item that has it is a KIND of thing.
SUBCLASS_OF = "P279"

#: How many language editions must write about a thing. Measured on this
#: channel's own candidates: the subjects run 86-164 and the near-misses —
#: a district in Bekasi called Pond, an academic journal called Britain —
#: run 1 to 11.
MIN_SITELINKS = 20


def _get(params: dict[str, Any], timeout: int = 30) -> dict:
    global _last_call

    wait = MIN_INTERVAL_S - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()

    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wikipedia(params: dict[str, Any], timeout: int = 30) -> dict:
    global _last_call

    wait = MIN_INTERVAL_S - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()

    url = WIKIPEDIA + "?" + urllib.parse.urlencode({**params, "format": "json"})
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def article_item(phrase: str) -> tuple[str | None, str]:
    """The Wikidata item of the English Wikipedia article for this phrase.

    Redirects are followed, which is how "King Tut" becomes Tutankhamun.
    Returns (item id, article title).
    """
    try:
        found = _wikipedia({"action": "query", "titles": phrase,
                            "prop": "pageprops", "redirects": 1})
    except Exception:
        return None, ""
    for page_id, page in ((found.get("query") or {}).get("pages") or {}).items():
        if page_id == "-1":
            return None, ""
        return ((page.get("pageprops") or {}).get("wikibase_item"),
                page.get("title", ""))
    return None, ""


#: Link titles that are never a subject: the apparatus of an encyclopaedia.
NOT_A_SUBJECT = re.compile(
    r"\((disambiguation|identifier|album|game|film|song|band|magazine)\)|"
    r"^(ISBN|ISSN|Doi|Bibcode|PMID|Geographic coordinate|List of)", re.I)


def article_links(title: str, limit: int = 40) -> list[str]:
    """What the LEAD of this article links to.

    This is where a film's supporting subjects come from. A cluster's own
    Shorts name one or two things between them and a documentary needs six;
    the lead of the Petra article links to Ad Deir, Al-Khazneh and Aretas IV,
    and those are what the film is made of.

    The lead, not the article. `prop=links` over a whole page returns every
    link sorted ALPHABETICALLY, which for Easter Island is Algarrobo,
    American Samoa and Aniwa Island — true, alphabetical and useless.
    """
    try:
        found = _wikipedia({"action": "parse", "page": title,
                            "prop": "links", "section": 0, "redirects": 1})
    except Exception:
        return []
    out = []
    for link in ((found.get("parse") or {}).get("links") or []):
        name = link.get("*", "")
        if link.get("ns") != 0 or "exists" not in link:
            continue
        if not name or ":" in name or NOT_A_SUBJECT.search(name):
            continue
        out.append(name)
    return out[:limit]


def find_items(phrase: str, limit: int = 6) -> list[str]:
    """Wikidata ids whose label matches this phrase.

    Several, not one. Taking the first match rejected Petra, Britain and
    King Tut — all real subjects — because the first item labelled "Petra"
    is a GIVEN NAME, which has no coordinates and is not a place. The
    question is whether ANY thing by this name is a subject, so several are
    asked and the first that qualifies answers.
    """
    try:
        found = _get({"action": "wbsearchentities", "search": phrase,
                      "language": "en", "limit": 8, "type": "item"})
    except Exception:
        return []
    import re

    # "Petrarca" starts with "Petra" and is not it. A prefix match has to end
    # on a word boundary.
    pattern = re.compile(r"^" + re.escape(phrase.lower()) + r"(\b|$)")
    ids = []
    for hit in found.get("search", []):
        if pattern.match((hit.get("label") or "").lower()):
            ids.append(hit["id"])
    return ids[:limit]


def describe(item_id: str) -> dict[str, Any]:
    """The claims that say what kind of thing this is."""
    try:
        found = _get({"action": "wbgetentities", "ids": item_id,
                      "props": "claims|descriptions|sitelinks",
                      "languages": "en"})
    except Exception:
        return {}
    entity = (found.get("entities") or {}).get(item_id) or {}
    claims = entity.get("claims") or {}

    def ids_of(prop: str) -> list[str]:
        out = []
        for claim in claims.get(prop, []):
            value = (((claim.get("mainsnak") or {}).get("datavalue") or {})
                     .get("value") or {})
            if isinstance(value, dict) and "id" in value:
                out.append(value["id"])
        return out

    return {
        "id": item_id,
        "description": (((entity.get("descriptions") or {}).get("en") or {})
                        .get("value", "")),
        "sitelinks": len(entity.get("sitelinks") or {}),
        "is_a_class": SUBCLASS_OF in claims,
        "has_coordinates": COORDINATES in claims,
        "is_a_person": bool(set(claims) & {BIRTH, DEATH}),
        "is_dated": bool(set(claims) & {POINT_IN_TIME, START_TIME}),
        "instance_of": ids_of(INSTANCE_OF),
    }


def _verdict(phrase: str, item_id: str, facts: dict[str, Any]) -> dict[str, Any]:
    classes = set(facts["instance_of"])
    if classes & REFUSED_CLASSES:
        return {"phrase": phrase, "subject": False, "item": item_id,
                "description": facts["description"],
                "why": "a disambiguation page or a list, not a thing"}
    if facts["is_a_class"]:
        return {"phrase": phrase, "subject": False, "item": item_id,
                "description": facts["description"],
                "sitelinks": facts["sitelinks"],
                "why": "a kind of thing, not a thing — its instances are the "
                       "subjects"}
    if facts["sitelinks"] < MIN_SITELINKS:
        return {"phrase": phrase, "subject": False, "item": item_id,
                "description": facts["description"],
                "sitelinks": facts["sitelinks"],
                "why": f"only {facts['sitelinks']} language editions write "
                       f"about it; too obscure to carry a documentary"}

    # A DATE ALONE IS NOT ENOUGH. Everything has a date: the journal called
    # Science began in 1880 and the Universe at the Big Bang, and neither is
    # what a Short about science or the universe was about. A subject has to
    # be somewhere, or be someone, or be one of the few kinds of thing that
    # is neither and still filmable. A date supports those; it does not stand
    # in for them. A dated EVENT that is filmable almost always has
    # coordinates too.
    reasons = []
    if facts["has_coordinates"]:
        reasons.append("it is somewhere")
    if facts["is_a_person"]:
        reasons.append("it is someone")
    allowed = (classes & set(ALLOWED_CLASSES)) - REFUSED_CLASSES
    if allowed:
        reasons.append("it is a " + ALLOWED_CLASSES[sorted(allowed)[0]])
    if reasons and facts["is_dated"]:
        reasons.append("and it is dated")

    return {
        "phrase": phrase, "item": item_id,
        "description": facts["description"],
        "sitelinks": facts["sitelinks"],
        "subject": bool(reasons),
        "why": "; ".join(reasons) or
               "not a place, a person, a structure or a dated event",
    }


@lru_cache(maxsize=2048)
def is_a_subject(phrase: str) -> dict[str, Any]:
    """Is this a place, a person, a structure or a dated event?

    Cached: the picker asks about the same phrase once as a cluster and
    again as a supporting entity of three other clusters, and each miss is
    two rate-limited API calls.
    """
    # what an English reader means by the phrase, first
    article, title = article_item(phrase)
    if article:
        facts = describe(article)
        if facts:
            verdict = _verdict(phrase, article, facts)
            verdict["article"] = title
            return verdict

    items = find_items(phrase)
    if not items:
        return {"phrase": phrase, "subject": False,
                "why": "no Wikidata item matches this phrase"}
    verdicts = []
    for item_id in items:
        facts = describe(item_id)
        if facts:
            verdicts.append(_verdict(phrase, item_id, facts))
    if not verdicts:
        return {"phrase": phrase, "subject": False,
                "why": "the items could not be read"}
    # the most written-about thing that IS a subject answers; if none is,
    # the most written-about one explains why not
    subjects = [v for v in verdicts if v["subject"]]
    pool = subjects or verdicts
    return max(pool, key=lambda v: v.get("sitelinks", 0))


def main() -> int:
    for phrase in sys.argv[1:]:
        verdict = is_a_subject(phrase)
        mark = "SUBJECT" if verdict["subject"] else "no      "
        print(f"{mark}  {phrase:22s} {verdict.get('description','')[:40]:40s} "
              f"{verdict['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

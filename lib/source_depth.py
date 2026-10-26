"""Can this topic be made, or only written about?

WHY THIS GATE EXISTS
--------------------
Run #1's topic was chosen on interest and never checked for pictures, and a
third of its slots came back as text cards and schematics because the archive
had nothing for them. A documentary is not an essay: a subject the archive is
thin on is a subject that becomes forty minutes of captions over a gradient.

So before a topic is accepted, every named entity in it is counted — not
searched, COUNTED, against the sources that would actually supply the film,
with the licence filter applied, because an asset the filter would refuse is
not an asset.

WHAT COUNTS AS DEPTH
--------------------
Eight usable assets per entity, across the top six entities. Eight is two
more than the six an act needs, so a subject that only just clears is still
one failed fetch away from a text card; six entities because a film is four
acts and an act is about six subjects.

COUNTED CHEAPLY
---------------
Wikimedia category membership is the main measure and the only one that is
both free and deep: a category is curated by people, so membership means a
person decided this picture is of this thing. Commons search drifts — it
returned a coat of arms for "Egyptian granite sarcophagus" — so categories
are asked first and search is a fallback that is counted at a discount.

The museum APIs are asked for the entities that look like objects rather than
places. They are keyless and quick, and they are the difference between a
subject with twelve photographs of a site and a subject with twelve
photographs of a site AND four of the thing that was found there.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Any

COMMONS = "https://commons.wikimedia.org/w/api.php"
UA = ("wak3upsociety-documentary/1.0 "
      "(https://github.com/ToolbeltiOS/OpenMontage; topic depth check)")

#: Commons throttles hard and an earlier pass collected 429s, so this waits.
MIN_INTERVAL_S = 1.2
_last_call = 0.0

#: A search hit is weaker evidence than a category member, because search
#: drifts and a category is curated. Counted at this weight.
SEARCH_DISCOUNT = 0.5

#: Only these extensions are assets. An SVG of a coat of arms is not footage.
USABLE = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webm", ".ogv", ".mp4")


def _get(params: dict[str, Any], timeout: int = 30,
         api: str | None = None) -> dict:
    global _last_call

    wait = MIN_INTERVAL_S - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()

    url = (api or COMMONS) + "?" + urllib.parse.urlencode(
        {**params, "format": "json"})
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


WIKIDATA = "https://www.wikidata.org/w/api.php"

#: Trailing words a Commons category adds to a subject's own name without
#: making it a different subject. `Category:Durupınar Site` is the Durupınar
#: site; `Category:Mount Ararat (Free State)` is a hill in South Africa.
CATEGORY_SUFFIXES = ("site", "sites")


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("_", " ").split())


def _is_own_category(entity: str, category: str) -> bool:
    """Is this category the subject itself, rather than something matching it?

    Exact, or the subject plus a generic trailing noun. A parenthetical
    qualifier means a DISAMBIGUATION, which is the one case where a matching
    title reliably indicates a different thing.
    """
    want, got = _norm(entity), _norm(category)
    if got == want:
        return True
    if got.startswith(want + " "):
        rest = got[len(want) + 1:]
        return rest in CATEGORY_SUFFIXES
    return False


def commons_category(entity: str) -> str | None:
    """The entity's OWN Commons category, from Wikidata, resolved by label.

    Commons files a subject under whatever its editors chose, and searching
    the category namespace finds that name only by luck of spelling. Durupınar
    is filed under `Category:Durupınar Site` — capital S, Turkish ı — and
    every lowercase or ASCII spelling of it returns zero members.

    Wikidata knows the answer: P373 is the Commons category, and the
    commonswiki sitelink is the same thing when P373 is absent. The item is
    resolved BY LABEL rather than by a guessed Q-number — Durupınar is
    Q1267546, and a guess at it would have been a different subject entirely.

    This is also what makes membership trustworthy. A category that Wikidata
    says IS this subject's category can be counted by membership alone; a
    category that merely matched a search cannot, because "Mount Ararat"
    matches "Mount Ararat (Free State)", which is a hill in South Africa.
    """
    try:
        found = _get({"action": "wbsearchentities", "language": "en",
                      "limit": 5, "search": entity}, api=WIKIDATA)
        hits = found.get("search") or []
        # THE LABEL HAS TO BE THE SAME THING, NOT THE NEAREST THING.
        #
        # wbsearchentities matches aliases and prefixes and returns whatever
        # is closest, which is not the same question. Measured: "Ark van
        # Noach" — the 2012 Dutch full-scale build — returns Q7747, "Noah's
        # Ark", because the Dutch phrase is an alias of the biblical vessel;
        # counting its category would have credited the build with 56 files
        # of a different subject. And "Durupınar" returns nothing at all,
        # because the item's label is "Durupınar site".
        #
        # So an inexact label is no answer, and the search-derived categories
        # below are left to answer instead.
        want = _norm(entity)
        qid = next((h["id"] for h in hits if _norm(h.get("label", "")) == want),
                   None)
        if not qid:
            return None
        data = _get({"action": "wbgetentities", "ids": qid,
                     "props": "claims|sitelinks"}, api=WIKIDATA)
        ent = (data.get("entities") or {}).get(qid) or {}
        for claim in (ent.get("claims") or {}).get("P373", []):
            value = (((claim.get("mainsnak") or {}).get("datavalue") or {})
                     .get("value"))
            if value:
                return str(value)
        link = ((ent.get("sitelinks") or {}).get("commonswiki") or {}).get("title")
        if link:
            return link.split(":", 1)[-1]
    except Exception:
        return None
    return None


def find_categories(entity: str, limit: int = 4) -> list[str]:
    """The categories a person would have filed this thing under.

    Asking for `Category:<entity>` by name finds nothing for most subjects:
    Commons files the Great Pyramid under "Great Pyramid of Giza" and the
    Nazca lines under "Nazca lines", and an exact-name lookup returned ZERO
    members for all three test entities — which made the whole depth measure
    fall through to search, which is the half that drifts.

    So the category namespace is searched first and the best matches are
    counted. A category whose title does not contain the entity's own words
    is dropped: "Plates from Piazzi Smyth 1877" comes back for "Great
    Pyramid" and is a different subject.
    """
    try:
        found = _get({"action": "query", "list": "search", "srsearch": entity,
                      "srnamespace": 14, "srlimit": 10})
    except Exception:
        return []
    needles = [w.lower() for w in entity.split() if len(w) > 3]
    names = []
    for match in ((found.get("query") or {}).get("search") or []):
        title = match["title"].split(":", 1)[-1]
        if needles and not all(n in title.lower() for n in needles):
            continue
        names.append(title)

    # An exact category leads, then one that begins with the entity. Without
    # the ordering "Maryhill Stonehenge" — a replica in Washington State —
    # counts towards Stonehenge, because its title does contain the word.
    lowered = entity.lower()
    names.sort(key=lambda t: (t.lower() != lowered,
                              not t.lower().startswith(lowered), len(t)))
    return names[:limit]


def category_members(category: str, limit: int = 60) -> list[str]:
    """Files a person put in this category."""
    try:
        found = _get({
            "action": "query", "list": "categorymembers",
            "cmtitle": f"Category:{category}", "cmtype": "file",
            "cmlimit": min(limit, 500),
        })
    except Exception:
        return []
    return [m["title"] for m in
            ((found.get("query") or {}).get("categorymembers") or [])]


def search_files(term: str, limit: int = 40) -> list[str]:
    """Commons full-text, which drifts and is counted at a discount."""
    try:
        found = _get({
            "action": "query", "list": "search", "srsearch": f"{term} filetype:bitmap",
            "srnamespace": 6, "srlimit": min(limit, 50),
        })
    except Exception:
        return []
    return [m["title"] for m in ((found.get("query") or {}).get("search") or [])]


def _media(titles: list[str]) -> list[str]:
    """Files that are media at all, whatever they are called."""
    kept = []
    for title in titles:
        name = title.split(":", 1)[-1]
        if name.lower().endswith(USABLE):
            kept.append(name)
    return kept


def _usable(titles: list[str], term: str) -> list[str]:
    """Media whose NAME carries the subject.

    The name test is the same one the asset bank uses, and it is what stops a
    text search for "Durupınar" — which returns photographs of Mount Ararat,
    because the search is fuzzy — from counting toward it.

    IT IS FOR SEARCH RESULTS, NOT FOR CATEGORY MEMBERS. See `depth_of`.
    """
    needles = [w.lower() for w in term.split() if len(w) > 3]
    kept = []
    for name in _media(titles):
        if needles and not any(n in name.lower() for n in needles):
            continue
        kept.append(name)
    return kept


def depth_of(entity: str, min_assets: int = 8) -> dict[str, Any]:
    """How many usable assets exist for this one thing."""
    # The entity's OWN category first, from Wikidata, then whatever the
    # category search suggests. The two are counted differently below.
    own = commons_category(entity)
    searched = find_categories(entity) or [entity]
    categories = ([own] if own else []) + [c for c in searched if c != own]

    members: list[str] = []          # from the subject's own category
    loose: list[str] = []            # from categories that merely matched
    for category in dict.fromkeys(categories):
        found = category_members(category)
        if (own and category == own) or _is_own_category(entity, category):
            members += found
        else:
            loose += found
        if len(members) + len(loose) >= min_assets * 4:
            break

    # MEMBERSHIP IS THE EVIDENCE, FOR A CATEGORY THIS NARROW.
    #
    # `find_categories` already requires every significant word of the entity
    # to appear in the category's own title, so what comes back is the
    # subject's own category and not a continent's. Applying the filename test
    # to its members a second time asks a question membership has already
    # answered — and answers it wrongly for anything photographed by people
    # who do not write English.
    #
    # Measured on Durupınar: `Category:Durupınar Site` holds thirteen files,
    # named in Turkish, Polish and Czech — "Arka Noego", "Noemova archa",
    # "NuhunGemisi", "Üzengili". The name test kept ONE, and the subject was
    # reported as unsourceable at 0.5 usable assets. It has thirteen.
    #
    # The test still applies to search results below, where it is the only
    # thing standing between the count and a fuzzy match.
    # MEMBERSHIP IS THE EVIDENCE, FOR THE CATEGORY WIKIDATA NAMES.
    #
    # A category Wikidata says IS this subject's category has been curated by
    # people who decided each picture is of this thing, and the filename adds
    # nothing to that. Applying the name test to its members asks a question
    # membership has already answered — and answers it wrongly for anything
    # photographed by people who do not write English.
    #
    # Measured on Durupınar: `Category:Durupınar Site` holds thirteen files,
    # named in Turkish, Polish and Czech — "Arka Noego", "Noemova archa",
    # "NuhunGemisi", "Üzengili". The name test kept ONE, and the subject was
    # reported as unsourceable at 0.5 usable assets.
    #
    # A category that merely MATCHED a search keeps the name test, because
    # "Mount Ararat" matches "Mount Ararat (Free State)", a hill in South
    # Africa whose farm photographs are not this subject.
    from_categories = _media(members) + _usable(loose, entity)
    counted = float(len(from_categories))
    from_search: list[str] = []
    if counted < min_assets:
        from_search = _usable(search_files(entity), entity)
        counted += SEARCH_DISCOUNT * len(
            [f for f in from_search if f not in from_categories])

    return {
        "entity": entity,
        "categories": categories[:3],
        "category_files": len(from_categories),
        "search_files": len(from_search),
        "counted": round(counted, 1),
        "clears": counted >= min_assets,
        "examples": from_categories[:4] or from_search[:4],
    }


def entities_of(candidate: dict[str, Any], ledger: list[dict[str, Any]],
                limit: int = 10, check_relevance: bool = True) -> list[str]:
    """The named things a film about this cluster would be made of.

    Three sources, in order of how much they know:

        the cluster itself   what the audience responded to
        its Shorts' titles   what the channel already said about it
        its Wikipedia links  what the subject is actually made of

    The third matters most and was missing at first. A cluster's eight
    stored titles name one or two things between them, a documentary needs
    six, and every cluster measured 1/6 until the article was asked. The
    article about Easter Island names Rano Raraku and Ahu Tongariki in its
    first paragraphs; those are the film.
    """
    from collections import Counter

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from entity_check import article_item, article_links, is_a_subject
    from pick_topic import entities_in

    # The SUBJECT'S ARTICLE TITLE, not the phrase. Articles link to
    # "Tutankhamun"; nothing links to "King Tut", so testing the phrase
    # rejected every supporting entity of a cluster whose name is a nickname.
    _, subject_title = article_item(candidate["entity"])
    subject_title = subject_title or candidate["entity"]

    def about_each_other(name: str, subject: str) -> bool:
        """Does this thing's own article mention the subject?

        The lead of the Easter Island article links to the moai and to the
        National Geospatial-Intelligence Agency, because an encyclopaedia
        cites who measured the coordinates. Both are real things with deep
        Commons categories, and only one of them is in the film. A supporting
        subject is one the two articles are about EACH OTHER — Rano Raraku
        links back, Pitcairn Island and the Pacific Ocean do not.
        """
        _, title = article_item(name)
        links = article_links(title or name, limit=60)
        return any(subject.lower() in link.lower() for link in links)

    ordered = [candidate["entity"]]
    seen = {candidate["entity"].lower()}

    def consider(name: str) -> bool:
        if name.lower() in seen or len(ordered) >= limit:
            return False
        seen.add(name.lower())
        # A supporting entity only has to be real, not famous: Orongo has
        # fourteen language editions and is exactly the size of an act.
        from entity_check import MIN_SITELINKS_SUPPORTING

        if not is_a_subject(name, MIN_SITELINKS_SUPPORTING,
                            as_cluster=False)["subject"]:
            return False
        if check_relevance and not about_each_other(name, subject_title):
            return False
        ordered.append(name)
        return True

    counts: Counter[str] = Counter()
    for title in candidate.get("titles", []):
        for name in entities_in(title):
            counts[name] += 1
    for name, _ in counts.most_common():
        consider(name)

    if len(ordered) < limit:
        _, title = article_item(candidate["entity"])
        for name in article_links(title or candidate["entity"]):
            if not consider(name):
                continue
            if len(ordered) >= limit:
                break
    return ordered[:limit]


def check_cluster(candidate: dict[str, Any], ledger: list[dict[str, Any]],
                  min_assets: int = 8, entities: int = 6) -> dict[str, Any]:
    """Is there enough to build a film about this?"""
    names = entities_of(candidate, ledger, limit=max(entities * 2, 10))
    depths = [depth_of(name, min_assets) for name in names]
    depths.sort(key=lambda d: d["counted"], reverse=True)

    top = depths[:entities]
    deepest = sum(1 for d in top if d["clears"])
    return {
        "entities": depths,
        "deepest_six": f"{deepest}/{entities}",
        "eligible": len(top) >= entities and all(d["clears"] for d in top),
        "min_assets": min_assets,
        "thin": [d["entity"] for d in top if not d["clears"]],
    }

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


def _get(params: dict[str, Any], timeout: int = 30) -> dict:
    global _last_call

    wait = MIN_INTERVAL_S - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()

    url = COMMONS + "?" + urllib.parse.urlencode({**params, "format": "json"})
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


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


def _usable(titles: list[str], term: str) -> list[str]:
    """Files that are media, and whose name carries the subject.

    The name test is the same one the asset bank uses, and it is what stops a
    category of "Egypt" contributing a photograph of a modern street sign to
    the count for "Great Pyramid".
    """
    needles = [w.lower() for w in term.split() if len(w) > 3]
    kept = []
    for title in titles:
        name = title.split(":", 1)[-1]
        if not name.lower().endswith(USABLE):
            continue
        if needles and not any(n in name.lower() for n in needles):
            continue
        kept.append(name)
    return kept


def depth_of(entity: str, min_assets: int = 8) -> dict[str, Any]:
    """How many usable assets exist for this one thing."""
    categories = find_categories(entity) or [entity]
    members: list[str] = []
    for category in dict.fromkeys(categories):
        members += category_members(category)
        if len(members) >= min_assets * 4:
            break

    from_categories = _usable(members, entity)
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
        if not is_a_subject(name)["subject"]:
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

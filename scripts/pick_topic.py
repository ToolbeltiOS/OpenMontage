#!/usr/bin/env python3
"""What the next documentary should be about, and whether it can be made.

THE TWO QUESTIONS, IN ORDER
---------------------------
A weekly documentary fails in two ways. It is about something nobody wants to
watch, or it is about something there are no pictures of. Run #1 answered the
first by hand and never asked the second, and paid for it: a third of its
slots came back as text cards and schematics because the archive had nothing.

So this asks them in order and refuses to skip the second.

    1. WHAT PERFORMS. The Shorts ledger is 500 posts of measured audience
       response across the channel's whole niche. A cluster of Shorts that
       did well is an audience that showed up for that subject.

    2. IS IT A THING. Clustering by capitalised phrase produces topics and it
       also produces "Million Years", "Found", "Pond" and "Build". Neither
       other check can tell them apart — those Shorts really did get views,
       and Commons really does have a deep category for ponds — so the
       phrase is asked of Wikidata: a documentary subject is a place, a
       person, a structure or a dated event. See lib/entity_check.py.

    3. WHAT CAN BE BUILT. For each named entity in a cluster, count the
       assets that actually exist and that the licence filter would accept.
       A cluster is eligible only if its top six entities each clear eight.

They run in that order because each is slower than the last, and counting
assets for a phrase that is not a thing is a slow way to learn nothing.

NO DEPRIORITISATION. The channel's niche is conspiracy, mystery, archaeology,
space and religion, and the ranking is by measured performance within it. A
subject is not demoted for being the channel's subject.

    python scripts/pick_topic.py --project-root . --top 3
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

#: The droplet holds the Shorts ledger. Read-only, over SSH, as everything
#: that touches the Shorts side is.
SSH_HOST = "toolbelt@143.198.34.8"
SSH_KEY = Path.home() / ".ssh" / "wak3up_key"
LEDGER = "~/wak3up/temp/performance_history.json"

#: A cluster is eligible only if its top entities each clear this many usable
#: assets. Eight is two more than the six a 20-minute act needs, so a subject
#: that only just clears is still one failed fetch away from a text card.
MIN_ASSETS_PER_ENTITY = 8

#: ...across this many of its entities. Six because an act is roughly six
#: subjects and a film is four acts; a cluster with two deep entities and
#: four thin ones is a film that runs out in act two.
ENTITIES_CHECKED = 6

#: Shorts newer than this have not finished accumulating views.
MIN_AGE_DAYS = 7

#: Words that carry no subject. A title is three or four words of substance
#: and a lot of this.
STOPWORDS = set("""a an the and or but of in on at to for with from by as is
are was were be been being this that these those it its they them their there
here what which who whom whose when where why how all any both each few more
most other some such no nor not only own same so than too very can will just
should now you your we our us i me my he she his her him them one two three
did do does doing done had has have having if into about after before over
under again further then once because while during above below up down out
off new old first last next best worst shorts short video real truth facts
fact secret secrets hidden revealed revealing explained story history
mystery""".split())

#: Entities are capitalised multi-word phrases, which in this corpus is what
#: a place or a person looks like.
ENTITY = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+(?:of|the|de|al|el)\s+)?"
                    r"(?:\s+[A-Z][a-z]{2,})*)\b")


def read_ledger(host: str = SSH_HOST, key: Path = SSH_KEY,
                path: str = LEDGER) -> list[dict[str, Any]]:
    """The Shorts performance ledger, over SSH, read-only."""
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=20", "-o", "BatchMode=yes",
         "-i", str(key), host, f"cat {path}"],
        capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise SystemExit(
            f"could not read the Shorts ledger from {host}: "
            f"{result.stderr.strip()[:200]}")
    return json.loads(result.stdout)


def age_days(entry: dict[str, Any], now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    raw = (entry.get("uploaded_at") or "").replace("Z", "+00:00")
    try:
        when = datetime.fromisoformat(raw)
    except ValueError:
        return 0.0
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (now - when).total_seconds() / 86400


def entities_in(title: str) -> list[str]:
    """The named things a title is about."""
    cleaned = re.sub(r"#\w+", " ", title)
    found = []
    for match in ENTITY.finditer(cleaned):
        phrase = " ".join(match.group(1).split())
        words = [w for w in phrase.split() if w.lower() not in STOPWORDS]
        if not words:
            continue
        phrase = " ".join(words)
        if len(phrase) >= 4 and phrase.lower() not in STOPWORDS:
            found.append(phrase)
    return found


def cluster(ledger: list[dict[str, Any]], min_age_days: float = MIN_AGE_DAYS
            ) -> list[dict[str, Any]]:
    """Group the ledger by the entity its titles name, and score each group.

    Scored on MEDIAN views rather than mean: one Short that found an
    algorithm is not an audience for a subject, and a mean lets it speak for
    five that did not.
    """
    import statistics

    buckets: dict[str, list[dict]] = defaultdict(list)
    for entry in ledger:
        if age_days(entry) < min_age_days:
            continue
        for name in set(entities_in(entry.get("title", ""))):
            buckets[name].append(entry)

    clusters = []
    for name, entries in buckets.items():
        if len(entries) < 2:
            continue                       # one post is an anecdote
        views = [int(e.get("views") or 0) for e in entries]
        engagement = [float(e.get("engagement_rate") or 0) for e in entries]
        clusters.append({
            "entity": name,
            "shorts": len(entries),
            "median_views": int(statistics.median(views)),
            "best_views": max(views),
            "mean_engagement": round(statistics.fmean(engagement), 2),
            "titles": [e.get("title", "") for e in entries][:8],
            "urls": [e.get("url", "") for e in entries][:8],
        })
    clusters.sort(key=lambda c: (c["median_views"], c["shorts"]), reverse=True)
    return clusters


def already_made(published_path: Path) -> set[str]:
    """Entities the channel has already made a documentary about."""
    if not published_path.exists():
        return set()
    done: set[str] = set()
    for film in (json.loads(published_path.read_text()).get("films") or []):
        done.update(name.lower() for name in (film.get("entities") or []))
        done.update(entities_in(film.get("title", "")))
    return {name.lower() for name in done}


def blacklisted(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip().lower() for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")}


#: Title shapes, filled with the subject. These are not invented: each is the
#: shape of a title that already performed on this channel, and the brief
#: quotes the Short it came from so the claim can be checked.
TITLE_SHAPES = [
    "{entity}: The Part Nobody Can Explain",
    "What {entity} Was Really Built For",
    "The {entity} Problem",
    "{entity} Should Not Exist",
]


def split_container(candidate: dict[str, Any], limit: int = 3
                    ) -> list[dict[str, Any]]:
    """The film-sized things inside a container, as candidates of their own.

    A country is not a documentary; the thing in the country is. The parts
    come from what the channel's own Shorts named first — that is what the
    audience actually responded to — and then from the lead of the
    container's article.

    They inherit the container's measured performance, HALVED and marked
    `derived_from`, because the Shorts were about the container and the
    evidence for the part is weaker by exactly that much. A brief built from
    one says so.
    """
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(0, str(ROOT / "lib"))
    from entity_check import article_item, article_links, is_a_subject

    seen = {candidate["entity"].lower()}
    parts: list[dict[str, Any]] = []

    def consider(name: str) -> None:
        if len(parts) >= limit or name.lower() in seen:
            return
        seen.add(name.lower())
        verdict = is_a_subject(name)
        if not verdict["subject"]:
            return
        parts.append({
            **candidate,
            "entity": name,
            "derived_from": candidate["entity"],
            "median_views": candidate["median_views"] // 2,
            "wikidata": verdict,
            "note": (f"split out of {candidate['entity']}, which is a "
                     f"container. The Shorts were about "
                     f"{candidate['entity']}; the evidence for this part is "
                     f"weaker and its score is halved to say so."),
        })

    for title in candidate.get("titles", []):
        for name in entities_in(title):
            consider(name)
    if len(parts) < limit:
        _, article = article_item(candidate["entity"])
        for name in article_links(article or candidate["entity"]):
            consider(name)
            if len(parts) >= limit:
                break
    return parts


#: Angle constraints the owner has set on a specific subject, keyed by
#: entity. These OVERRIDE the derived angle, because a derived angle is read
#: off Shorts titles and the owner knows what the channel has already made.
#:
#: The picker cannot know that run #1 covered the walking statues; the
#: ledger records the film, not its arguments.
ANGLE_CONSTRAINTS: dict[str, dict[str, Any]] = {
    "easter island": {
        "spine": [
            "rongorongo — the undeciphered script",
            "the collapse debate — ecocide against rats and the 1862 slave "
            "raids, both sides' best case",
            "the buried statue bodies",
            "the birdman cult at Orongo",
        ],
        "recap": {
            "what": "the walking statues",
            "max_seconds": 60,
            "where": "act 1",
            "why": "run #1 covered them; they are the hook the audience "
                   "arrives with and not the film",
        },
        # Named explicitly rather than parsed out of the prose above: the
        # depth check has to answer "can the film be made AS SPECIFIED",
        # and guessing which words in a sentence are the subjects is how it
        # would answer a different question.
        "entities": [
            "Rongorongo", "Orongo", "Rano Raraku", "Moai",
            "Polynesian rat", "Ahu Tongariki",
        ],
        "set_by": "owner, 2026-10-21",
    },
    "noah": {
        "spine": [
            "the same story in older cultures — Gilgamesh tablet XI, read by "
            "George Smith in 1872; Atrahasis; the Manu flood",
            "the Black Sea deluge hypothesis (Ryan & Pitman, 1997), and its "
            "critics",
            "the Ark's stated dimensions, and the Dutch full-scale build",
            "Durupınar and the Ararat expeditions — the claims, their best "
            "evidence, and the geological reading",
        ],
        # Measured with lib/source_depth.py on 2026-10-26, not guessed. The
        # two that do not clear are LISTED ANYWAY, so the brief's depth table
        # shows them failing rather than reporting 8 of 8 on a list that quietly
        # dropped them.
        "entities": [
            "Epic of Gilgamesh", "Flood Tablet",
            "George Smith (Assyriologist)", "Matsya", "Black Sea",
            "Noah's Ark", "Ark van Noach", "Mount Ararat",
            "Atrahasis", "Durupınar",
        ],
        "thin": {
            "Atrahasis": {
                "counted": 2.0,
                "shoot_instead": ["Cuneiform tablets", "Epic of Gilgamesh"],
                "why": "it is a text, and the text survives as tablets that "
                       "are photographed under other names",
            },
            "Durupınar": {
                "counted": 0.5,
                "shoot_instead": ["Mount Ararat", "public-domain satellite "
                                  "imagery (NASA/USGS), which is not in a "
                                  "Commons category under this name"],
                "why": "this is the one that matters: a boat-shaped formation "
                       "is a VISUAL claim, and an act built around a picture "
                       "that does not exist will talk over something else",
            },
        },
        "register": {
            "both_sides": "Believers and sceptics each get their strongest "
                          "case, stated at its strongest.",
            "evidence": "Nothing is stated as fact without a ledger entry.",
            "forbidden": ["sermon", "debunk"],
            "why": "the subject is why the same story exists across cultures. "
                   "A film that arrives knowing the answer is not "
                   "investigating, and either register loses the half of the "
                   "audience it was not written for.",
        },
        "titles": {
            "min_chars": 30,
            "max_chars": 45,
            "exemplars": ["The Flood Before the Bible",
                          "They Keep Finding the Ark"],
            "exemplars_note": "they are 26 and 25 characters, so neither "
                              "meets the 30-45 rule stated beside them — "
                              "the rule is the length, the exemplars are "
                              "the voice",
            "candidates": [
                "The Flood Story Before the Bible",
                "Everybody Keeps Finding Noah's Ark",
                "The Flood That Predates the Bible",
                "Four Cultures, One Flood Story",
            ],
        },
        "set_by": "owner, 2026-10-26",
    },
}


def angle_of(candidate: dict[str, Any]) -> dict[str, Any]:
    """What the audience actually responded to, in their own titles.

    The angle is not generated. It is the recurring claim across the Shorts
    that performed, quoted, because a brief that invents its own angle has
    thrown away the only evidence it had.
    """
    import statistics

    titles = candidate.get("titles", [])
    cleaned = [re.sub(r"\s*#\w+", "", t).strip() for t in titles if t]
    words = Counter(
        w.lower() for t in cleaned for w in re.findall(r"[A-Za-z']+", t)
        if w.lower() not in STOPWORDS and len(w) > 3)
    angle = {
        "recurring_words": [w for w, _ in words.most_common(8)],
        "source_titles": cleaned[:6],
        "claim": (f"The Shorts that performed on {candidate['entity']} keep "
                  f"returning to: " + ", ".join(w for w, _ in words.most_common(4))
                  + ". The film has to answer that, not introduce the subject."),
    }
    constraint = ANGLE_CONSTRAINTS.get(candidate["entity"].lower())
    if constraint:
        angle["constraint"] = constraint
        claim = "The open files are: " + "; ".join(constraint["spine"]) + ". "
        # A recap is only meaningful where a previous film already argued
        # something. A subject the channel has not covered has nothing to
        # recap, and reading constraint["recap"] unconditionally made the
        # second constraint anybody added a KeyError.
        recap = constraint.get("recap")
        if recap:
            claim += (
                f"{recap['what'].capitalize()} get a recap of no more than "
                f"{recap['max_seconds']} seconds in {recap['where']} and are "
                f"not the spine — {recap['why']}.")
        register = constraint.get("register")
        if register:
            claim += (f"{register['both_sides']} {register['evidence']} "
                      f"No {' or '.join(register['forbidden'])} register.")
        angle["claim"] = claim
    return angle


def write_brief(brief: dict[str, Any], out_dir: Path) -> Path:
    """One readable brief, for a human to choose from."""
    entity = brief["entity"]
    angle = brief["angle"]
    constraint = angle.get("constraint")
    lines = [
        f"# Brief — {entity}",
        "",
        f"**Median {brief['median_views']} views across {brief['shorts']} "
        f"Shorts** (best {brief['best_views']}, mean engagement "
        f"{brief['mean_engagement']}%). "
        + (brief.get("wikidata", {}).get("description", "") or ""),
        "",
        "## The angle",
        "",
        angle["claim"],
        "",
    ]
    if constraint:
        lines += [
            f"*Set by {constraint['set_by']}; it overrides what the Shorts "
            f"titles would suggest, because the picker cannot know what a "
            f"previous film already argued.*",
            "",
            "**The spine, in order:**", "",
        ]
        lines += [f"{n}. {item}" for n, item in enumerate(constraint["spine"], 1)]
        recap = constraint.get("recap")
        if recap:
            lines += [
                "",
                f"**{recap['what'].capitalize()}:** at most "
                f"{recap['max_seconds']}s, in {recap['where']}, as a recap. "
                f"{recap['why'].capitalize()}.",
            ]
        register = constraint.get("register")
        if register:
            lines += [
                "", "**Register.**",
                f"- {register['both_sides']}",
                f"- {register['evidence']}",
                f"- No {' or '.join(register['forbidden'])} register.",
                f"- {register['why'][:1].upper()}{register['why'][1:]}",
            ]
        thin = constraint.get("thin")
        if thin:
            lines += [
                "", "**Named in the spine, but thin on Commons.** Measured, "
                "not assumed — these will not clear the asset floor and the "
                "film has to be shot around them:", "",
                "| entity | counted | shoot instead | why |",
                "|---|---|---|---|",
            ]
            for name, row in thin.items():
                lines.append(
                    f"| {name} | {row['counted']} | "
                    f"{', '.join(row['shoot_instead'])} | {row['why']} |")
        lines.append("")
    lines += [
        "## Title candidates",
        "",
    ]
    lines += [f"{n}. {t}" for n, t in enumerate(brief["title_candidates"], 1)]
    lines += ["", "## The Shorts this came from", ""]
    for title, url in zip(angle["source_titles"], brief.get("urls", [])):
        lines.append(f"- {title}  \n  {url}")
    if brief.get("spine_entities"):
        clears = sum(1 for r in brief["spine_entities"] if r["clears"])
        lines += ["", "## The spine, and whether it can be sourced", "",
                  "These are the film's own subjects, named in the "
                  "constraint. The list below them is what the island's "
                  "article suggests, which is a different and weaker "
                  "question.", "",
                  "| entity | category files | counted | clears 8 |",
                  "|---|---|---|---|"]
        for row in brief["spine_entities"]:
            lines.append(f"| {row['entity']} | {row['category_files']} | "
                         f"{row['counted']} | "
                         f"{'yes' if row['clears'] else '**no**'} |")
        lines += ["", f"**{clears} of {len(brief['spine_entities'])}** spine "
                      f"entities clear {brief['min_assets']} usable assets.", ""]

    lines += ["", "## What the island's article suggests", "",
              "| entity | category files | counted | clears 8 |",
              "|---|---|---|---|"]
    for row in brief.get("entities", [])[:10]:
        lines.append(f"| {row['entity']} | {row['category_files']} | "
                     f"{row['counted']} | {'yes' if row['clears'] else '**no**'} |")
    lines += ["",
              f"Eligible: **{brief['deepest_six']}** of the top entities clear "
              f"{brief['min_assets']} usable assets each.", ""]
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"brief_{re.sub(r'[^a-z0-9]+', '_', entity.lower())}.md"
    dest.write_text("\n".join(lines))
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--candidates", type=int, default=12,
                    help="how many clusters to run the source-depth check on")
    ap.add_argument("--published", default=None)
    ap.add_argument("--blacklist", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--ledger-json", default=None,
                    help="read the ledger from a file instead of over SSH")
    ap.add_argument("--split", type=int, default=3,
                    help="how many sub-entities to take out of a container")
    ap.add_argument("--skip-depth", action="store_true",
                    help="rank only; do not count assets")
    args = ap.parse_args()

    published = Path(args.published) if args.published else ROOT / "artifacts" / "published.json"
    blacklist = Path(args.blacklist) if args.blacklist else ROOT / "artifacts" / "topic_blacklist.txt"

    ledger = (json.loads(Path(args.ledger_json).read_text())
              if args.ledger_json else read_ledger())
    print(f"ledger: {len(ledger)} Shorts")

    clusters = cluster(ledger)
    print(f"clusters: {len(clusters)} entities named by two or more")

    done, banned = already_made(published), blacklisted(blacklist)
    fresh = [c for c in clusters
             if c["entity"].lower() not in done and c["entity"].lower() not in banned]
    print(f"after skipping {len(clusters) - len(fresh)} already made or blacklisted: "
          f"{len(fresh)}")

    # Is it a thing, and is it FILM-SIZED? Cheap, and it removes most of what
    # clustering invents.
    from entity_check import is_a_subject

    subjects = []
    for candidate in fresh[:args.candidates * 3]:
        verdict = is_a_subject(candidate["entity"])
        if verdict["subject"]:
            subjects.append({**candidate, "wikidata": verdict})
        elif verdict.get("container"):
            # A CONTAINER IS SPLIT, NOT DROPPED. The audience that watched
            # two Shorts about Japan watched them for something inside
            # Japan, and throwing the cluster away throws that away too. The
            # sub-entities inherit the evidence and are marked derived, so a
            # brief never claims the Shorts were about it.
            print(f"   container: {candidate['entity'][:26]:26s} "
                  f"{verdict['why'][:46]}")
            for part in split_container(candidate, args.split):
                print(f"      -> {part['entity']}")
                subjects.append(part)
        else:
            print(f"   not a subject: {candidate['entity'][:28]:28s} "
                  f"{verdict['why'][:52]}")
        if len(subjects) >= args.candidates:
            break
    # Re-sorted, because a split inserts its parts where the container was
    # and a halved score has to rank where a halved score belongs. Without
    # this, two parts of Japan at 214 came above Noah at 366 purely because
    # Japan was second in the list.
    subjects.sort(key=lambda c: (c["median_views"], c["shorts"]), reverse=True)
    print(f"of those, {len(subjects)} name something "
          f"({sum(1 for c in subjects if c.get('derived_from'))} split out of "
          f"a container)")

    briefs = []
    if args.skip_depth:
        briefs = [{**c, "eligible": None} for c in subjects[:args.top]]
    else:
        from source_depth import check_cluster

        for candidate in subjects:
            depth = check_cluster(candidate, ledger,
                                  min_assets=MIN_ASSETS_PER_ENTITY,
                                  entities=ENTITIES_CHECKED)
            print(f"   {candidate['entity'][:34]:34s} "
                  f"median {candidate['median_views']:5d} views  "
                  f"depth {depth['deepest_six']}  "
                  f"{'ELIGIBLE' if depth['eligible'] else 'thin'}")
            if depth["eligible"]:
                angle = angle_of(candidate)
                constraint = angle.get("constraint")
                if constraint and constraint.get("entities"):
                    from source_depth import depth_of

                    depth["spine_entities"] = [
                        depth_of(name, MIN_ASSETS_PER_ENTITY)
                        for name in constraint["entities"]]
                titles = constraint.get("titles") if constraint else None
                briefs.append({
                    **candidate, **depth, "angle": angle,
                    # The owner's candidates when they set any: the generic
                    # shapes are read off the channel's Shorts and know
                    # nothing about THIS film's argument. For Noah they would
                    # also have produced "Noah: The Part Nobody Can Explain",
                    # which is the last film's title with a word swapped.
                    "title_candidates": (
                        titles["candidates"] if titles else
                        [shape.format(entity=candidate["entity"])
                         for shape in TITLE_SHAPES]),
                    **({"title_rule": {k: titles[k] for k in titles
                                       if k != "candidates"}}
                       if titles else {}),
                })
            if len(briefs) >= args.top:
                break

    out = Path(args.out) if args.out else ROOT / "artifacts" / "topic_briefs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated": datetime.now(timezone.utc).isoformat(),
        "ledger_size": len(ledger),
        "clusters_considered": len(fresh),
        "min_assets_per_entity": MIN_ASSETS_PER_ENTITY,
        "entities_checked": ENTITIES_CHECKED,
        "briefs": briefs,
    }, indent=1) + "\n")
    written = [write_brief(b, ROOT / "reports" / "briefs") for b in briefs
               if b.get("angle")]
    print(f"\n{len(briefs)} briefs -> {out.relative_to(ROOT)}")
    for path in written:
        print(f"   {path.relative_to(ROOT)}")
    return 0 if briefs else 1


if __name__ == "__main__":
    raise SystemExit(main())

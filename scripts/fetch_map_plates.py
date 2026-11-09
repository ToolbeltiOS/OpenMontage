#!/usr/bin/env python3
"""Historical map plates, for routes that are claims about the past.

A route drawn across a 2026 satellite relief is a claim about the present.
Drawn across the chart the people in the film were actually using, it is a
claim about them. These are those charts.

WHY THE LIST IS CURATED AND NOT A SEARCH
-----------------------------------------
A search for old maps of a region returns engravings, views, title pages and
frontispieces, and they all look like maps in a result list. The 1786 La
Perouse plate "Monuments et insulaires de l'ile de Paques" came back from
every query for a chart of Rapa Nui and is a LANDSCAPE PAINTING of people
sitting under the moai. It would have rendered as a route drawn across a
picture of a hillside. Each plate below was looked at before it was listed.

COVERAGE IS AUTHORED, AND SAYS SO
----------------------------------
`map_route` may only use a plate that actually covers the route, so every
plate carries a bounding box. Commons does not record one, and reading a
graticule off a scan is not something to do by guesswork, so the boxes are
AUTHORED from the known coordinates of the site each plate depicts, and the
manifest records them as authored rather than as measured off the plate.
They are deliberately tight: a plate claimed to cover more than it does puts
a route off the edge of the paper.

LIBRARY OF CONGRESS IS NOT REACHABLE FROM HERE. www.loc.gov answers scripted
requests with a Cloudflare interstitial and HTTP 403, so every plate below
comes from Wikimedia Commons. LoC remains the better source for US-held
survey sheets if someone fetches them by hand.

    python3 scripts/fetch_map_plates.py --dry-run
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEST = ROOT / "assets" / "library" / "plates"
UA = {"User-Agent": "OpenMontage/1.0 (documentary; contact via repo)"}

#: Seconds between Commons calls. The same floor the asset bank keeps.
MIN_INTERVAL = 3.0

#: The plates. `bbox` is (west, south, east, north) in degrees.
PLATES = [
    {
        "name": "rapa-nui-1797",
        "title": "File:Plan de l'Isle de Paque (1797).jpg",
        "region": "rapa-nui",
        # The whole island, which is what the chart shows, plus coastal
        # profiles below it. Island extent from its own coordinates.
        "bbox": (-109.47, -27.21, -109.19, -27.03),
        "coverage": "the island of Rapa Nui",
        "surveyed": 1786,
        "published": 1797,
        "style": "engraved admiralty chart, hachured relief",
    },
    {
        "name": "tiryns-1841",
        "title": "File:Tirynthe - Aldenhoven Ferdinand - 1841.jpg",
        "region": "argolid",
        # The citadel only: this is a site plan a few hundred metres across,
        # not a map of the Argolid.
        "bbox": (22.798, 37.598, 22.802, 37.602),
        "coverage": "the citadel of Tiryns",
        "surveyed": 1841,
        "published": 1841,
        "style": "engraved site plan, hachured walls",
    },
    {
        "name": "hawara-labyrinth-1849",
        "title": "File:Lepsius-Projekt tw 1-1-48.jpg",
        "region": "faiyum",
        # Lepsius's "Situationsplan des Labyrinths und seiner Pyramiden",
        # the Hawara complex at the mouth of the Faiyum.
        "bbox": (30.88, 29.26, 30.92, 29.30),
        "coverage": "the Hawara pyramid and labyrinth",
        "surveyed": 1843,
        "published": 1849,
        "style": "lithographed survey plan, tinted relief",
    },
]


def api(**params) -> Any:
    params.setdefault("format", "json")
    params.setdefault("action", "query")
    url = ("https://commons.wikimedia.org/w/api.php?"
           + urllib.parse.urlencode(params))
    with urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


def info(titles: list[str]) -> dict[str, dict]:
    d = api(titles="|".join(titles), prop="imageinfo",
            iiprop="url|size|extmetadata",
            iiextmetadatafilter="LicenseShortName|Artist|UsageTerms")
    out = {}
    for page in d.get("query", {}).get("pages", {}).values():
        ii = (page.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        out[page.get("title", "")] = {
            "url": ii.get("url"),
            "width": ii.get("width"),
            "height": ii.get("height"),
            "licence": (meta.get("LicenseShortName") or {}).get("value", ""),
            "artist": re.sub(r"<[^>]+>", "",
                             (meta.get("Artist") or {}).get("value", "")).strip(),
        }
    return out


def main() -> int:
    import lib.library_licence as licence

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    DEST.mkdir(parents=True, exist_ok=True)
    meta = info([p["title"] for p in PLATES])
    entries = []
    for plate in PLATES:
        got = meta.get(plate["title"])
        if not got or not got.get("url"):
            raise SystemExit(f"{plate['title']}: not found on Commons")
        dest = DEST / f"{plate['name']}.jpg"
        e = {
            "name": plate["name"],
            "kind": "map-plate",
            "provider": "Wikimedia Commons",
            "provider_key": "commons",
            "licence": got["licence"],
            "licence_statement": "https://commons.wikimedia.org/wiki/"
                                 + urllib.parse.quote(plate["title"]),
            "licence_recorded": dt.date.today().isoformat(),
            "attribution": got["artist"],
            "url": "https://commons.wikimedia.org/wiki/"
                   + urllib.parse.quote(plate["title"]),
            "path": str(dest.relative_to(ROOT)),
            "title": plate["title"],
            "region": plate["region"],
            "bbox": list(plate["bbox"]),
            "bbox_basis": "authored from the site's known coordinates, not "
                          "read off the plate's graticule",
            "coverage": plate["coverage"],
            "surveyed": plate["surveyed"],
            "published": plate["published"],
            "style": plate["style"],
            "pixels": f"{got['width']}x{got['height']}",
        }
        problems = licence.check(e)
        if problems:
            raise SystemExit(f"REFUSED {plate['name']}: " + "; ".join(problems))
        entries.append(e)
        print(f"  {plate['name']:<22} {got['licence']:<16} "
              f"{got['width']}x{got['height']}  {got['artist'][:34]}")
        if args.dry_run or dest.exists():
            continue
        # THROTTLED AND RETRIED. Commons answers a burst with HTTP 429 and
        # the third plate was refused on the first run; `lib/asset_bank.py`
        # keeps a 3-second floor between calls for the same reason. A plate
        # is tens of megabytes, so a refusal here costs the whole fetch.
        for attempt in range(1, 5):
            time.sleep(MIN_INTERVAL)
            try:
                with urllib.request.urlopen(
                        urllib.request.Request(got["url"], headers=UA),
                        timeout=300) as r:
                    dest.write_bytes(r.read())
                break
            except urllib.error.HTTPError as err:
                if err.code != 429 or attempt == 4:
                    raise
                wait = MIN_INTERVAL * 2 ** attempt
                print(f"    429, waiting {wait:.0f}s", flush=True)
                time.sleep(wait)

    if args.dry_run:
        print(f"\n  {len(entries)} plates would be written")
        return 0

    path = ROOT / "assets" / "library" / "manifest.json"
    blob = json.loads(path.read_text())
    by = {a["path"]: a for a in blob["assets"]}
    for e in entries:
        by[e["path"]] = e
    blob["assets"] = sorted(by.values(), key=lambda a: a["path"])
    path.write_text(json.dumps(blob, indent=1) + "\n")
    print(f"\n  manifest: {len(by)} assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

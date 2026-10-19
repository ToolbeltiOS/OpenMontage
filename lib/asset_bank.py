#!/usr/bin/env python3
"""Build a project asset bank from Wikimedia category listings.

Why category listing and not search: Commons full-text search drifts
semantically — it returned a coat of arms for "Egyptian granite sarcophagus",
sepoys at rifle drill for "copper tube drill", and a WWI machine gun corps for
"Egyptian sledge". Category membership is curated by people, so it cannot
drift that way. The shipped stock_sources/wikimedia.py still uses search; this
does not.

Method, per named subject:
  1. list=categorymembers  (files, plus one level of subcategory descent)
  2. prop=imageinfo        (url, size, extmetadata -> artist + licence)
  3. reject any filename that carries no subject term
  4. rank by pixel count
  5. download the top N, rejecting near-uniform frames (grayscale std < 18)

Everything kept is recorded with its provenance and licence, because a third
of these are share-alike and the credit block is generated from this file.

Throttled deliberately: an earlier pass hammered the API, collected 429s, and
— because the client swallowed errors into empty results — reported every
category as empty. Errors here are surfaced, never absorbed.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = ("wak3upsociety-documentary/1.0 "
      "(https://github.com/ToolbeltiOS/OpenMontage; asset bank) "
      "python-urllib")
MIN_INTERVAL = 3.0          # seconds between API calls (Commons throttles hard)
MIN_STDDEV = 18.0           # grayscale std below this is a blank/near-uniform frame
MIN_BANK_LONG_EDGE = 3000   # nothing smaller is bankable: it cannot fill 1080p
                            # with a push, and yields no derived framings
TOP_N = 8
POOL_N = 20          # downloaded per subject; TOP_N are chosen from it
MAX_PER_SERIES = 3   # files one upload session may contribute to the pool

_last_call = 0.0


def api(params: dict) -> dict:
    """One throttled call. Raises on error rather than returning {}."""
    global _last_call
    wait = MIN_INTERVAL - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    params = {**params, "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                _last_call = time.time()
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry = int(e.headers.get("Retry-After", "5"))
                print(f"    429; sleeping {retry}s", flush=True)
                time.sleep(retry + 1)
                continue
            raise
        except Exception as e:
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def category_files(category: str, descend: bool = True) -> list[str]:
    titles, subcats = [], []
    cont = {}
    while True:
        d = api({"action": "query", "list": "categorymembers",
                 "cmtitle": category, "cmlimit": "500",
                 "cmtype": "file|subcat", **cont})
        for m in d.get("query", {}).get("categorymembers", []):
            (subcats if m["title"].startswith("Category:") else titles).append(m["title"])
        if "continue" in d:
            cont = d["continue"]
        else:
            break
    if descend:
        for sc in subcats[:6]:
            titles += category_files(sc, descend=False)
    return titles


def imageinfo(titles: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(titles), 40):
        d = api({"action": "query", "titles": "|".join(titles[i:i + 40]),
                 "prop": "imageinfo",
                 "iiprop": "url|size|extmetadata|mime"})
        for pg in d.get("query", {}).get("pages", []):
            ii = (pg.get("imageinfo") or [{}])[0]
            if not ii.get("url"):
                continue
            meta = ii.get("extmetadata", {})
            out.append({
                "title": pg["title"],
                "url": ii["url"],
                "descriptionurl": ii.get("descriptionurl"),
                "width": ii.get("width", 0),
                "height": ii.get("height", 0),
                "mime": ii.get("mime", ""),
                "artist": re.sub("<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip(),
                "licence": (meta.get("LicenseShortName") or {}).get("value", ""),
                "credit": re.sub("<[^>]+>", "", (meta.get("Credit") or {}).get("value", "")).strip(),
            })
    return out


# A site category contains the site's museum. Category:Mycenae returned six
# vitrines of pottery before this list existed, because "Mycenae" is in the
# filename of a museum photograph exactly as it is in the filename of the Lion
# Gate. Negative terms are per-project, not universal — a film about pottery
# would want the opposite list.
DEFAULT_EXCLUDE = [
    "museum", "exhibit", "vitrine", "display case", "showcase", "gallery of",
    "vase", "pottery", "sherd", "krater", "amphora", "figurine", "jewellery",
    "jewelry", "coin", "stamp", "poster", "logo", "map of", "diagram", "plan of",
    "model of", "reconstruction", "replica", "book", "cover", "sign", "plaque",
    "panel", "information board", "ticket", "flag", "portrait of",
]


def series_key(title: str) -> str:
    """Collapse a filename to the upload session it came from.

    Stonehenge has 740 usable files, and the twenty largest were all one
    photographer's afternoon: "Amesbury, Stonehenge Wiltshire 1000097
    20230817 0001", 0002, 0003... Ranking by resolution hands the whole pool
    to whoever shot the site with the best camera, and no amount of
    diversity selection inside that pool can recover a second viewpoint.
    Stripping digits leaves the series, which is what needs capping.
    """
    t = re.sub(r"\d+", "", title.lower().replace("_", " "))
    t = re.sub(r"[^a-z ]+", " ", t)
    return " ".join(t.split())[:40]


def filename_has_term(title: str, terms: list[str], exclude: list[str] | None = None) -> bool:
    """Match on word boundaries, not substrings.

    "cart" as a substring matches "cartes postales", so a subject looking for
    ox carts banked eight postcards from Laos and Indochina. Multi-word terms
    still match as phrases; single words must stand alone.
    """
    t = " " + title.lower().replace("_", " ").replace("-", " ") + " "
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = " " + " ".join(t.split()) + " "
    if any(f" {x.lower().strip()} " in t or (" " in x and x.lower() in t)
           for x in (exclude if exclude is not None else DEFAULT_EXCLUDE)):
        return False
    for term in terms:
        term = term.lower().strip()
        if " " in term:
            if term in t:
                return True
        elif f" {term} " in t:
            return True
    return False


def signature(path: str, n: int = 16) -> "np.ndarray | None":
    """A tiny grayscale thumbnail, used to spot near-duplicate photographs."""
    import numpy as np
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf",
                          f"format=gray,scale={n}:{n}", "-frames:v", "1",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    if len(raw) < n * n:
        return None
    a = np.frombuffer(raw[: n * n], dtype=np.uint8).astype(np.float32)
    a -= a.mean()
    norm = np.linalg.norm(a)
    return a / norm if norm > 1e-6 else None


def too_similar(sig, kept_sigs, threshold: float = 0.92) -> float | None:
    """Correlation against everything already kept for this subject.

    A category often holds several frames of one photograph — Mycenae returned
    three shots of the same Lion Gate plate from one DPLA scan. Eight assets
    that are visually three do not fix repetition, they hide it.
    """
    import numpy as np
    for other in kept_sigs:
        c = float(np.dot(sig, other))
        if c > threshold:
            return c
    return None


def grayscale_stddev(path: str) -> float:
    import subprocess
    out = subprocess.run(
        ["ffmpeg", "-nostats", "-v", "error", "-i", path, "-vf",
         "format=gray,scale=160:-1,signalstats", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    # signalstats does not print on a still through -f null on every build;
    # fall back to a histogram spread via ffprobe-free numpy decode
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf",
                          "format=gray,scale=160:-2", "-frames:v", "1",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    if not raw:
        return 0.0
    a = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
    return float(a.std())


def download(url: str, dest: str) -> bool:
    global _last_call
    wait = MIN_INTERVAL - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as fh:
            fh.write(r.read())
        _last_call = time.time()
        return True
    except Exception as e:
        print(f"    download failed: {e}", flush=True)
        return False


def build(subjects: dict, out_dir: str, bank_path: str, top_n: int = TOP_N) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    bank = json.load(open(bank_path)) if os.path.exists(bank_path) else {"subjects": {}}

    for name, spec in subjects.items():
        if name in bank["subjects"] and len(bank["subjects"][name]["assets"]) >= top_n:
            print(f"{name}: already banked ({len(bank['subjects'][name]['assets'])})", flush=True)
            continue
        print(f"{name}: listing {len(spec['categories'])} categories", flush=True)
        titles: list[str] = []
        for cat in spec["categories"]:
            try:
                got = category_files(cat)
                print(f"    {cat}: {len(got)} files", flush=True)
                titles += got
            except Exception as e:
                print(f"    {cat}: ERROR {e}", flush=True)
        titles = list(dict.fromkeys(titles))
        if not titles:
            print(f"    {name}: NO FILES — category names are probably wrong", flush=True)
            bank["subjects"][name] = {"terms": spec["terms"], "categories": spec["categories"],
                                      "assets": [], "note": "no category members found"}
            continue

        try:
            infos = imageinfo(titles)
        except Exception as e:
            print(f"    {name}: imageinfo ERROR {e}", flush=True)
            infos = []
        raw_n = len(infos)
        infos = [i for i in infos if i["mime"].startswith("image/")
                 and filename_has_term(i["title"], spec["terms"],
                                       spec.get("exclude", DEFAULT_EXCLUDE))
                 and i["width"] * i["height"] > 0]
        print(f"    {raw_n} files described -> {len(infos)} pass filename + mime", flush=True)
        infos.sort(key=lambda i: i["width"] * i["height"], reverse=True)

        # Download a pool, then choose a DIVERSE subset from it.
        #
        # Ranking by pixel count alone returns the same photograph repeatedly.
        # Stonehenge's top eight were eight frames of the monument from one
        # distance and angle on one overcast afternoon: different files, one
        # shot. Correlation rejection does not catch it, because the clouds
        # differ enough to pass.
        #
        # So keep the sharpest candidate, then repeatedly add whichever
        # remaining candidate is LEAST like everything kept so far. That
        # selects for range of framing and light, which is what makes a bank
        # of eight worth eight slots.
        import numpy as np

        pool = []
        series_count: dict[str, int] = {}
        for info in infos:
            if len(pool) >= POOL_N:
                break
            sk = series_key(info["title"])
            if series_count.get(sk, 0) >= MAX_PER_SERIES:
                continue
            # Commons appends ?utm_source=... to imageinfo URLs, so splitext on
            # the whole URL returns a tracking-parameter tail, not ".jpg".
            url_path = urllib.parse.urlparse(info["url"]).path
            ext = os.path.splitext(url_path)[1].lower() or ".jpg"
            if ext not in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"):
                print(f"    skip (ext {ext}): {info['title'][:54]}", flush=True)
                continue
            aid = f"wm_{abs(hash(info['title'])) % 10**9}"
            dest = os.path.join(out_dir, aid + ".jpg")
            if not os.path.exists(dest):
                if not download(info["url"], dest):
                    continue
            if max(info["width"], info["height"]) < MIN_BANK_LONG_EDGE:
                print(f"    reject (too small {info['width']}x{info['height']}): "
                      f"{info['title'][:48]}", flush=True)
                if os.path.exists(dest):
                    os.remove(dest)
                continue
            sd = grayscale_stddev(dest)
            if sd < MIN_STDDEV:
                print(f"    reject (flat, std {sd:.1f}): {info['title'][:54]}", flush=True)
                os.remove(dest)
                continue
            sig = signature(dest)
            if sig is None:
                continue
            series_count[sk] = series_count.get(sk, 0) + 1
            pool.append({"info": info, "aid": aid, "dest": dest, "sd": sd, "sig": sig})

        # Keep in resolution order, rejecting anything that looks like one
        # already kept.
        #
        # Two failed approaches are worth recording. Ranking by pixel count
        # alone returned eight frames of Stonehenge from one angle on one
        # afternoon — different files, one shot. Selecting for maximum
        # diversity instead returned a car park, a tourist and some scrubland:
        # genuinely varied, genuinely unusable, because "least like the others"
        # rewards whatever is least like a photograph of the subject.
        #
        # Resolution order tracks "someone took this deliberately". The
        # correlation gate at 0.85 — stricter than the 0.92 that let the
        # Stonehenge aerials through — removes the near-twins without reaching
        # for the junk at the bottom of the category.
        kept = []
        chosen = []
        for cand in pool:
            if len(kept) >= top_n:
                break
            if chosen:
                worst = max(float(np.dot(cand["sig"], k["sig"])) for k in chosen)
                if worst > 0.85:
                    print(f"    reject (near-duplicate r={worst:.2f}): "
                          f"{cand['info']['title'][:50]}", flush=True)
                    continue
            chosen.append(cand)
            info = cand["info"]
            kept.append({
                "asset_id": cand["aid"], "path": cand["dest"], "subject": name,
                "title": info["title"], "page": info["descriptionurl"],
                "width": info["width"], "height": info["height"],
                "artist": info["artist"], "licence": info["licence"],
                "credit": info["credit"], "stddev": round(cand["sd"], 1),
                "provider": "wikimedia",
            })
            print(f"    keep {len(kept)}/{top_n}: {info['width']}x{info['height']} "
                  f"{info['title'][:52]}", flush=True)
        pool = [c for c in pool if c not in chosen]
        for leftover in pool:
            if os.path.exists(leftover["dest"]):
                os.remove(leftover["dest"])

        bank["subjects"][name] = {"terms": spec["terms"], "categories": spec["categories"],
                                  "assets": kept}
        json.dump(bank, open(bank_path, "w"), indent=1, ensure_ascii=False)

    total = sum(len(v["assets"]) for v in bank["subjects"].values())
    print(f"\nbank: {len(bank['subjects'])} subjects, {total} assets")
    return bank


if __name__ == "__main__":
    subjects = json.load(open(sys.argv[1]))
    build(subjects, sys.argv[2], sys.argv[3])

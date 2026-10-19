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
TOP_N = 8

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


def filename_has_term(title: str, terms: list[str]) -> bool:
    t = title.lower().replace("_", " ")
    return any(term.lower() in t for term in terms)


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
                 and filename_has_term(i["title"], spec["terms"])
                 and i["width"] * i["height"] > 0]
        print(f"    {raw_n} files described -> {len(infos)} pass filename + mime", flush=True)
        infos.sort(key=lambda i: i["width"] * i["height"], reverse=True)

        kept = []
        kept_sigs: list = []
        for info in infos:
            if len(kept) >= top_n:
                break
            # Commons appends query parameters to imageinfo URLs
            # (?utm_source=...), so splitext on the whole URL returns the tail
            # of a tracking parameter, not the file extension. Every candidate
            # was being skipped by this check, silently, and the subject came
            # back empty from 283 perfectly good files. Parse the path.
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
                if ext not in (".jpg", ".jpeg"):
                    import subprocess
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", dest,
                                    "-q:v", "2", dest + ".jpg"], check=False)
                    if os.path.exists(dest + ".jpg"):
                        os.replace(dest + ".jpg", dest)
            sd = grayscale_stddev(dest)
            if sd < MIN_STDDEV:
                print(f"    reject (flat, std {sd:.1f}): {info['title'][:60]}", flush=True)
                os.remove(dest)
                continue
            sig = signature(dest)
            if sig is not None:
                c = too_similar(sig, kept_sigs)
                if c is not None:
                    print(f"    reject (near-duplicate, r={c:.2f}): "
                          f"{info['title'][:52]}", flush=True)
                    os.remove(dest)
                    continue
                kept_sigs.append(sig)
            kept.append({
                "asset_id": aid, "path": dest, "subject": name,
                "title": info["title"], "page": info["descriptionurl"],
                "width": info["width"], "height": info["height"],
                "artist": info["artist"], "licence": info["licence"],
                "credit": info["credit"], "stddev": round(sd, 1),
                "provider": "wikimedia",
            })
            print(f"    keep {len(kept)}/{top_n}: {info['width']}x{info['height']} "
                  f"{info['title'][:56]}", flush=True)
        bank["subjects"][name] = {"terms": spec["terms"], "categories": spec["categories"],
                                  "assets": kept}
        json.dump(bank, open(bank_path, "w"), indent=1, ensure_ascii=False)

    total = sum(len(v["assets"]) for v in bank["subjects"].values())
    print(f"\nbank: {len(bank['subjects'])} subjects, {total} assets")
    return bank


if __name__ == "__main__":
    subjects = json.load(open(sys.argv[1]))
    build(subjects, sys.argv[2], sys.argv[3])

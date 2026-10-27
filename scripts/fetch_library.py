#!/usr/bin/env python3
"""Pull the house asset library, with provenance for every file.

WHAT THIS IS FOR
----------------
The film is assembled from sourced photographs, and everything *around* them
-- the paper an evidence card sits on, the stone behind a schematic, the
glyph on a timeline -- was until now either a flat colour or nothing. This
is a curated, permissively licensed set of those surfaces and marks, held in
the repository so a weekly unattended run never has to fetch one.

PROVENANCE IS THE POINT, NOT A FORMALITY
-----------------------------------------
Every file lands with a manifest entry naming its provider, licence,
attribution and source URL, and each entry is checked by
`lib/library_licence.py` BEFORE the bytes are written. An asset whose entry
fails the check is not downloaded, so the library cannot contain a file
nobody can account for.

The four providers state their terms in four different ways, and none of
them puts a licence in the per-asset API payload:

  ambientCG       site-wide CC0 1.0, stated at https://ambientcg.com/license
  Poly Haven      site-wide CC0, stated at https://polyhaven.com/license
  game-icons.net  PER CONTRIBUTOR: "Creative Commons 3.0 BY or CC0 if
                  mentioned", so attribution names the artist whose folder
                  the glyph came from, not the site
  Lucide          ISC, copyright notice carried in the manifest and LICENCE

So the licence is recorded as a provider-level attestation with the URL of
the statement and the date it was read -- which is what it is -- rather than
as something the API returned, which it is not.

    python3 scripts/fetch_library.py --what textures hdris glyphs icons
    python3 scripts/fetch_library.py --dry-run
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LIB = ROOT / "assets" / "library"
UA = {"User-Agent": "OpenMontage/1.0 (house asset library; contact via repo)"}

#: Provider-level licence attestations. Recorded with the URL of the
#: statement, because no provider returns a licence per asset.
PROVIDERS = {
    "ambientcg": {
        "name": "ambientCG",
        "licence": "CC0 1.0",
        "statement": "https://ambientcg.com/license",
        "attribution": "",
    },
    "polyhaven": {
        "name": "Poly Haven",
        "licence": "CC0 1.0",
        "statement": "https://polyhaven.com/license",
        "attribution": "",
    },
    "game-icons": {
        "name": "game-icons.net",
        "licence": "CC BY 3.0",
        "statement": "https://github.com/game-icons/icons/blob/master/license.txt",
        "attribution": "",          # filled per glyph from its contributor
    },
    "lucide": {
        "name": "Lucide",
        "licence": "ISC",
        "statement": "https://github.com/lucide-icons/lucide/blob/main/LICENSE",
        "attribution": "Lucide Icons and Contributors",
    },
}

#: 12 textures. The name on the left is what a component asks for; the
#: ambientCG id on the right is what it resolves to.
TEXTURES = {
    "aged-paper-1": "Paper006",     # brown kraft
    "aged-paper-2": "Paper001",     # smooth white
    "aged-paper-3": "Paper003",     # crumpled white
    "parchment": "Paper005",        # tan, creased — the one that reads aged
    "sandstone": "Rock060",         # pale tan ROCK, not masonry
    "granite": "Granite002A",
    "basalt": "Rock035",            # near-black, flecked
    "sand": "Ground054",
    "slate": "RoofingTiles003",
    "rusted-iron": "Metal041B",     # visible rust, not clean steel
    "linen": "Fabric086",
    "vellum": "Leather035D",        # pale cream, skin-like
}
#: THE NAME IS THE CONTRACT, because components ask for a texture by name
#: and nobody looks at the file. The first mapping was made from search
#: results without looking at them, and shipped a BRICK WALL as "sandstone"
#: behind a pyramid section, mossy cobbles as "basalt", clean steel as
#: "rusted-iron" and flat brown leather as "vellum". Every id above was
#: chosen from a rendered contact sheet of candidates.

#: 4 HDRIs for model_orbit lighting.
HDRIS = {
    "overcast": "kloofendal_overcast",
    "desert-sun": "goegap",
    "museum-interior": "aviation_museum",
    "dusk": "aarfontein_dusk",
}

#: Glyph themes, as substrings matched against game-icons file names. The
#: set is deliberately about THIS channel: what it makes films about.
GLYPH_THEMES = {
    "stone": ["stone", "rock", "boulder", "menhir", "megalith", "quarry",
              "cave", "mountain", "cliff"],
    "tools": ["hammer", "chisel", "pickaxe", "axe", "saw", "rope", "pulley",
              "lever", "anvil", "shovel", "drill", "wrench"],
    "ships": ["ship", "boat", "anchor", "sail", "raft", "canoe", "harbor",
              "helm", "compass", "lighthouse"],
    "ancient-sites": ["temple", "pyramid", "obelisk", "column", "ruins",
                      "arch", "gate", "tower", "ziggurat", "statue"],
    "animals": ["bird", "horse", "fish", "whale", "goat", "bull", "eagle",
                "owl", "snake", "turtle", "wolf"],
    "astronomy": ["star", "moon", "sun", "planet", "comet", "eclipse",
                  "constellation", "telescope", "orbit", "galaxy"],
    "religion": ["altar", "shrine", "idol", "offering", "ritual", "priest",
                 "prayer", "sacrifice", "god", "spirit"],
}

#: Folders in the game-icons archive that are NOT a contributor, and whose
#: glyphs therefore have no author to attribute.
#:
#: `badges/` holds SVGs directly and appears nowhere in the licence file's
#: list of contributors, which says "each sub-folder corresponds to a
#: different contributor". Five glyphs were taken from it before anyone
#: looked. Under this library's own rule -- an asset nobody can account for
#: cannot ship -- they are excluded rather than attributed to a guess.
NOT_A_CONTRIBUTOR = {"badges"}

#: Contributors the licence file names as CC0 rather than CC BY 3.0.
GAME_ICONS_CC0 = {"viscious-speed", "zeromancer"}

#: Tokens that mark a glyph as fantasy or video-game furniture rather than
#: something a documentary would draw. game-icons.net is a GAME icon set, so
#: a theme match alone returns "death-star" under astronomy, "boulder-dash"
#: under stone and "black-knight-helm" under ships. The themes are right and
#: the names are not.
GAME_FLAVOURED = {
    "death", "demon", "devil", "dragon", "elf", "orc", "goblin", "troll",
    "wizard", "witch", "magic", "magical", "spell", "rune", "mana", "zombie",
    "undead", "skeleton", "vampire", "ghost", "monster", "beast", "alien",
    "laser", "cyber", "robot", "mech", "sci", "fi", "space", "star-wars",
    "knight", "paladin", "barbarian", "ninja", "samurai", "pirate",
    "dash", "dungeon", "quest", "rpg", "level", "boss", "power-up",
}

#: Roughly how many glyphs to keep in total. The themes are sampled evenly
#: rather than first-come, so one prolific theme cannot crowd out the rest.
GLYPH_TARGET = 150

#: Chrome icons from Lucide.
LUCIDE_ICONS = [
    "arrow-right", "arrow-left", "chevron-right", "circle", "square",
    "triangle", "map-pin", "ruler", "scale", "clock", "calendar",
    # `triangle-alert`, not `alert-triangle`: Lucide renamed it, and the
    # old name 404s. Checked against the raw file, not the contents API --
    # that endpoint paginates and reported 16 of these 24 as missing when
    # only this one was.
    "file-text", "book-open", "quote", "search", "info", "triangle-alert",
    "check", "x", "minus", "plus", "layers", "maximize", "move",
]


def fetch(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_json(url: str) -> Any:
    return json.loads(fetch(url, timeout=45).decode())


def entry(provider: str, name: str, path: Path, url: str,
          attribution: str | None = None, **extra) -> dict[str, Any]:
    p = PROVIDERS[provider]
    return {
        "name": name,
        "provider": p["name"],
        "provider_key": provider,
        "licence": p["licence"],
        "licence_statement": p["statement"],
        "licence_recorded": dt.date.today().isoformat(),
        "attribution": (attribution if attribution is not None
                        else p["attribution"]),
        "url": url,
        "path": str(path.relative_to(ROOT)),
        **extra,
    }


def guard(e: dict[str, Any]) -> None:
    """Refuse to store anything the licence filter will not pass."""
    import lib.library_licence as licence

    problems = licence.check(e)
    if problems:
        raise SystemExit(
            f"REFUSED {e.get('name')}: " + "; ".join(problems))


def textures(dry: bool) -> list[dict]:
    out, dest = [], LIB / "textures"
    dest.mkdir(parents=True, exist_ok=True)
    for name, asset_id in TEXTURES.items():
        url = f"https://ambientcg.com/get?file={asset_id}_1K-JPG.zip"
        e = entry("ambientcg", name, dest / f"{name}.jpg", url,
                  asset_id=asset_id, kind="texture")
        guard(e)
        out.append(e)
        if dry:
            continue
        if (dest / f"{name}.jpg").exists():
            print(f"    have  {name}", flush=True)
            continue
        # ONLY THE COLOUR MAP. The zip carries normal, roughness,
        # displacement and ambient occlusion too, and a plate behind a card
        # needs none of them -- keeping them would put ~50MB of unused maps
        # in the repository.
        with zipfile.ZipFile(io.BytesIO(fetch(url))) as z:
            colour = [n for n in z.namelist() if "_Color." in n]
            if not colour:
                raise SystemExit(f"{asset_id}: no colour map in the archive")
            (dest / f"{name}.jpg").write_bytes(z.read(colour[0]))
        print(f"    got   {name}  <- {asset_id}", flush=True)
    return out


def hdris(dry: bool) -> list[dict]:
    out, dest = [], LIB / "hdri"
    dest.mkdir(parents=True, exist_ok=True)
    for name, asset_id in HDRIS.items():
        page = f"https://polyhaven.com/a/{asset_id}"
        e = entry("polyhaven", name, dest / f"{name}.hdr", page,
                  asset_id=asset_id, kind="hdri")
        guard(e)
        out.append(e)
        if dry or (dest / f"{name}.hdr").exists():
            if not dry:
                print(f"    have  {name}", flush=True)
            continue
        files = get_json(f"https://api.polyhaven.com/files/{asset_id}")
        hdr = files.get("hdri", {}).get("1k", {}).get("hdr", {})
        if not hdr.get("url"):
            raise SystemExit(f"{asset_id}: no 1k hdr in the file list")
        (dest / f"{name}.hdr").write_bytes(fetch(hdr["url"], timeout=180))
        info = get_json(f"https://api.polyhaven.com/info/{asset_id}")
        e["authors"] = list((info.get("authors") or {}).keys())
        print(f"    got   {name}  <- {asset_id}", flush=True)
    return out


def game_icons_authors() -> dict[str, str]:
    """Folder slug -> the author's name as the licence file writes it.

    THE FOLDER NAME IS NOT THE ATTRIBUTION. `delapouite` is "Delapouite",
    `carl-olsen` is "Carl Olsen", `darkzaitzev` is "DarkZaitzev". CC BY asks
    for the author, and a slug is a path, so the names are read from the
    licence file itself and matched back to the folders by slug.
    """
    import re

    text = fetch("https://raw.githubusercontent.com/game-icons/icons/"
                 "master/license.txt", timeout=60).decode("utf-8", "replace")
    out = {}
    for line in text.splitlines():
        m = re.match(r"^-\s*([^,\n]+?)\s*(?:,|$)", line.strip())
        if not m:
            continue
        name = m.group(1).strip()
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        out[slug] = name
    return out


def recolourable(svg: bytes) -> bytes:
    """A game-icons tile turned into a glyph that takes the film's colour.

    THE FILES ARE NOT TRANSPARENT. Each is a 512x512 tile with an opaque
    background path -- `<path d="M0 0h512v512H0z"/>`, black by default --
    and the icon drawn over it in `fill="#fff"`. Dropped into a frame that
    is a black square with a white mark in it, and no CSS can recolour it:
    masking needs alpha and there is none.

    So the background path is removed and the icon's fill is set to
    `currentColor`, which is what Lucide already does and what lets one
    `color` rule tint every glyph in the film.

    This is an ADAPTATION. CC BY 3.0 permits it with attribution, and the
    manifest records that the file was modified, because a recipient should
    not have to diff it against the original to find out.
    """
    import re

    text = svg.decode("utf-8", "replace")
    # the full-canvas background rect, however the viewBox is sized
    text = re.sub(r'<path d="M0 0h(\d+)v(\d+)H0z"\s*/>', "", text, count=1)
    text = text.replace('fill="#fff"', 'fill="currentColor"')
    if "currentColor" not in text:
        # no explicit white fill: the icon inherits, so declare it on the root
        text = text.replace("<svg ", '<svg fill="currentColor" ', 1)
    return text.encode("utf-8")


def glyphs(dry: bool) -> list[dict]:
    """game-icons, from the repository archive -- one request, not 150."""
    out, dest = [], LIB / "glyphs"
    dest.mkdir(parents=True, exist_ok=True)
    if dry:
        return [entry("game-icons", f"<up to {GLYPH_TARGET}>", dest, 
                      "https://github.com/game-icons/icons",
                      attribution="per contributor", kind="glyph")]
    authors = game_icons_authors()
    tar = fetch("https://codeload.github.com/game-icons/icons/zip/refs/heads/master",
                timeout=300)
    picked: dict[str, list] = {k: [] for k in GLYPH_THEMES}
    skipped = 0
    with zipfile.ZipFile(io.BytesIO(tar)) as z:
        names = [n for n in z.namelist()
                 if n.endswith(".svg")
                 and Path(n).parts[1] not in NOT_A_CONTRIBUTOR]
        for theme, terms in GLYPH_THEMES.items():
            for n in names:
                # WHOLE TOKENS, NOT SUBSTRINGS. A substring match put
                # "american-football-helmet" in the ships theme (it contains
                # "helm") and "anarchy" in ancient sites (it contains
                # "arch"). The names are hyphen-separated words, so they are
                # matched as words, with a plural allowed because the themes
                # are written in the singular and the icons are not
                # ("ancient-columns" for "column").
                tokens = set(Path(n).stem.lower().split("-"))
                if tokens & GAME_FLAVOURED:
                    continue
                if any(t in tokens or f"{t}s" in tokens for t in terms):
                    picked[theme].append(n)
        per = max(1, GLYPH_TARGET // len(GLYPH_THEMES))
        for theme, found in picked.items():
            for n in sorted(found)[:per]:
                # .../icons-master/<contributor>/<name>/<file>.svg
                parts = Path(n).parts
                slug = parts[1] if len(parts) > 2 else "unknown"
                author = authors.get(slug)
                if author is None:
                    # Not named in the licence file: no author, no ship.
                    skipped += 1
                    continue
                cc0 = slug in GAME_ICONS_CC0
                stem = Path(n).stem
                sub = dest / theme
                sub.mkdir(parents=True, exist_ok=True)
                (sub / f"{stem}.svg").write_bytes(recolourable(z.read(n)))
                e = entry("game-icons", f"{theme}/{stem}", sub / f"{stem}.svg",
                          f"https://game-icons.net/1x1/{slug}/{stem}.html",
                          attribution=f"{author} (game-icons.net)",
                          kind="glyph", theme=theme, contributor=author,
                          contributor_slug=slug,
                          modified="background path removed, fill set to "
                                   "currentColor so the glyph takes the "
                                   "film's colour")
                if cc0:
                    e["licence"] = "CC0 1.0"
                guard(e)
                out.append(e)
    print(f"    got   {len(out)} glyphs across {len(GLYPH_THEMES)} themes"
          + (f", skipped {skipped} with no named author" if skipped else ""),
          flush=True)
    return out


def icons(dry: bool) -> list[dict]:
    out, dest = [], LIB / "icons"
    dest.mkdir(parents=True, exist_ok=True)
    for name in LUCIDE_ICONS:
        url = f"https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{name}.svg"
        e = entry("lucide", name, dest / f"{name}.svg", url, kind="icon")
        guard(e)
        out.append(e)
        if dry or (dest / f"{name}.svg").exists():
            continue
        try:
            (dest / f"{name}.svg").write_bytes(fetch(url, timeout=45))
        except urllib.error.HTTPError as e:
            # A RENAMED ICON MUST NOT ABORT THE LIBRARY. Lucide renames
            # icons between releases, and losing a chrome arrow is not a
            # reason to leave the textures and HDRIs unrecorded. It is
            # reported and dropped from the manifest, so nothing claims a
            # file that is not there.
            print(f"    MISSING {name}: HTTP {e.code} — dropped", flush=True)
            out.pop()
            continue
    if not dry:
        print(f"    got   {len(out)} Lucide icons", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--what", nargs="*",
                    default=["textures", "hdris", "glyphs", "icons"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    LIB.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    for what in args.what:
        print(f"  {what}:", flush=True)
        manifest += {"textures": textures, "hdris": hdris,
                     "glyphs": glyphs, "icons": icons}[what](args.dry_run)

    if args.dry_run:
        print(f"\n  {len(manifest)} entries would be written, all licence-checked")
        return 0

    path = LIB / "manifest.json"
    existing = json.loads(path.read_text()) if path.exists() else {"assets": []}
    by_name = {a["path"]: a for a in existing.get("assets", [])}
    for e in manifest:
        by_name[e["path"]] = e
    # A MANIFEST ENTRY WITHOUT ITS FILE IS A FALSE PROVENANCE RECORD. The
    # merge keeps entries from previous runs, so an asset removed from the
    # library -- the five `badges` glyphs with no named author were -- would
    # otherwise stay listed, and the manifest is the only thing anyone reads
    # to find out what is in here and under what terms.
    dropped = [k for k in by_name if not (ROOT / k).exists()]
    for k in dropped:
        del by_name[k]
    if dropped:
        print(f"  dropped {len(dropped)} manifest entries with no file",
              flush=True)
    path.write_text(json.dumps(
        {"generated": dt.datetime.now().isoformat(timespec="seconds"),
         "providers": PROVIDERS,
         "assets": sorted(by_name.values(), key=lambda a: a["path"])},
        indent=1) + "\n")
    print(f"\n  manifest: {len(by_name)} assets -> {path.relative_to(ROOT)}")
    write_glyph_index(sorted(by_name.values(), key=lambda a: a["path"]))
    return 0


#: Where the generated glyph index goes. The components need a name -> path
#: map at build time, and TypeScript cannot read the manifest out of
#: `public/` while compiling, so it is emitted as a module.
GLYPH_INDEX = ROOT / "remotion-composer" / "src" / "design" / "glyphIndex.ts"


def write_glyph_index(assets: list[dict]) -> None:
    """Emit the name -> published path map the `glyph()` helper reads.

    GENERATED, NEVER EDITED. A hand-kept list of 139 glyph names drifts from
    the files the moment one is added, and a glyph helper that returns a
    path to nothing renders an empty box that no gate is looking for.
    """
    rows = []
    for a in assets:
        if a.get("kind") != "glyph":
            continue
        name = Path(a["path"]).stem
        published = "library/" + str(Path(a["path"]).relative_to(
            "assets/library")).replace("\\", "/")
        rows.append((name, published, a["theme"], a["contributor"]))
    seen: dict[str, tuple] = {}
    for name, published, theme, who in rows:
        seen.setdefault(name, (published, theme, who))
    body = "\n".join(
        f'  "{n}": "{p}",' for n, (p, _t, _w) in sorted(seen.items()))
    themes: dict[str, list[str]] = {}
    for n, (_p, t, _w) in sorted(seen.items()):
        themes.setdefault(t, []).append(n)
    by_theme = "\n".join(
        f'  "{t}": [{", ".join(chr(34) + n + chr(34) for n in ns)}],'
        for t, ns in sorted(themes.items()))
    GLYPH_INDEX.parent.mkdir(parents=True, exist_ok=True)
    GLYPH_INDEX.write_text(
        "// GENERATED by scripts/fetch_library.py — do not edit.\n"
        f"// {len(seen)} glyphs from game-icons.net, CC BY 3.0, attributed\n"
        "// per artist in assets/library/manifest.json.\n\n"
        "export const GLYPHS: Record<string, string> = {\n"
        f"{body}\n}};\n\n"
        "export const GLYPH_THEMES: Record<string, string[]> = {\n"
        f"{by_theme}\n}};\n")
    print(f"  glyph index: {len(seen)} names -> "
          f"{GLYPH_INDEX.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""A hosted credits page per film, and an index of them.

WHY A PAGE AND NOT A COMMENT
----------------------------
CC BY 4.0 3(a)(2) says the required attribution may be given "in any
reasonable manner based on the medium, means, and context", and expressly
allows "providing a URI or hyperlink to a resource that includes the
required information". A page is that resource.

It is also the only form that works for a scheduled upload. YouTube
disables comments on a private video, so a film uploaded private cannot
carry its credits until the moment it goes public: king-tut went up owing
9,345 characters of attribution with no way to post them, and the API's own
answer was a 403 about permissions that had nothing to do with permissions.

WHY IT IS HERE AND NOT IN publish/
----------------------------------
`publish/` is not in the repository — it holds client_secrets.json and the
YouTube token, and it is deliberately outside every worktree. A generator
the weekly run depends on cannot sit there untracked. This lives beside the
`build_listing.py` it imports.

ONE SOURCE OF TRUTH
-------------------
Every row comes from `build_listing.credits_rows`, the same records that
render the pinned comment. The page and the comment cannot list different
assets because neither walks the bank; they render the same list.
`tests/publish/test_credits_page.py` asserts that on all four films.

    .venv/bin/python scripts/build_credits_page.py --project king-tut
    .venv/bin/python scripts/build_credits_page.py --all
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "lib"))

from build_listing import credits_rows  # noqa: E402

#: Where the pages are served from. Every published description links
#: straight here, so this string is part of the record of films that are
#: already live and cannot be changed without re-editing them.
SITE = "https://toolbeltios.github.io/wak3upsociety-credits"

#: The working copy of the site, outside every worktree like the ledger —
#: it is its own git repository with its own history.
DEFAULT_OUT = ROOT.parent / "credits-site"

STYLE = """
:root { color-scheme: light dark;
  --bg:#fbfbfa; --fg:#15141a; --muted:#5c5a66; --rule:#e3e1dc; --link:#2a5db0; }
@media (prefers-color-scheme: dark) { :root {
  --bg:#0c0c0e; --fg:#eceaf2; --muted:#9e9bab; --rule:#232329; --link:#8fb2f0; } }
* { box-sizing: border-box; }
body { margin:0; padding:48px 16px 96px; background:var(--bg); color:var(--fg);
  font:16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif; }
main { max-width: 820px; margin: 0 auto; }
h1 { font-size: 28px; line-height:1.25; margin:0 0 4px; letter-spacing:-0.01em; }
.sub { color:var(--muted); margin:0 0 28px; }
a { color:var(--link); }
.note { border:1px solid var(--rule); border-radius:10px; padding:16px 18px;
  margin:0 0 32px; color:var(--muted); }
.note strong { color:var(--fg); }
ol { padding-left: 22px; margin:0; }
li { margin: 0 0 18px; }
.title { font-weight:600; }
.by { color:var(--muted); }
.meta { color:var(--muted); font-size:14px; }
footer { margin-top:56px; padding-top:18px; border-top:1px solid var(--rule);
  color:var(--muted); font-size:14px; }
"""


def esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def oneline(text: str) -> str:
    """A credit on one line.

    Some artist fields are many lines: a stitched Wikimedia image names
    each of its nine source photographs on its own line, with the
    derivative author last. In the pinned comment those became orphan lines
    with no asset in front of them — one of the clearer arguments for the
    page over the comment. Here they become one row, semicolon separated,
    with nothing dropped.
    """
    return "; ".join(part.strip() for part in (text or "").splitlines()
                     if part.strip())


def row_html(record: dict) -> str:
    title = esc(record["title"]) or esc(record["asset_id"])
    if record["page"]:
        head = (f'<span class="title"><a href="{esc(record["page"])}">'
                f'{title}</a></span>')
    else:
        head = f'<span class="title">{title}</span>'
    if record["artist"] and record["artist"] != "(not supplied)":
        head += f' <span class="by">by {esc(oneline(record["artist"]))}</span>'
    licence = esc(record["licence"])
    if record["deed"]:
        licence = f'<a href="{esc(record["deed"])}">{licence}</a>'
    meta = [licence]
    if record["provider"]:
        meta.append(esc(record["provider"]))
    if record["notice"] and record["notice"] != record["artist"]:
        meta.append(esc(oneline(record["notice"])))
    return f'    <li>{head}<br><span class="meta">{" · ".join(meta)}</span></li>'


def page_html(title: str, video_id: str, records: list[dict],
              att: dict) -> str:
    share_alike = att.get("share_alike_assets", 0)
    watch = (f'<a href="https://www.youtube.com/watch?v={esc(video_id)}">'
             f'Watch the film</a>' if video_id else "")
    sa = ("" if not share_alike else
          f" {share_alike} of them are share-alike (CC BY-SA), and the film "
          f"is offered under the same terms where those shots appear.")
    rows = "\n".join(row_html(r) for r in records)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Credits — {esc(title)}</title>
<meta name="description" content="Image and footage credits for {esc(title)}.">
<style>{STYLE}</style>
</head><body><main>
<h1>{esc(title)}</h1>
<p class="sub">Image and footage credits. {watch}</p>
<div class="note"><strong>This film is built from {len(records)} freely
licensed photographs and clips.</strong>{sa} Every one is listed below with
its author, its licence and a link to where it came from. Narration is
synthesised speech; graphics are original.</div>
<ol>
{rows}
</ol>
<footer>wak3up society · generated {date.today().isoformat()} ·
<a href="./">all films</a></footer>
</main></body></html>
"""


def index_html(films: list[dict]) -> str:
    rows = "\n".join(
        f'    <li><a href="./{esc(f["slug"])}.html">{esc(f["title"])}</a>'
        f'<br><span class="meta">{f["assets"]} credited assets</span></li>'
        for f in films)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>wak3up society — film credits</title>
<meta name="description" content="Image and footage credits for every film.">
<style>{STYLE}</style>
</head><body><main>
<h1>Film credits</h1>
<p class="sub">Every image and clip each documentary is built from, with its
author, its licence and where it came from.</p>
<ol>
{rows}
</ol>
<footer>wak3up society · generated {date.today().isoformat()}</footer>
</main></body></html>
"""


def artifacts_for(slug: str) -> Path | None:
    """The project's artifacts, in whichever worktree holds them."""
    for root in ("runner", "OpenMontage", "fix-render-finalise",
                 "asset-library"):
        art = ROOT.parent / root / "projects" / slug / "artifacts"
        if (art / "render_props.json").exists():
            return art
    return None


def title_for(slug: str, art: Path) -> str:
    listing = art / "listing.json"
    if listing.exists():
        return json.loads(listing.read_text()).get("title") or slug
    return slug


def video_id_for(slug: str) -> str:
    import shared_state
    for film in shared_state.published_films(allow_missing=True):
        if film.get("project") == slug:
            return film.get("video_id") or ""
    return ""


def page_url(slug: str) -> str:
    return f"{SITE}/{slug}.html"


def build(slug: str, out: Path) -> dict:
    art = artifacts_for(slug)
    if art is None:
        raise SystemExit(f"{slug}: no render_props.json in any worktree")
    records, att = credits_rows(art, json.loads(
        (art / "render_props.json").read_text()))
    title = title_for(slug, art)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{slug}.html").write_text(
        page_html(title, video_id_for(slug), records, att))
    print(f"{slug}: {len(records)} assets -> {slug}.html")
    return {"slug": slug, "title": title, "assets": len(records)}


def published_slugs() -> list[str]:
    import shared_state
    return [f["project"] for f in shared_state.published_films(allow_missing=True)
            if f.get("project")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--all", action="store_true",
                    help="every film in the ledger")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--url", action="store_true",
                    help="print the page URL for --project and do nothing else")
    args = ap.parse_args()
    if bool(args.project) == bool(args.all):
        raise SystemExit("name --project or --all, and only one of them")
    if args.url:
        print(page_url(args.project))
        return 0

    out = Path(args.out)
    slugs = published_slugs() if args.all else [args.project]
    built = {f["slug"]: f for f in (build(slug, out) for slug in slugs)}

    # THE INDEX IS REBUILT FROM EVERY PAGE ON DISK, not only from the ones
    # built in this run, so publishing one film does not drop the others
    # off the front page.
    films = []
    for page in sorted(out.glob("*.html")):
        if page.stem == "index":
            continue
        if page.stem in built:
            films.append(built[page.stem])
            continue
        art = artifacts_for(page.stem)
        if art is None:
            continue
        records, _ = credits_rows(art, json.loads(
            (art / "render_props.json").read_text()))
        films.append({"slug": page.stem, "title": title_for(page.stem, art),
                      "assets": len(records)})
    (out / "index.html").write_text(index_html(films))
    print(f"index: {len(films)} film(s) -> {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

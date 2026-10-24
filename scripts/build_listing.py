#!/usr/bin/env python3
"""Build a film's YouTube listing from the project's own records.

`publish/build_listing.py` is run #1's and is hardcoded to it. This is the
same shape with the project as an argument, which is what the weekly chain
needs: `publish_doc.py` looks for `artifacts/listing.json` and says the
compose stage builds it, and until now nothing did.

Nothing here is typed twice. The title is the script's. Chapters are the
MEASURED section boundaries — the narration wavs, not the script's planned
times, because the two disagree by seconds and the wavs are what is in the
film. Sources come from the research brief, music from the EDL, and credits
from the assets the film actually cut to, read out of `render_props.json`
rather than the whole bank: a bank entry nobody used is not a credit owed.

YouTube caps a description at 5,000 characters, and a full attribution block
runs well past that, so the description carries the hook, the chapters, the
sources and the music, and the credits go in the pinned comment.

    .venv/bin/python scripts/build_listing.py --project easter-island
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ["cold_open", "title_sequence", "act1", "act2", "act3", "act4", "outro"]
DESCRIPTION_LIMIT = 5000

#: A section that is a card rather than a chapter anyone would skip to.
NOT_A_CHAPTER = {"title_sequence"}


def dur(path: Path) -> float:
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)]).strip())


def hms(t: float) -> str:
    t = int(t)
    if t >= 3600:
        return f"{t // 3600:d}:{(t % 3600) // 60:02d}:{t % 60:02d}"
    return f"{t // 60:02d}:{t % 60:02d}"


def chapter_title(section: dict) -> str:
    """The section's label, without the 'Act 2 — ' the script writes for itself."""
    label = (section.get("label") or section["id"]).strip()
    return re.sub(r"^Act\s+\d+\s*[—-]\s*", "", label)


def chapters(art: Path, aud: Path, script: dict) -> list[dict]:
    """Measured boundaries, from the narration this film actually carries."""
    by_id = {s["id"]: s for s in script["sections"]}
    out, t = [], 0.0
    for name in SECTIONS:
        wav = aud / f"{name}.wav"
        if not wav.exists():
            continue
        if name not in NOT_A_CHAPTER and name in by_id:
            out.append({"time": hms(t), "start_seconds": round(t, 2),
                        "title": chapter_title(by_id[name])})
        t += dur(wav)
    return out


def hook(script: dict, limit: int = 420) -> str:
    """The film's own opening, which is the one hook that cannot drift.

    A hand-written hook is a second copy of the premise that nothing keeps
    in step with the film. The cold open already is the hook — it is what a
    viewer hears in the first forty seconds — so it is quoted, trimmed to
    whole sentences.
    """
    text = next(s["text"] for s in script["sections"] if s["id"] == "cold_open")
    text = re.sub(r"\[(?:beat|air)[^\]]*\]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.findall(r"[^.!?]+[.!?]", text)
    out = ""
    for s in sentences:
        if len(out) + len(s) > limit:
            break
        out += s
    return out.strip() or text[:limit]


def used_assets(props: dict) -> list[dict]:
    """Every bank asset the cut list actually points at, by id."""
    ids = set()
    for cut in props.get("cuts", []):
        for value in cut.values():
            if isinstance(value, str) and "/" in value:
                stem = Path(value).stem
                ids.add(stem.split("_", 1)[-1] if stem[:9].isalnum() else stem)
                ids.add(stem)
    # A clip is stored at a resolution the screening record does not name,
    # so `pixabay_video_137001_1080` has to match `pixabay_video_137001`.
    ids |= {re.sub(r"_\d{3,4}$", "", i) for i in ids}
    return ids


def credits_block(art: Path, props: dict) -> tuple[str, dict]:
    """Creator, licence and source URL for every asset the film cut to."""
    # EVERY bank file, not just the first. The fetcher writes more than one —
    # `asset_bank.json` alongside `asset_bank_deep.json` and
    # `asset_bank_small.json` — and reading only `asset_bank.json` left 18
    # Wikimedia images in the delivered film with no credit at all, most of
    # them CC BY-SA, where attribution is a condition of the licence and not
    # a courtesy. Anything legible in the film has to be answerable for.
    entries: dict[str, dict] = {}
    for bank_file in sorted(art.glob("asset_bank*.json")):
        bank = json.loads(bank_file.read_text())
        for subject in bank.get("subjects", {}).values():
            for a in subject.get("assets", []):
                entries.setdefault(a["asset_id"], a)
        for d in bank.get("derived", []):
            entries.setdefault(d["asset_id"], d)
            # a crop is credited to the photograph it came from
            if d.get("parent_id"):
                entries.setdefault(d["parent_id"], d)

    wanted = used_assets(props)
    rows, share_alike = {}, 0
    for aid, a in entries.items():
        if aid not in wanted:
            continue
        licence = a.get("licence") or "unknown"
        artist = (a.get("artist") or "").strip() or "(not supplied)"
        page = a.get("page") or ""
        rows[f"{artist} — {licence} — {page}"] = licence
    for licence in rows.values():
        if "BY-SA" in licence.upper():
            share_alike += 1

    # The texture clips are not in the bank — they are screened separately,
    # because their role is different: elemental mood beds, never a named
    # site. They are still in the film and still carry a licence, so they are
    # still credited. Missing them is how a credits block ends up covering
    # 48 of the 84 assets a film actually cut to.
    textures = 0
    screening = art / "texture_screening.json"
    if screening.exists():
        ts = json.loads(screening.read_text())
        licence = ts.get("licence") or "Pixabay Content License"
        for clip in ts.get("kept", []):
            cid = clip.get("clip_id") or ""
            if cid not in wanted:
                continue
            num = re.sub(r"\D+", "", cid.replace("_1080", ""))
            url = f"https://pixabay.com/videos/id-{num}/" if num else ""
            rows[f"{num or cid} — {licence} (free, no attribution required)"
                 f" — {url}"] = licence
            textures += 1

    lines = ["IMAGE AND FOOTAGE CREDITS", "",
             "This film uses freely licensed material.", ""]
    lines += sorted(rows)
    block = "\n".join(lines)
    return block, {"credit_required_assets": len(rows),
                   "share_alike_assets": share_alike,
                   "texture_clips": textures}


def music_lines(ed: dict) -> list[str]:
    out = []
    for bed in (ed.get("music") or {}).get("beds", []):
        stem = os.path.splitext(bed["track"])[0]
        name, composer = (stem.split(" - ", 1) + [""])[:2]
        licence = bed.get("licence") or bed.get("license") or ""
        row = f"{name.strip()} — {composer.strip()}" + (f" — {licence}" if licence else "")
        out.append(row)
        if str(bed.get("source_url", "")).startswith("http"):
            out.append(bed["source_url"])
    return out


def build(project: str) -> dict:
    proj = ROOT / "projects" / project
    art, aud = proj / "artifacts", proj / "assets" / "audio"
    script = json.loads((art / "script.json").read_text())
    brief = json.loads((art / "research_brief.json").read_text())
    ed = json.loads((art / "edit_decisions.json").read_text())
    props = json.loads((art / "render_props.json").read_text())

    chaps = chapters(art, aud, script)
    block, att = credits_block(art, props)

    parts = [hook(script), ""]
    parts += ["CHAPTERS"] + [f"{c['time']} {c['title']}" for c in chaps] + [""]

    primary = [s for s in brief.get("sources", [])
               if s.get("reliability") == "primary"][:12]
    if primary:
        parts.append("SOURCES")
        for s in primary:
            parts.append(s["title"])
            if s.get("url"):
                parts.append(s["url"])
        parts.append("")

    mus = music_lines(ed)
    if mus:
        parts += ["MUSIC"] + mus + [""]

    parts += [
        "IMAGE AND FOOTAGE CREDITS",
        f"This film is built from {att['credit_required_assets']} freely "
        f"licensed photographs and clips. {att['share_alike_assets']} of them "
        f"are share-alike (CC BY-SA), and the film is offered under the same "
        f"terms where those shots appear.",
        "Every credit — creator, licence and source URL — is in the pinned "
        "comment, because the full list is longer than a YouTube description "
        "may be.",
        "",
        "Narration is synthesised speech. Graphics are original.",
        "",
        "New video every Monday.",
    ]
    description = "\n".join(parts)

    tags = ["Easter Island", "Rapa Nui", "moai", "Rano Raraku", "rongorongo",
            "birdman", "Orongo", "archaeology", "Polynesia", "ancient history",
            "collapse", "Jared Diamond", "Katherine Routledge", "documentary",
            "ancient engineering"]

    return {
        "title": script["title"],
        "description": description,
        "tags": tags[:15],
        "categoryId": "27",
        "defaultLanguage": "en",
        "defaultAudioLanguage": "en",
        "privacyStatus": "public",
        "selfDeclaredMadeForKids": False,
        "license": "youtube",
        "embeddable": True,
        "publicStatsViewable": True,
        "containsSyntheticMedia": True,
        "playlist": "Documentaries",
        "chapters": chaps,
        "pinned_comment": block,
        "attribution": att,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    listing = build(args.project)
    out = Path(args.out) if args.out else (
        ROOT / "projects" / args.project / "artifacts" / "listing.json")
    out.write_text(json.dumps(listing, indent=1, ensure_ascii=False),
                   encoding="utf-8")

    desc = listing["description"]
    over = len(desc) > DESCRIPTION_LIMIT
    print(f"title: {listing['title']}")
    print(f"description {len(desc)} chars (limit {DESCRIPTION_LIMIT})"
          f"{'  OVER LIMIT' if over else '  ok'}")
    print(f"chapters {len(listing['chapters'])}  tags {len(listing['tags'])}  "
          f"pinned comment {len(listing['pinned_comment'])} chars")
    print(f"written: {out}")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())

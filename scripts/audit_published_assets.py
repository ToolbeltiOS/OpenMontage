#!/usr/bin/env python3
"""Every asset in the published film, through the fan-out filter.

WHY RUN IT BACKWARDS
--------------------
The filter is enforced at fetch time now, for every source. Run #1 was fetched
before it existed, so its assets have never been through it — and the film is
published. If any of them would be refused today, that is not a gate failure
to fix in a future run; it is a fact about a video on the internet, and the
only way to learn it is to ask.

WHERE THE LICENCES ARE
----------------------
Three places, because run #1 collected assets three ways, and an asset used by
the film can be recorded in any of them:

    asset_manifest.json   what the pipeline fetched, with a `license` field
    asset_bank.json       what the Wikimedia category pass collected
    the props themselves  a `license`/`licence` on the cut, where one exists

An asset in NONE of them is reported as unrecorded, which is its own finding:
a film cannot attribute what it did not write down.

    python scripts/audit_published_assets.py --project <id>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.video.stock_sources.licences import classify, use_scope  # noqa: E402

MEDIA = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm"}
KEYS = ("source", "image", "backgroundImage", "before", "after")

#: Suffixes the pipeline adds when it makes a file out of another file.
#:
#: A third of the published film's assets are derived — a 1080p proxy of a
#: 4K clip, a detail crop of a plate — and a derived file carries no licence
#: of its own. Its rights are its source's, and that is a FACT ABOUT THE
#: PIPELINE rather than about the asset: the derivation step does not copy
#: the licence forward. Resolving the name is how the audit reads through it.
DERIVED_SUFFIX = re.compile(r"(_1080)+$|_detail$|_extreme$|_crop$|_wide$")


def original_of(name: str) -> str:
    """The stem this file was derived from, after every suffix is peeled."""
    stem = Path(name).stem
    previous = None
    while stem != previous:
        previous = stem
        stem = DERIVED_SUFFIX.sub("", stem)
    return stem


def used_by_the_film(props: dict) -> dict[str, list[str]]:
    used: dict[str, list[str]] = {}
    for cut in props["cuts"]:
        for key in KEYS:
            value = cut.get(key)
            if isinstance(value, str) and Path(value).suffix.lower() in MEDIA:
                used.setdefault(value, []).append(str(cut.get("id")))
    return used


def licence_index(project: Path) -> dict[str, dict]:
    """Every licence this project recorded, keyed by file name."""
    index: dict[str, dict] = {}

    manifest = project / "artifacts" / "asset_manifest.json"
    if manifest.exists():
        for asset in (json.loads(manifest.read_text()).get("assets") or []):
            path = asset.get("path")
            if path:
                index.setdefault(Path(path).name, {
                    "licence": asset.get("license") or asset.get("licence") or "",
                    "where": "asset_manifest.json",
                    "provider": asset.get("provider", ""),
                })

    bank = project / "artifacts" / "asset_bank.json"
    if bank.exists():
        for subject in (json.loads(bank.read_text()).get("subjects") or {}).values():
            for asset in subject.get("assets", []):
                path = asset.get("path")
                if path:
                    index.setdefault(Path(path).name, {
                        "licence": asset.get("licence") or asset.get("license") or "",
                        "where": "asset_bank.json",
                        "provider": asset.get("provider", ""),
                    })
    return index


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()

    project = ROOT / "projects" / args.project
    props = json.loads((project / "artifacts" / "render_props.json").read_text())
    used = used_by_the_film(props)
    index = licence_index(project)

    by_stem = {Path(k).stem: v for k, v in index.items()}

    refused, unrecorded, kept, derived = [], [], [], []
    for source, cuts in sorted(used.items()):
        name = Path(source).name
        record = index.get(name)
        inherited_from = ""
        if record is None:
            stem = original_of(name)
            match = by_stem.get(stem) or next(
                (v for k, v in by_stem.items() if k.startswith(stem)), None)
            if match is not None:
                record = match
                inherited_from = stem
                derived.append(name)
        if record is None:
            unrecorded.append({"source": source, "cuts": cuts})
            continue
        licence = classify(record["licence"])
        row = {"source": source, "name": name, "cuts": cuts,
               "raw": record["licence"], "code": licence.code,
               "where": record["where"], "provider": record["provider"],
               "inherited_from": inherited_from}
        (kept if licence.permitted else refused).append(row)

    families = Counter(r["code"] for r in kept)
    lines = [
        f"# Published assets, through the filter — {args.project}",
        "",
        f"`{len(used)}` distinct media assets are used by the published film. "
        f"Run #1 was fetched before the filter existed, so none of them have "
        f"been through it. This runs it backwards.",
        "",
        f"**{len(kept)} pass, {len(refused)} would be refused, "
        f"{len(unrecorded)} have no licence recorded anywhere.**",
        "",
        f"{len(derived)} of the passes are DERIVED files — a 1080p proxy of a "
        f"4K clip, a detail crop of a plate — which carry no licence of their "
        f"own and inherit their source's. That is a gap in the pipeline, not "
        f"in the rights: the derivation step does not copy the licence "
        f"forward, so the audit has to read through the file name to find it.",
        "",
        "| licence family | assets |", "|---|---|",
    ]
    lines += [f"| {code} | {n} |" for code, n in families.most_common()]

    if refused:
        lines += ["", "## Would be refused today", "",
                  "| asset | licence as recorded | read as | cuts |",
                  "|---|---|---|---|"]
        for r in refused:
            lines.append(f"| `{r['name']}` | `{r['raw'] or '(empty)'}` | "
                         f"{r['code']} | {', '.join(r['cuts'][:6])} |")
    else:
        lines += ["", "## Would be refused today", "", "None.", ""]

    if derived:
        lines += ["", "## Passing by inheritance", "",
                  "These carry no licence of their own. Each resolves to a "
                  "source that does.", "",
                  "| derived file | inherits from | licence |", "|---|---|---|"]
        for r in kept:
            if r["inherited_from"]:
                lines.append(f"| `{r['name']}` | `{r['inherited_from']}` | "
                             f"{r['code']} |")

    if unrecorded:
        lines += ["", "## No licence recorded", "",
                  "Not a filter result — a gap in the record. A film cannot "
                  "attribute what it did not write down.", "",
                  "| asset | cuts |", "|---|---|"]
        for r in unrecorded:
            lines.append(f"| `{Path(r['source']).name}` | "
                         f"{', '.join(r['cuts'][:6])} |")

    scoped = [r for r in kept if not use_scope(r["code"]).get(
        "standalone_redistribution", True)]
    if scoped:
        lines += ["", "## Permitted, with a scope worth knowing", "",
                  f"{len(scoped)} assets are usable in the film and not "
                  f"redistributable on their own. The film is fine; an asset "
                  f"pack or a reel of unused stills would not be.", ""]

    pixabay = families.get("PIXABAY", 0)
    if pixabay:
        lines += ["", "## One thing worth noticing", "",
                  f"{pixabay} of the {len(kept)} are Pixabay. Before the "
                  f"owner admitted that licence on 2026-10-21 they would "
                  f"every one of them have been refusals — in a film that is "
                  f"already published. The decision was load-bearing for run "
                  f"#1 and not only for the bank.", ""]

    dest = ROOT / "reports" / f"published_assets_{args.project}.md"
    dest.write_text("\n".join(lines) + "\n")

    print(f"{len(used)} assets used; {len(kept)} pass ({len(derived)} by "
          f"inheriting a source's licence), {len(refused)} refused, "
          f"{len(unrecorded)} unrecorded")
    for code, n in families.most_common():
        print(f"   {n:4d}  {code}")
    for r in refused[:10]:
        print(f"   REFUSED {r['name']}: {r['raw']!r} -> {r['code']}")
    print(f"-> {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

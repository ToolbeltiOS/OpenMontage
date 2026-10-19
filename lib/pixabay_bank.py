#!/usr/bin/env python3
"""Register the screened Pixabay elemental clips in the asset bank.

These were screened in run #1 — watched, kept or rejected — so they are not
re-queried here. Re-screening already-approved material is how a pipeline
loses provenance: the point of the bank is that every asset carries where it
came from and under what licence, not that every asset is fetched again.

Texture clips are banked whole. The reuse rule allows each one once; if the
bank runs short the planner authors texture rather than repeating a clip.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    bank_path, manifest_path = sys.argv[1], sys.argv[2]
    bank = json.load(open(bank_path))
    manifest = json.load(open(manifest_path))

    clips = {}
    for a in manifest["assets"]:
        if a.get("provider") != "pixabay_video":
            continue
        path = a["path"]
        if not os.path.exists(path):
            continue
        aid = "px_" + os.path.splitext(os.path.basename(path))[0]
        if aid in clips:
            continue
        clips[aid] = {
            "asset_id": aid,
            "path": path,
            "subject": "elemental_texture",
            "title": os.path.basename(path),
            "page": a.get("original_url"),
            "licence": a.get("license", "Pixabay Content License"),
            "artist": None,
            "provider": "pixabay_video",
            "kind": "video",
            "screened_in": "run #1",
        }
    bank.setdefault("subjects", {})["elemental_texture"] = {
        "terms": ["elemental", "texture"],
        "categories": [],
        "assets": sorted(clips.values(), key=lambda c: c["asset_id"]),
        "note": "screened in run #1; registered rather than re-queried",
    }
    json.dump(bank, open(bank_path, "w"), indent=1, ensure_ascii=False)
    print(f"elemental texture clips banked: {len(clips)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

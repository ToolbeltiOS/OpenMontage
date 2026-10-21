"""What kind of frame is this? CLIP zero-shot, on the playbook's vocabulary.

WHY THE MOOD TABLE NEEDS IT
---------------------------
The mood table picks a camera move from the beat and the register, and the
ASSET gets one veto over the result: a push into a dense frame becomes a lock,
because a frame that is already full reads as a zoom on a photograph rather
than an approach to a subject. That veto is the only place the picture itself
is allowed an opinion, and it cannot work while `asset_class` is a field
nobody fills in.

THE VOCABULARY IS THE PLAYBOOK'S
--------------------------------
`vast, intimate, dark, bright, dense, empty` — six words, and they are not
six independent questions. They are three pairs, and that is how they are
asked:

    scale        vast      <-> intimate
    luminance    bright    <-> dark
    occupancy    dense     <-> empty

Asking CLIP to choose one of six leaves it comparing "dark" against "vast",
which are not alternatives — a frame can be both, and run #1's material
mostly is. Asked as three contests it answers three times, and the asset
carries the winner of each with its margin, so a near-tie is visible rather
than being rounded into a confident label.

LUMINANCE IS MEASURED, NOT ASKED
--------------------------------
bright/dark is the one pair a pixel can answer better than a model can, and
the model is worse at it than it looks: on the bank's own frames CLIP put
"a dark photograph" ahead of "a bright photograph" for images whose mean luma
was over 200. So that pair is decided by the frame's own luminance and CLIP is
not consulted. The other two are judgements about content and stay with CLIP.

    python3 lib/asset_classifier.py <image>...
    python3 lib/asset_classifier.py --project <id>      # the whole bank
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: The three contests, each a pair of prompts. CLIP compares within a pair and
#: never across pairs.
CONTESTS: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
    "scale": (("vast", "a vast landscape photographed from far away, wide open space"),
              ("intimate", "a close-up photograph of a single object, shot from near by")),
    "occupancy": (("dense", "a photograph crowded with detail filling the whole frame"),
                  ("empty", "a photograph that is mostly empty space with one small subject")),
}

#: Mean luma, 0-255, above which a frame is bright and below which it is dark.
#: The bank's own frames sit either side of this with room to spare.
BRIGHT_LUMA = 110.0

#: Suffixes that need a frame taken out of them before CLIP can look. A third
#: of the bank is video, and a classifier that only reads stills classifies
#: two thirds of the bank.
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".avi"}

#: How far apart the two prompts in a contest have to be before the answer is
#: called rather than recorded as a tie. Cosine similarities from CLIP sit in
#: a narrow band, so this is a margin between two of them, not a confidence.
MIN_MARGIN = 0.005


def still_of(path: str | Path, into: Path) -> Path:
    """A frame to look at: the file itself, or one taken from the middle of it.

    The middle, not the first frame: a clip that opens on a fade gives a
    black frame, which classifies as dark and empty and is a fact about the
    fade rather than about the shot.
    """
    import subprocess

    path = Path(path)
    if path.suffix.lower() not in VIDEO_SUFFIXES:
        return path
    duration = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)]).strip() or 0.0)
    dest = into / f"{path.stem}.jpg"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{duration / 2:.3f}",
         "-i", str(path), "-frames:v", "1", "-q:v", "3", str(dest)], check=True)
    return dest


def mean_luma(path: str | Path) -> float:
    from PIL import Image
    import numpy as np

    with Image.open(path) as im:
        return float(np.asarray(im.convert("L").resize((128, 72))).mean())


def classify_images(paths: list[str]) -> list[dict[str, Any]]:
    """One row per asset: the winner of each contest, and by how much."""
    import tempfile

    import numpy as np

    sys.path.insert(0, str(ROOT / "lib"))
    from clip_embedder import embed_images, embed_texts

    prompts: list[str] = []
    for pair in CONTESTS.values():
        prompts += [pair[0][1], pair[1][1]]
    text = np.asarray(embed_texts(prompts), dtype="float32")

    with tempfile.TemporaryDirectory() as tmp:
        stills = [str(still_of(p, Path(tmp))) for p in paths]
        images = np.asarray(embed_images(stills), dtype="float32")
        return _rows(paths, stills, images, text)


def _rows(paths, stills, images, text) -> list[dict[str, Any]]:
    rows = []
    for i, path in enumerate(paths):
        row: dict[str, Any] = {"path": path, "classes": [], "margins": {}}
        sims = images[i] @ text.T
        for n, (name, pair) in enumerate(CONTESTS.items()):
            a, b = float(sims[2 * n]), float(sims[2 * n + 1])
            winner = pair[0][0] if a >= b else pair[1][0]
            margin = abs(a - b)
            row["margins"][name] = round(margin, 5)
            if margin >= MIN_MARGIN:
                row["classes"].append(winner)
            else:
                row["margins"][name + "_tie"] = True
        luma = mean_luma(stills[i])
        row["mean_luma"] = round(luma, 1)
        row["classes"].append("bright" if luma >= BRIGHT_LUMA else "dark")
        rows.append(row)
    return rows


def classify_bank(project: str) -> dict[str, Any]:
    """Every asset in the project's bank, by subject."""
    bank_path = ROOT / "projects" / project / "artifacts" / "asset_bank.json"
    bank = json.loads(bank_path.read_text())

    paths, index = [], []
    for subject, entry in bank.get("subjects", {}).items():
        for asset in entry.get("assets", []):
            local = asset.get("path") or asset.get("file") or asset.get("local")
            if not local:
                continue
            full = Path(local) if str(local).startswith("/") else ROOT / local
            if not full.exists():
                continue
            paths.append(str(full))
            index.append((subject, asset))

    rows = classify_images(paths) if paths else []
    out: dict[str, Any] = {"project": project, "assets": [], "missing": 0}
    for (subject, asset), row in zip(index, rows):
        out["assets"].append({
            "subject": subject,
            "path": os.path.relpath(row["path"], ROOT),
            "classes": row["classes"],
            "mean_luma": row["mean_luma"],
            "margins": row["margins"],
            "licence": asset.get("licence") or asset.get("license") or "",
        })
    out["missing"] = sum(
        1 for entry in bank.get("subjects", {}).values()
        for a in entry.get("assets", [])) - len(out["assets"])
    return out


def classify_props(props_path: Path) -> dict[str, Any]:
    """Every asset a props file actually uses.

    The bank is what was COLLECTED; a props file is what was USED, and run #1
    used 98 distinct assets of which only 19 are in the bank — the rest came
    from the site-stills pass and the proxy renders, which never went through
    the bank at all. Classifying the bank alone leaves the mood table with an
    opinion about a tenth of the film.
    """
    blob = json.loads(props_path.read_text())
    cuts = blob["cuts"] if isinstance(blob, dict) else blob
    media = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm"}

    seen: dict[str, None] = {}
    for cut in cuts:
        for key in ("source", "image", "backgroundImage", "before", "after"):
            value = cut.get(key)
            if not isinstance(value, str) or Path(value).suffix.lower() not in media:
                continue
            full = Path(value) if value.startswith("/") else ROOT / value
            if full.exists():
                seen.setdefault(str(full), None)

    paths = list(seen)
    rows = classify_images(paths) if paths else []
    return {
        "source": str(props_path.relative_to(ROOT) if props_path.is_relative_to(ROOT)
                      else props_path),
        "assets": [{
            "path": os.path.relpath(row["path"], ROOT),
            "classes": row["classes"],
            "mean_luma": row["mean_luma"],
            "margins": row["margins"],
        } for row in rows],
        "missing": 0,
    }


def annotate_cuts(cuts: list[dict[str, Any]], project: str) -> int:
    """Put each cut's asset class on the cut, so the mood table can veto.

    Matched on the file, by name: a cut's `source` may be an absolute path, a
    repository-relative one or a staged copy under the composer's public
    directory, and all three are the same picture. Matching on the basename is
    what survives that.

    Returns how many cuts were annotated. A cut whose asset is not in the bank
    gets nothing and falls back to the beat alone, which is what run #1's
    material does anyway.
    """
    # The film's own assets first, then the bank: a props file is what was
    # USED and the bank is what was COLLECTED, and run #1's film draws 98
    # distinct assets of which only 19 are in the bank.
    artifacts = ROOT / "projects" / project / "artifacts"
    classes: dict[str, Any] = {"assets": []}
    for name in ("asset_classes_film.json", "asset_classes.json"):
        path = artifacts / name
        if path.exists():
            classes["assets"] += json.loads(path.read_text()).get("assets", [])
    if not classes["assets"]:
        return 0
    by_name = {Path(a["path"]).name: a for a in classes.get("assets", [])}

    annotated = 0
    for cut in cuts:
        source = cut.get("source") or cut.get("image") or ""
        if not isinstance(source, str) or not source:
            continue
        # a staged copy is "<cut id>__<original name>"
        name = Path(source).name
        row = by_name.get(name) or by_name.get(name.split("__", 1)[-1])
        if not row:
            continue
        # the mood table takes ONE class, and the one it acts on is occupancy:
        # `never_push_into: [dense]` is the only veto in the playbook.
        for candidate in ("dense", "empty", "vast", "intimate"):
            if candidate in row["classes"]:
                cut.setdefault("asset_class", candidate)
                break
        cut.setdefault("asset_classes", row["classes"])
        annotated += 1
    return annotated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="*")
    ap.add_argument("--project", default=None)
    ap.add_argument("--props", default=None,
                    help="classify what a props file uses, not what the bank holds")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.project or args.props:
        result = (classify_props(Path(args.props)) if args.props
                  else classify_bank(args.project))
        dest = Path(args.out) if args.out else (
            ROOT / "projects" / args.project / "artifacts" / "asset_classes.json")
        dest.write_text(json.dumps(result, indent=1) + "\n")
        from collections import Counter

        counts = Counter(c for a in result["assets"] for c in a["classes"])
        print(f"{len(result['assets'])} assets classified "
              f"({result['missing']} had no file on disk)")
        for name, n in counts.most_common():
            print(f"   {n:4d}  {name}")
        print(f"-> {dest.relative_to(ROOT) if dest.is_absolute() and dest.is_relative_to(ROOT) else dest}")
        return 0

    for row in classify_images(args.images):
        print(f"{Path(row['path']).name}: {', '.join(row['classes'])} "
              f"(luma {row['mean_luma']}, margins {row['margins']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

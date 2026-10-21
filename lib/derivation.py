"""When one asset is made from another, the rights come with it.

WHY
---
A third of the published film's assets are derived: a 1080p proxy of a 4K
clip, a detail crop of a plate. The derivation step made the file and recorded
nothing, so the derived file had no licence, no provider and no attribution,
and the audit had to read through the FILE NAME to find out whose it was —
peeling `_1080` and `_detail` off a stem and hoping the result matched
something.

That works until a name does not follow the pattern, and it is the wrong
shape of answer anyway: a credit block generated from a guess is a credit
block that can be wrong without anyone knowing. Ninety-eight of ninety-eight
passed the audit by inheritance, and not one of them said so in writing.

So the derivation writes it down, at the moment it happens, and the ledger is
the record. A derived asset whose entry is missing is a gate failure, not a
puzzle.

    python3 lib/derivation.py --project <id> --backfill
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

LEDGER_NAME = "derived_assets.json"

#: Suffixes the pipeline adds when it makes a file out of a file. Used only
#: by the BACKFILL, which writes down what run #1's derivations did not.
#: Nothing made from here on relies on a name.
DERIVED_SUFFIX = re.compile(r"(_1080)+$|_detail$|_extreme$|_crop$|_wide$")

#: What travels from an original to anything made out of it.
CARRIED = ("licence", "provider", "attribution", "source_url", "creator")


def ledger_path(project_dir: Path) -> Path:
    return project_dir / "artifacts" / LEDGER_NAME


def load_ledger(project_dir: Path) -> dict[str, dict[str, Any]]:
    path = ledger_path(project_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text()).get("derived", {})


def _write(project_dir: Path, ledger: dict[str, dict[str, Any]]) -> Path:
    path = ledger_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {"derived": dict(sorted(ledger.items()))}, indent=1) + "\n")
    return path


def originals(project_dir: Path) -> dict[str, dict[str, Any]]:
    """Every asset this project recorded rights for, keyed by file name."""
    index: dict[str, dict[str, Any]] = {}

    manifest = project_dir / "artifacts" / "asset_manifest.json"
    if manifest.exists():
        for asset in (json.loads(manifest.read_text()).get("assets") or []):
            path = asset.get("path")
            if path:
                index.setdefault(Path(path).name, {
                    "licence": asset.get("license") or asset.get("licence") or "",
                    "provider": asset.get("provider", ""),
                    "attribution": asset.get("creator") or asset.get("artist") or "",
                    "source_url": asset.get("original_url", ""),
                    "creator": asset.get("creator", ""),
                })

    bank = project_dir / "artifacts" / "asset_bank.json"
    if bank.exists():
        for subject in (json.loads(bank.read_text()).get("subjects") or {}).values():
            for asset in subject.get("assets", []):
                path = asset.get("path")
                if path:
                    index.setdefault(Path(path).name, {
                        "licence": asset.get("licence") or asset.get("license") or "",
                        "provider": asset.get("provider", ""),
                        "attribution": asset.get("artist", ""),
                        "source_url": asset.get("page", ""),
                        "creator": asset.get("artist", ""),
                    })
    return index


def record(original: str, derived: str, project_dir: Path | str,
           how: str = "") -> dict[str, Any]:
    """Write down that `derived` was made from `original`, and whose it is.

    Called by the step that makes the file, so the record cannot drift from
    what happened. Returns the entry; writing a second time for the same
    derived file updates it.
    """
    project_dir = Path(project_dir)
    index = originals(project_dir)
    source = index.get(Path(original).name, {})
    entry = {
        "derived_from": Path(original).name,
        "derived_from_path": str(original),
        "how": how,
        **{key: source.get(key, "") for key in CARRIED},
        "rights_recorded": bool(source.get("licence")),
    }
    ledger = load_ledger(project_dir)
    ledger[Path(derived).name] = entry
    _write(project_dir, ledger)
    return entry


def backfill(project_dir: Path, used: list[str]) -> dict[str, Any]:
    """Write down what run #1's derivations did not.

    Resolves a derived name to its original by peeling the suffixes, which is
    what the audit used to do in its head every time it ran. Doing it once and
    writing it down is the difference between a record and an inference.
    """
    index = originals(project_dir)
    by_stem = {Path(name).stem: name for name in index}
    ledger = load_ledger(project_dir)

    written, unresolved = 0, []
    for source in used:
        name = Path(source).name
        if name in index or name in ledger:
            continue
        stem = Path(name).stem
        previous = None
        while stem != previous:
            previous = stem
            stem = DERIVED_SUFFIX.sub("", stem)
        match = by_stem.get(stem) or next(
            (v for k, v in by_stem.items() if k.startswith(stem)), None)
        if match is None:
            unresolved.append(name)
            continue
        ledger[name] = {
            "derived_from": match,
            "derived_from_path": match,
            "how": "backfilled from the file name, 2026-10-21",
            **{key: index[match].get(key, "") for key in CARRIED},
            "rights_recorded": bool(index[match].get("licence")),
        }
        written += 1
    _write(project_dir, ledger)
    return {"written": written, "unresolved": unresolved,
            "total": len(ledger)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--backfill", action="store_true")
    args = ap.parse_args()

    project_dir = ROOT / "projects" / args.project
    if args.backfill:
        props = json.loads(
            (project_dir / "artifacts" / "render_props.json").read_text())
        media = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm"}
        used = sorted({
            value for cut in props["cuts"]
            for key in ("source", "image", "backgroundImage", "before", "after")
            for value in [cut.get(key)]
            if isinstance(value, str) and Path(value).suffix.lower() in media})
        result = backfill(project_dir, used)
        print(f"{result['written']} derivations written, "
              f"{len(result['unresolved'])} unresolved, "
              f"{result['total']} in the ledger")
        for name in result["unresolved"][:10]:
            print("   unresolved:", name)
        print(f"-> {ledger_path(project_dir).relative_to(ROOT)}")
        return 0

    ledger = load_ledger(project_dir)
    missing = [k for k, v in ledger.items() if not v["rights_recorded"]]
    print(f"{len(ledger)} derived assets; {len(missing)} with no rights on "
          f"their original")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())

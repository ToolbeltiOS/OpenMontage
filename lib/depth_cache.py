#!/usr/bin/env python3
"""A depth map for every photographic still, estimated once and kept.

WHY A CACHE AND NOT A STEP
--------------------------
Depth Anything V2 takes about two seconds a picture on this machine. A bank
of ninety-four assets is three minutes, which is nothing once and a great
deal every time a cut is re-rendered. The map is written beside the asset and
keyed by the CONTENT of the image, so re-running is free and a replaced
photograph is re-estimated rather than quietly inheriting the old one's
geometry.

WHY NOT DEPTHFLOW'S OWN ESTIMATOR
---------------------------------
DepthFlow bundles one, and it cannot run here: `depthflow.estimators` calls
`int.to_bytes(8)` without a byte order, which needs Python 3.11, and the
pipeline's venv is 3.10. The model itself is a plain `transformers` load, so
this calls it directly — and it has to be called directly anyway, because
the cache key and the storage location are decisions this project is making
rather than DepthFlow's.

WHAT A DEPTH MAP IS HERE
------------------------
A 16-bit PNG beside the asset, normalised per image so 0 is the furthest
pixel in that frame and 65535 the nearest. Normalisation is per image on
purpose: the renderer wants relative depth within one photograph and nothing
compares two photographs to each other.

    python3 lib/depth_cache.py --project easter-island
    python3 lib/depth_cache.py --image path.jpg --out depth.png
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: The model. Small is 25M parameters and runs in about two seconds on an M1;
#: Base and Large are better on fine structure and are not worth four times
#: the time for a photograph that will be on screen for seven seconds behind
#: a slow move.
MODEL = "depth-anything/Depth-Anything-V2-Small-hf"

#: The longest edge the estimator sees. The map is upsampled to the asset's
#: own size afterwards; estimating at full 6000 px costs minutes and adds
#: nothing a parallax shader can use.
ESTIMATE_LONG_EDGE = 1536

#: Suffix for the cached map, beside the asset.
SUFFIX = ".depth.png"

_MODEL: Any = None
_PROC: Any = None


def _load():
    global _MODEL, _PROC
    if _MODEL is None:
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation

        _PROC = AutoImageProcessor.from_pretrained(MODEL)
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        _MODEL = AutoModelForDepthEstimation.from_pretrained(MODEL)
        _MODEL = _MODEL.to(device).eval()
        _MODEL._device_name = device
    return _MODEL, _PROC


def content_key(path: Path) -> str:
    """What the cache is keyed on: the file's own bytes.

    Not its mtime and not its name. A photograph swapped for a better crop
    under the same name must be re-estimated, and a file merely touched must
    not be.
    """
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def depth_path(image: Path) -> Path:
    return image.with_suffix(image.suffix + SUFFIX)


def estimate(image_path: Path):
    """The depth map for one image, as a float array at the image's size."""
    import numpy as np
    import torch
    from PIL import Image

    model, proc = _load()
    im = Image.open(image_path).convert("RGB")
    full = im.size
    work = im.copy()
    work.thumbnail((ESTIMATE_LONG_EDGE, ESTIMATE_LONG_EDGE))
    with torch.no_grad():
        batch = {k: v.to(model._device_name)
                 for k, v in proc(images=work, return_tensors="pt").items()}
        out = model(**batch)
    depth = torch.nn.functional.interpolate(
        out.predicted_depth.unsqueeze(1), size=(full[1], full[0]),
        mode="bicubic", align_corners=False).squeeze().cpu().numpy()
    return depth.astype(np.float32)


def write(depth, path: Path) -> dict[str, Any]:
    """Normalise per image and write a 16-bit PNG."""
    import numpy as np
    from PIL import Image

    lo, hi = float(depth.min()), float(depth.max())
    span = max(hi - lo, 1e-6)
    scaled = ((depth - lo) / span * 65535.0).clip(0, 65535).astype(np.uint16)
    Image.fromarray(scaled).save(path)
    return {"min": round(lo, 4), "max": round(hi, 4),
            "height": int(depth.shape[0]), "width": int(depth.shape[1])}


def ensure(image_path: Path, force: bool = False) -> dict[str, Any]:
    """The cached map for one image, estimating it if it is not there."""
    image_path = Path(image_path)
    out = depth_path(image_path)
    key = content_key(image_path)
    stamp = out.with_suffix(out.suffix + ".json")

    if out.exists() and stamp.exists() and not force:
        try:
            have = json.loads(stamp.read_text())
            if have.get("source_sha256_16") == key:
                return {**have, "cached": True, "path": str(out)}
        except Exception:
            pass

    depth = estimate(image_path)
    measured = write(depth, out)
    record = {"source": str(image_path), "source_sha256_16": key,
              "model": MODEL, "estimate_long_edge": ESTIMATE_LONG_EDGE,
              **measured}
    stamp.write_text(json.dumps(record, indent=1) + "\n")
    return {**record, "cached": False, "path": str(out)}


def bank_assets(project: str) -> list[dict[str, Any]]:
    """Every asset in every bank file for a project."""
    art = ROOT / "projects" / project / "artifacts"
    rows: list[dict[str, Any]] = []
    for bank in sorted(art.glob("asset_bank*.json")):
        blob = json.loads(bank.read_text())
        for subject in (blob.get("subjects") or {}).values():
            rows += subject.get("assets") or []
    seen, out = set(), []
    for row in rows:
        if row.get("asset_id") in seen:
            continue
        seen.add(row.get("asset_id"))
        out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--image")
    ap.add_argument("--out")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if args.image:
        record = ensure(Path(args.image), args.force)
        if args.out:
            import shutil

            shutil.copy(record["path"], args.out)
        print(json.dumps(record, indent=1))
        return 0

    if not args.project:
        print("pass --project or --image", file=sys.stderr)
        return 2

    rows = bank_assets(args.project)
    done = cached = missing = 0
    for row in rows[:args.limit]:
        path = Path(row["path"])
        if not path.exists():
            missing += 1
            continue
        record = ensure(path, args.force)
        cached += bool(record["cached"])
        done += 1
        print(f"  {'cached' if record['cached'] else 'estimated'}  "
              f"{row['asset_id']:16s} {record['width']}x{record['height']}",
              flush=True)
    print(f"\n{done} assets, {cached} already cached, {missing} files missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

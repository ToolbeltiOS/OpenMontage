"""The film's thumbnail, from its own hero still, in the house style.

WHY IT IS NOT A FRAME GRAB
--------------------------
`build_deliverables` pulled one with `ffmpeg -ss 1130`, which is a frame of
the film: act number, scene index, source line, caption furniture, and
whatever the narration happened to be saying at 18:50. At 320px wide on a
phone none of that reads — it is noise competing with the only two things
that have to: the picture and the title. The `DocThumbnail` composition
exists for this and its own docstring says why it is not `SlotPreview` with
the chrome switched off.

WHICH STILL
-----------
The first HERO cut that carries a photograph. The planner already marks the
cuts a film turns on; of king-tut's seven, two carry photographs and the
first is the Abydos king list the film opens on and argues from. The rule
is deterministic so that a re-render produces the same thumbnail, and the
human gate is what catches a bad pick — see `scripts/telegram_gate.py`,
whose whole premise is that an "ok" given to something nobody saw is
indistinguishable from an informed one.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "remotion-composer"

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


def artifacts_for(slug: str) -> Path | None:
    for root in ("runner", "OpenMontage", "fix-render-finalise",
                 "asset-library"):
        art = ROOT.parent / root / "projects" / slug / "artifacts"
        if (art / "render_props.json").exists():
            return art
    return None


def _image_of(cut: dict[str, Any]) -> str | None:
    for key in ("source", "backgroundImage", "image"):
        value = cut.get(key)
        if isinstance(value, str) and value.lower().endswith(IMAGE_SUFFIXES):
            return value
    return None


def hero_still(cuts: list[dict[str, Any]]) -> tuple[str, str]:
    """(image path, the cut it came from). Raises if the film has none."""
    for cut in cuts:
        if cut.get("hero"):
            image = _image_of(cut)
            if image:
                return image, str(cut.get("id"))
    # No hero carries a photograph — an all-authored film. Fall back to the
    # first photograph anywhere, rather than failing a delivery over it.
    for cut in cuts:
        image = _image_of(cut)
        if image:
            return image, str(cut.get("id"))
    raise SystemExit("this film has no photograph to make a thumbnail from")


def build(slug: str, out: Path, *, title: str | None = None,
          title_side: str = "left", scale: float = 1.0,
          offset_x: float = 0.0, offset_y: float = 0.0,
          kicker: str | None = None) -> dict[str, Any]:
    art = artifacts_for(slug)
    if art is None:
        raise SystemExit(f"{slug}: no render_props.json in any worktree")
    cuts = json.loads((art / "render_props.json").read_text())["cuts"]
    image, from_cut = hero_still(cuts)

    if title is None:
        listing = art / "listing.json"
        title = (json.loads(listing.read_text()).get("title")
                 if listing.exists() else slug)

    props: dict[str, Any] = {"image": image, "title": title,
                             "titleSide": title_side, "scale": scale,
                             "offsetX": offset_x, "offsetY": offset_y}
    if kicker:
        props["kicker"] = kicker

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(props, fh)
        props_path = fh.name
    png = out.with_suffix(".png")
    subprocess.run(
        [str(COMPOSER / "node_modules" / ".bin" / "remotion"), "still",
         "src/index.tsx", "DocThumbnail", str(png),
         f"--props={props_path}", "--log=error"],
        cwd=COMPOSER, check=True)
    # YouTube takes JPEG and caps a custom thumbnail at 2 MB.
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(png),
                    "-q:v", "2", str(out)], check=True)
    png.unlink(missing_ok=True)
    Path(props_path).unlink(missing_ok=True)

    size = out.stat().st_size
    if size > 2_000_000:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out),
                        "-q:v", "6", str(out)], check=True)
        size = out.stat().st_size
    return {"path": str(out), "image": image, "from_cut": from_cut,
            "title": title, "bytes": size}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--title-side", default="left", choices=("left", "right"))
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--offset-x", type=float, default=0.0)
    ap.add_argument("--offset-y", type=float, default=0.0)
    ap.add_argument("--kicker", default=None)
    args = ap.parse_args()

    out = Path(args.out) if args.out else (
        ROOT / "projects" / args.project / "renders" / "thumbnail.jpg")
    made = build(args.project, out, title=args.title,
                 title_side=args.title_side, scale=args.scale,
                 offset_x=args.offset_x, offset_y=args.offset_y,
                 kicker=args.kicker)
    print(f"{args.project}: {made['from_cut']} -> {made['path']} "
          f"({made['bytes'] / 1024:.0f} KB)")
    print(f"   image {made['image']}")
    print(f"   title {made['title']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

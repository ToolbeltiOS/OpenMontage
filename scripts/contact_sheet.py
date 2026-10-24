#!/usr/bin/env python3
"""Tile images into numbered contact sheets for visual screening.

Picking a clip or a still by filename or by search rank is how a documentary
ends up with a green valley standing in for "dark void in masonry". The asset
director says to confirm every pick by eye, and this is how a few hundred
candidates get looked at: uniform tiles, a printed index beside each sheet, so
a decision can be written down as "sheet 2, tile 14".

NOT ffmpeg's `tile` filter. Two attempts with it produced sheets holding the
first one and the first eight images of twenty-four, silently — the image2
demuxer wants a contiguous numbered sequence of identically-sized inputs and
drops the rest without an error. A contact sheet that quietly omits most of
what it was asked to show is worse than none, because the omission looks like
an empty slot in the bank.

    .venv/bin/python scripts/contact_sheet.py --dir <images> --out <prefix> --cols 6 --rows 4
"""
from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path

from PIL import Image, ImageDraw

EXTS = ("jpg", "jpeg", "png", "webp")
FIELD = (16, 16, 20)       # the playbook's near-black, so a tile reads in context
LABEL = (237, 230, 216)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True, help="output prefix; _NN.png is appended")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--rows", type=int, default=4)
    ap.add_argument("--tile-width", type=int, default=360)
    ap.add_argument("--pad", type=int, default=8)
    args = ap.parse_args()

    files = sorted(
        p for ext in EXTS
        for p in glob.glob(os.path.join(args.dir, f"*.{ext}"))
    )
    if not files:
        print(f"no images in {args.dir}")
        return 1

    per_sheet = args.cols * args.rows
    tw = args.tile_width
    th = int(round(tw * 9 / 16))
    pad = args.pad

    index_lines = []
    sheets = 0
    for start in range(0, len(files), per_sheet):
        chunk = files[start:start + per_sheet]
        sheets += 1
        w = args.cols * tw + (args.cols + 1) * pad
        h = args.rows * th + (args.rows + 1) * pad
        sheet = Image.new("RGB", (w, h), FIELD)
        draw = ImageDraw.Draw(sheet)
        for i, src in enumerate(chunk):
            col, row = i % args.cols, i // args.cols
            x = pad + col * (tw + pad)
            y = pad + row * (th + pad)
            try:
                with Image.open(src) as im:
                    im = im.convert("RGB")
                    im.thumbnail((tw, th), Image.LANCZOS)
                    sheet.paste(im, (x + (tw - im.width) // 2,
                                     y + (th - im.height) // 2))
            except Exception as exc:                  # a bad file is a fact
                draw.text((x + 8, y + 8), f"unreadable\n{type(exc).__name__}",
                          fill=LABEL)
            draw.rectangle([x, y, x + tw, y + th], outline=(58, 54, 48))
            draw.text((x + 6, y + 4), str(i + 1), fill=LABEL)
            index_lines.append(
                f"sheet {sheets} tile {i + 1:2d}  {os.path.basename(src)}")
        out = f"{args.out}_{sheets:02d}.png"
        sheet.save(out)
        print(f"wrote {out}  ({len(chunk)} tiles, row-major, {args.cols} per row)")

    index = Path(f"{args.out}_index.txt")
    index.write_text("\n".join(index_lines) + "\n")
    print(f"wrote {index}  ({len(files)} images over {sheets} sheets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

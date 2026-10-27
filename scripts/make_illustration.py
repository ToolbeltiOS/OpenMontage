#!/usr/bin/env python3
"""Render an illustration — and refuse to, until the cost is accepted.

THIS SCRIPT WILL NOT SPEND MONEY BY ACCIDENT
---------------------------------------------
There is no free tier for FLUX on fal.ai, and no FAL_KEY is configured in
this environment, so the default path here is to stop and say what it would
cost. `--i-accept-cost` is required, and it takes the per-image figure the
caller believes they are paying, which is then printed back with the total.
A flag that is just a yes/no can be set once and forgotten; one that has to
carry a number has to be thought about.

THE $0 ROUTE EXISTS AND IS PREFERRED. `tools/_comfyui/workflows/` holds a
Flux text-to-image workflow, and a local ComfyUI costs nothing per image.
It was not running when this was written (nothing on :8188), so it is
offered rather than assumed.

    python3 scripts/make_illustration.py --list            # the three tests
    python3 scripts/make_illustration.py --estimate
    python3 scripts/make_illustration.py --backend comfyui
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEST = ROOT / "assets" / "library" / "illustrations"

#: The three test subjects.
TESTS = {
    "pausanias-at-tiryns":
        "a Greek traveller in a himation standing before the colossal "
        "unworked limestone blocks of the Tiryns citadel wall, scale of a "
        "man against the masonry, second century AD",
    "sledge-teams":
        "teams of people hauling a large carved stone statue on a wooden "
        "sledge with ropes over bare ground, many figures straining, no "
        "machinery",
    "ark-build":
        "a very large wooden vessel under construction on dry land, timber "
        "frames and scaffolding, workers with adzes and bow drills, "
        "ancient near-eastern dress",
}

#: Per-image prices, in US dollars, as third-party trackers reported them
#: in late 2026. NOT confirmed against fal.ai's own pricing page, which did
#: not load, so they are a guide for the estimate and not an authority.
PRICES = {
    "fal/flux-schnell": 0.003,
    "fal/flux-dev": 0.025,
    "fal/flux2-dev-turbo": 0.008,
    "comfyui-local": 0.0,
}


def estimate(backend: str, count: int) -> str:
    price = PRICES.get(backend)
    if price is None:
        return f"{backend}: no price on record"
    return (f"{backend}: ${price:.4f}/image x {count} = ${price * count:.4f}"
            + ("  (local, no charge)" if price == 0 else ""))


def main() -> int:
    import lib.illustration_spec as spec

    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="fal/flux-dev",
                    choices=sorted(PRICES))
    ap.add_argument("--subjects", nargs="*", default=sorted(TESTS))
    ap.add_argument("--estimate", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--i-accept-cost", type=float, default=None,
                    metavar="USD_PER_FILM",
                    help="the per-FILM budget you accept, in dollars. The "
                         "run is refused if the estimate exceeds it. "
                         "Required before anything is generated on a paid "
                         "backend.")
    args = ap.parse_args()

    if args.list:
        for name, subject in TESTS.items():
            print(f"  {name}\n     {spec.full_prompt(subject)[:150]}...")
        return 0

    n = len(args.subjects)
    print(f"  {n} illustration(s), backend {args.backend}")
    print("  " + estimate(args.backend, n))
    print(f"  FAL_KEY configured: {bool(os.environ.get('FAL_KEY'))}")
    reachable = False
    try:
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=3)
        reachable = True
    except Exception:
        pass
    print(f"  local ComfyUI on :8188: {'reachable' if reachable else 'not running'}")

    if args.estimate:
        return 0

    price = PRICES[args.backend]
    total = price * n
    if price > 0:
        if args.i_accept_cost is None:
            print("\n  STOPPED. This backend charges per image and nothing "
                  "has been generated.")
            print(f"  This run would cost ${total:.4f}. Re-run with "
                  f"--i-accept-cost <your per-film budget> to proceed, or "
                  f"--backend comfyui-local for the $0 route.")
            return 2
        # A PER-FILM CAP, NOT A PER-IMAGE PRICE. The thing worth bounding is
        # what a film costs, because the image count is what grows: a cap of
        # $0.05 buys about sixteen schnell images or two dev ones, and the
        # script says which rather than leaving it to be worked out after
        # the bill.
        if total > args.i_accept_cost + 1e-9:
            print(f"\n  STOPPED. {n} image(s) on {args.backend} is "
                  f"${total:.4f}, over the ${args.i_accept_cost:.4f} cap "
                  f"for this film. Nothing generated.")
            affordable = int(args.i_accept_cost // price) if price else 0
            print(f"  At ${price:.4f}/image the cap affords {affordable} "
                  f"image(s), or use a cheaper backend: "
                  + ", ".join(f"{b} (${PRICES[b]:.4f})"
                              for b in sorted(PRICES, key=PRICES.get)
                              if PRICES[b] < price) or "none cheaper")
            return 2
        print(f"\n  Within budget: ${total:.4f} of ${args.i_accept_cost:.4f}.")
        if not os.environ.get("FAL_KEY"):
            print("\n  STOPPED. FAL_KEY is not configured, so this backend "
                  "cannot be called at all.")
            return 2
    if args.backend == "comfyui-local" and not reachable:
        print("\n  STOPPED. ComfyUI is not running on :8188.")
        return 2

    DEST.mkdir(parents=True, exist_ok=True)
    print("\n  (generation would run here; records written with "
          "lib/illustration_spec.licence_record)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

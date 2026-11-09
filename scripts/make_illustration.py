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

#: Per-image prices, in US dollars.
#:
#: Pixazo is first because it has a FREE TIER -- 750 images a month -- and
#: the price below is what an image costs once that is gone. The Shorts
#: pipeline in ~/Desktop/wak3up already uses the same endpoint, and the free
#: allowance is held by the ACCOUNT and shared across every key on it, so
#: the two pipelines spend the same bucket. See lib/pixazo_quota.py.
#:
#: The fal figures come from third-party trackers and were not confirmed
#: against fal.ai's own pricing page, which did not load.
PRICES = {
    "pixazo/flux-1-schnell": 0.0012,
    "cloudflare/flux-1-schnell": 0.0,
    "fal/flux-schnell": 0.003,
    "fal/flux2-dev-turbo": 0.008,
    "fal/flux-dev": 0.025,
}

#: Backends with a free allowance, where the price above applies only after
#: it runs out. The quota check, not the price, governs these.
FREE_TIER = {"pixazo/flux-1-schnell", "cloudflare/flux-1-schnell"}

#: The endpoint and auth header the Shorts pipeline uses, read from
#: ~/Desktop/wak3up/visual_generator.py. Azure API Management, hence the
#: Ocp-Apim header rather than a bearer token.
PIXAZO_URL = "https://gateway.pixazo.ai/flux-1-schnell/v1/getData"
PIXAZO_AUTH_HEADER = "Ocp-Apim-Subscription-Key"

#: Cloudflare Workers AI, the fallback. Free-tier allowance is per account
#: in neurons rather than images, so it is not counted the same way.
CLOUDFLARE_URL = ("https://api.cloudflare.com/client/v4/accounts/"
                  "{account}/ai/run/@cf/black-forest-labs/flux-1-schnell")


def estimate(backend: str, count: int) -> str:
    price = PRICES.get(backend)
    if price is None:
        return f"{backend}: no price on record"
    return (f"{backend}: ${price:.4f}/image x {count} = ${price * count:.4f}"
            + ("  (local, no charge)" if price == 0 else ""))


def generate_pixazo(prompt: str, negative: str, dest: Path,
                    size: tuple[int, int] = (1920, 1080)) -> tuple[bool, str]:
    """One image from Pixazo's FLUX.1 schnell, same endpoint as the Shorts run.

    The negative prompt is folded into the prompt text. Pixazo's schnell
    endpoint takes `prompt`, `num_steps`, `width` and `height` and nothing
    else -- there is no negative field -- so the house negative is appended
    as a clause rather than silently dropped, which would leave an
    illustration free to come back photoreal.
    """
    import requests

    key = os.environ.get("PIXAZO_API_KEY", "")
    if not key:
        return False, "PIXAZO_API_KEY is not set"
    body = {
        "prompt": f"{prompt}. Not: {negative}" if negative else prompt,
        "num_steps": 4,
        "width": size[0],
        "height": size[1],
    }
    try:
        r = requests.post(PIXAZO_URL, timeout=120, json=body, headers={
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            PIXAZO_AUTH_HEADER: key,
        })
    except Exception as e:                                  # noqa: BLE001
        return False, f"request failed: {e}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}: {r.text[:160]}"
    url = (r.json() or {}).get("output", "")
    if not url:
        return False, f"no output url: {str(r.json())[:160]}"
    img = requests.get(url, timeout=120)
    if img.status_code != 200:
        return False, f"image fetch HTTP {img.status_code}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(img.content)
    return True, str(dest)


def generate_cloudflare(prompt: str, negative: str, dest: Path,
                        size: tuple[int, int] = (1920, 1080)
                        ) -> tuple[bool, str]:
    """The fallback: Workers AI, same model, different shape of answer.

    Workers AI returns base64 in a JSON envelope rather than a URL, and
    takes `steps` where Pixazo takes `num_steps`. Treating the two as
    interchangeable is how a fallback silently returns nothing.
    """
    import base64

    import requests

    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    if not (token and account):
        return False, "CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID not set"
    try:
        r = requests.post(
            CLOUDFLARE_URL.format(account=account), timeout=120,
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": f"{prompt}. Not: {negative}" if negative else prompt,
                  "steps": 4})
    except Exception as e:                                  # noqa: BLE001
        return False, f"request failed: {e}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}: {r.text[:160]}"
    blob = (r.json() or {}).get("result", {})
    b64 = blob.get("image") if isinstance(blob, dict) else None
    if not b64:
        return False, f"no image in result: {str(r.json())[:160]}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(base64.b64decode(b64))
    return True, str(dest)


BACKENDS = {
    "pixazo/flux-1-schnell": generate_pixazo,
    "cloudflare/flux-1-schnell": generate_cloudflare,
}


def main() -> int:
    import lib.illustration_spec as spec
    try:
        from lib.env_loader import load_env
        load_env()
    except Exception:                                       # noqa: BLE001
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="pixazo/flux-1-schnell",
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

    import lib.pixazo_quota as quota

    n = len(args.subjects)
    print(f"  {n} illustration(s), backend {args.backend}")
    free = args.backend in FREE_TIER
    if args.backend.startswith("pixazo"):
        ok, why = quota.check(n)
        print(f"  free-tier quota: {'OK' if ok else 'REFUSED'}")
        print(f"    {why}")
        print(f"  key configured: {bool(os.environ.get('PIXAZO_API_KEY'))}")
        if not ok:
            print("\n  STOPPED on the free-tier ceiling. Nothing generated.")
            return 2
    else:
        print("  " + estimate(args.backend, n))

    if args.estimate:
        return 0

    price = PRICES[args.backend]
    total = price * n
    if price > 0 and not free:
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
    fn = BACKENDS.get(args.backend)
    if fn is None:
        print(f"\n  STOPPED. {args.backend} has no client in this script.")
        return 2

    DEST.mkdir(parents=True, exist_ok=True)
    records, made, failed = [], 0, []
    import time as _time

    for i, name in enumerate(args.subjects):
        subject = TESTS.get(name, name)
        prompt = spec.full_prompt(subject)
        dest = DEST / f"{name}.png"
        if i:
            # Under 80% of the published rate limit, and the cautious of the
            # two published figures. See lib/pixazo_quota.py.
            _time.sleep(quota.spacing_seconds())
        ok, detail = fn(prompt, spec.NEGATIVE_PROMPT, dest)
        print(f"  {'made ' if ok else 'FAILED'} {name}: {detail[:110]}",
              flush=True)
        if not ok:
            failed.append((name, detail))
            continue
        made += 1
        rec = spec.licence_record(subject, args.backend, prompt)
        rec["path"] = str(dest.relative_to(ROOT))
        records.append(rec)

    if made and args.backend.startswith("pixazo"):
        total_used = quota.record(made)
        print(f"\n  recorded {made} against the free tier "
              f"({total_used} this month by OpenMontage; the Shorts "
              f"pipeline's usage is not visible from here)")

    if records:
        man = DEST / "manifest.json"
        blob = json.loads(man.read_text()) if man.exists() else {"assets": []}
        by = {a["path"]: a for a in blob["assets"]}
        for r in records:
            by[r["path"]] = r
        blob["assets"] = sorted(by.values(), key=lambda a: a["path"])
        man.write_text(json.dumps(blob, indent=1) + "\n")
        print(f"  provenance: {len(by)} record(s) -> "
              f"{man.relative_to(ROOT)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

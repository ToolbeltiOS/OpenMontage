#!/usr/bin/env python3
"""Is the YouTube grant good enough to run a week unattended?

Three questions, and the third is the one that matters:

    SCOPES   upload, youtube, force-ssl (captions) and yt-analytics.readonly
             (the Tuesday metrics). A missing scope fails at the last step of
             a run that has already spent an hour rendering.

    REFRESH  does it refresh right now.

    USE      how long since it was last refreshed. This client's consent
             screen is PUBLISHED — the droplet's uploader carries the same
             client_id in the same project and refreshes it daily — so
             nothing here expires on a schedule. What does kill a refresh
             token on a published client is SIX MONTHS of disuse, which is
             what the March `invalid_grant` was.

Run it after re-authorising.

    python scripts/check_youtube_auth.py
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "scripts"))

REQUIRED = {
    "https://www.googleapis.com/auth/youtube.upload": "upload the film",
    "https://www.googleapis.com/auth/youtube": "playlist, thumbnail",
    "https://www.googleapis.com/auth/youtube.force-ssl": "captions.insert, comments",
    "https://www.googleapis.com/auth/yt-analytics.readonly": "the Tuesday metrics",
}


def main() -> int:
    from publish_doc import (INACTIVITY_MONTHS, TOKEN, check_token,
                             days_since_last_use)

    if not TOKEN.exists():
        print(f"no token at {TOKEN}")
        print("run:  python ~/Developer/wak3up-docs/publish/yt_authorize.py")
        return 1

    credentials = pickle.loads(TOKEN.read_bytes())
    granted = set(credentials.scopes or [])

    print("SCOPES")
    missing = []
    for scope, why in REQUIRED.items():
        ok = scope in granted
        print(f"  {'yes' if ok else 'NO '}  {scope.split('/auth/')[-1]:28s} {why}")
        if not ok:
            missing.append(scope)
    extra = granted - set(REQUIRED)
    for scope in sorted(extra):
        print(f"  ---  {scope.split('/auth/')[-1]:28s} (not needed, not a problem)")

    print("\nREFRESH")
    refreshed, message = check_token()
    print(f"  {message}")

    idle = days_since_last_use()
    print("\nUSE")
    if idle is None:
        print("  not yet marked — this run marks it")
    else:
        print(f"  last used {idle:.1f} days ago; the limit is "
              f"{INACTIVITY_MONTHS} months of disuse")
    print("  (consent screen published: same client_id as the droplet's "
          "uploader, which refreshes daily)")

    print("\nVERDICT")
    if missing:
        print("  NOT READY — re-authorise with every scope:")
        print("    python ~/Developer/wak3up-docs/publish/yt_authorize.py")
        for scope in missing:
            print(f"      missing: {scope}")
        return 1
    if not refreshed:
        print(f"  NOT READY — {message}")
        return 2
    print("  READY — every scope granted, the token refreshes, and nothing "
          "expires on a schedule.")
    print(f"  A weekly run touches it every 7 days against a "
          f"{INACTIVITY_MONTHS}-month limit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

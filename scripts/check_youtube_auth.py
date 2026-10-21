#!/usr/bin/env python3
"""Is the YouTube grant good enough to run a week unattended?

Three questions, and the third is the one that matters:

    SCOPES   upload, youtube, force-ssl (captions) and yt-analytics.readonly
             (the Tuesday metrics). A missing scope fails at the last step of
             a run that has already spent an hour rendering.

    REFRESH  does it refresh right now.

    AGE      has it been refreshing for more than seven days. A Google OAuth
             client in TESTING mode expires refresh tokens at seven days, and
             a token cannot be asked what mode its client is in — it can only
             be watched. A refresh token older than seven days that still
             works is from a published consent screen, because a testing one
             would already be dead.

Run it after re-authorising, and again a week later.

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
    from publish_doc import TESTING_MODE_DAYS, TOKEN, check_token, token_age_days

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

    age = token_age_days()
    print("\nAGE")
    if age is None:
        print("  not yet marked — this run marks it; the seven-day proof "
              "starts now")
    else:
        print(f"  {age:.1f} days of continuous refreshing")

    print("\nVERDICT")
    if missing:
        print("  NOT READY — re-authorise with every scope:")
        print("    python ~/Developer/wak3up-docs/publish/yt_authorize.py")
        for scope in missing:
            print(f"      missing: {scope}")
        return 1
    if not refreshed:
        print("  SCOPES OK, consent screen UNPROVEN.")
        print(f"  The token works today. It has to keep working for "
              f"{TESTING_MODE_DAYS} days to prove the consent screen is "
              f"published; until then an unattended Friday could fail at the "
              f"upload.")
        print("  Publish it at: Google Cloud Console > APIs & Services >")
        print("                 OAuth consent screen > Publish app")
        print(f"  (project: wak3upsociety-pipeline)")
        return 2
    print("  READY — every scope granted, and the consent screen is published.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

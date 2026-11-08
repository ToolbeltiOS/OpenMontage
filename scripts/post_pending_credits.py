#!/usr/bin/env python3
"""Post the credits comment a scheduled film could not carry.

WHY THIS EXISTS
---------------
YouTube disables comments on a PRIVATE video, and a film uploaded private
and scheduled is private until its publish time. Measured on the four films
made so far: easter-island and noah went up PUBLIC immediately and their
credits posted with the upload; king-tut was the first uploaded private and
scheduled, and `commentThreads.list` answers `commentsDisabled` for it while
both public films list their threads. A short link-free comment fails the
same way, so it is not the length or the attribution URLs.

The API's own answer is 403 "insufficient permissions. The request might not
be properly authorized", which reads as a missing scope and is not one —
`check_youtube_auth.py` reports youtube.force-ssl granted.

A SECOND COPY, NOT THE RECORD. The attribution itself is the hosted
credits page the description links to, which is pushed before the upload
and is live from the moment anyone can see the film — CC BY 4.0 3(a)(2)
allows exactly that, "providing a URI or hyperlink to a resource that
includes the required information". This posts the same list as a comment
because a reader on the video should not have to leave it, and because a
page and a comment that agree are better than either alone. Nothing depends
on it: if it never runs, the film is still properly attributed.

IDEMPOTENT. It refuses to post twice: a recorded comment_id is enough to
stop, and failing that it reads the video's existing threads and stops if
one of ours is already there. Run it as often as you like.

    .venv/bin/python scripts/post_pending_credits.py --project king-tut
    .venv/bin/python scripts/post_pending_credits.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "lib"))


def pending(project: str) -> dict | None:
    """The publish record of a film that still owes its credits."""
    record_path = ROOT / "projects" / project / "artifacts" / "publish.json"
    if not record_path.exists():
        return None
    record = json.loads(record_path.read_text())
    if record.get("comment_id"):
        return None
    return record


def already_ours(yt, video_id: str, text: str) -> str | None:
    """Has this comment already been posted? The ledger can be lost; the
    channel cannot."""
    from googleapiclient.errors import HttpError
    try:
        threads = yt.commentThreads().list(
            part="snippet", videoId=video_id, maxResults=100).execute()
    except HttpError:
        return None
    head = text.strip()[:60]
    for thread in threads.get("items", []):
        body = (thread["snippet"]["topLevelComment"]["snippet"]
                .get("textOriginal", ""))
        if body.strip()[:60] == head:
            return thread["id"]
    return None


def post(project: str, dry_run: bool = False) -> int:
    record = pending(project)
    if record is None:
        print(f"{project}: nothing owed")
        return 0
    artifacts = ROOT / "projects" / project / "artifacts"
    listing = json.loads((artifacts / "listing.json").read_text())
    text = listing.get("pinned_comment")
    if not text:
        print(f"{project}: no credits comment in the listing")
        return 0

    video_id = record["video_id"]
    import publish_doc as P
    from googleapiclient.errors import HttpError
    yt = P.client()

    status = yt.videos().list(part="status", id=video_id).execute()
    if not status.get("items"):
        print(f"{project}: {video_id} is not there any more")
        return 1
    privacy = status["items"][0]["status"].get("privacyStatus")
    print(f"{project}: {video_id} is {privacy}, {len(text)} chars owed")
    if privacy != "public":
        when = record.get("publish_at", "its publish time")
        print(f"   still private — comments are disabled until {when}")
        return 2

    existing = already_ours(yt, video_id, text)
    if existing:
        print(f"   already posted as {existing} — recording it, posting nothing")
    elif dry_run:
        print("   dry run: nothing posted")
        return 0
    else:
        try:
            existing = yt.commentThreads().insert(part="snippet", body={
                "snippet": {"videoId": video_id, "topLevelComment": {
                    "snippet": {"textOriginal": text}}}}).execute()["id"]
            print(f"   posted {existing}")
        except HttpError as error:
            print(f"   FAILED {error.resp.status}: "
                  f"{error.content.decode()[:200]}")
            return 1

    record["comment_id"] = existing
    record["manual"] = [m for m in record.get("manual", [])
                        if "CREDITS COMMENT" not in m.upper()]
    record["manual"].append("PIN the credits comment (no API for it)")
    record.setdefault("done", []).append(
        f"credits comment posted {datetime.now(timezone.utc).isoformat()}")
    (artifacts / "publish.json").write_text(json.dumps(record, indent=1) + "\n")

    import telegram
    telegram.send(
        f"<b>Credits posted</b> — {listing['title']}\n"
        f"https://www.youtube.com/watch?v={video_id}\n"
        f"✓ {len(text)} characters of attribution\n"
        f"· PIN it in Studio — there is no API for pinning")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--all", action="store_true",
                    help="every project that owes a credits comment")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if bool(args.project) == bool(args.all):
        raise SystemExit("name --project or --all, and only one of them")

    projects = ([args.project] if args.project else
                sorted(p.name for p in (ROOT / "projects").iterdir()
                       if pending(p.name)))
    if not projects:
        print("nothing owed")
        return 0
    worst = 0
    for project in projects:
        worst = max(worst, post(project, args.dry_run))
    return worst


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Publish a finished documentary, scheduled, private until it goes.

REUSES RUN #1's PUBLISH PATH, PARAMETERISED. `publish/build_listing.py` and
`publish/upload.py` are run #1's record and are hardcoded to it; the shape of
what they do is right and is what this follows — listing from the project's
own artifacts, resumable upload, thumbnail, playlist, credits comment — with
the project as an argument and three things added that a weekly run needs:

    publishAt       private now, public next Monday 09:00 America/Toronto.
                    A film that uploads public at 3am has no premiere and no
                    chance to be pulled.
    captions        the sidecar SRT, via captions.insert. Run #1 burnt them
                    into the picture; run #2 ships a track.
    the ledger      artifacts/publish.json for this film, and an append to
                    artifacts/published.json, which the topic picker reads to
                    know what has already been made.

BEFORE THE FIRST RUN the OAuth refresh token has to survive longer than a
week, or every Friday at 22:00 will fail at the last step. See
`--check-token`: a Google OAuth client in TESTING mode issues refresh tokens
that expire after SEVEN DAYS, and the only cure is publishing the consent
screen.

    python scripts/publish_doc.py --project <id> --check-token
    python scripts/publish_doc.py --project <id> --dry-run
    python scripts/publish_doc.py --project <id>
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

PUBLISH_DIR = Path.home() / "Developer" / "wak3up-docs" / "publish"
TOKEN = PUBLISH_DIR / "yt_token.pkl"
#: Written beside the token the first time it is seen, so that "has this
#: refresh token lived longer than a week" is answerable at all.
TOKEN_SEEN = PUBLISH_DIR / "yt_token_first_seen.json"

RETRIABLE = {500, 502, 503, 504}
PLAYLIST = "Documentaries"
PUBLISH_HOUR = 9
PUBLISH_TZ = "America/Toronto"

#: A refresh token from a client in TESTING mode dies after this long.
TESTING_MODE_DAYS = 7


def next_monday(hour: int = PUBLISH_HOUR, tz_name: str = PUBLISH_TZ) -> datetime:
    """The next Monday at 09:00 local, as UTC.

    Next, not this: a run that finishes on Monday morning schedules for the
    following week rather than for four hours' time.
    """
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    days = (7 - now.weekday()) % 7 or 7
    target = (now + timedelta(days=days)).replace(
        hour=hour, minute=0, second=0, microsecond=0)
    return target.astimezone(timezone.utc)


def token_age_days() -> float | None:
    """How long this refresh token has been working, in days."""
    if not TOKEN_SEEN.exists():
        return None
    try:
        seen = json.loads(TOKEN_SEEN.read_text())
    except Exception:
        return None
    first = datetime.fromisoformat(seen["first_seen"])
    if first.tzinfo is None:
        first = first.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - first).total_seconds() / 86400


def check_token(verbose: bool = True) -> tuple[bool, str]:
    """Can this token still refresh, and has it proved it will keep doing so?

    Proof is the only thing that works here. A token cannot be asked whether
    its consent screen is published; what it can do is keep refreshing, and a
    refresh token that is more than seven days old and still works is from a
    client in production, because a testing one would be dead.
    """
    from google.auth.transport.requests import Request

    if not TOKEN.exists():
        return False, f"no token at {TOKEN}: run publish/yt_authorize.py"

    credentials = pickle.loads(TOKEN.read_bytes())
    if not credentials.refresh_token:
        return False, "the token carries no refresh token: re-authorise"
    try:
        credentials.refresh(Request())
    except Exception as error:
        return False, (f"the refresh token no longer works ({error}). If the "
                       f"OAuth consent screen is in TESTING, Google expires "
                       f"refresh tokens after {TESTING_MODE_DAYS} days — "
                       f"publish the consent screen and re-authorise.")
    TOKEN.write_bytes(pickle.dumps(credentials))

    if not TOKEN_SEEN.exists():
        TOKEN_SEEN.write_text(json.dumps({
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "note": "written the first time the token refreshed; its age is "
                    "how we know the consent screen is published",
        }, indent=1) + "\n")

    age = token_age_days() or 0.0
    if age > TESTING_MODE_DAYS:
        return True, (f"the refresh token has worked for {age:.1f} days, "
                      f"longer than the {TESTING_MODE_DAYS}-day testing "
                      f"limit: the consent screen is published")
    return False, (
        f"the refresh token works, and it is only {age:.1f} days old — which "
        f"does not yet PROVE it will survive a week. A client in testing "
        f"mode expires them at {TESTING_MODE_DAYS} days. Either publish the "
        f"OAuth consent screen (Google Cloud Console > APIs & Services > "
        f"OAuth consent screen > Publish app) and re-run this, or wait until "
        f"the token is {TESTING_MODE_DAYS}+ days old and let it prove itself.")


def client():
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    credentials = pickle.loads(TOKEN.read_bytes())
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        TOKEN.write_bytes(pickle.dumps(credentials))
    return build("youtube", "v3", credentials=credentials)


def upload(yt, listing: dict, video: Path, publish_at: datetime) -> str:
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {k: listing[k] for k in
                    ("title", "description", "tags", "categoryId",
                     "defaultLanguage", "defaultAudioLanguage")},
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at.isoformat().replace("+00:00", "Z"),
            **{k: listing[k] for k in
               ("selfDeclaredMadeForKids", "license", "embeddable",
                "publicStatsViewable", "containsSyntheticMedia")
               if k in listing},
        },
    }
    media = MediaFileUpload(str(video), chunksize=8 * 1024 * 1024,
                            resumable=True, mimetype="video/mp4")
    request = yt.videos().insert(part="snippet,status", body=body,
                                 media_body=media)
    response, tries, last = None, 0, 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                percent = int(status.progress() * 100)
                if percent >= last + 5:
                    print(f"  {percent}%", flush=True)
                    last = percent
        except HttpError as error:
            if error.resp.status in RETRIABLE and tries < 5:
                tries += 1
                time.sleep(2 ** tries)
                continue
            raise
    return response["id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--listing", default=None)
    ap.add_argument("--video", default=None)
    ap.add_argument("--thumbnail", default=None)
    ap.add_argument("--captions", default=None)
    ap.add_argument("--check-token", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ok, message = check_token()
    print(("token: " if ok else "TOKEN: ") + message)
    if args.check_token:
        return 0 if ok else 1
    if not ok and not args.dry_run:
        import telegram
        telegram.send(f"<b>Publish blocked</b>\n{message}")
        return 1

    project = ROOT / "projects" / args.project
    artifacts = project / "artifacts"
    listing_path = Path(args.listing) if args.listing else artifacts / "listing.json"
    if not listing_path.exists():
        # Same shape of failure as a missing script: an earlier stage exited
        # 0 and wrote nothing. Said plainly rather than as a traceback.
        print(f"no listing at {listing_path} — nothing to publish. The "
              f"listing is built from the project's own artifacts by the "
              f"compose stage.")
        return 1
    listing = json.loads(listing_path.read_text())
    video = Path(args.video) if args.video else project / "renders" / "final.mp4"
    thumbnail = Path(args.thumbnail) if args.thumbnail else project / "renders" / "thumbnail.jpg"
    captions = Path(args.captions) if args.captions else artifacts / "captions.en.srt"
    publish_at = next_monday()

    print(f"{args.project}: {listing['title']!r}")
    print(f"  video     {video} ({'present' if video.exists() else 'MISSING'})")
    print(f"  thumbnail {thumbnail} ({'present' if thumbnail.exists() else 'missing'})")
    print(f"  captions  {captions} ({'present' if captions.exists() else 'missing'})")
    print(f"  private now, public {publish_at.isoformat()} "
          f"({PUBLISH_HOUR:02d}:00 {PUBLISH_TZ})")
    if args.dry_run:
        print("dry run: nothing uploaded")
        return 0
    if not video.exists():
        raise SystemExit(f"no video at {video}")

    yt = client()
    video_id = upload(yt, listing, video, publish_at)
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"uploaded: {url}")

    done, manual = [f"uploaded private, scheduled {publish_at.isoformat()}"], []
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    if thumbnail.exists():
        try:
            yt.thumbnails().set(videoId=video_id,
                                media_body=MediaFileUpload(str(thumbnail))).execute()
            done.append("custom thumbnail set")
        except HttpError as error:
            manual.append(f"thumbnail rejected ({error.resp.status}) — "
                          f"set it in Studio: {thumbnail}")

    try:
        found = yt.playlists().list(part="snippet", mine=True, maxResults=50).execute()
        playlist_id = next(
            (p["id"] for p in found.get("items", [])
             if p["snippet"]["title"] == PLAYLIST), None)
        if playlist_id is None:
            playlist_id = yt.playlists().insert(part="snippet,status", body={
                "snippet": {"title": PLAYLIST},
                "status": {"privacyStatus": "public"}}).execute()["id"]
            done.append(f"playlist {PLAYLIST!r} created")
        yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
        done.append(f"added to {PLAYLIST!r}")
    except HttpError as error:
        playlist_id = None
        manual.append(f"playlist failed ({error.resp.status}) — add it in Studio")

    comment_id = None
    if listing.get("pinned_comment"):
        try:
            comment_id = yt.commentThreads().insert(part="snippet", body={
                "snippet": {"videoId": video_id, "topLevelComment": {"snippet": {
                    "textOriginal": listing["pinned_comment"]}}}}).execute()["id"]
            done.append("credits comment posted")
            manual.append("PIN the credits comment (no API for it)")
        except HttpError as error:
            manual.append(f"credits comment failed ({error.resp.status})")

    if captions.exists():
        try:
            yt.captions().insert(
                part="snippet",
                body={"snippet": {"videoId": video_id, "language": "en",
                                  "name": "English", "isDraft": False}},
                media_body=MediaFileUpload(str(captions),
                                           mimetype="application/octet-stream")
            ).execute()
            done.append("closed captions uploaded")
        except HttpError as error:
            manual.append(f"captions failed ({error.resp.status}) — "
                          f"upload {captions.name} in Studio")
    else:
        manual.append(f"no caption file at {captions}")

    manual += ["set the End Screen (no API)"]

    record = {
        "project": args.project, "video_id": video_id, "url": url,
        "title": listing["title"], "uploaded": datetime.now(timezone.utc).isoformat(),
        "publish_at": publish_at.isoformat(), "playlist_id": playlist_id,
        "comment_id": comment_id, "done": done, "manual": manual,
    }
    (artifacts / "publish.json").write_text(json.dumps(record, indent=1) + "\n")

    ledger_path = ROOT / "artifacts" / "published.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {"films": []}
    ledger["films"].append({
        "project": args.project, "video_id": video_id, "title": listing["title"],
        "url": url, "published": publish_at.date().isoformat(),
        "entities": listing.get("entities", []),
    })
    ledger_path.write_text(json.dumps(ledger, indent=1) + "\n")

    import telegram
    telegram.send(
        f"<b>Scheduled</b> — {listing['title']}\n{url}\n"
        f"Public {publish_at.astimezone().strftime('%a %d %b %H:%M')} "
        f"({PUBLISH_TZ})\n\n"
        + "\n".join(f"✓ {d}" for d in done)
        + ("\n\n<b>In Studio:</b>\n" + "\n".join(f"· {m}" for m in manual)
           if manual else ""))
    print("\n".join(done + [f"MANUAL: {m}" for m in manual]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

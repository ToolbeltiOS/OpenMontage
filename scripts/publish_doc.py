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

BEFORE THE FIRST RUN the OAuth refresh token has to keep working, or every
Friday at 22:00 will fail at the last step. See `--check-token`.

WHAT ACTUALLY EXPIRES ONE, established 2026-10-21. This client's consent
screen is PUBLISHED: `publish/client_secrets.json` and the droplet's
`~/wak3up/client_secrets.json` carry the same client_id in the same project,
and the Shorts poster refreshes it daily without dying — which a client in
testing could not do, since testing expires refresh tokens after seven days.

So the March `invalid_grant` was not testing status. On a published client a
refresh token dies from SIX MONTHS OF DISUSE, from the user revoking access,
or from passing the hundred-tokens-per-account-per-client limit. Disuse is
the one that fits a token minted once for a single film and left alone.

A weekly run is twenty-six times more often than the inactivity rule needs,
so it will not fire — but the check still watches the gap, because the rule
that bit once is the rule worth watching.

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

#: A refresh token on a PUBLISHED client dies after this long unused.
#: Google's documented rule; the weekly run touches it every seven days.
INACTIVITY_MONTHS = 6

#: Warn once the gap gets within this of the cliff.
WARN_AFTER_MONTHS = 4

#: Kept so the old proof-by-age file and anything that imported this name
#: still resolve. Nothing uses it for a decision any more: this client is
#: published, which the matching client_ids and the daily Shorts refresh
#: establish.
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


def days_since_last_use() -> float | None:
    """How long since this token was last refreshed, in days.

    This is the number that matters on a published client: six months of
    disuse kills a refresh token, and nothing else here is on a clock.
    """
    if not TOKEN_SEEN.exists():
        return None
    try:
        seen = json.loads(TOKEN_SEEN.read_text())
    except Exception:
        return None
    raw = seen.get("last_used") or seen.get("first_seen")
    last = datetime.fromisoformat(raw)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).total_seconds() / 86400


def _mark_used() -> None:
    now = datetime.now(timezone.utc).isoformat()
    record = {}
    if TOKEN_SEEN.exists():
        try:
            record = json.loads(TOKEN_SEEN.read_text())
        except Exception:
            record = {}
    record.setdefault("first_seen", now)
    record["last_used"] = now
    record["note"] = (
        "This client's consent screen is published: the same client_id is in "
        "publish/client_secrets.json and the droplet's, and the Shorts "
        "poster refreshes it daily. On a published client a refresh token "
        "dies from six months of DISUSE, so last_used is the field that "
        "matters.")
    TOKEN_SEEN.write_text(json.dumps(record, indent=1) + "\n")


def check_token(verbose: bool = True) -> tuple[bool, str]:
    """Does this token refresh, and is it being used often enough to live?

    No proof-by-age any more. That test existed because a client in testing
    mode expires refresh tokens at seven days and a token cannot be asked
    what mode its client is in — but this one's mode is established: the
    droplet's uploader carries the identical client_id in the same project
    and refreshes it daily, which testing mode would not survive.
    """
    from google.auth.transport.requests import Request

    if not TOKEN.exists():
        return False, f"no token at {TOKEN}: run publish/yt_authorize.py"

    credentials = pickle.loads(TOKEN.read_bytes())
    if not credentials.refresh_token:
        return False, "the token carries no refresh token: re-authorise"

    idle = days_since_last_use()
    try:
        credentials.refresh(Request())
    except Exception as error:
        hint = ""
        if idle is not None and idle > INACTIVITY_MONTHS * 30:
            hint = (f" It had not been used for {idle / 30:.1f} months, past "
                    f"the {INACTIVITY_MONTHS}-month inactivity limit, which "
                    f"is the likeliest cause.")
        return False, (f"the refresh token no longer works ({error}).{hint} "
                       f"Re-authorise with publish/yt_authorize.py.")
    TOKEN.write_bytes(pickle.dumps(credentials))
    _mark_used()

    if idle is not None and idle > WARN_AFTER_MONTHS * 30:
        return True, (f"refreshes, and had gone {idle / 30:.1f} months "
                      f"unused — the limit is {INACTIVITY_MONTHS}. A weekly "
                      f"run keeps it alive; a long pause would not.")
    return True, (f"refreshes. Consent screen published, so nothing expires "
                  f"on a schedule; the live rule is "
                  f"{INACTIVITY_MONTHS} months unused"
                  + (f" and it has been {idle:.1f} days" if idle is not None
                     else ""))


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

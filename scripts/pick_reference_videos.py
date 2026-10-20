#!/usr/bin/env python3
"""Pick each reference channel's most-viewed upload inside a duration window.

Read-only against the YouTube Data API, reusing the authorised OAuth
credentials in publish/ (channels.list, playlistItems.list, videos.list only).

Why the uploads playlist instead of search.list with order=viewCount: the
API's duration buckets are short (<4m), medium (4-20m) and long (>20m), so a
10-30 minute window straddles two of them and search.list cannot express it.
Walking the uploads playlist and reading contentDetails.duration is exact, and
costs less quota than a paged search.

A channel whose catalogue has nothing in the window is reported as such —
`pick` is null and `in_window` is 0 — rather than silently falling back to a
shorter video, because a channel trailer is not a pacing reference.

Usage:
  python scripts/pick_reference_videos.py [--min-minutes 10] [--max-minutes 30]
                                          [--out reports/reference_candidates.json]
                                          [--handle @LEMMiNO ...]
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_TOKEN = Path.home() / "Developer/wak3up-docs/publish/yt_token.pkl"
DEFAULT_HANDLES = ["@LEMMiNO", "@BarelySociable", "@FallofCivilizations"]
ISO8601 = re.compile(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def iso_duration_seconds(value: str) -> int:
    """ISO-8601 duration -> seconds; -1 when the API returns a form we cannot read."""
    m = ISO8601.fullmatch(value or "")
    if not m:
        return -1
    days, hours, minutes, seconds = (int(x) if x else 0 for x in m.groups())
    return ((days * 24 + hours) * 60 + minutes) * 60 + seconds


def client(token: Path):
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    if not token.exists():
        sys.exit(f"no authorised token at {token}")
    creds = pickle.loads(token.read_bytes())
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def channel(yt, handle: str) -> dict:
    resp = yt.channels().list(
        part="snippet,contentDetails,statistics", forHandle=handle
    ).execute()
    items = resp.get("items") or []
    if not items:
        sys.exit(f"no channel for handle {handle}")
    item = items[0]
    return {
        "handle": handle,
        "title": item["snippet"]["title"],
        "channel_id": item["id"],
        "uploads_playlist": item["contentDetails"]["relatedPlaylists"]["uploads"],
        "subscribers": int(item["statistics"].get("subscriberCount", 0)),
        "video_count": int(item["statistics"].get("videoCount", 0)),
    }


def uploads(yt, playlist_id: str) -> list[str]:
    ids: list[str] = []
    page = None
    while True:
        resp = yt.playlistItems().list(
            part="contentDetails", playlistId=playlist_id,
            maxResults=50, pageToken=page,
        ).execute()
        ids += [i["contentDetails"]["videoId"] for i in resp.get("items", [])]
        page = resp.get("nextPageToken")
        if not page:
            return ids


def details(yt, video_ids: list[str]) -> list[dict]:
    out: list[dict] = []
    for start in range(0, len(video_ids), 50):
        resp = yt.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(video_ids[start:start + 50]),
        ).execute()
        for v in resp.get("items", []):
            out.append({
                "video_id": v["id"],
                "title": v["snippet"]["title"],
                "published": v["snippet"]["publishedAt"][:10],
                "duration_s": iso_duration_seconds(v["contentDetails"]["duration"]),
                "views": int(v["statistics"].get("viewCount", 0)),
                "url": f"https://www.youtube.com/watch?v={v['id']}",
            })
    return out


def survey(yt, handle: str, min_s: int, max_s: int) -> dict:
    ch = channel(yt, handle)
    videos = details(yt, uploads(yt, ch["uploads_playlist"]))
    by_views = sorted(videos, key=lambda v: -v["views"])
    in_window = [v for v in by_views if min_s <= v["duration_s"] <= max_s]
    ch.update({
        "videos_read": len(videos),
        "in_window": len(in_window),
        "pick": in_window[0] if in_window else None,
        "runners_up": in_window[1:5],
        "most_viewed_any_length": by_views[:3],
        "shortest": sorted(videos, key=lambda v: v["duration_s"])[:3],
    })
    return ch


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--handle", action="append", dest="handles")
    ap.add_argument("--min-minutes", type=float, default=10)
    ap.add_argument("--max-minutes", type=float, default=30)
    ap.add_argument("--token", type=Path, default=DEFAULT_TOKEN)
    ap.add_argument("--out", type=Path, default=Path("reports/reference_candidates.json"))
    args = ap.parse_args()

    yt = client(args.token)
    min_s, max_s = int(args.min_minutes * 60), int(args.max_minutes * 60)
    channels = [survey(yt, h, min_s, max_s) for h in (args.handles or DEFAULT_HANDLES)]

    report = {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window_minutes": [args.min_minutes, args.max_minutes],
        "source": "YouTube Data API v3 (read-only)",
        "channels": channels,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")

    for ch in channels:
        pick = ch["pick"]
        head = f"{ch['title']}: {ch['in_window']} of {ch['videos_read']} in window"
        if pick:
            mins, secs = divmod(pick["duration_s"], 60)
            print(f"{head} -> {pick['title']} ({mins}m{secs:02d}s, "
                  f"{pick['views']:,} views, {pick['video_id']})")
        else:
            print(f"{head} -> NO CANDIDATE in window")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""What the films actually did, every Tuesday.

WHY TUESDAY
-----------
The films publish Monday 09:00. By Tuesday morning a day of data exists, which
is enough to see whether the opening held and nowhere near enough to judge the
film — so the summary says both, and the picker is not allowed to weight
anything on it until three films exist. One film's numbers are a fact about
that film; three are the beginning of a pattern.

WHAT IT PULLS
-------------
    views, average view duration, average percentage viewed
    the retention curve at 10-second resolution
    impressions and their click-through rate
    subscribers gained

The retention curve is the one that is worth having and the one nobody reads
in Studio: it says WHERE people left, and a documentary that loses a third of
its audience in the first forty seconds has a cold open problem, not a
subject problem.

SCOPE
-----
This needs `yt-analytics.readonly`, which the upload token does not carry.
Without it the API answers 403 and this says so rather than returning zeros —
a metrics file full of zeros is worse than no metrics file.

    python scripts/pull_metrics.py --check
    python scripts/pull_metrics.py
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

TOKEN = Path.home() / "Developer" / "wak3up-docs" / "publish" / "yt_token.pkl"
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"

#: How finely the retention curve is sampled, in seconds.
RETENTION_STEP_S = 10

#: Films needed before the picker may weight clusters on measured retention.
MIN_FILMS_TO_WEIGHT = 3


def credentials():
    from google.auth.transport.requests import Request

    if not TOKEN.exists():
        raise SystemExit(f"no token at {TOKEN}")
    creds = pickle.loads(TOKEN.read_bytes())
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_bytes(pickle.dumps(creds))
    return creds


def has_analytics_scope(creds) -> bool:
    return ANALYTICS_SCOPE in (creds.scopes or [])


def query(analytics, video_id: str, start: str, end: str,
          metrics: str, dimensions: str = "") -> dict:
    request = analytics.reports().query(
        ids="channel==MINE", startDate=start, endDate=end,
        metrics=metrics, filters=f"video=={video_id}",
        **({"dimensions": dimensions} if dimensions else {}))
    return request.execute()


def retention(analytics, video_id: str, start: str, end: str) -> list[dict]:
    """Where people left, as a curve."""
    found = analytics.reports().query(
        ids="channel==MINE", startDate=start, endDate=end,
        metrics="audienceWatchRatio,relativeRetentionPerformance",
        dimensions="elapsedVideoTimeRatio",
        filters=f"video=={video_id}").execute()
    rows = found.get("rows") or []
    return [{"elapsed_ratio": round(float(r[0]), 4),
             "watch_ratio": round(float(r[1]), 4)} for r in rows]


def pull(video_id: str, published: str, analytics) -> dict:
    start = published
    end = date.today().isoformat()
    basic = query(analytics, video_id, start, end,
                  "views,estimatedMinutesWatched,averageViewDuration,"
                  "averageViewPercentage,subscribersGained")
    headers = [h["name"] for h in basic.get("columnHeaders", [])]
    row = (basic.get("rows") or [[0] * len(headers)])[0]
    measured = dict(zip(headers, row))

    try:
        impressions = query(analytics, video_id, start, end,
                            "impressions,impressionsClickThroughRate")
        imp_headers = [h["name"] for h in impressions.get("columnHeaders", [])]
        imp_row = (impressions.get("rows") or [[0] * len(imp_headers)])[0]
        measured.update(dict(zip(imp_headers, imp_row)))
    except Exception as error:
        measured["impressions_error"] = str(error)[:160]

    try:
        measured["retention"] = retention(analytics, video_id, start, end)
    except Exception as error:
        measured["retention_error"] = str(error)[:160]
    return measured


def biggest_drop(curve: list[dict], runtime_s: float) -> tuple[float, float]:
    """Where the audience left fastest, in seconds, and by how much."""
    worst, at = 0.0, 0.0
    for a, b in zip(curve, curve[1:]):
        drop = a["watch_ratio"] - b["watch_ratio"]
        if drop > worst:
            worst, at = drop, b["elapsed_ratio"] * runtime_s
    return at, worst


def summarise(films: list[dict]) -> str:
    lines = [f"<b>Documentaries — {date.today().isoformat()}</b>", ""]
    for film in films:
        m = film["metrics"]
        lines.append(f"<b>{film['title'][:48]}</b>")
        lines.append(
            f"  {int(m.get('views', 0))} views · "
            f"{int(m.get('averageViewDuration', 0))}s avg "
            f"({m.get('averageViewPercentage', 0):.0f}%) · "
            f"+{int(m.get('subscribersGained', 0))} subs")
        ctr = m.get("impressionsClickThroughRate")
        if ctr is not None:
            lines.append(f"  {int(m.get('impressions', 0))} impressions, "
                         f"{float(ctr):.1f}% CTR")
        curve = m.get("retention") or []
        if curve and film.get("runtime_seconds"):
            at, drop = biggest_drop(curve, film["runtime_seconds"])
            lines.append(f"  steepest drop at {int(at // 60)}:{int(at % 60):02d} "
                         f"(-{drop * 100:.0f}%)")
        lines.append("")
    if len(films) < MIN_FILMS_TO_WEIGHT:
        lines.append(f"<i>{len(films)} film(s). The picker will not weight "
                     f"topics on retention until there are "
                     f"{MIN_FILMS_TO_WEIGHT}.</i>")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--quiet", action="store_true",
                    help="write the files, post nothing")
    args = ap.parse_args()

    creds = credentials()
    if not has_analytics_scope(creds):
        message = (
            "the YouTube token has no yt-analytics.readonly scope, so metrics "
            "cannot be read. Add the scope to publish/yt_authorize.py and "
            "re-authorise; the upload scopes alone return 403 here, and a "
            "metrics file full of zeros is worse than no metrics file.")
        print("SCOPE:", message)
        if not args.quiet:
            import telegram
            telegram.send(f"<b>Metrics blocked</b>\n{message}")
        return 1
    if args.check:
        print("scope: yt-analytics.readonly present")
        return 0

    ledger_path = ROOT / "artifacts" / "published.json"
    if not ledger_path.exists():
        print("nothing published yet")
        return 0
    films = json.loads(ledger_path.read_text()).get("films") or []
    if not films:
        print("nothing published yet")
        return 0

    from googleapiclient.discovery import build

    analytics = build("youtubeAnalytics", "v2", credentials=creds)
    today = date.today().isoformat()
    pulled = []
    for film in films:
        video_id = film.get("video_id")
        if not video_id:
            continue
        print(f"{film['title'][:40]} ({video_id})")
        measured = pull(video_id, film.get("published", today), analytics)
        out = ROOT / "artifacts" / "metrics" / video_id
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{today}.json").write_text(json.dumps({
            "video_id": video_id, "title": film.get("title"),
            "published": film.get("published"), "pulled": today,
            "metrics": measured}, indent=1) + "\n")
        pulled.append({**film, "metrics": measured})
        print(f"   {int(measured.get('views', 0))} views, "
              f"{int(measured.get('averageViewDuration', 0))}s average")

    if pulled and not args.quiet:
        import telegram
        telegram.send(summarise(pulled))
    print(f"-> artifacts/metrics/ ({len(pulled)} films)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Has the channel already made this film? Asked of things that are not a file.

WHY A SECOND LINE
-----------------
The picker's primary exclusion is the published ledger, which now lives
outside every branch (see lib/shared_state.py). That fixes the way it broke
on 2026-11-06 — one copy per branch, and the runner read the one without
last week's film in it.

But the failure was not really "the file was on the wrong branch". It was
"one file was the only thing standing between the picker and remaking a
film", and a single file is a single point of failure however carefully it
is placed. It can be reverted, merged away, hand-edited, or simply not
written because the publish step died after the upload and before the
append.

So two more questions get asked, and neither of them reads that ledger:

    1. IS THERE ALREADY A PROJECT FOR IT? `projects/<slug>/` is created by
       the run itself, before anything is published. It answers "has this
       been attempted", which the ledger cannot: a run that uploaded and
       then crashed leaves a project and no ledger entry.

       Asked of EVERY WORKTREE, not just the caller's. `projects/noah/`
       exists only in the development worktree — the automation worktree has
       never seen it — so a check scoped to one tree would have missed Noah
       exactly as the ledger did.

    2. IS IT ALREADY ON YOUTUBE? The channel is the authority on what the
       channel has published. If a film exists, it is there, whatever any
       file on this Mac says.

ONLY LONG-FORM UPLOADS COUNT, AND THIS IS THE WHOLE TRICK
---------------------------------------------------------
The channel is 864 uploads, of which about 855 are Shorts — and the Shorts
are where the picker's candidates COME FROM. `pick_topic.py` clusters the
Shorts ledger by the entity their titles name; a subject is a candidate
precisely because several Shorts about it did well.

So a "have we covered this" check that looked at all uploads would exclude
every candidate the picker is capable of producing, every week, for ever,
and the run would fail with "no eligible topic" and look like a ranking
problem. Measured on 2026-11-06: 864 uploads, 9 of them 8 minutes or more,
3 of those the documentaries, 1 a 28-day livestream.

Hence a floor and a ceiling. The floor separates a documentary from a
Short. The ceiling drops the 24/7 ambient livestream, which is 40,538
minutes long and tagged with things like "sleep music".
"""
from __future__ import annotations

import json
import os
import pickle
import re
import subprocess
from pathlib import Path
from typing import Any

#: A documentary is at least this long. The channel's Shorts top out around
#: 75 seconds and its shortest long-form video is 8m11s.
MIN_FILM_SECONDS = 480

#: ...and at most this long. Above it is not a film but the livestream.
MAX_FILM_SECONDS = 10800

#: The token the publisher already uses. This module only reads.
#: scripts/publish_doc.py owns the token's freshness bookkeeping; a
#: read-only consumer must not duplicate that, only the refresh.
TOKEN = Path.home() / "Developer" / "wak3up-docs" / "publish" / "yt_token.pkl"

_ISO_DURATION = re.compile(
    r"^P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?$")


def norm(text: str) -> str:
    """A subject's name, reduced to what two spellings of it have in common.

    Letters and digits only, lowercased. This is what makes the tag
    `#MaryMagdalene` match the entity `Mary Magdalene`: the channel's older
    films tag in hashtag style and the pipeline's films tag in prose style,
    and a comparison that respected the difference would match neither.
    """
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def slug_of(topic: str) -> str:
    """The project directory name `run_weekly.sh` would create for a topic.

    It must agree with the shell, because the question being asked is
    "would this run collide with a directory that already exists". The shell
    is:

        printf '%s' "$TOPIC" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-'

    — uppercase folded, spaces to hyphens, everything else DELETED. The
    deletion is why `Durupınar` becomes `durupnar`: the Turkish dotless i is
    not in `a-z`. That is the shell's behaviour and therefore the directory
    that exists, so it is reproduced rather than improved.
    """
    lowered = (topic or "").lower().replace(" ", "-")
    return "".join(c for c in lowered if c in
                   "abcdefghijklmnopqrstuvwxyz0123456789-")


def duration_seconds(iso: str) -> float:
    """An ISO-8601 duration as YouTube returns it, in seconds."""
    found = _ISO_DURATION.match(iso or "")
    if not found:
        return 0.0
    days, hours, minutes, seconds = (
        float(part) if part else 0.0 for part in found.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


# ── 1. is there already a project for it ────────────────────────────────

def worktree_roots(repo: Path) -> list[Path]:
    """Every worktree of this repository, the caller's included.

    `git worktree list` rather than globbing the parent directory: the
    answer has to be "the trees this repository actually has", and a sibling
    directory that happens to sit next to them is not one.
    """
    try:
        listing = subprocess.run(
            ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return [Path(repo)]
    if listing.returncode != 0:
        return [Path(repo)]
    roots = [Path(line.split(" ", 1)[1].strip())
             for line in listing.stdout.splitlines()
             if line.startswith("worktree ")]
    return roots or [Path(repo)]


def project_slugs(repo: Path) -> dict[str, Path]:
    """Every `projects/<slug>` directory in every worktree, by slug."""
    found: dict[str, Path] = {}
    for root in worktree_roots(repo):
        projects = root / "projects"
        if not projects.is_dir():
            continue
        for entry in sorted(projects.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                found.setdefault(entry.name, entry)
    return found


# ── 2. is it already on YouTube ─────────────────────────────────────────

def youtube_client():
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    if not TOKEN.exists():
        raise FileNotFoundError(
            f"no YouTube token at {TOKEN}: run publish/yt_authorize.py")
    credentials = pickle.loads(TOKEN.read_bytes())
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        TOKEN.write_bytes(pickle.dumps(credentials))
    return build("youtube", "v3", credentials=credentials)


def channel_films(client=None, *, min_seconds: float = MIN_FILM_SECONDS,
                  max_seconds: float = MAX_FILM_SECONDS) -> list[dict[str, Any]]:
    """The channel's long-form uploads: id, title, tags, length.

    Reads the uploads playlist rather than search.list, because search is
    eventually consistent and a film published four days ago is exactly the
    case that must not be missed.
    """
    client = client or youtube_client()
    channel = client.channels().list(part="contentDetails", mine=True).execute()
    items = channel.get("items") or []
    if not items:
        raise RuntimeError("the YouTube token authenticates no channel")
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    video_ids: list[str] = []
    page = None
    while True:
        listing = client.playlistItems().list(
            part="contentDetails", playlistId=uploads,
            maxResults=50, pageToken=page).execute()
        video_ids += [row["contentDetails"]["videoId"]
                      for row in listing.get("items") or []]
        page = listing.get("nextPageToken")
        if not page:
            break

    films: list[dict[str, Any]] = []
    seen: set[str] = set()
    for start in range(0, len(video_ids), 50):
        batch = client.videos().list(
            part="snippet,contentDetails",
            id=",".join(video_ids[start:start + 50])).execute()
        for video in batch.get("items") or []:
            if video["id"] in seen:
                continue           # the uploads playlist can list a live
                                   # broadcast twice
            seen.add(video["id"])
            length = duration_seconds(video["contentDetails"].get("duration"))
            if not (min_seconds <= length <= max_seconds):
                continue
            films.append({
                "video_id": video["id"],
                "title": video["snippet"].get("title", ""),
                "tags": video["snippet"].get("tags") or [],
                "seconds": length,
            })
    return films


def covered_subjects(films: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Normalised subject -> the long-form videos that already cover it.

    A film's subjects are its TAGS plus the capitalised phrases in its
    title. The tags carry the weight: `publish_doc.py` writes the film's own
    entity list into them, so the Noah film is tagged `Noah`, `Ararat`,
    `Gilgamesh` — the subjects themselves, in the channel's own words,
    stored on the channel.
    """
    from pick_topic import entities_in

    covered: dict[str, list[str]] = {}
    for film in films:
        names = list(film.get("tags") or [])
        names += entities_in(film.get("title", ""))
        for name in names:
            key = norm(name)
            if len(key) < 3:
                continue
            ids = covered.setdefault(key, [])
            if film["video_id"] not in ids:
                ids.append(film["video_id"])
    return covered


# ── the question, asked of all of it ────────────────────────────────────

def why_ineligible(entity: str, *, made: set[str] | None = None,
                   banned: set[str] | None = None,
                   projects: dict[str, Path] | None = None,
                   covered: dict[str, list[str]] | None = None) -> str | None:
    """Why this subject cannot be this week's film, or None if it can.

    A REASON RATHER THAN A BOOLEAN. The 2026-11-06 run printed "after
    skipping 2 already made or blacklisted: 64" and nothing else, so the one
    fact worth having — which list Noah failed to be on — was not in the
    log. Every exclusion now says which defence caught it and what the
    evidence was.
    """
    made = made or set()
    banned = banned or set()
    projects = projects or {}
    covered = covered or {}

    lowered = entity.lower()
    if lowered in made:
        return "already published (in the ledger)"
    if lowered in banned:
        return "blacklisted"

    slug = slug_of(entity)
    if slug and slug in projects:
        return f"projects/{slug}/ already exists ({projects[slug]})"

    videos = covered.get(norm(entity))
    if videos:
        return ("already a long-form upload on the channel "
                f"({', '.join(videos)})")
    return None

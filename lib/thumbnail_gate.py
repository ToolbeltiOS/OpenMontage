"""The thumbnail is shown before it goes live, and nothing waits for it.

THE SHAPE OF THIS GATE
----------------------
The script gate blocks: nothing after it means anything until a person has
read the script. This one must not. The thumbnail is the last thing made
and the schedule is the one thing that cannot slip, so:

    at delivery   the thumbnail is generated and POSTED
    the upload    proceeds immediately — private, scheduled Monday 09:00
    on "ok"       it is set on the video
    on "no"/notes it is regenerated and re-posted
    by Sunday 20:00 with no reply, it is SET ANYWAY and the reply says so

The deadline is the point of the design. A generated thumbnail beats
YouTube's auto-frame every time, so silence must not cost the film one —
and waiting for an answer must not cost it the Monday. The worst case of
not replying is the thumbnail you were shown.

WHY A RECORD ON DISK
--------------------
The reply arrives hours later, in another process, possibly after a reboot.
`artifacts/thumbnail_gate.json` is where the state lives: which still was
used, what was already tried, where in the Telegram update stream to read
from, and when the deadline falls.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

#: Sunday evening, local. Far enough before a Monday 09:00 publish to set a
#: thumbnail calmly, late enough to be a whole weekend of asking.
DEADLINE_WEEKDAY = 6          # Monday is 0
DEADLINE_HOUR = 20

#: A FILM THAT IS ALREADY PUBLIC GETS TWO HOURS, NOT A WEEKEND.
#:
#: The weekend is sized for the gap between delivery and a scheduled Monday
#: 09:00: it is the whole time there is, and nothing is live during it. When
#: the film goes public immediately that reasoning inverts — the audience is
#: already looking at the thumbnail, and "by Sunday 20:00" is a deadline
#: five days after the thing it was meant to decide.
#:
#: Measured 2026-11-23: film #6 was delivered at 10:42, the gate posted with
#: a deadline of Sunday 2026-11-29 20:00, and the film went public at 15:48
#: the same day. The record said `waiting` for six days over a live video.
#: Two hours is long enough for a reply from someone who is awake and short
#: enough that the answer still means something.
PUBLIC_NOW_HOURS = 2

#: Variants tried in order when the answer is "no" with no usable notes.
#: Each is a different reading of the same film rather than a nudge of the
#: same crop — a "no" to a thumbnail is rarely a request to move it 5%.
VARIANTS = [
    {"title_side": "left"},
    {"title_side": "right"},
    {"title_side": "left", "scale": 1.18},
    {"title_side": "right", "scale": 1.18, "offset_x": -0.06},
]


def digest(path: Path) -> str:
    """sha256 of a file, so a record can say WHICH picture it means."""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def pin(slug: str, source: Path, attempt: int) -> tuple[Path, str]:
    """Keep a copy of the exact bytes that were POSTED, beside the record.

    `renders/thumbnail.jpg` is a working path: the delivery stage rewrites
    it on every render, and a "no" regenerates it in place. The reply comes
    back hours later, so a gate that uploads "whatever is at that path now"
    sets a picture nobody approved — approving what you were shown and
    receiving what happened to be there afterwards.

    Measured 2026-11-25 on film #6: delivery regenerated the thumbnail at
    18:52:39, the gate posted it, the owner replied ok at 18:53:13, and the
    published image was restored over that path at 18:54. Nothing diverged
    only because the replacement upload ran afterwards. Ordering is not a
    guarantee, so the bytes are pinned instead.
    """
    kept = source.parent.parent / "artifacts" / f"thumbnail_posted_{attempt}.jpg"
    kept.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, kept)
    return kept, digest(kept)


def record_path(slug: str) -> Path:
    return ROOT / "projects" / slug / "artifacts" / "thumbnail_gate.json"


def deadline_for(publish_at: str | None, now: datetime | None = None,
                 public_now: bool = False) -> datetime:
    """When the thumbnail is set whether or not anyone has answered.

    The Sunday 20:00 before a SCHEDULED film goes public — far enough
    before to set it calmly, late enough to be a whole weekend of asking.

    `public_now` is the other case and it is not a shorter version of the
    same thing: the film is live, the audience can see the thumbnail, and
    there is nothing left to be early for. Two hours.

    With no publish date — a record written at delivery, before the upload
    — the next Sunday 20:00 after now, so the rule is the same shape either
    way and never lands in the past.
    """
    now = now or datetime.now()
    if public_now:
        return now + timedelta(hours=PUBLIC_NOW_HOURS)
    if publish_at:
        when = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
        when = when.astimezone().replace(tzinfo=None)
        back = (when.weekday() - DEADLINE_WEEKDAY) % 7
        candidate = (when - timedelta(days=back)).replace(
            hour=DEADLINE_HOUR, minute=0, second=0, microsecond=0)
        if candidate >= when:
            candidate -= timedelta(days=7)
        if candidate > now:
            return candidate
        # The publish is upon us; do not invent a deadline in the past.
        return min(when, now + timedelta(hours=1))
    ahead = (DEADLINE_WEEKDAY - now.weekday()) % 7 or 7
    return (now + timedelta(days=ahead)).replace(
        hour=DEADLINE_HOUR, minute=0, second=0, microsecond=0)


def _publish_record(slug: str) -> dict[str, Any]:
    path = ROOT / "projects" / slug / "artifacts" / "publish.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _publish_at(slug: str) -> str | None:
    return _publish_record(slug).get("publish_at")


def is_public(slug: str, now: datetime | None = None) -> bool:
    """Is the film already in front of an audience?

    `public_immediately` is written by `scripts/publish_doc.py --now`. The
    date comparison is the belt: a scheduled film whose moment has passed
    is just as public as one uploaded live.
    """
    record = _publish_record(slug)
    if not record:
        return False
    if record.get("public_immediately"):
        return True
    when = record.get("publish_at")
    if not when:
        return False
    try:
        moment = datetime.fromisoformat(
            str(when).replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except ValueError:
        return False
    return moment <= (now or datetime.now())


def effective_deadline(slug: str, record: dict[str, Any],
                       now: datetime | None = None) -> datetime:
    """The deadline as it stands NOW, not as it was written.

    The gate's record is written at delivery, hours before the upload, so
    the deadline in it was computed without knowing how the film would go
    out. When the film then goes public immediately, the stored Sunday is
    a week-long wait over a live video — film #6, 2026-11-23. Recomputing
    here keeps the record honest without needing the publisher to reach
    back into it.
    """
    now = now or datetime.now()
    stored = datetime.fromisoformat(record["deadline"])
    if not is_public(slug, now):
        return stored
    # Two hours from the moment the audience could first see it. Never
    # later than the deadline already promised in the record.
    base = now
    for when in (_publish_record(slug).get("uploaded"),
                 _publish_record(slug).get("publish_at"),
                 record.get("posted")):
        if not when:
            continue
        try:
            base = datetime.fromisoformat(
                str(when).replace("Z", "+00:00"))
        except ValueError:
            continue
        base = base.astimezone().replace(tzinfo=None) if base.tzinfo else base
        break
    return min(stored, base + timedelta(hours=PUBLIC_NOW_HOURS))


def video_id(slug: str) -> str | None:
    path = ROOT / "projects" / slug / "artifacts" / "publish.json"
    if path.exists():
        return json.loads(path.read_text()).get("video_id")
    return None


def post(slug: str, attempt: int = 0, notes: str | None = None
         ) -> dict[str, Any]:
    """Generate the thumbnail, show it, and write down what we are waiting
    for. Returns the record. Never raises on a Telegram failure: a film
    must not fail to publish because a photo did not send."""
    import telegram
    from build_thumbnail import build

    variant = VARIANTS[min(attempt, len(VARIANTS) - 1)]
    out = ROOT / "projects" / slug / "renders" / "thumbnail.jpg"
    made = build(slug, out, **variant)
    kept, sha = pin(slug, Path(made["path"]), attempt)

    offset = 0
    try:
        updates = telegram.updates(timeout=0)
        offset = max((u.get("update_id", 0) for u in updates), default=0)
    except Exception:                       # noqa: BLE001
        pass

    deadline = deadline_for(_publish_at(slug), public_now=is_public(slug))
    caption = (
        f"<b>Thumbnail — {slug}</b>\n"
        f"From {made['from_cut']}, the film's own hero still. "
        f"{'Attempt ' + str(attempt + 1) + '. ' if attempt else ''}"
        f"{variant}\n\n"
        f"Reply <b>ok</b> to set it, <b>no</b> for a different one, or send "
        f"notes.\n"
        f"<i>The upload is not waiting for this. With no reply it is set "
        f"anyway at {deadline:%a %d %b %H:%M}.</i>")
    if notes:
        caption += f"\n\nYour notes: {telegram.escape(notes)}"
    try:
        telegram.send_photo(made["path"], caption=caption)
    except Exception as error:              # noqa: BLE001
        print(f"   thumbnail posted nowhere ({error}); it is still on disk")

    record = {"slug": slug, "state": "waiting", "attempt": attempt,
              "variant": variant, "from_cut": made["from_cut"],
              # `path` is where it was BUILT and may be rewritten by anything;
              # `posted_file` and `sha256` are the picture that was shown.
              "path": made["path"],
              "posted_file": str(kept), "sha256": sha, "offset": offset,
              "posted": datetime.now().isoformat(timespec="seconds"),
              "deadline": deadline.isoformat(timespec="seconds")}
    record_path(slug).write_text(json.dumps(record, indent=1) + "\n")
    return record


def classify(reply: str) -> str:
    word = (reply or "").strip().lower()
    if word in ("ok", "okay", "yes", "y", "👍", "good"):
        return "ok"
    if word in ("no", "n", "nope"):
        return "no"
    return "notes" if word else "none"


def set_on_video(slug: str, why: str,
                 record: dict[str, Any] | None = None) -> bool:
    """thumbnails.set, and say so. Returns whether it went up.

    WHAT GOES UP IS WHAT WAS POSTED. The file is taken from the record's
    `posted_file` and checked against the `sha256` written beside it, so a
    picture regenerated at the working path between the question and the
    answer cannot be uploaded in place of the one that was approved.
    """
    import telegram
    sys.path.insert(0, str(ROOT / "scripts"))
    import publish_doc as P
    from googleapiclient.http import MediaFileUpload

    vid = video_id(slug)
    record = record or {}
    pinned = record.get("posted_file")
    if pinned:
        path = Path(pinned)
        if not path.exists():
            telegram.send(f"<b>Thumbnail not set</b> — {slug}\nThe picture "
                          f"that was posted is gone from {path}, so there is "
                          f"nothing to set that anyone has seen.")
            return False
        if record.get("sha256") and digest(path) != record["sha256"]:
            telegram.send(f"<b>Thumbnail not set</b> — {slug}\n{path.name} "
                          f"is not the file that was posted — its bytes "
                          f"changed. Nothing is uploaded.")
            return False
    else:
        # A record written before the bytes were pinned. Say so rather than
        # pretend the old path is the approved picture.
        path = ROOT / "projects" / slug / "renders" / "thumbnail.jpg"
        why += " (a record from before the posted file was pinned, so this " \
               "is whatever is at the working path)"
    if not vid or not path.exists():
        return False
    try:
        P.client().thumbnails().set(
            videoId=vid, media_body=MediaFileUpload(str(path))).execute()
    except Exception as error:              # noqa: BLE001
        telegram.send(f"<b>Thumbnail failed</b> — {slug}\n{error}")
        return False
    telegram.send(f"<b>Thumbnail set</b> — {slug}\n{why}\n"
                  f"https://www.youtube.com/watch?v={vid}")
    return True


def resolve(slug: str, now: datetime | None = None) -> str:
    """Act on whatever has happened since the thumbnail was posted."""
    import telegram

    path = record_path(slug)
    if not path.exists():
        return "nothing pending"
    record = json.loads(path.read_text())
    if record.get("state") != "waiting":
        return record.get("state", "done")

    verdict, reply = "none", ""
    try:
        for update in telegram.updates(offset=record.get("offset", 0) + 1):
            text = ((update.get("message") or {}).get("text") or "").strip()
            if text:
                verdict, reply = classify(text), text
    except Exception:                       # noqa: BLE001
        pass

    now = now or datetime.now()
    deadline = effective_deadline(slug, record, now)

    if verdict == "ok":
        record["state"] = "set" if set_on_video(
            slug, "you said ok", record) else "failed"
    elif verdict in ("no", "notes"):
        nxt = post(slug, attempt=record.get("attempt", 0) + 1,
                   notes=reply if verdict == "notes" else None)
        return f"regenerated as attempt {nxt['attempt'] + 1}"
    elif now >= deadline:
        record["state"] = "set" if set_on_video(
            slug,
            f"no reply by {deadline:%a %d %b %H:%M}, so it went up as shown — "
            f"a generated thumbnail beats the auto-frame",
            record) else "failed"
        record["by_deadline"] = True
    else:
        return f"waiting until {record['deadline']}"

    path.write_text(json.dumps(record, indent=1) + "\n")
    return record["state"]


def post_quietly(slug: str) -> str:
    """Post the thumbnail; never let it take the film down with it.

    `SystemExit` IS NOT AN `Exception`. It inherits from `BaseException`, so
    `except Exception` does not catch it — and SystemExit is the most likely
    failure on this path, not an exotic one: `build_thumbnail` raises it for
    a project with no props, and `stage_assets` raises it when an asset the
    props name has moved.

    Measured 2026-11-09: a two-minute slice rendered every pass, passed all
    seven gates, printed FILM DELIVERY: PASS — and then died here, because
    the slice's label is not a real project. The film was finished and the
    process still exited non-zero.

    KeyboardInterrupt is deliberately NOT caught: stopping a render by hand
    must stop it.
    """
    try:
        record = post(slug)
        return (f"thumbnail: {record['from_cut']} posted, set anyway at "
                f"{record['deadline']} if nobody replies")
    except (Exception, SystemExit) as error:
        return (f"thumbnail gate did not run ({type(error).__name__}: "
                f"{error}); the film is unaffected")

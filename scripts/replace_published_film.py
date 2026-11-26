#!/usr/bin/env python3
"""Put a re-rendered film up as a new video and retire the old one.

WHY A REPLACEMENT IS NOT AN EDIT
--------------------------------
YouTube will not let you swap the file behind a published video. A film
that has to change is a NEW upload, and the old one has to be dealt with
rather than left to compete with it in search, in the channel's uploads
and in anyone's watch later.

WHAT IT DOES, IN THIS ORDER
---------------------------
  1. uploads the new film PUBLIC, with the same title, description,
     thumbnail and captions the old one carried;
  2. sets the old video to UNLISTED — never deleted, because its id is in
     links, in the ledger's history and in whatever anyone has saved — and
     puts one line at the top of its description pointing at the new one;
  3. updates the shared ledger so the topic picker reads the new id, and
     keeps the old one beside it as `replaces`;
  4. leaves the credits page to be rebuilt, which picks up the new id —
     and that page, linked from the description, IS the attribution. No
     comment is posted on the new video; the one on the retired video is
     left where it is.

THE PICKER'S OTHER DEFENCE IS UNAFFECTED, and this is worth stating
because it looks like it should be: `lib/already_covered.channel_films`
reads the channel's UPLOADS PLAYLIST, which lists unlisted videos as well
as public ones for the account that owns them. The retired film therefore
goes on naming its subject, and the new one names it too. The subject
stays covered twice over.

    scripts/replace_published_film.py --project <slug> --dry-run
    scripts/replace_published_film.py --project <slug>
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "scripts"))

#: The line that goes at the top of the retired video's description.
POINTER = ("This upload has been replaced. The corrected film is here: "
           "https://www.youtube.com/watch?v={new}")


def ledger_rows() -> list[dict]:
    import shared_state
    return shared_state.read_published(shared_state.published_path(),
                                       allow_missing=True).get("films", [])


def retire(yt, old_id: str, new_id: str, dry_run: bool) -> str:
    """Unlisted, with one line at the top of its description."""
    got = yt.videos().list(part="snippet,status", id=old_id).execute()
    items = got.get("items") or []
    if not items:
        raise SystemExit(f"no video {old_id} on this channel")
    video = items[0]
    snippet = video["snippet"]
    pointer = POINTER.format(new=new_id)
    if snippet.get("description", "").startswith(pointer):
        return "already retired"
    snippet["description"] = pointer + "\n\n" + snippet.get("description", "")
    if dry_run:
        return f"would set {old_id} unlisted and prepend the pointer"
    yt.videos().update(part="snippet,status", body={
        "id": old_id,
        # categoryId and title are required on a snippet update, and
        # defaultLanguage is dropped if it is not sent back.
        "snippet": {k: snippet[k] for k in
                    ("title", "description", "tags", "categoryId",
                     "defaultLanguage", "defaultAudioLanguage")
                    if k in snippet},
        "status": {**video["status"], "privacyStatus": "unlisted"},
    }).execute()
    return f"{old_id} set unlisted, pointer added"


def update_ledger(project: str, new_id: str, old_id: str, title: str,
                  dry_run: bool) -> str:
    """One row per film, pointing at the new video.

    `publish_doc` writes the ledger through `shared_state.append_film`,
    which is idempotent on VIDEO ID — so a replacement's upload appends a
    SECOND row for a film that already has one, because the new id matches
    nothing. This collapses them: the original row keeps its `entities`
    and the date the subject was first published, takes the new id, and
    lists every id it has had in `replaces`.

    Under the lock, like every other writer. `append_film` cannot express
    it, which is why this is the one read-modify-write that matches on the
    project instead of the id.
    """
    import shared_state
    path = shared_state.published_path()
    if dry_run:
        rows = [r for r in ledger_rows() if r.get("project") == project]
        return (f"would collapse {len(rows)} row(s) for {project} into one "
                f"naming {new_id} (was {old_id})")
    with shared_state._locked(path):
        ledger = shared_state.read_published(path, allow_missing=True)
        films = ledger.get("films") or []
        mine = [r for r in films if r.get("project") == project]
        if not mine:
            raise SystemExit(f"{project} is not in the ledger — nothing "
                             f"was written")
        # The oldest row is the record of the subject: it carries the
        # entities the picker matches on and the date it was first made.
        base = next((r for r in mine if r.get("video_id") == old_id), mine[0])
        seen = [r.get("video_id") for r in mine
                if r.get("video_id") and r.get("video_id") != new_id]
        record = dict(base)
        record["replaces"] = sorted(set([*base.get("replaces", []), *seen]))
        record["video_id"] = new_id
        record["url"] = f"https://www.youtube.com/watch?v={new_id}"
        record["title"] = title or record.get("title")
        record["replaced_utc"] = datetime.now(timezone.utc).isoformat(
            timespec="seconds")
        ledger["films"] = [r for r in films if r.get("project") != project]
        ledger["films"].append(record)
        ledger["films"].sort(key=lambda r: r.get("published") or "")
        shared_state._write_atomic(path, json.dumps(ledger, indent=1) + "\n")
    return (f"ledger: one row for {project} naming {new_id}, "
            f"replaces {record['replaces']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--new-video", default=None,
                    help="skip the upload and retire against a video that "
                         "is already up (resuming a half-done replacement)")
    args = ap.parse_args(argv)

    project = ROOT / "projects" / args.project
    publish = project / "artifacts" / "publish.json"
    if not publish.exists():
        raise SystemExit(f"no publish record at {publish}")
    old = json.loads(publish.read_text())
    old_id = old.get("video_id")
    if not old_id:
        raise SystemExit(f"{publish} names no video to replace")
    listing = json.loads(
        (project / "artifacts" / "listing.json").read_text())

    print(f"{args.project}: replacing {old_id} — {listing['title']!r}")

    import publish_doc
    new_id = args.new_video
    if new_id is None:
        if args.dry_run:
            print("  would upload the new film PUBLIC with the same title, "
                  "description, thumbnail and captions")
            new_id = "<new>"
        else:
            rc = publish_doc.main(["--project", args.project, "--now"])
            if rc != 0:
                raise SystemExit("the upload failed; nothing was retired")
            new_id = json.loads(publish.read_text())["video_id"]
            print(f"  uploaded: https://www.youtube.com/watch?v={new_id}")
    else:
        print(f"  using the video already up: {new_id}")

    yt = None if args.dry_run else publish_doc.client()
    if args.dry_run:
        print(f"  {POINTER.format(new=new_id)}")
        print(f"  would set {old_id} unlisted")
    else:
        print("  " + retire(yt, old_id, new_id, args.dry_run))
    print("  " + update_ledger(args.project, new_id, old_id,
                               listing.get("title"), args.dry_run))
    print("  next: scripts/publish_credits_page.sh "
          f"{args.project} — the page links to the video id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

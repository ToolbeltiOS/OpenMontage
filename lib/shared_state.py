"""State that belongs to the CHANNEL, not to a branch.

WHY THIS EXISTS
---------------
On 2026-11-06 the Friday picker chose Noah, four days after Noah was
published. Nothing was wrong with the picker: it skips any subject in
`artifacts/published.json`, and the copy it read did not have Noah in it.

That file was TRACKED IN GIT, so there was one copy per branch. Noah was
built and published out of the `asset-library` worktree, and
`publish_doc.py` appended the film to the `asset-library` copy. The runner
reads its own worktree, pinned to `automation`, whose copy still ended at
Easter Island. Two files, both named `artifacts/published.json`, both
honest about their own branch, and the one the runner reads had never heard
of last week's film.

A ledger of what the CHANNEL has published is not a property of a branch.
The channel has one past. So it lives here, outside every worktree, at

    ~/Developer/wak3up-docs/state/

which is the same thing already done for the YouTube token — see
`PUBLISH_DIR` in scripts/publish_doc.py. Every worktree reads and writes
this one file, and a merge can no longer lose a film or a branch fork one.

WHAT IS IN IT
-------------
    published.json    the films the channel has published. The picker's
                      primary exclusion list and the tripwire's "did a film
                      get made this week".
    topic_picks.jsonl  one line per topic the picker chose, as a RECORD.

THE PICK HISTORY IS NOT A GATE. It records what was chosen, by which
commit, in which tree — the thing that was impossible to reconstruct when
this bug was being diagnosed. It deliberately excludes nothing: a run that
died after picking a subject must be able to pick it again, and the
"was this already attempted" question is answered by whether
`projects/<slug>/` exists, not by this file.

WHY A READER RAISES
-------------------
`read_published()` refuses a missing or unparseable ledger instead of
returning "nothing has been published yet". Those two answers are
indistinguishable to a caller and they mean opposite things: one is a fresh
machine, the other is the failure this module exists to stop. A picker that
reads damage as an empty ledger re-picks every film the channel has ever
made. The sibling wak3up poster learned the same lesson the same way — a
nightly job wrote `[]` over a schedule in a write race and the readers took
it for an empty week.

So writes go through `append_film()`, which holds a lock for the whole
read-modify-write and replaces the file atomically; a half-written ledger
cannot be observed, and two worktrees publishing at once cannot lose a
film between them.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

#: Overridable so tests can point at a scratch directory. The default is an
#: absolute path rather than anything derived from the repository, because
#: "derived from the repository" is how there came to be two of these.
DEFAULT_STATE_DIR = Path.home() / "Developer" / "wak3up-docs" / "state"
STATE_DIR_ENV = "WAK3UP_DOCS_STATE"


class LedgerDamaged(RuntimeError):
    """The ledger exists but cannot be read as a ledger.

    Separate from a missing one on purpose: a missing ledger can be seeded,
    damage must be looked at.
    """


def state_dir() -> Path:
    return Path(os.environ.get(STATE_DIR_ENV) or DEFAULT_STATE_DIR)


def published_path() -> Path:
    return state_dir() / "published.json"


def picks_path() -> Path:
    return state_dir() / "topic_picks.jsonl"


def _lock_path(target: Path) -> Path:
    return target.with_suffix(target.suffix + ".lock")


@contextmanager
def _locked(target: Path) -> Iterator[None]:
    """Hold an exclusive lock across a whole read-modify-write.

    The lock is a FILE BESIDE THE TARGET, not the target itself: the write
    is an atomic replace, so a lock held on the target's own inode would be
    released onto a file that is no longer the one anybody opens.
    """
    lock = _lock_path(target)
    lock.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(lock, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        os.close(handle)


def _write_atomic(target: Path, text: str) -> None:
    """Replace `target` in one step, or not at all."""
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=str(target.parent),
                                    prefix=target.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w") as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, target)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def read_published(path: Path | None = None, *,
                   allow_missing: bool = False) -> dict[str, Any]:
    """The films the channel has published.

    Raises unless `allow_missing`, because a caller that cannot tell a fresh
    machine from a lost ledger will pick a film that already exists.

    `path` overrides the shared location. It exists for tests and for
    answering "what does THAT file say" by hand; nothing in the pipeline
    passes it, because the point of this module is that there is one.
    """
    path = Path(path) if path else published_path()
    if not path.exists():
        if allow_missing:
            return {"films": []}
        raise FileNotFoundError(
            f"no published ledger at {path}.\n"
            f"This is the channel's record of what it has already made, and "
            f"without it the picker cannot tell a new subject from last "
            f"week's film. Seed it (a films list, one entry per published "
            f"video, each with video_id, title, published and entities), or "
            f"set {STATE_DIR_ENV} to the directory that holds it.")
    try:
        ledger = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise LedgerDamaged(
            f"{path} is not readable as JSON ({error}). It is NOT being "
            f"treated as an empty ledger: that would re-pick every film the "
            f"channel has made. Repair it by hand.") from error
    if not isinstance(ledger, dict) or not isinstance(ledger.get("films"), list):
        raise LedgerDamaged(
            f"{path} parsed but has no `films` list, so it is not a ledger. "
            f"Refusing to read it as an empty one.")
    return ledger


def published_films(path: Path | None = None, *,
                    allow_missing: bool = False) -> list[dict[str, Any]]:
    return read_published(path, allow_missing=allow_missing)["films"]


def append_film(record: dict[str, Any]) -> Path:
    """Add one published film to the ledger, under a lock.

    Idempotent on `video_id`: publishing is retried, and a retry that
    appended a second entry would make the ledger disagree with the channel
    about how many films exist.
    """
    path = published_path()
    with _locked(path):
        ledger = read_published(path, allow_missing=True)
        films = ledger.setdefault("films", [])
        video_id = record.get("video_id")
        for existing in films:
            if video_id and existing.get("video_id") == video_id:
                existing.update(record)
                break
        else:
            films.append(record)
        _write_atomic(path, json.dumps(ledger, indent=1) + "\n")
    return path


def record_pick(entity: str, slug: str, **context: Any) -> Path:
    """Append one line to the pick history. A record, not a gate."""
    path = picks_path()
    line = json.dumps({
        "when": datetime.now(timezone.utc).isoformat(),
        "entity": entity,
        "slug": slug,
        **context,
    }, sort_keys=True)
    with _locked(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as out:
            out.write(line + "\n")
            out.flush()
            os.fsync(out.fileno())
    return path


def read_picks() -> list[dict[str, Any]]:
    """The pick history, oldest first. A damaged line is skipped, not fatal:
    nothing gates on this file, so one bad line must not stop a run."""
    path = picks_path()
    if not path.exists():
        return []
    picks = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            picks.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return picks

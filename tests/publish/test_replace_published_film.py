"""Replacing a published film, without losing what the ledger knows.

YouTube will not swap the file behind a published video, so a film that
has to change is a NEW upload and the old one has to be retired. Films #5
and #6 are both being replaced for defects that reached the screen — NaN
where six timeline cards' years should be, and six maps drawn across a
third of the planet.

THE LEDGER IS THE PART THAT CAN GO WRONG QUIETLY. `publish_doc` writes it
through `shared_state.append_film`, which is idempotent on VIDEO ID, so a
replacement's upload appends a SECOND row for a film that already has one
— the new id matches nothing. Two rows for one film is how the picker
comes to think a subject was made twice, and the entities it matches on
live on the first row.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import shared_state                                            # noqa: E402

spec = importlib.util.spec_from_file_location(
    "replace_published_film", ROOT / "scripts" / "replace_published_film.py")
RP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RP)

OLD, NEW = "NWSDd5RJQ0Y", "newVideoId1"
SLUG = "atomic-bombings-of-hiroshima-and-nagasaki"


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    """A ledger of our own, shaped like the real one."""
    path = tmp_path / "published.json"
    path.write_text(json.dumps({"films": [
        {"project": "king-tut", "video_id": "d8e1wVEqCUs",
         "title": "King Tut", "url": "u", "published": "2026-11-09",
         "entities": ["Tutankhamun"]},
        {"project": SLUG, "video_id": OLD, "title": "Hiroshima",
         "url": f"https://www.youtube.com/watch?v={OLD}",
         "published": "2026-11-16",
         "entities": ["Hiroshima", "Nagasaki", "Groves"]},
    ]}, indent=1))
    monkeypatch.setattr(shared_state, "published_path", lambda: path)
    monkeypatch.setattr(
        RP, "ledger_rows",
        lambda: shared_state.read_published(path, allow_missing=True)["films"])
    return path


def films(path: Path, slug: str = SLUG) -> list[dict]:
    return [r for r in json.loads(path.read_text())["films"]
            if r["project"] == slug]


def after_upload(path: Path) -> None:
    """What `publish_doc` leaves behind: a second row, new id, no history."""
    blob = json.loads(path.read_text())
    blob["films"].append({"project": SLUG, "video_id": NEW,
                          "title": "Hiroshima", "url": "u",
                          "published": "2026-11-25", "entities": []})
    path.write_text(json.dumps(blob, indent=1))


class TestTheLedgerEndsWithOneRow:
    def test_two_rows_become_one(self, ledger):
        after_upload(ledger)
        assert len(films(ledger)) == 2
        RP.update_ledger(SLUG, NEW, OLD, "Hiroshima", dry_run=False)
        assert len(films(ledger)) == 1

    def test_it_names_the_new_video(self, ledger):
        after_upload(ledger)
        RP.update_ledger(SLUG, NEW, OLD, "Hiroshima", dry_run=False)
        row = films(ledger)[0]
        assert row["video_id"] == NEW
        assert row["url"].endswith(NEW)

    def test_the_entities_survive(self, ledger):
        """THE ONE THAT MATTERS FOR THE PICKER. They live on the original
        row, and the row the upload appends has none."""
        after_upload(ledger)
        RP.update_ledger(SLUG, NEW, OLD, "Hiroshima", dry_run=False)
        assert films(ledger)[0]["entities"] == [
            "Hiroshima", "Nagasaki", "Groves"]

    def test_the_first_publication_date_survives(self, ledger):
        """When the subject was made, not when it was re-made."""
        after_upload(ledger)
        RP.update_ledger(SLUG, NEW, OLD, "Hiroshima", dry_run=False)
        assert films(ledger)[0]["published"] == "2026-11-16"

    def test_the_old_id_is_kept(self, ledger):
        after_upload(ledger)
        RP.update_ledger(SLUG, NEW, OLD, "Hiroshima", dry_run=False)
        assert films(ledger)[0]["replaces"] == [OLD]

    def test_replacing_twice_accumulates_rather_than_forgets(self, ledger):
        after_upload(ledger)
        RP.update_ledger(SLUG, NEW, OLD, "Hiroshima", dry_run=False)
        RP.update_ledger(SLUG, "thirdId", NEW, "Hiroshima", dry_run=False)
        row = films(ledger)[0]
        assert row["video_id"] == "thirdId"
        assert set(row["replaces"]) == {OLD, NEW}

    def test_the_other_films_are_untouched(self, ledger):
        after_upload(ledger)
        RP.update_ledger(SLUG, NEW, OLD, "Hiroshima", dry_run=False)
        assert len(films(ledger, "king-tut")) == 1
        assert len(json.loads(ledger.read_text())["films"]) == 2

    def test_a_dry_run_writes_nothing(self, ledger):
        before = ledger.read_text()
        said = RP.update_ledger(SLUG, NEW, OLD, "Hiroshima", dry_run=True)
        assert ledger.read_text() == before
        assert "would" in said

    def test_a_film_that_is_not_in_the_ledger_refuses(self, ledger):
        with pytest.raises(SystemExit):
            RP.update_ledger("never-made", NEW, OLD, "x", dry_run=False)


class FakeYouTube:
    """Enough of the API to watch what the retirement sends."""

    def __init__(self, description: str = "The original description."):
        self.sent: dict | None = None
        self._video = {
            "id": OLD,
            "snippet": {"title": "Hiroshima", "description": description,
                        "tags": ["a"], "categoryId": "27",
                        "defaultLanguage": "en"},
            "status": {"privacyStatus": "public", "license": "youtube",
                       "selfDeclaredMadeForKids": False},
        }

    def videos(self):
        return self

    def list(self, **_kw):
        return self

    def update(self, part=None, body=None):
        self.sent = body
        return self

    def execute(self):
        if self.sent is not None:
            return self.sent
        return {"items": [self._video]}


class TestTheOldVideoIsRetiredNotDeleted:
    def test_it_becomes_unlisted(self):
        yt = FakeYouTube()
        RP.retire(yt, OLD, NEW, dry_run=False)
        assert yt.sent["status"]["privacyStatus"] == "unlisted"

    def test_the_pointer_is_the_first_line(self):
        yt = FakeYouTube()
        RP.retire(yt, OLD, NEW, dry_run=False)
        first = yt.sent["snippet"]["description"].splitlines()[0]
        assert first == RP.POINTER.format(new=NEW)
        assert NEW in first

    def test_the_original_description_is_kept_below_it(self):
        yt = FakeYouTube("The original description.")
        RP.retire(yt, OLD, NEW, dry_run=False)
        assert "The original description." in yt.sent["snippet"]["description"]

    def test_the_title_and_tags_are_sent_back(self):
        """A snippet update drops whatever it does not carry."""
        yt = FakeYouTube()
        RP.retire(yt, OLD, NEW, dry_run=False)
        assert yt.sent["snippet"]["title"] == "Hiroshima"
        assert yt.sent["snippet"]["tags"] == ["a"]
        assert yt.sent["snippet"]["categoryId"] == "27"

    def test_running_it_twice_changes_nothing(self):
        yt = FakeYouTube(RP.POINTER.format(new=NEW) + "\n\nThe original.")
        assert RP.retire(yt, OLD, NEW, dry_run=False) == "already retired"
        assert yt.sent is None

    def test_a_dry_run_sends_nothing(self):
        yt = FakeYouTube()
        said = RP.retire(yt, OLD, NEW, dry_run=True)
        assert yt.sent is None and "would" in said

    def test_nothing_is_ever_deleted(self):
        source = (ROOT / "scripts" / "replace_published_film.py").read_text()
        assert "videos().delete" not in source
        assert "delete(" not in source

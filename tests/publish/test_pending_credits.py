"""A scheduled film owes its credits until it goes public.

YouTube disables comments on a private video. Measured on the four films:

    easter-island  public_immediately=True   credits posted
    noah           public_immediately=True   credits posted
    king-tut       public_immediately=False  commentThreads.list ->
                                             commentsDisabled, insert -> 403

The 403 says "insufficient permissions. The request might not be properly
authorized", which is not what it is: every scope is granted. So the
publisher no longer attempts it on a scheduled upload, and says plainly
what is owed and when it can be done.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

SOURCE = (ROOT / "scripts" / "publish_doc.py").read_text()
POSTER = (ROOT / "scripts" / "post_pending_credits.py").read_text()


class TestTheSchedulerDoesNotTryTheImpossible:
    def test_a_scheduled_upload_does_not_attempt_the_comment(self):
        """The guard is on publish_at, not on a caught exception: a 403 that
        reads as a missing scope costs an hour to disbelieve."""
        assert 'if listing.get("pinned_comment") and publish_at is not None:' \
            in SOURCE

    def test_it_says_what_is_owed_and_when_it_can_be_done(self):
        assert "POST THE CREDITS COMMENT after the film goes public" in SOURCE
        assert "disables comments while a video is private" in SOURCE

    def test_the_public_path_still_posts_with_the_upload(self):
        """A film published with --now has comments and must carry its
        credits immediately, as noah and easter-island did."""
        assert 'elif listing.get("pinned_comment"):' in SOURCE
        assert 'yt.commentThreads().insert(' in SOURCE

    def test_the_reason_is_written_down_with_its_measurement(self):
        for phrase in ("commentsDisabled", "easter-island and noah",
                       "youtube.force-ssl"):
            assert phrase in SOURCE, phrase


class TestThePosterRefusesToPostTwice:
    """A credits comment posted twice is worse than one posted late."""

    def test_a_recorded_comment_id_stops_it(self, tmp_path, monkeypatch):
        import post_pending_credits as C
        project = tmp_path / "projects" / "film" / "artifacts"
        project.mkdir(parents=True)
        (project / "publish.json").write_text(json.dumps(
            {"video_id": "abc", "comment_id": "already-there"}))
        monkeypatch.setattr(C, "ROOT", tmp_path)
        assert C.pending("film") is None

    def test_a_missing_comment_id_is_what_it_looks_for(self, tmp_path,
                                                      monkeypatch):
        import post_pending_credits as C
        project = tmp_path / "projects" / "film" / "artifacts"
        project.mkdir(parents=True)
        (project / "publish.json").write_text(json.dumps(
            {"video_id": "abc", "comment_id": None}))
        monkeypatch.setattr(C, "ROOT", tmp_path)
        assert C.pending("film") == {"video_id": "abc", "comment_id": None}

    def test_a_comment_already_on_the_channel_stops_it(self):
        """The record can be lost; the channel cannot. Matching on the first
        sixty characters, because YouTube returns what it stored."""
        import post_pending_credits as C
        text = "CREDITS\n\nEvery still in this film, with its author and "\
               "licence, in the order they appear.\n\n1. ..."

        class FakeThreads:
            def list(self, **kw):
                return self

            def execute(self):
                return {"items": [{"id": "thread-1", "snippet": {
                    "topLevelComment": {"snippet": {"textOriginal": text}}}}]}

        class FakeYT:
            def commentThreads(self):
                return FakeThreads()

        assert C.already_ours(FakeYT(), "abc", text) == "thread-1"
        assert C.already_ours(FakeYT(), "abc", "something else") is None

    def test_it_is_runnable_for_every_film_at_once(self):
        assert '"--all"' in POSTER

    def test_a_private_video_is_reported_not_attempted(self):
        """Exit 2, distinct from a real failure's 1, so a scheduled run can
        tell 'not yet' from 'broken'."""
        assert 'if privacy != "public":' in POSTER
        assert "return 2" in POSTER

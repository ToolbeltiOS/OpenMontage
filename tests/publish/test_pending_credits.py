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

    def test_it_records_where_the_credits_actually_are(self):
        """Not as an owed item: the attribution is the hosted page the
        description links to, and the page is up before the upload runs.
        The comment is a second copy, and if it never posts the film is
        still attributed."""
        assert "credits are at {page_url(args.project)}" in SOURCE
        assert "done.append(" in SOURCE
        assert "POST THE CREDITS COMMENT" not in SOURCE, (
            "the comment is a backup copy and cannot be a manual chore")

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


class TestTheAgentThatPostsThemLater:
    """Hourly, forever, because a Monday-morning one-off is a thing someone
    has to remember. The other three agents are covered by
    tests/automation/test_runner_wiring.py, which parametrises over
    launchd/com.wak3up.docs.*.plist and so covers this one the day it
    arrives — that is why those tests are not repeated here."""

    PLIST = ROOT / "launchd" / "com.wak3up.docs.afterpublish.plist"

    def plist(self):
        import plistlib
        return plistlib.loads(self.PLIST.read_bytes())

    def test_the_agent_exists(self):
        assert self.PLIST.exists()

    def test_it_runs_every_hour(self):
        """StartInterval and not StartCalendarInterval: launchd runs a
        missed interval when the Mac wakes, and this Mac sleeps."""
        d = self.plist()
        assert d["StartInterval"] == 3600
        assert "StartCalendarInterval" not in d

    def test_it_runs_the_poster_over_every_film(self):
        d = self.plist()
        assert d["ProgramArguments"][-1] == "--all"
        assert d["ProgramArguments"][-2].endswith("after_publish.py")

    def test_it_runs_from_the_runner_worktree(self):
        d = self.plist()
        assert d["WorkingDirectory"] == "/Users/mac/Developer/wak3up-docs/runner"
        assert all("/runner/" in a for a in d["ProgramArguments"][:-1])

    def test_it_also_runs_when_it_is_loaded(self):
        """A film may already be public and owed its credits."""
        assert self.plist()["RunAtLoad"] is True


class TestTheLinkIsInTheDescription:
    """CC BY 4.0 3(a)(2) is satisfied by a link to a resource carrying the
    required information. That link is the attribution, so it goes above
    the fold and it goes in the description, which publishes with the film
    — not in a comment that cannot exist while the video is private."""

    SOURCE = (ROOT / "scripts" / "build_listing.py").read_text()

    def test_the_description_links_the_page(self):
        assert "page_url(project)" in self.SOURCE
        assert "from build_credits_page import page_url" in self.SOURCE

    def test_it_sits_directly_under_the_hook(self):
        """Not only in the credits block at the bottom, where nobody
        reading three lines will see it."""
        top = self.SOURCE[self.SOURCE.find("parts = [hook(script)"):]
        assert top.index("page_url(project)") < top.index("CHAPTERS")

    def test_it_says_how_many_assets_and_under_what_terms(self):
        """A bare link is not a licence summary."""
        top = self.SOURCE[self.SOURCE.find("parts = [hook(script)"):]
        head = top[:top.index("CHAPTERS")]
        # The sentence is split across f-string literals in the source, so
        # the joined text is what gets asserted, not the lines.
        joined = "".join(head.split('"')[1::2])
        assert "freely licensed images and clips" in joined, joined[:200]
        assert "each credited with its author and licence" in joined
        assert "credit_required_assets" in head

    def test_the_pinned_comment_is_no_longer_what_the_description_cites(self):
        assert "is in the pinned comment" not in self.SOURCE

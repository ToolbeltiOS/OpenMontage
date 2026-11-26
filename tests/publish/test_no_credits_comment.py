"""The credits comment is withdrawn. The page in the description is the record.

WHY THERE IS A TEST FILE FOR SOMETHING THAT NO LONGER HAPPENS

The comment was never the attribution. CC BY 4.0 3(a)(2) is satisfied by
"providing a URI or hyperlink to a resource that includes the required
information", and that resource — the hosted credits page — is pushed
before the upload runs and linked above the fold in the description. The
comment was a second copy of the same list, and it cost:

  * a per-film manual chore, "PIN the credits comment (no API for it)",
    which was never required by anything;
  * an hourly launchd agent and a whole script, because YouTube disables
    comments on a private video and a scheduled film is private until it
    goes live;
  * a length limit measured against the live API (8,000, not the
    documented 10,000) and a split-into-replies path for the films whose
    banks run past it;
  * an idempotency check against the channel, because a credits comment
    posted twice is worse than one posted late.

All of that is gone. This file is the guard that it stays gone — the same
shape as the bash-guard removal, where the test that the forms worked was
replaced by the test that they are not there. The comments already on the
six published films are left exactly where they are: withdrawing the
mechanism is not a reason to go back and delete what it posted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "lib"))

PUBLISHER = (ROOT / "scripts" / "publish_doc.py").read_text()
AFTER = (ROOT / "scripts" / "after_publish.py").read_text()
REPLACE = (ROOT / "scripts" / "replace_published_film.py").read_text()


class TestNothingPostsAComment:
    def test_the_poster_script_is_gone(self):
        assert not (ROOT / "scripts" / "post_pending_credits.py").exists()

    def test_nothing_imports_it(self):
        for path in sorted((ROOT / "scripts").glob("*.py")) + \
                sorted((ROOT / "lib").glob("*.py")):
            assert "post_pending_credits" not in path.read_text(), path.name

    def test_no_source_of_ours_inserts_a_comment(self):
        """A rule over the tree, not a list of the three files I happened to
        edit: the next script that reaches for commentThreads().insert fails
        here rather than on the channel."""
        offenders = []
        for folder in ("scripts", "lib"):
            for path in sorted((ROOT / folder).glob("*.py")):
                body = path.read_text()
                if "commentThreads().insert" in body or \
                        "comments().insert" in body:
                    offenders.append(path.name)
        assert offenders == [], offenders

    def test_the_length_limit_and_the_split_went_with_it(self):
        """Dead code with a passing test suite is the shape this project has
        already been bitten by three times."""
        assert "COMMENT_LIMIT" not in PUBLISHER
        assert "def split_comment" not in PUBLISHER

    def test_the_publisher_says_where_the_credits_are_instead(self):
        assert "credits are at {page_url(args.project)}" in PUBLISHER
        assert "done.append(" in PUBLISHER

    def test_the_replacement_does_not_post_one_either(self):
        assert "commentThreads" not in REPLACE
        assert "No\n     comment is posted on the new video" in REPLACE


class TestTheAgentKeepsOnlyTheThumbnailJob:
    PLIST = ROOT / "launchd" / "com.wak3up.docs.afterpublish.plist"

    def plist(self):
        import plistlib
        return plistlib.loads(self.PLIST.read_bytes())

    def test_after_publish_does_not_mention_credits_work(self):
        assert "post_pending_credits" not in AFTER
        assert "credits FAILED" not in AFTER

    def test_it_still_resolves_the_thumbnail(self):
        assert "thumbnail_gate" in AFTER
        assert "resolve(slug)" in AFTER

    def test_the_agent_still_exists_and_runs_hourly(self):
        """StartInterval and not StartCalendarInterval: launchd runs a missed
        interval when the Mac wakes, and this Mac sleeps."""
        d = self.plist()
        assert d["StartInterval"] == 3600
        assert "StartCalendarInterval" not in d

    def test_it_runs_over_every_film_from_the_runner(self):
        d = self.plist()
        assert d["ProgramArguments"][-1] == "--all"
        assert d["ProgramArguments"][-2].endswith("after_publish.py")
        assert d["WorkingDirectory"] == "/Users/mac/Developer/wak3up-docs/runner"

    def test_it_also_runs_when_it_is_loaded(self):
        """A film may already be public and waiting on its thumbnail."""
        assert self.plist()["RunAtLoad"] is True


class FakeYouTube:
    """Enough of the API for a publish to run to the end of its paperwork."""

    def __init__(self):
        self.commented = False

    # Anything the publisher reaches for that is not a comment is a no-op
    # that answers plausibly; a comment call is recorded and would fail the
    # assertion below.
    def thumbnails(self):
        return self

    def playlists(self):
        return self

    def playlistItems(self):
        return self

    def captions(self):
        return self

    def commentThreads(self):                # pragma: no cover - must not run
        self.commented = True
        return self

    def comments(self):                      # pragma: no cover - must not run
        self.commented = True
        return self

    def set(self, **_kw):
        return self

    def insert(self, **_kw):
        return self

    def list(self, **_kw):
        return self

    def execute(self):
        return {"items": [{"id": "PL1", "snippet": {"title": "Documentaries"}}],
                "id": "thread-1",
                "snippet": {"topLevelComment": {"id": "top-1"}}}


@pytest.fixture()
def published(tmp_path, monkeypatch):
    """A whole film on disk, published through a faked API.

    `--root` exists for exactly this: the project is built in a temporary
    directory and the publisher reaches it by the SAME default paths the
    weekly chain uses, so what is tested is the path that runs on Friday.
    """
    import publish_doc as P
    import shared_state
    import telegram

    project = tmp_path / "projects" / "film"
    (project / "artifacts").mkdir(parents=True)
    (project / "renders").mkdir(parents=True)
    (project / "artifacts" / "listing.json").write_text(json.dumps({
        "title": "A Film", "description": "d", "tags": ["t"],
        "categoryId": "27", "containsSyntheticMedia": True,
        "entities": ["Someone"],
        # The block is still built by build_listing; nothing posts it.
        "pinned_comment": "CREDITS\n\n1. A photograph — Someone — CC BY 4.0",
    }))
    (project / "renders" / "final.mp4").write_bytes(b"\x00")
    (project / "renders" / "thumbnail.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (project / "artifacts" / "captions.en.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nWord\n\n")

    monkeypatch.setenv(shared_state.STATE_DIR_ENV, str(tmp_path / "state"))
    (tmp_path / "state").mkdir()
    monkeypatch.setattr(P, "check_token", lambda: (True, "fine"))
    yt = FakeYouTube()
    monkeypatch.setattr(P, "client", lambda: yt)
    monkeypatch.setattr(P, "upload", lambda *a, **k: "vid00000001")
    monkeypatch.setattr(P, "caption_verdict", lambda *a, **k: (True, "PASS"))
    monkeypatch.setattr(telegram, "send", lambda *a, **k: None)

    assert P.main(["--project", "film", "--root", str(tmp_path), "--now"]) == 0
    record = json.loads(
        (project / "artifacts" / "publish.json").read_text())
    return record, yt


class TestAPublishLeavesNoCommentOwedEntry:
    def test_no_comment_was_posted(self, published):
        _record, yt = published
        assert yt.commented is False

    def test_nothing_in_the_manual_list_is_about_a_comment(self, published):
        record, _yt = published
        for item in record["manual"]:
            low = item.lower()
            assert "comment" not in low, item
            assert "pin " not in low, item
            assert "credits" not in low, item

    def test_the_manual_list_is_the_end_screen_and_the_disclosure(self,
                                                                  published):
        record, _yt = published
        assert len(record["manual"]) == 2, record["manual"]
        assert any("End Screen" in m for m in record["manual"])
        assert any("Altered content" in m for m in record["manual"])

    def test_the_record_no_longer_carries_a_comment_id(self, published):
        """The field was what `post_pending_credits` read to decide a film
        still owed its credits. Nothing owes them, so nothing records it."""
        record, _yt = published
        assert "comment_id" not in record

    def test_the_credits_are_reported_as_done_not_owed(self, published):
        record, _yt = published
        assert any("credits are at" in d and "attribution" in d
                   for d in record["done"]), record["done"]


class TestTheLinkIsInTheDescription:
    """Kept from the file this replaces. With the comment withdrawn, this
    link is the ONLY place the attribution lives for a viewer on the video,
    so these tests matter more than they did, not less."""

    SOURCE = (ROOT / "scripts" / "build_listing.py").read_text()

    def test_the_description_links_the_page(self):
        assert "page_url(project)" in self.SOURCE
        assert "from build_credits_page import page_url" in self.SOURCE

    def test_it_sits_directly_under_the_hook(self):
        """Not only in the credits block at the bottom, where nobody reading
        three lines will see it."""
        top = self.SOURCE[self.SOURCE.find("parts = [hook(script)"):]
        assert top.index("page_url(project)") < top.index("CHAPTERS")

    def test_it_says_how_many_assets_and_under_what_terms(self):
        """A bare link is not a licence summary."""
        top = self.SOURCE[self.SOURCE.find("parts = [hook(script)"):]
        head = top[:top.index("CHAPTERS")]
        joined = "".join(head.split('"')[1::2])
        assert "freely licensed images and clips" in joined, joined[:200]
        assert "each credited with its author and licence" in joined
        assert "credit_required_assets" in head

    def test_the_description_does_not_cite_a_pinned_comment(self):
        assert "is in the pinned comment" not in self.SOURCE

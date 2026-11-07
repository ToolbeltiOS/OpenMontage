"""Noah must not be eligible, and it must take three independent failures
to make him eligible again.

THE BUG THIS HOLDS SHUT
-----------------------
The Noah film published 2026-11-02 (gQvV4K3LxVc). On Friday 2026-11-06 the
weekly picker chose Noah, and it was right to, given what it was looking at:
`artifacts/published.json` was TRACKED IN GIT, so there was one copy per
branch. Noah was built and published out of the `asset-library` worktree and
appended to that branch's copy. The runner is pinned to `automation`, whose
copy ended at Easter Island.

Nothing in the suite could have caught it, because nothing asserted anything
about what the picker excludes. These do, three times over:

    the ledger          — now outside every worktree (lib/shared_state.py)
    the project directory — in ANY worktree, not just the caller's
    the channel itself  — the long-form uploads, read from YouTube

Each is tested so that it alone is enough. The 2026-11-06 failure was one
check having one bad input; a single defence is a single point of failure
however carefully its file is placed.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "scripts"))

import already_covered                                  # noqa: E402
import shared_state                                     # noqa: E402
from already_covered import (covered_subjects, project_slugs, slug_of,
                             why_ineligible)             # noqa: E402

#: The three films the channel had published when this was written. The
#: video ids are the identity: a title can be edited in Studio.
PUBLISHED = {
    "smlOZ9v2jdM": "They Said It Couldn't Be Built",
    "CDpzQKwTBsI": "Easter Island: The Part Nobody Can Explain",
    "gQvV4K3LxVc": "The Flood Story Before the Bible",
}

#: The Noah film's real tags, as they are on YouTube. `publish_doc.py` writes
#: the film's own entity list into them, which is why the channel can be
#: asked what it has covered without consulting any file on this Mac.
NOAH_TAGS = ["Aksu", "Ararat", "Atrahasis", "Bible", "Bosporus", "Flood",
             "Gilgamesh", "Giosan", "Noah", "Shuruppak", "Utnapishtim",
             "coracle", "cubits", "documentary", "history"]

IN_CI = bool(os.environ.get("CI"))


def three_films() -> list[dict]:
    """The ledger as it should be: all three, with Noah in it."""
    return [
        {"project": "they-said-it-couldnt-be-built", "video_id": "smlOZ9v2jdM",
         "title": "They Said It Couldn't Be Built", "published": "2026-10-20",
         "entities": ["Great Pyramid", "Giza", "Stonehenge", "Moai"]},
        {"project": "easter-island", "video_id": "CDpzQKwTBsI",
         "title": "Easter Island: The Part Nobody Can Explain",
         "published": "2026-10-26",
         "entities": ["Easter Island", "Rapa Nui", "moai", "Orongo"]},
        {"project": "noah", "video_id": "gQvV4K3LxVc",
         "title": "The Flood Story Before the Bible", "published": "2026-11-02",
         "entities": ["Flood", "Noah", "Atrahasis", "Gilgamesh", "Ararat"]},
    ]


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """A shared ledger in a scratch directory, holding the three films."""
    monkeypatch.setenv(shared_state.STATE_DIR_ENV, str(tmp_path))
    for film in three_films():
        shared_state.append_film(film)
    return tmp_path / "published.json"


class FakeYouTube:
    """Enough of the Data API to answer "what has this channel uploaded".

    A fake rather than a recording: the suite blocks outbound sockets (see
    tests/conftest.py) because provider calls bill per request.
    """

    def __init__(self, videos: list[dict]):
        self._videos = videos

    # the googleapiclient shape: client.resource().list(...).execute()
    class _Call:
        def __init__(self, payload):
            self._payload = payload

        def execute(self):
            return self._payload

    def channels(self):
        return _Resource(lambda **kw: self._Call({"items": [
            {"contentDetails": {"relatedPlaylists": {"uploads": "UUtest"}}}]}))

    def playlistItems(self):
        def listing(**kw):
            return self._Call({"items": [
                {"contentDetails": {"videoId": v["id"]}} for v in self._videos]})
        return _Resource(listing)

    def videos(self):
        def listing(**kw):
            wanted = set((kw.get("id") or "").split(","))
            return self._Call({"items": [
                {"id": v["id"],
                 "snippet": {"title": v["title"], "tags": v.get("tags") or []},
                 "contentDetails": {"duration": v["duration"]}}
                for v in self._videos if v["id"] in wanted]})
        return _Resource(listing)


class _Resource:
    def __init__(self, listing):
        self._listing = listing

    def list(self, **kw):
        return self._listing(**kw)


def the_real_channel() -> FakeYouTube:
    """The channel as it actually is: three documentaries among the Shorts."""
    shorts = [
        {"id": f"short{n:03d}", "title": f"Noah's Ark Found in Turkey? #Shorts",
         "duration": "PT37S",
         "tags": ["ancient", "history", "mystery", "secret", "shorts", "viral"]}
        for n in range(6)
    ]
    return FakeYouTube(shorts + [
        {"id": "gQvV4K3LxVc", "title": "The Flood Story Before the Bible",
         "duration": "PT19M46S", "tags": NOAH_TAGS},
        {"id": "CDpzQKwTBsI",
         "title": "Easter Island: The Part Nobody Can Explain",
         "duration": "PT20M11S",
         "tags": ["Easter Island", "Rapa Nui", "moai", "Orongo", "rongorongo"]},
        {"id": "smlOZ9v2jdM",
         "title": "They Said It Couldn't Be Built — The Impossible Stones",
         "duration": "PT20M09S",
         "tags": ["Giza", "Great Pyramid", "Stonehenge", "Sacsayhuaman"]},
        # The 24/7 ambient livestream: long-form by duration and not a film.
        {"id": "kBN0kHXj0Fk",
         "title": "Ancient Mysteries Ethereal Ambient — Sleep, Study, Focus",
         "duration": "PT40538M23S",
         "tags": ["sleep music", "ambient", "Ancient Mysteries Ambient"]},
    ])


# ── the headline: with the three films, Noah is not eligible ────────────

class TestNoahIsNotEligible:
    def test_the_ledger_alone_excludes_him(self, ledger):
        from pick_topic import already_made

        made = already_made()
        assert "noah" in made
        assert why_ineligible("Noah", made=made) == \
            "already published (in the ledger)"

    def test_the_project_directory_alone_excludes_him(self):
        """With an EMPTY ledger and no YouTube.

        This is the defence that would have caught 2026-11-06 on its own,
        and only because it looks in every worktree: `projects/noah/` has
        never existed in the automation tree.
        """
        reason = why_ineligible(
            "Noah", made=set(),
            projects={"noah": Path("/Users/mac/Developer/wak3up-docs/"
                                   "OpenMontage/projects/noah")})
        assert reason is not None and "projects/noah/" in reason

    def test_the_channel_alone_excludes_him(self):
        """With an EMPTY ledger and no project directory.

        The tag `Noah` is on the Noah film because the publisher put it
        there. No file on this Mac is consulted.
        """
        from already_covered import channel_films

        films = channel_films(the_real_channel())
        covered = covered_subjects(films)
        reason = why_ineligible("Noah", made=set(), covered=covered)
        assert reason is not None and "gQvV4K3LxVc" in reason

    def test_all_three_defences_agree(self, ledger):
        from already_covered import channel_films
        from pick_topic import already_made

        covered = covered_subjects(channel_films(the_real_channel()))
        for defence in ({"made": already_made()},
                        {"projects": {"noah": Path("/tmp/projects/noah")}},
                        {"covered": covered}):
            assert why_ineligible("Noah", **defence) is not None, defence

    def test_the_other_two_films_are_excluded_too(self, ledger):
        from already_covered import channel_films
        from pick_topic import already_made

        covered = covered_subjects(channel_films(the_real_channel()))
        made = already_made()
        for entity in ("Easter Island", "Rapa Nui", "Gilgamesh", "Ararat",
                       "Great Pyramid", "Stonehenge"):
            assert why_ineligible(entity, made=made, covered=covered), entity


class TestAFreshSubjectStillGetsThrough:
    """A defence that excludes everything is not a defence, it is an outage."""

    def test_a_fresh_subject_survives_all_three(self, ledger):
        """The defences must not exclude everything.

        That is the failure mode worth guarding: three checks that each look
        reasonable and between them leave no eligible topic, which surfaces
        as "no eligible topic" and reads like a ranking bug.

        THE EXAMPLE USED TO BE KING TUT, and this test failed on
        2026-11-07 because it had stopped being true: the 2026-11-06 run
        made a King Tut film, `projects/king-tut` appeared, and the
        project-directory defence began excluding it — correctly. A subject
        stops being fresh the moment the pipeline touches it, so the example
        is pinned here and the project list is supplied, rather than read off
        whatever this machine happens to have made this week.
        """
        from already_covered import channel_films
        from pick_topic import already_made

        covered = covered_subjects(channel_films(the_real_channel()))
        assert why_ineligible(
            "Antikythera Mechanism", made=already_made(), banned=set(),
            projects={}, covered=covered) is None

    def test_and_king_tut_is_now_correctly_excluded_by_its_directory(self):
        """The other half of the same fact, asserted rather than implied."""
        reason = why_ineligible("King Tut", made=set(), banned=set(),
                                projects=project_slugs(ROOT), covered={})
        assert reason and "project" in reason.lower(), reason

    def test_the_shorts_are_not_treated_as_coverage(self):
        """THE TRAP. The picker's candidates are read off the channel's own
        Shorts titles: a subject is a candidate because Shorts about it did
        well. A coverage check that counted Shorts would therefore exclude
        every candidate it is possible to produce — every week, for ever —
        and the run would fail with "no eligible topic", which looks like a
        ranking bug and is not.

        The Shorts in this fixture are titled "Noah's Ark Found in Turkey?"
        and tagged `ancient, history, mystery`. None of that may count.
        """
        from already_covered import channel_films

        shorts_only = FakeYouTube([
            {"id": "s1", "title": "Gobekli Tepe's Forbidden Secret #Shorts",
             "duration": "PT37S", "tags": ["ancient", "mystery"]},
            {"id": "s2", "title": "What's Inside This Mexican Cave? #Shorts",
             "duration": "PT45S", "tags": ["history", "secret"]},
        ])
        assert channel_films(shorts_only) == []
        assert covered_subjects(channel_films(shorts_only)) == {}

        # and in the mixed, real-shaped channel: the documentaries counted,
        # the Shorts and the livestream not
        films = channel_films(the_real_channel())
        assert {f["video_id"] for f in films} == set(PUBLISHED)

    def test_the_livestream_is_not_a_film(self):
        """40,538 minutes is not a documentary. Without the ceiling its tags
        — "sleep music", "ambient" — would join the coverage set."""
        from already_covered import channel_films

        assert "kBN0kHXj0Fk" not in {
            f["video_id"] for f in channel_films(the_real_channel())}


# ── the mechanics each defence rests on ─────────────────────────────────

class TestTheSlugMatchesTheShell:
    """The project-directory check asks "does projects/<slug> exist", so its
    slug has to be the one run_weekly.sh would create. The shell is

        tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-'

    which DELETES what it cannot map — `Durupınar` loses its dotless i."""

    @pytest.mark.parametrize("topic,expected", [
        ("Noah", "noah"),
        ("King Tut", "king-tut"),
        ("Easter Island", "easter-island"),
        ("They Said It Couldn't Be Built", "they-said-it-couldnt-be-built"),
        ("Durupınar", "durupnar"),
        ("Atomic bombings of Hiroshima and Nagasaki",
         "atomic-bombings-of-hiroshima-and-nagasaki"),
    ])
    def test_slug(self, topic, expected):
        assert slug_of(topic) == expected

    def test_run_weekly_still_builds_the_slug_the_same_way(self):
        """If the shell changes, this check is comparing against directories
        that no longer get created."""
        body = (ROOT / "scripts" / "run_weekly.sh").read_text()
        assert "tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-'" in body


class TestTheLedgerRefusesToLookEmpty:
    """A reader that turns damage into "nothing published yet" re-picks every
    film the channel has ever made. The sibling wak3up poster learned this
    when a nightly job wrote `[]` over a schedule and the readers took it
    for an empty week."""

    def test_missing_raises_for_the_picker(self, tmp_path, monkeypatch):
        monkeypatch.setenv(shared_state.STATE_DIR_ENV, str(tmp_path))
        with pytest.raises(FileNotFoundError):
            shared_state.read_published()

    def test_damaged_raises_even_with_allow_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv(shared_state.STATE_DIR_ENV, str(tmp_path))
        (tmp_path / "published.json").write_text("{ this is not json")
        with pytest.raises(shared_state.LedgerDamaged):
            shared_state.read_published(allow_missing=True)

    def test_a_list_instead_of_a_ledger_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv(shared_state.STATE_DIR_ENV, str(tmp_path))
        (tmp_path / "published.json").write_text("[]")
        with pytest.raises(shared_state.LedgerDamaged):
            shared_state.read_published()

    def test_appending_the_same_film_twice_does_not_duplicate_it(
            self, tmp_path, monkeypatch):
        """Publishing is retried. A retry that appended again would make the
        ledger disagree with the channel about how many films exist."""
        monkeypatch.setenv(shared_state.STATE_DIR_ENV, str(tmp_path))
        film = three_films()[2]
        shared_state.append_film(film)
        shared_state.append_film({**film, "title": "Retitled in Studio"})
        films = shared_state.published_films()
        assert len(films) == 1
        assert films[0]["title"] == "Retitled in Studio"


class TestThePickHistoryIsARecordAndNotAGate:
    def test_a_recorded_pick_does_not_exclude_the_subject(self, tmp_path,
                                                          monkeypatch):
        """A run that died after picking must be able to pick again. If this
        ever starts failing, someone has turned the history into a gate and
        a crashed Friday now burns a subject for ever."""
        monkeypatch.setenv(shared_state.STATE_DIR_ENV, str(tmp_path))
        shared_state.record_pick("King Tut", "king-tut", head="deadbee")
        assert [p["entity"] for p in shared_state.read_picks()] == ["King Tut"]
        assert why_ineligible("King Tut", made=set()) is None


# ── and the state this machine is actually in ───────────────────────────

@pytest.mark.skipif(IN_CI, reason="asserts the state of this Mac, not the repo")
class TestTheRealStateOnThisMachine:
    def test_the_shared_ledger_holds_all_three_films(self):
        """The regression itself: the ledger the runner reads must have Noah
        in it. Asserted against the real file, because a seeding that was
        done once by hand is exactly the kind of thing that silently rots."""
        films = shared_state.published_films()
        found = {f.get("video_id"): f.get("title") for f in films}
        for video_id, title in PUBLISHED.items():
            assert video_id in found, (
                f"{title} ({video_id}) is not in "
                f"{shared_state.published_path()} — the picker will offer it "
                f"again")

    def test_the_ledger_is_not_in_any_worktree(self):
        """It was tracked in git, which is what forked it. If a branch brings
        a copy back, the picker has two answers again."""
        from already_covered import worktree_roots

        strays = [root / "artifacts" / "published.json"
                  for root in worktree_roots(ROOT)
                  if (root / "artifacts" / "published.json").exists()]
        assert not strays, (
            f"a per-branch ledger is back: {strays}. The shared one at "
            f"{shared_state.published_path()} is the authority; a copy in a "
            f"worktree is the 2026-11-06 bug waiting to be read.")

    def test_the_noah_project_is_visible_from_here(self):
        """The 2026-11-06 regression: the picker must see Noah's directory
        from whatever tree it is running in, or it offers him again."""
        slugs = project_slugs(ROOT)
        assert "noah" in slugs, (
            f"projects/noah not found from {ROOT}; searched "
            f"{len(slugs)} project directories")

    def test_a_project_only_another_worktree_has_is_still_found(self):
        """The cross-worktree search, controlled on what this machine has.

        This assertion used to read

            assert not (ROOT / "projects" / "noah").exists()

        and it broke on 2026-11-07, when Noah's licence records were added to
        .gitignore's allow-list and `projects/noah` appeared in every
        worktree. The property was never broken; the control was keyed on one
        particular film happening to be absent locally, which is not a fact
        about the search. So it asks for ANY slug the local tree does not
        have, and `TestTheSearchSpansWorktrees` below guards the property
        without needing the machine to supply one.
        """
        local = {entry.name for entry in (ROOT / "projects").iterdir()
                 if entry.is_dir() and not entry.name.startswith(".")} \
            if (ROOT / "projects").is_dir() else set()
        slugs = project_slugs(ROOT)
        elsewhere = {slug: path for slug, path in slugs.items()
                     if slug not in local}
        if not elsewhere:
            pytest.skip(
                f"every project this machine has is also in {ROOT.name}, so "
                f"there is nothing here that only another worktree holds. "
                f"TestTheSearchSpansWorktrees covers the property.")
        for slug, path in elsewhere.items():
            assert ROOT not in path.parents, (
                f"{slug} was reported at {path}, which is inside {ROOT} — "
                f"then it was never a cross-worktree find")


class TestTheSearchSpansWorktrees:
    """The property itself, built rather than borrowed from the machine.

    `TestTheRealStateOnThisMachine` was the ONLY coverage of the
    cross-worktree search, and its control was an accident of which films
    happened to be checked out where. The moment that accident changed the
    test went red while the code was fine. This one constructs the situation:
    a slug that exists in the second worktree and nowhere else.
    """

    def test_a_slug_in_the_second_worktree_is_found_from_the_first(
            self, tmp_path, monkeypatch):
        import already_covered

        here, there = tmp_path / "here", tmp_path / "there"
        (here / "projects" / "mine").mkdir(parents=True)
        (there / "projects" / "theirs").mkdir(parents=True)
        monkeypatch.setattr(already_covered, "worktree_roots",
                            lambda repo: [here, there])

        slugs = already_covered.project_slugs(here)
        assert set(slugs) == {"mine", "theirs"}
        assert slugs["theirs"] == there / "projects" / "theirs", (
            "the slug was found, but not in the worktree that has it")

    def test_the_first_worktree_wins_a_slug_two_of_them_have(
            self, tmp_path, monkeypatch):
        """`setdefault`, asserted: a duplicate must not shadow the first.

        Which matters because the picker uses the PATH to read the project,
        and two worktrees on different branches hold different films under
        the same slug.
        """
        import already_covered

        here, there = tmp_path / "here", tmp_path / "there"
        for root in (here, there):
            (root / "projects" / "shared").mkdir(parents=True)
        monkeypatch.setattr(already_covered, "worktree_roots",
                            lambda repo: [here, there])

        slugs = already_covered.project_slugs(here)
        assert slugs["shared"] == here / "projects" / "shared"

    def test_a_worktree_with_no_projects_directory_is_skipped_not_fatal(
            self, tmp_path, monkeypatch):
        import already_covered

        here, bare = tmp_path / "here", tmp_path / "bare"
        (here / "projects" / "mine").mkdir(parents=True)
        bare.mkdir()
        monkeypatch.setattr(already_covered, "worktree_roots",
                            lambda repo: [here, bare])
        assert set(already_covered.project_slugs(here)) == {"mine"}

    def test_a_dotfile_is_not_a_project(self, tmp_path, monkeypatch):
        import already_covered

        here = tmp_path / "here"
        (here / "projects" / ".DS_Store_dir").mkdir(parents=True)
        (here / "projects" / "real").mkdir(parents=True)
        monkeypatch.setattr(already_covered, "worktree_roots",
                            lambda repo: [here])
        assert set(already_covered.project_slugs(here)) == {"real"}

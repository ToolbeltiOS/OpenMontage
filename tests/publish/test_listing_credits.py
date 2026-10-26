"""Everything the film cut to is credited, and nothing else is.

WHY THIS TEST EXISTS
--------------------
The first listing built for easter-island credited 40 of the 84 assets the
film actually cut to. Two whole classes were missing:

  - 18 Wikimedia images, because the builder read `asset_bank.json` and the
    fetcher also writes `asset_bank_deep.json` and `asset_bank_small.json`.
    Most were CC BY-SA, where attribution is a CONDITION of the licence.
  - 18 Pixabay texture clips, which are screened separately from the bank
    because their role is different, and so were in neither file the
    builder read.

A missing credit is not a cosmetic defect. It is the difference between
using share-alike material and breaching it, and nothing else in the chain
would have caught it: every licence gate passes on the assets, because the
assets are fine. It is the LISTING that was wrong.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "easter-island"
ART = ROOT / "projects" / PROJECT / "artifacts"

pytestmark = pytest.mark.skipif(
    not (ART / "listing.json").exists(),
    reason="no listing built for this project yet")


def used_stems() -> set[str]:
    """Every asset the cut list points at, by filename stem."""
    props = json.loads((ART / "render_props.json").read_text())
    out = set()
    for cut in props["cuts"]:
        for value in cut.values():
            if isinstance(value, str) and ("/assets/" in value or "/proxies/" in value):
                out.add(Path(value).stem)
    return out


def known_ids() -> set[str]:
    """Every asset id the project has a licence record for."""
    ids = set()
    for bank_file in sorted(ART.glob("asset_bank*.json")):
        bank = json.loads(bank_file.read_text())
        for subject in bank.get("subjects", {}).values():
            for a in subject.get("assets", []):
                ids.add(a["asset_id"])
        for d in bank.get("derived", []):
            ids.add(d["asset_id"])
            if d.get("parent_id"):
                ids.add(d["parent_id"])
    screening = ART / "texture_screening.json"
    if screening.exists():
        for clip in json.loads(screening.read_text()).get("kept", []):
            ids.add(clip["clip_id"])
    return ids


class TestEveryAssetInTheFilmHasALicenceRecord:
    def test_nothing_is_cut_to_that_the_project_cannot_account_for(self):
        unknown = {s for s in used_stems()
                   if s not in known_ids()
                   and re.sub(r"_\d{3,4}$", "", s) not in known_ids()}
        assert not unknown, (
            f"{len(unknown)} assets are in the film with no licence record "
            f"anywhere in the project: {sorted(unknown)[:8]}")


class TestThePinnedCommentCoversTheFilm:
    def test_every_distinct_source_the_film_uses_has_a_row(self):
        """Worked out from the project's records, not from a count floor.

        A floor does not catch this. Dropping `asset_bank_deep.json` left 18
        CC BY-SA images uncredited and still produced 58 rows, which clears
        any round number worth writing down. So the expected credits are
        derived here independently and compared exactly.

        Credits legitimately COLLAPSE — several crops of one photograph are
        one credit — so the comparison is on distinct (artist, licence,
        page), which is what a credit actually is.
        """
        listing = json.loads((ART / "listing.json").read_text())
        rows = {r for r in listing["pinned_comment"].split("\n") if " — " in r}
        assert listing["attribution"]["credit_required_assets"] == len(rows)

        used = used_stems()
        expected = set()
        for bank_file in sorted(ART.glob("asset_bank*.json")):
            bank = json.loads(bank_file.read_text())
            records = []
            for subject in bank.get("subjects", {}).values():
                records += subject.get("assets", [])
            records += bank.get("derived", [])
            for a in records:
                if a.get("asset_id") not in used and a.get("parent_id") not in used:
                    continue
                artist = (a.get("artist") or "").strip() or "(not supplied)"
                expected.add((artist, a.get("licence") or "unknown",
                              a.get("page") or ""))
        got = {tuple(r.split(" — ", 2)) for r in rows
               if "Pixabay Content License" not in r}
        missing = expected - got
        assert not missing, (
            f"{len(missing)} sources the film cut to have no credit row — "
            f"e.g. {sorted(missing)[:3]}")

    def test_the_texture_clips_are_credited(self):
        """They are screened outside the bank, which is how they were lost."""
        listing = json.loads((ART / "listing.json").read_text())
        assert listing["attribution"]["texture_clips"] > 0
        assert "Pixabay Content License" in listing["pinned_comment"]

    def test_every_credited_licence_is_one_the_filter_admits(self):
        """NC and ND are refused at fetch time; this is the last check."""
        listing = json.loads((ART / "listing.json").read_text())
        rows = [r for r in listing["pinned_comment"].split("\n") if " — " in r]
        allowed = ("CC0", "PUBLIC DOMAIN", "CC BY", "PIXABAY")
        for row in rows:
            licence = row.split(" — ")[1].upper()
            assert any(licence.startswith(a) for a in allowed), row
            assert "-NC" not in licence and "-ND" not in licence, row

    def test_it_fits_in_a_youtube_comment(self):
        listing = json.loads((ART / "listing.json").read_text())
        assert len(listing["pinned_comment"]) <= 10000


class TestTheDescription:
    def test_it_fits(self):
        listing = json.loads((ART / "listing.json").read_text())
        assert len(listing["description"]) <= 5000

    def test_the_chapters_are_the_measured_boundaries(self):
        """Not the script's planned times — the two differ by seconds.

        The script plans act 1 at 50.2s; the narration the film carries puts
        it at 52s. A chapter mark on the planned time lands mid-sentence.
        """
        listing = json.loads((ART / "listing.json").read_text())
        script = json.loads((ART / "script.json").read_text())
        planned = {s["id"]: s["start_seconds"] for s in script["sections"]}
        act1 = next(c for c in listing["chapters"]
                    if "hillside" in c["title"])
        assert abs(act1["start_seconds"] - planned["act1"]) > 0.5, (
            "the chapter is on the script's planned time, not the measured one")

    def test_the_title_sequence_is_not_a_chapter(self):
        listing = json.loads((ART / "listing.json").read_text())
        assert not any("Title" in c["title"] for c in listing["chapters"])


class TestPublicNowIsASeparateBranch:
    """`publishAt` and `privacyStatus: public` are mutually exclusive.

    `publishAt` is only meaningful on a private video; sending it alongside
    `public` is rejected by the API. So the two are one branch and not a merge
    of two dicts, and the default stays scheduled: a film that uploads public
    at 3am has no premiere and no chance to be pulled. `--now` is for a film a
    human is watching go out.
    """

    @staticmethod
    def _body(publish_at):
        """The body `upload` builds, without touching the network."""
        import sys
        from datetime import datetime, timezone
        from pathlib import Path
        from unittest import mock

        sys.path.insert(0, str(Path("scripts").resolve()))
        import publish_doc

        listing = {"title": "T", "description": "D", "tags": ["a"],
                   "categoryId": "27", "defaultLanguage": "en",
                   "defaultAudioLanguage": "en", "license": "youtube",
                   "embeddable": True, "publicStatsViewable": True,
                   "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": True}
        captured = {}

        class FakeRequest:
            def next_chunk(self):
                return None, {"id": "VID"}

        class FakeVideos:
            def insert(self, part, body, media_body):
                captured.update(body)
                return FakeRequest()

        class FakeYT:
            def videos(self):
                return FakeVideos()

        with mock.patch.object(publish_doc, "MediaFileUpload", create=True):
            with mock.patch("googleapiclient.http.MediaFileUpload",
                            lambda *a, **k: None):
                publish_doc.upload(FakeYT(), listing, Path("x.mp4"), publish_at)
        return captured

    def test_scheduled_is_private_with_a_publish_at(self):
        from datetime import datetime, timezone

        when = datetime(2026, 11, 2, 13, 0, tzinfo=timezone.utc)
        status = self._body(when)["status"]
        assert status["privacyStatus"] == "private"
        assert status["publishAt"] == "2026-11-02T13:00:00Z"

    def test_now_is_public_with_no_publish_at(self):
        status = self._body(None)["status"]
        assert status["privacyStatus"] == "public"
        assert "publishAt" not in status, (
            "publishAt alongside public is rejected by the API")

    def test_both_carry_the_declarations_either_way(self):
        from datetime import datetime, timezone

        for when in (None, datetime(2026, 11, 2, 13, 0, tzinfo=timezone.utc)):
            status = self._body(when)["status"]
            assert status["containsSyntheticMedia"] is True, (
                "the narration is synthesised and the declaration must "
                "survive both branches")
            assert status["selfDeclaredMadeForKids"] is False

    def test_the_weekly_runner_does_not_pass_now(self):
        """There is no undo for an audience that has already seen it."""
        from pathlib import Path

        runner = Path("scripts/run_weekly.sh").read_text()
        assert "--now" not in runner, (
            "the unattended weekly run must never publish immediately")


class TestTheListingKnowsWhatTheFilmIsAbout:
    """`tags` was fifteen hardcoded Easter Island strings.

    Everything else in `build` is derived from the project's own artifacts.
    `tags` was not, and `build` is what the weekly run calls for every film —
    so the next film would have published somebody else's subject in its own
    metadata, and `entities` went to the ledger empty, which is what the topic
    picker reads to avoid making the same film twice.

    The source is the script's own `pronunciation_guides`: the script stage
    writes one for every name the narrator could not read cold, so the list is
    by construction the unusual named things the film discusses. A regex over
    capitalised words cannot do this — `rongorongo`, `moai` and `tangata manu`
    are lower case and each is the subject of an act.
    """

    @staticmethod
    def _script(guides, title="A Film About Things"):
        return {"title": title,
                "sections": [{"id": "act1", "text": "Some narration.",
                              "pronunciation_guides": guides}]}

    def test_the_guides_are_the_subjects(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("scripts").resolve()))
        from build_listing import subjects

        got = subjects(self._script(
            [{"word": "rongorongo", "phonetic": "x"},
             {"word": "tangata manu", "phonetic": "y"}]), {})
        assert "rongorongo" in got and "tangata manu" in got, got

    def test_a_lower_case_subject_survives(self):
        """The thing a capitalised-word regex would have dropped."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("scripts").resolve()))
        from build_listing import subjects

        assert "moai" in subjects(
            self._script([{"word": "moai", "phonetic": "MOH-eye"}]), {})

    def test_the_title_names_a_subject_without_a_guide(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("scripts").resolve()))
        from build_listing import subjects

        got = subjects(self._script([], title="Easter Island: The Open Files"),
                       {})
        assert "Easter Island" in got, got

    def test_non_ascii_names_are_counted_not_dropped(self):
        """INJECTED: json.dumps escapes them by default, and the default sorted
        this film's third-most-discussed person last."""
        import json as _json
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("scripts").resolve()))
        from build_listing import subjects

        script = self._script([{"word": "Eugène Eyraud", "phonetic": "x"},
                               {"word": "Zeta", "phonetic": "y"}])
        script["sections"][0]["text"] = "Eugène Eyraud " * 5 + "Zeta"
        assert _json.dumps(script).count("Eugène") == 0, (
            "the escaping this test is about has changed")
        got = subjects(script, {})
        assert got[0] == "Eugène Eyraud", got

    def test_a_script_with_no_subjects_refuses_rather_than_shipping_generic(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("scripts").resolve()))
        import build_listing

        assert build_listing.MIN_SUBJECT_TAGS >= 3
        src = Path("scripts/build_listing.py").read_text()
        assert "no subject in its metadata" in src
        assert "raise SystemExit" in src

    def test_the_generic_tags_cannot_be_squeezed_out(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("scripts").resolve()))
        import build_listing

        named = [f"Subject {i}" for i in range(40)]
        keep = [t for t in build_listing.GENERIC_TAGS
                if t.lower() not in {n.lower() for n in named}]
        tags = named[:build_listing.MAX_TAGS - len(keep)] + keep
        assert len(tags) == build_listing.MAX_TAGS
        for t in build_listing.GENERIC_TAGS:
            assert t in tags

    def test_no_easter_island_string_is_hardcoded_any_more(self):
        """The whole point: build() is called for every film."""
        from pathlib import Path

        src = Path("scripts/build_listing.py").read_text()
        body = src[src.index("def build(project"):]
        for leaked in ("Easter Island", "rongorongo", "Rapa Nui", "Orongo",
                       "Rano Raraku", "Jared Diamond"):
            assert leaked not in body, (
                f"{leaked!r} is hardcoded in build(); the next film would "
                f"publish it as its own subject")


class TestWhatCannotBeVerifiedIsSaidOutLoud:
    """`containsSyntheticMedia` does not come back from videos.list.

    Every other status field round-trips — privacy, licence, embeddable,
    publicStatsViewable, madeForKids, selfDeclaredMadeForKids — so the absence
    of this one is not obviously benign: it is either write-only or silently
    dropped, and from the API there is no way to tell. The narration IS
    synthesised, so it is not a field to assume about.
    """

    def test_a_synthetic_film_gets_a_studio_item_for_it(self):
        from pathlib import Path

        src = Path("scripts/publish_doc.py").read_text()
        assert 'if listing.get("containsSyntheticMedia")' in src
        assert "cannot be verified from here" in src

    def test_the_item_is_only_added_when_the_listing_declares_it(self):
        from pathlib import Path

        src = Path("scripts/publish_doc.py").read_text()
        i = src.index('if listing.get("containsSyntheticMedia")')
        assert "manual.append" in src[i:i + 400]

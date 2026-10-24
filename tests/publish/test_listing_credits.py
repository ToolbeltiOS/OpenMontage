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

"""When one asset is made from another, the rights come with it.

A third of run #1's assets are derived — a 1080p proxy, a detail crop — and
the derivation step recorded nothing, so the audit read the FILE NAME to find
out whose they were. That worked for all 33 and is a guess; a credit block
generated from a guess can be wrong without anyone knowing.
"""
from __future__ import annotations

import json

import pytest

from lib import derivation


@pytest.fixture
def project(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "asset_manifest.json").write_text(json.dumps({"assets": [
        {"path": "assets/video/quarry.mp4", "license": "CC BY-SA 4.0",
         "provider": "wikimedia", "creator": "A Photographer",
         "original_url": "https://commons.wikimedia.org/wiki/File:Quarry.mp4"},
        {"path": "assets/images/plate.jpg", "license": "CC0 1.0",
         "provider": "met_museum", "creator": "The Met"},
        {"path": "assets/images/nameless.jpg", "license": "",
         "provider": "unknown"},
    ]}))
    return tmp_path


class TestRecording:
    def test_the_rights_travel_to_the_derived_file(self, project):
        entry = derivation.record("assets/video/quarry.mp4",
                                  "renders/proxies/quarry_1080.mp4", project,
                                  "transcoded to 1080p")
        assert entry["licence"] == "CC BY-SA 4.0"
        assert entry["provider"] == "wikimedia"
        assert entry["attribution"] == "A Photographer"
        assert entry["derived_from"] == "quarry.mp4"
        assert entry["how"] == "transcoded to 1080p"
        assert entry["rights_recorded"] is True

    def test_it_is_written_where_the_audit_reads_it(self, project):
        derivation.record("assets/images/plate.jpg",
                          "renders/proxies/plate.jpg", project)
        ledger = derivation.load_ledger(project)
        assert ledger["plate.jpg"]["licence"] == "CC0 1.0"
        assert derivation.ledger_path(project).exists()

    def test_recording_twice_updates_rather_than_duplicates(self, project):
        derivation.record("assets/images/plate.jpg", "p.jpg", project, "first")
        derivation.record("assets/images/plate.jpg", "p.jpg", project, "second")
        ledger = derivation.load_ledger(project)
        assert len(ledger) == 1
        assert ledger["p.jpg"]["how"] == "second"

    def test_an_original_with_no_rights_is_recorded_as_such(self, project):
        """Not silently blank: a derived file whose source has no licence is
        the thing the audit needs to see."""
        entry = derivation.record("assets/images/nameless.jpg", "n_1080.jpg",
                                  project)
        assert entry["rights_recorded"] is False
        assert entry["licence"] == ""

    def test_an_unknown_original_still_leaves_a_trail(self, project):
        entry = derivation.record("somewhere/else.jpg", "else_1080.jpg", project)
        assert entry["derived_from"] == "else.jpg"
        assert entry["rights_recorded"] is False


class TestBackfill:
    def test_it_resolves_the_suffixes_run_1_used(self, project):
        result = derivation.backfill(project, [
            "renders/proxies/quarry_1080.mp4",
            "renders/proxies/quarry_1080_1080.mp4",
            "assets/images/plate_detail.jpg",
            "assets/images/plate_extreme.jpg",
        ])
        assert result["written"] == 4 and result["unresolved"] == []
        ledger = derivation.load_ledger(project)
        assert ledger["quarry_1080_1080.mp4"]["licence"] == "CC BY-SA 4.0"
        assert ledger["plate_detail.jpg"]["licence"] == "CC0 1.0"

    def test_a_name_it_cannot_resolve_is_reported_not_guessed(self, project):
        result = derivation.backfill(project, ["assets/images/mystery.jpg"])
        assert result["unresolved"] == ["mystery.jpg"]
        assert "mystery.jpg" not in derivation.load_ledger(project)

    def test_an_original_is_not_treated_as_a_derivation(self, project):
        result = derivation.backfill(project, ["assets/images/plate.jpg"])
        assert result["written"] == 0

    def test_backfilling_says_it_was_backfilled(self, project):
        derivation.backfill(project, ["renders/proxies/quarry_1080.mp4"])
        assert "backfilled" in derivation.load_ledger(project)[
            "quarry_1080.mp4"]["how"]


class TestTheRealProject:
    """Run #1's own ledger, which the audit now reads instead of guessing."""

    def test_every_derived_asset_has_its_rights(self):
        from pathlib import Path

        project = derivation.ROOT / "projects" / "they-said-it-couldnt-be-built"
        ledger = derivation.load_ledger(project)
        assert len(ledger) == 33, f"expected run #1's 33 derivations, got {len(ledger)}"
        missing = [name for name, entry in ledger.items()
                   if not entry["rights_recorded"]]
        assert missing == [], missing

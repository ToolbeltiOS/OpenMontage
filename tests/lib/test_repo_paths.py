"""An artifact that names its inputs must not name the machine it ran on.

king-tut's `edit_decisions.json` carried SEVENTY paths beginning
`/Users/mac/Developer/wak3up-docs/runner/`. Not merely long: that prefix
names one WORKTREE of one clone, so the EDL could not be read in the sibling
worktree six inches away, and committing it as it stood would have put that
into shared history.

`renders/mix_report.json` had the opposite failure with the same cause — bare
basenames — and re-mixing king-tut from its own report died on `exit status
254` while the beds sat in the project the whole time.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import repo_paths as RP  # noqa: E402


class TestResolveIsAFallbackAndNeverARewrite:
    """The property that makes it safe under the render.

    It can turn a failing path into a working one and cannot change a path
    that already worked. A resolution change that applied to every film
    would otherwise be the riskiest kind of fix.
    """

    def test_an_absolute_path_is_untouched(self):
        assert RP.resolve("/nowhere/at/all.mp3") == "/nowhere/at/all.mp3"

    def test_an_absolute_path_that_exists_is_untouched(self):
        here = str(ROOT / "lib" / "repo_paths.py")
        assert RP.resolve(here) == here

    def test_a_relative_path_that_already_resolves_is_untouched(self, monkeypatch):
        monkeypatch.chdir(ROOT)
        assert RP.resolve("lib/repo_paths.py") == "lib/repo_paths.py"

    def test_a_relative_path_that_does_not_resolve_is_rooted(self, tmp_path,
                                                             monkeypatch):
        monkeypatch.chdir(tmp_path)
        got = RP.resolve("lib/repo_paths.py")
        assert got == os.path.join(RP.ROOT, "lib/repo_paths.py")
        assert os.path.exists(got)

    def test_an_unfindable_path_comes_back_as_given(self):
        """So the error names what the artifact asked for."""
        assert RP.resolve("beds/nope.wav") == "beds/nope.wav"

    def test_empty_and_non_strings_pass_through(self):
        assert RP.resolve("") == ""
        assert RP.resolve(None) is None


class TestRelativeRefusesToLeaveTheRepo:
    def test_a_path_inside_becomes_relative(self):
        assert RP.relative(str(ROOT / "lib" / "repo_paths.py")) == \
            "lib/repo_paths.py"

    def test_a_path_outside_is_none_and_not_a_dotdot_chain(self):
        """`os.path.relpath` would return ../../../Users/... — which resolves
        to nothing elsewhere while looking reproducible."""
        assert RP.relative("/Users/mac/wak3up/assets/ambient_sources/x.mp3") \
            is None

    def test_the_root_is_the_repo(self):
        assert (Path(RP.ROOT) / ".gitignore").exists()
        assert (Path(RP.ROOT) / "lib" / "repo_paths.py").exists()


class TestKingTutsEdlIsCommittedAndPortable:
    """The decision is which bed covers which span. The spelling is not.

    Normalised 2026-11-10 on the owner's ruling: a worktree-absolute path in
    shared history is worse than a normalised copy. All seventy paths were
    normalised, not just the three beds — leaving sixty-seven
    worktree-absolute image paths in while fixing three bed paths would have
    committed the very thing the ruling objects to.
    """

    EDL = ROOT / "projects" / "king-tut" / "artifacts" / "edit_decisions.json"

    @pytest.fixture(scope="class")
    def edl(self) -> dict:
        if not self.EDL.exists():
            pytest.skip("king-tut's EDL is not in this worktree")
        return json.loads(self.EDL.read_text())

    def test_it_contains_no_absolute_path_at_all(self, edl):
        found = []

        def scan(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    scan(v, f"{path}.{k}")
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    scan(v, f"{path}[{i}]")
            elif isinstance(o, str) and o.startswith("/"):
                found.append((path, o))

        scan(edl)
        assert found == [], found[:5]

    def test_no_worktree_name_survives_anywhere_in_the_file(self, edl):
        """The specific string that made it unshareable."""
        blob = json.dumps(edl)
        for naming in ("wak3up-docs/runner", "wak3up-docs/fix-render-finalise",
                       "/Users/mac"):
            assert naming not in blob, naming

    def test_the_three_bed_decisions_are_intact(self, edl):
        beds = edl["music"]["beds"]
        assert [b["name"] for b in beds] == ["open_act1", "act2_act3",
                                             "act4_outro"]
        assert [b["track"] for b in beds] == [
            "trimmed/bed_cinematic_quiet.wav",
            "trimmed/bed_dark_drone.wav",
            "trimmed/bed_drone_minimal.wav"]

    def test_the_bed_paths_point_into_the_project(self, edl):
        for bed in edl["music"]["beds"]:
            assert bed["path"].startswith("projects/king-tut/assets/music/")
            assert not os.path.isabs(bed["path"])

    def test_the_rejections_are_intact_with_their_reasons(self, edl):
        """Why a bed was NOT chosen is as much a decision as which was."""
        rejected = edl["music"]["rejected"]
        assert len(rejected) == 3
        assert all(r.get("track") and len(r.get("why", "")) > 20
                   for r in rejected)

    def test_the_cut_count_is_unchanged(self, edl):
        """A normalisation that dropped a cut would be a rewrite."""
        assert len(edl["cuts"]) == 161

    def test_every_asset_path_is_repo_relative(self, edl):
        keys = ("source", "image", "backgroundSrc", "backgroundImage", "path")
        for cut in edl["cuts"]:
            for key in keys:
                v = cut.get(key)
                if isinstance(v, str) and ("assets/" in v):
                    assert v.startswith("projects/king-tut/"), (key, v)

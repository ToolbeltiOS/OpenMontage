"""ITEM 8.2: can a mix report be followed back to the files it names?

`scripts/export_excerpts.py` calls `renders/mix_report.json` the authority
for what the mix was made of. It recorded each bed as a BARE FILENAME, and
`lib/music_brightness.py` resolved that against the current working
directory, so the authority named the tracks without being able to find
them.

Measured 2026-11-09: re-mixing king-tut from its own report died on

    ffmpeg ... 'bed_cinematic_quiet.wav' ... exit status 254

while the three beds were in
projects/king-tut/assets/music/candidates/trimmed/ the whole time.

A bed from OUTSIDE the repo is a different case and is recorded absolute and
flagged, because "this film cannot be re-mixed from a clone" is a real
property of the mix. easter-island's and they-said-it's beds came from
/Users/mac/wak3up/assets/ambient_sources, so that flag is not hypothetical.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import music_brightness as MB  # noqa: E402


def report_track(path: str) -> dict:
    """`mix_audio.report_track`, loaded without importing the whole mixer.

    Importing lib/mix_audio.py executes module-level work that wants a
    project on disk, and this test is about one pure function in it.
    """
    src = (ROOT / "lib" / "mix_audio.py").read_text()
    body = src[src.index("def report_track"):src.index("def bed_spread")]
    ns: dict = {"os": os, "ROOT": str(ROOT)}
    exec(body, ns)
    return ns["report_track"](path)


class TestABedInsideTheRepoIsRecordedRepoRelative:
    IN_REPO = "projects/king-tut/assets/music/candidates/trimmed/bed_x.wav"

    def test_the_path_is_relative(self):
        row = report_track(str(ROOT / self.IN_REPO))
        assert row["track"] == self.IN_REPO
        assert not os.path.isabs(row["track"])

    def test_it_says_it_is_in_the_repo(self):
        assert report_track(str(ROOT / self.IN_REPO))["track_in_repo"] is True

    def test_the_bare_name_is_kept_too_under_its_own_key(self):
        """Readers that want a label still have one, and it is not `track`.

        `build_deliverables` basenames the track for the deliverables row;
        the report keeps the name so nothing has to re-derive it.
        """
        row = report_track(str(ROOT / self.IN_REPO))
        assert row["track_name"] == "bed_x.wav"

    def test_it_does_not_collide_with_the_span_s_own_name(self):
        """The span is called "open_act1"; the file is called "bed_x.wav".

        The report builds each span as `{"name": ..., **report_track(...)}`,
        so a `name` key in this dict would silently overwrite the span's.
        """
        assert "name" not in report_track(str(ROOT / self.IN_REPO))


class TestABedOutsideTheRepoIsFlaggedNotRewritten:
    OUTSIDE = "/Users/mac/wak3up/assets/ambient_sources/EBB.mp3"

    def test_the_absolute_path_is_kept(self):
        assert report_track(self.OUTSIDE)["track"] == self.OUTSIDE

    def test_it_is_flagged(self):
        row = report_track(self.OUTSIDE)
        assert row["track_in_repo"] is False
        assert "cannot be re-mixed from a clone" in row["why"]

    def test_a_relative_path_is_never_invented_for_it(self):
        """`os.path.relpath` would happily return ../../../Users/... which
        resolves to nothing on any other machine and looks reproducible."""
        assert not report_track(self.OUTSIDE)["track"].startswith("..")


class TestTheResolverFindsARepoRelativeBed:
    def test_a_repo_relative_path_resolves_from_any_directory(self, tmp_path,
                                                              monkeypatch):
        """The half of the defect that lived in the reader.

        A relative path plus the wrong cwd is how the re-mix died.
        """
        rel = "lib/music_brightness.py"        # any file certainly in the repo
        monkeypatch.chdir(tmp_path)
        assert not os.path.exists(rel)
        assert MB.resolve(rel) == os.path.join(str(MB.ROOT), rel)
        assert os.path.exists(MB.resolve(rel))

    def test_an_absolute_path_is_untouched(self):
        assert MB.resolve("/nowhere/at/all.mp3") == "/nowhere/at/all.mp3"

    def test_a_path_correct_for_the_cwd_wins(self):
        assert MB.resolve("lib/music_brightness.py") == "lib/music_brightness.py"

    def test_an_unfindable_relative_path_is_returned_as_given(self):
        """So the error names what was asked for, not a path nobody wrote."""
        assert MB.resolve("beds/nope.wav") == "beds/nope.wav"

    def test_the_root_is_the_repo_and_not_the_lib_directory(self):
        assert (Path(MB.ROOT) / "lib" / "music_brightness.py").exists()
        assert (Path(MB.ROOT) / ".gitignore").exists()


class TestTheByEarSelectionIsInGit:
    """WHICH BED FOR WHICH SPAN IS A DECISION, and decisions are kept.

    The candidates are all still on disk and nothing else says which three
    were chosen. `.gitignore` un-ignores `edit_decisions.json` for this
    reason, alongside `script.json` and `listing.json`.
    """

    def test_the_gitignore_un_ignores_the_edl(self):
        rules = (ROOT / ".gitignore").read_text().splitlines()
        assert "!projects/*/artifacts/edit_decisions.json" in rules

    def test_it_sits_with_the_other_decision_artifacts(self):
        rules = (ROOT / ".gitignore").read_text()
        for decision in ("edit_decisions.json", "script.json",
                         "listing.json", "sound_design.json"):
            assert f"!projects/*/artifacts/{decision}" in rules, decision

    @pytest.mark.parametrize("film", ["easter-island",
                                      "they-said-it-couldnt-be-built"])
    def test_a_tracked_edl_names_its_beds(self, film):
        path = ROOT / "projects" / film / "artifacts" / "edit_decisions.json"
        if not path.exists():
            pytest.skip(f"{film} is not in this worktree")
        beds = (json.loads(path.read_text()).get("music") or {}).get("beds")
        assert beds, film
        assert all(b.get("track") for b in beds), film


class TestTheEditDirectorSaysHowToNameABed:
    """So the next EDL does not record a worktree path.

    Every EDL on disk names a bed in a way that cannot be resolved from a
    clone: two films point outside the repo, and king-tut's `path` names the
    runner worktree specifically.
    """

    DOC = ("skills", "pipelines", "narrated-documentary", "edit-director.md")

    @property
    def doc(self) -> str:
        return " ".join((ROOT.joinpath(*self.DOC)).read_text().split())

    def test_it_asks_for_a_path_relative_to_the_music_directory(self):
        assert "relative to the project's music directory" in self.doc

    def test_it_forbids_an_absolute_path(self):
        assert "Do not write an absolute `path`" in self.doc

    def test_it_says_why_the_selection_is_kept_in_git(self):
        assert "decision, made by ear" in self.doc
        assert "edit_decisions.json" in self.doc

    def test_it_keeps_the_audio_ignored(self):
        assert "audio stays ignored" in self.doc

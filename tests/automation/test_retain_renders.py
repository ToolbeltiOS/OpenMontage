"""Only a film the audience has seen gives up its render intermediates.

A film is written to the published ledger when it is UPLOADED, and the
weekly upload is private with a publishAt the following Monday 09:00. So
"in the ledger" is not "public": on 2026-11-15 film #5 was in the ledger
with `published: 2026-11-16`, a date in the future, and a rule keyed on the
ledger would have deleted the eighty minutes of recovery material belonging
to the one film that could still need it.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import retain_renders as R  # noqa: E402

TODAY = date(2026, 11, 15)


@pytest.fixture
def channel(tmp_path, monkeypatch):
    """A ledger with a public film and a scheduled one, and both on disk."""
    state = tmp_path / "state"
    state.mkdir()
    (state / "published.json").write_text(json.dumps({"films": [
        {"project": "king-tut", "video_id": "d8e1wVEqCUs",
         "published": "2026-11-09"},                      # public
        {"project": "hiroshima", "video_id": "NWSDd5RJQ0Y",
         "published": "2026-11-16"},                      # Monday, not yet
    ]}))
    monkeypatch.setenv("WAK3UP_DOCS_STATE", str(state))

    root = tmp_path / "repo"
    for project in ("king-tut", "hiroshima"):
        out = root / "remotion-composer" / "out" / project
        out.mkdir(parents=True)
        for name in ("look.mp4", "type.mov", "plate.mp4"):
            (out / name).write_bytes(b"x" * 1024)
        # the stills the look pass samples, which are a DIRECTORY
        frames = root / "remotion-composer" / "public" / f"frames_{project}"
        frames.mkdir(parents=True)
        for n in range(4):
            (frames / f"f_{n:05d}.jpg").write_bytes(b"y" * 512)
    return root


class TestOnlyAPublicFilmIsEligible:
    def test_a_film_the_audience_has_seen_is_eligible(self):
        assert R.is_public({"published": "2026-11-09"}, TODAY)

    def test_a_film_scheduled_for_tomorrow_is_NOT(self):
        """THE CONTROL: film #5's exact ledger row, on the day it was
        written."""
        assert not R.is_public({"published": "2026-11-16"}, TODAY)

    def test_a_film_going_public_today_is_not_yet(self):
        """Strictly before: a publishAt of 09:00 has not necessarily
        happened when a preflight runs at 21:00 the Thursday before, and
        the cost of waiting one day is nothing."""
        assert not R.is_public({"published": "2026-11-15"}, TODAY)

    def test_a_row_with_no_date_is_left_alone(self):
        assert not R.is_public({}, TODAY)
        assert not R.is_public({"published": "soon"}, TODAY)


class TestWhatItTakesAndWhatItLeaves:
    def test_it_finds_the_public_films_intermediates(self, channel):
        """Three now, not two: the stills joined the rule on 2026-11-20.

        Pinned by name and by total so a FOURTH entry cannot slip in
        unnoticed — the whole value of this rule is that what it deletes is
        a closed list with a rebuild cost recorded against each line.
        """
        rows, total = R.survey(today=TODAY, root=channel)
        assert sorted(r["name"] for r in rows) == [
            "frames_king-tut", "look.mp4", "type.mov"]
        assert {r["project"] for r in rows} == {"king-tut"}
        # 1024 for look, 1024 for type, 4 stills of 512 for the frames dir
        assert total == 1024 + 1024 + 4 * 512

    def test_the_scheduled_film_is_untouched(self, channel):
        R.main(["--apply", "--root", str(channel),
                "--today", TODAY.isoformat()])
        out = channel / "remotion-composer" / "out" / "hiroshima"
        for name in ("look.mp4", "type.mov", "plate.mp4"):
            assert (out / name).exists(), f"{name} of a film not yet public"

    def test_the_plate_is_never_deleted(self, channel):
        """Forty-four minutes and every cut re-rendered to rebuild."""
        R.main(["--apply", "--root", str(channel),
                "--today", TODAY.isoformat()])
        assert (channel / "remotion-composer" / "out" / "king-tut"
                / "plate.mp4").exists()

    def test_apply_deletes_the_two_rederivable_passes(self, channel):
        R.main(["--apply", "--root", str(channel),
                "--today", TODAY.isoformat()])
        out = channel / "remotion-composer" / "out" / "king-tut"
        assert not (out / "look.mp4").exists()
        assert not (out / "type.mov").exists()

    def test_without_apply_nothing_is_touched(self, channel):
        R.main(["--root", str(channel), "--today", TODAY.isoformat()])
        out = channel / "remotion-composer" / "out" / "king-tut"
        assert (out / "look.mp4").exists() and (out / "type.mov").exists()

    def test_it_is_idempotent(self, channel):
        assert R.main(["--apply", "--root", str(channel),
                       "--today", TODAY.isoformat()]) == 0
        assert R.main(["--apply", "--root", str(channel),
                       "--today", TODAY.isoformat()]) == 0

    def test_without_a_date_it_judges_against_the_wall_clock(self, channel):
        """WHICH IS WHY EVERY TEST ABOVE PASSES ONE. `survey` falls back to
        `date.today()`, so this file's own fixture — a film scheduled for
        2026-11-16 — stopped being "scheduled" on 2026-11-16 and the test
        asserting it was untouched began deleting it. It had passed for five
        days. Kept from the retention-frames branch through the rebase: the
        explicit `--today` calls are the fix, and this is the tripwire that
        says why they are explicit.
        """
        import inspect
        assert "today or date.today()" in inspect.getsource(R.survey)

    def test_nothing_is_both_kept_and_deleted(self):
        leaves = {pathlib.PurePath(t).name for t, _kind in R.DELETABLE}
        assert not leaves & set(R.KEPT)


class TestTheStillsGoTooNowThatTheyAreInTheRule:
    """Added on the owner's instruction, 2026-11-20, with the rebuild cost
    measured first: one ffmpeg decode of plate.mp4 at 345 frames a second
    sustained, so 107 seconds for a 36,864-frame film. 4.9 GB on
    atomic-bombings and 4.3 GB on king-tut — the cheapest thing in the rule
    to rebuild and the second largest to keep."""

    def test_a_public_films_stills_are_taken(self, channel):
        R.main(["--apply", "--root", str(channel), "--today", str(TODAY)])
        assert not (channel / "remotion-composer" / "public"
                    / "frames_king-tut").exists()

    def test_a_scheduled_films_stills_are_not(self, channel):
        R.main(["--apply", "--root", str(channel), "--today", str(TODAY)])
        assert (channel / "remotion-composer" / "public"
                / "frames_hiroshima").exists()

    def test_the_plate_they_are_rebuilt_from_survives(self, channel):
        """Deleting the stills AND the plate would make them unrecoverable."""
        R.main(["--apply", "--root", str(channel), "--today", str(TODAY)])
        assert (channel / "remotion-composer" / "out" / "king-tut"
                / "plate.mp4").exists()

    def test_a_directory_is_weighed_by_walking_it(self, channel):
        """`stat().st_size` on a directory is the size of the directory
        ENTRY — a few hundred bytes. It would have reported 4.9 GB of
        stills as nothing and deleted them for no recorded gain."""
        rows, total = R.survey(today=TODAY, root=channel)
        stills = [r for r in rows if r["name"].startswith("frames_")]
        assert len(stills) == 1, rows
        assert stills[0]["bytes"] == 4 * 512, stills[0]

    def test_the_rebuild_cost_is_recorded_beside_it(self):
        source = (ROOT / "scripts" / "retain_renders.py").read_text()
        assert "345 frames a second" in source
        assert "107 SECONDS" in source


class TestThePreflightSaysWhereTheSpaceIs:
    #: The call as the shell actually spells it — the path is quoted, so
    #: "retain_renders.py --oneline" is not a substring of the file. The
    #: first version of this test asserted that and failed on its own
    #: expectation rather than on the code.
    CALL = re.compile(r'retain_renders\.py"?\s+--oneline')

    def test_it_reports_without_applying(self):
        runner = (ROOT / "scripts" / "run_weekly.sh").read_text()
        assert self.CALL.search(runner), "the preflight does not survey"
        assert not re.search(r'retain_renders\.py"?\s+--apply', runner), (
            "a preflight must not delete anything")

    def test_it_is_reported_beside_the_disk_check(self):
        runner = (ROOT / "scripts" / "run_weekly.sh").read_text()
        at = self.CALL.search(runner).start()
        assert (runner.index("GB a film needs") < at
                < runner.index("the interpreter every check below needs"))

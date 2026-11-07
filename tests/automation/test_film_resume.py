"""A half-made film is finished; a published one is never remade.

WHY THIS TEST EXISTS
--------------------
On 2026-11-06 the run died one minute after the audio mix finished, with a
human-approved script, a scene plan, an asset bank, edit decisions, 425 KB
of render props and a 235 MB mix on disk. Everything but the picture.

Re-firing the runner would have made a DIFFERENT film. The topic picker
excludes any subject that already has a directory under `projects/` — a
defence added that same day so a published film could not be re-made — so a
re-fire sees `projects/king-tut`, rules King Tut out, and starts from
research on Hiroshima. The week's work and the human's approval would both
have been thrown away by a guard working exactly as designed.

The opposite error is worse and is one line away: `scripts/publish_doc.py`
writes NO checkpoint, so `publish` never shows as a completed stage. A
"finished" test that waited for one would call every delivered film
unfinished for ever and resume a published film every Friday instead of
making a new one. So the authority on finished is the published ledger at
~/Developer/wak3up-docs/state/published.json, which is the one record of
what the channel actually has.
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import pytest

from scripts import unfinished_film as uf

PIPELINE = ["research", "proposal", "script", "scene_plan", "assets", "edit",
            "compose", "publish"]


def fake_resume_state(by_project: dict[str, list[str]]) -> types.ModuleType:
    """A stand-in for resume_state whose verdicts the test controls."""
    module = types.ModuleType("resume_state")

    def state(project: str) -> dict:
        done = by_project.get(project, [])
        return {
            "project": project,
            "completed": done,
            "next": next((s for s in PIPELINE if s not in done), None),
            "stages": [{"stage": s, "done": s in done} for s in PIPELINE],
        }

    module.state = state
    return module


@pytest.fixture
def films(tmp_path, monkeypatch):
    """Lay out projects/ and control both the checkpoints and the ledger."""
    def build(completed: dict[str, list[str]], published: list[str],
              order: list[str] | None = None):
        projects = tmp_path / "projects"
        for i, name in enumerate(order or sorted(completed)):
            art = projects / name / "artifacts"
            art.mkdir(parents=True, exist_ok=True)
            marker = art / "script.json"
            marker.write_text("{}")
            # freshness() reads artifact mtimes; later in `order` is newer.
            os.utime(marker, (1_700_000_000 + i * 60,) * 2)
        monkeypatch.setattr(uf, "ROOT", tmp_path)
        monkeypatch.setitem(sys.modules, "resume_state",
                            fake_resume_state(completed))
        shared = types.ModuleType("shared_state")
        shared.published_films = lambda: [{"project": p, "video_id": "x"}
                                          for p in published]
        monkeypatch.setitem(sys.modules, "shared_state", shared)
        return projects
    return build


class TestTheFilmThatMustBeFinished:
    def test_a_film_stopped_before_the_picture_is_resumed(self, films):
        films({"king-tut": ["research", "proposal", "script", "scene_plan",
                            "assets", "edit"]}, published=[])
        assert [slug for slug, _, _ in uf.unfinished()] == ["king-tut"]

    def test_the_reason_names_the_next_stage(self, films):
        films({"king-tut": ["research", "proposal", "script", "scene_plan",
                            "assets", "edit"]}, published=[])
        _, why, _ = uf.unfinished()[0]
        assert "compose" in why

    def test_the_newest_half_made_film_comes_first(self, films):
        done = ["research", "proposal", "script"]
        films({"older": done, "newer": done}, published=[],
              order=["older", "newer"])
        assert [slug for slug, _, _ in uf.unfinished()] == ["newer", "older"]


class TestWhatIsNotResumed:
    def test_a_published_film_is_never_remade(self, films):
        """The ledger is the authority, and publish writes no checkpoint."""
        films({"noah": PIPELINE[:-1]}, published=["noah"])
        assert uf.unfinished() == [], (
            "noah is on the channel. Nothing may offer to finish it again — "
            "and it will never have a `publish` checkpoint, because "
            "publish_doc.py does not write one.")

    def test_a_film_that_never_reached_the_human_gate_is_not_resumed(self, films):
        """Before the script is approved a fresh run can do better."""
        films({"half-researched": ["research"]}, published=[])
        assert uf.unfinished() == []

    def test_a_film_with_a_publish_checkpoint_is_done(self, films):
        films({"old-one": PIPELINE}, published=[])
        assert uf.unfinished() == []

    def test_one_published_film_does_not_hide_an_unfinished_one(self, films):
        films({"noah": PIPELINE[:-1],
               "king-tut": ["research", "proposal", "script", "scene_plan",
                            "assets", "edit"]},
              published=["noah"], order=["noah", "king-tut"])
        assert [slug for slug, _, _ in uf.unfinished()] == ["king-tut"]

    def test_a_directory_that_is_not_a_project_does_not_stop_the_week(self, films):
        """An exception per directory must not refuse to make a film."""
        projects = films({"king-tut": ["research", "proposal", "script",
                                       "scene_plan", "assets", "edit"]},
                         published=[])
        (projects / ".DS_Store").write_text("junk")
        (projects / "not-a-project").mkdir()
        assert [slug for slug, _, _ in uf.unfinished()] == ["king-tut"]


class TestTheRealStateOnThisMachine:
    """Skipped on CI: this is about THIS Mac, on 2026-11-07."""

    @pytest.mark.skipif(bool(os.environ.get("CI")), reason="machine-specific")
    def test_the_three_published_films_are_in_the_ledger(self):
        slugs = uf.published_slugs()
        for film in ("they-said-it-couldnt-be-built", "easter-island", "noah"):
            assert film in slugs, (film, slugs)

    @pytest.mark.skipif(bool(os.environ.get("CI")), reason="machine-specific")
    def test_king_tut_is_not_published_and_so_is_resumable(self):
        assert "king-tut" not in uf.published_slugs()

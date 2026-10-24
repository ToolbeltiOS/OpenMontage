"""Re-entering a stage must not redo the work already on disk.

A `claude -p` stage that stops on a usage limit has usually done real work
first: the first attended run had a research brief, a proposal and an
approved script when the render stage died. Going back in without saying so
starts at research again — hours redone, the ledger spent twice, and a
second set of artifacts over a set that was fine.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

from scripts import resume_state as rs
from scripts import stage_usage as su


class TestWhatAStageIsToldOnReEntry:
    def test_a_completed_stage_is_marked_and_named(self):
        st = rs.state("easter-island")
        assert "script" in st["completed"]
        assert st["next"] == "scene_plan"

    def test_the_instruction_forbids_redoing_finished_work(self):
        text = rs.render(rs.state("easter-island"))
        assert "Do NOT redo" in text
        assert "spends the run twice" in text

    def test_a_checkpoint_without_its_artifact_is_not_done(self, monkeypatch, tmp_path):
        """The one state that must never read as finished.

        A completed checkpoint whose artifact is missing means the stage
        said it finished and the file is not there. Trusting it skips the
        stage and the next one fails on a file that does not exist.
        """
        import lib.checkpoint as cp
        monkeypatch.setattr(rs, "ROOT", tmp_path)
        monkeypatch.setattr(
            "lib.checkpoint.get_completed_stages",
            lambda *a, **k: ["research", "script"])
        monkeypatch.setattr("lib.checkpoint.get_next_stage", lambda *a, **k: "scene_plan")
        art = tmp_path / "projects" / "p" / "artifacts"
        art.mkdir(parents=True)
        (art / "research_brief.json").write_text("{}")
        st = rs.state("p")
        assert "research" in st["completed"]
        assert "script" not in st["completed"], (
            "a completed checkpoint with no artifact was treated as done")
        note = next(r["note"] for r in st["stages"] if r["stage"] == "script")
        assert "MISSING" in note

    def test_an_artifact_without_a_checkpoint_is_not_assumed_done(self):
        """Files lying around are not evidence a stage finished."""
        st = rs.state("easter-island")
        scene = next(r for r in st["stages"] if r["stage"] == "scene_plan")
        assert scene["exists"] and not scene["done"]
        assert "do not assume" in scene["note"]


class TestWhatAStageCost:
    def test_the_numbers_come_out_of_the_json_result(self):
        row = su.summarise({
            "num_turns": 47, "duration_api_ms": 2_900_000,
            "total_cost_usd": 12.4, "is_error": False, "subtype": "success",
            "usage": {"input_tokens": 900, "output_tokens": 48210,
                      "cache_read_input_tokens": 4_100_000,
                      "cache_creation_input_tokens": 220_000},
            "permission_denials": [],
        }, "script", 3380, 1)
        assert row["turns"] == 47
        assert row["wall"] == "56m20s"
        assert row["cost_usd"] == 12.4
        assert row["output_tokens"] == 48210

    def test_a_denied_permission_is_counted(self):
        """The defect that cost the first attended run gets its own column."""
        row = su.summarise(
            {"permission_denials": [{"tool": "Bash"}, {"tool": "WebSearch"}]},
            "script", 10, 1)
        assert row["permission_denials"] == 2
        assert "2 DENIED" in su.line(row)

    def test_an_unreadable_result_does_not_raise(self, tmp_path):
        """A stage that died before writing JSON must still be recordable."""
        path = tmp_path / "empty.json"
        path.write_text("")
        row = su.summarise(su.load(path), "render", 42, 2)
        assert row["turns"] is None
        assert "render" in su.line(row) and "attempt 2" in su.line(row)

    def test_the_agents_own_report_survives_the_json_format(self, tmp_path):
        """The readable stage log was the best artifact of the first run."""
        result = tmp_path / "r.json"
        report = tmp_path / "script_stage.log"
        result.write_text(json.dumps({"result": "Done. 73 beats, 2,678 words."}))
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "stage_usage.py"), str(result),
             "--stage", "script", "--seconds", "10", "--report", str(report)],
            check=True, capture_output=True)
        assert "73 beats" in report.read_text()

"""The confidence rule: a loop with a budget, not a wall.

A paragraph under the threshold is a TODO for --fix until it has spent its two
attempts; only then does it fail the stage. Getting that backwards would stop
a run on its first pass through material the rule is meant to repair.
"""
from __future__ import annotations

import json

import pytest

from lib import alignment_qa as qa


def words(scores, start=0.0, step=0.3):
    return [{"word": f"w{i}", "start": start + i * step,
             "end": start + i * step + 0.2, "score": s}
            for i, s in enumerate(scores)]


class TestParagraphs:
    def test_direction_is_not_narration(self):
        text = "[beat: reveal]\nThe granite came from Wales.\n[air 2.5s]\nNobody knows how."
        assert qa.paragraphs(text) == ["The granite came from Wales.",
                                       "Nobody knows how."]

    def test_words_are_split_by_token_count(self):
        paras = ["one two three", "four five"]
        rows = qa.by_paragraph(words([0.9] * 5), paras)
        assert [r["words_aligned"] for r in rows] == [3, 2]
        assert rows[0]["mean_score"] == pytest.approx(0.9)

    def test_a_short_alignment_is_reported_not_raised(self):
        """Fewer words than the script means the alignment is incomplete."""
        rows = qa.by_paragraph(words([0.8] * 2), ["one two three four"])
        assert rows[0]["words_expected"] == 4
        assert rows[0]["words_aligned"] == 2

    def test_mean_and_min_are_both_reported(self):
        rows = qa.by_paragraph(words([0.9, 0.1, 0.8]), ["a b c"])
        assert rows[0]["mean_score"] == pytest.approx(0.6)
        assert rows[0]["min_score"] == pytest.approx(0.1)


class TestTheGate:
    def _project(self, tmp_path, scores):
        art = tmp_path / "artifacts"
        art.mkdir(parents=True)
        (art / "script.json").write_text(json.dumps(
            {"sections": [{"id": "act1", "text": "one two three"}]}))
        caps = tmp_path / "assets" / "captions" / "act1"
        caps.mkdir(parents=True)
        (caps / "transcript.json").write_text(json.dumps(words(scores)))
        return tmp_path

    def test_a_confident_paragraph_is_not_flagged(self, tmp_path):
        rows = qa.assess(str(self._project(tmp_path, [0.8, 0.9, 0.7])), 0.5)
        assert not rows[0]["under_threshold"]

    def test_an_unconfident_paragraph_is_flagged(self, tmp_path):
        rows = qa.assess(str(self._project(tmp_path, [0.3, 0.2, 0.4])), 0.5)
        assert rows[0]["under_threshold"]
        assert rows[0]["mean_score"] == pytest.approx(0.3)

    def test_the_threshold_is_the_playbooks(self):
        pb = qa.load_playbook()
        assert pb["audio"]["alignment_qa"]["min_mean_confidence"] == 0.5
        assert pb["audio"]["alignment_qa"]["max_attempts"] == qa.MAX_ATTEMPTS

    def test_attempts_survive_a_rerun(self, tmp_path):
        project = self._project(tmp_path, [0.3])
        state = qa.load_state(str(project))
        state["attempts"]["act1#0"] = 1
        qa.save_state(str(project), state)
        assert qa.load_state(str(project))["attempts"]["act1#0"] == 1

    def test_nothing_is_resynthesised_without_a_command(self, tmp_path):
        """Silently passing would be worse than reporting that it cannot."""
        row = {"section_id": "act1", "index": 0, "text": "one two three"}
        assert qa.resynthesise(row, "", str(tmp_path)) is False
        assert qa.resynthesise(row, None, str(tmp_path)) is False

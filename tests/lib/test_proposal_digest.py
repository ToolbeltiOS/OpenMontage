"""The proposal digest: the decision, not the packet.

The script stage became a separate `claude -p` from an empty context on
2026-11-11, so it can no longer remember what the proposal decided — it has
to read it. `proposal_packet.json` is 31 KB on a real film and most of it is
addressed to the proposal reviewer, not the writer.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import proposal_digest as PD  # noqa: E402

PACKET = {
    "version": "3",
    "selected_concept": {"concept_id": "concept-b",
                         "rationale": "B is the only one whose ledger "
                                      "carries twenty minutes."},
    "concept_options": [
        {"id": "concept-a", "title": "The Wrong One", "hook": "not chosen"},
        {"id": "concept-b", "title": "The Right One",
         "hook": "Twenty-two blocks came out of the water.",
         "core_message": "Nobody agrees on its height.",
         "tone": "grave, patient", "narrative_structure": "debate",
         "key_points": ["The estimates differ by sixty metres.",
                        "The witnesses agree with each other."],
         "target_duration_seconds": 1200,
         "grounded_in": ["c05", "c06"]},
    ],
    "production_plan": {
        "playbook": "wak3up-documentary",
        "composition_mode": "atelier",
        "art_direction": "Archive-led engravings.",
        "voice_selection": {"voice_id": "bm_george", "provider": "kokoro"},
        "delivery_promise": {"promise_type": "source_led",
                             "approved_fallback": None},
        "render_runtime": "remotion",
        # the parts the writer has no business re-deciding
        "provider_rankings": {"image": ["a", "b"]},
        "alternative_paths": ["one", "two", "three"],
        "quality_tradeoffs": ["x"],
        "stages": [{"name": "research"}],
    },
    "cost_estimate": {"total_usd": 42.0},
    "metadata": {"author": "proposal stage"},
}


@pytest.fixture(scope="module")
def out() -> str:
    return PD.render(PACKET)


class TestItPrintsTheDecision:
    def test_the_chosen_concept_id_and_the_count(self, out):
        assert "CHOSEN: concept-b" in out
        assert "of 2 considered" in out

    def test_the_rationale(self, out):
        assert "only one whose ledger" in out

    def test_the_chosen_concept_and_not_the_other_one(self, out):
        assert "The Right One" in out
        assert "The Wrong One" not in out

    def test_the_fields_the_writer_needs(self, out):
        for field in ("hook", "core_message", "tone", "narrative_structure",
                      "key_points", "target_duration_seconds",
                      "grounded_in"):
            assert field in out, field

    def test_the_claim_ids_the_concept_rests_on(self, out):
        assert "c05" in out and "c06" in out

    def test_the_binding_parts_of_the_production_plan(self, out):
        for field in ("playbook", "composition_mode", "art_direction",
                      "voice_selection", "delivery_promise"):
            assert field in out, field

    def test_an_empty_value_is_not_printed_as_none(self, out):
        """`approved_fallback: null` as "None" reads like a decision."""
        assert "approved_fallback" not in out


class TestItLeavesOutWhatIsNotTheWritersBusiness:
    @pytest.mark.parametrize("field", ["cost_estimate", "provider_rankings",
                                       "alternative_paths",
                                       "quality_tradeoffs", "metadata"])
    def test_the_field_is_absent_from_the_body(self, out, field):
        """The closing paragraph NAMES what it left out, so the check has to
        be against the body and not the whole string — otherwise the
        explanation makes the test fail for being honest."""
        body = out.split("LEAVES OUT, DELIBERATELY")[0]
        assert field not in body

    def test_the_values_of_those_fields_are_absent_too(self, out):
        """Not just the key: the 42.0 cost and the provider list."""
        body = out.split("LEAVES OUT, DELIBERATELY")[0]
        assert "42.0" not in body
        assert "alternative" not in body

    def test_it_says_what_it_left_out(self, out):
        """So a stage that needs one knows it was a choice, not an omission."""
        assert "LEAVES OUT, DELIBERATELY" in out
        assert "closing report" in out

    def test_it_is_far_smaller_than_the_packet(self, out):
        whole = json.dumps(PACKET)
        assert len(out) < len(whole) * 1.2
        real = (ROOT / "projects" / "king-tut" / "artifacts" /
                "proposal_packet.json")
        if real.exists():
            digest = PD.render(json.loads(real.read_text()))
            assert len(digest) < len(real.read_text()) / 4


class TestAMismatchedSelectionIsReportedNotHidden:
    def test_an_unknown_selected_id_falls_back_and_says_so(self):
        packet = json.loads(json.dumps(PACKET))
        packet["selected_concept"]["concept_id"] = "concept-zz"
        out = PD.render(packet)
        assert "THIS IS A BUG" in out
        assert "concept-zz" in out

    def test_no_concepts_at_all_does_not_crash(self):
        out = PD.render({"selected_concept": {}, "concept_options": []})
        assert "CHOSEN" in out


class TestTheCommandLine:
    def test_a_missing_packet_exits_one_and_says_where(self, tmp_path):
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "proposal_digest.py"),
             "--project", "nope", "--packet", str(tmp_path / "gone.json")],
            capture_output=True, text=True)
        assert r.returncode == 1
        assert "no proposal packet at" in r.stderr

    def test_it_renders_the_real_packet(self, tmp_path):
        real = (ROOT / "projects" / "king-tut" / "artifacts" /
                "proposal_packet.json")
        if not real.exists():
            pytest.skip("king-tut's packet is not in this worktree")
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "proposal_digest.py"),
             "--project", "king-tut"], capture_output=True, text=True,
            cwd=str(ROOT))
        assert r.returncode == 0, r.stderr
        assert "CHOSEN:" in r.stdout

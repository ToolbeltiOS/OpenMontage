"""Forced alignment is cacheable, and run #5 paid for it twice.

WHY THIS TEST EXISTS
--------------------
2026-11-13. The edit stage was killed at its 60-turn cap having just
finished aligning 2,516 words of narration — 0 unplaced, worst run 0, a
clean result written to `artifacts/alignment_qa.json` and eight
`assets/captions/<section>/transcript.json` files. The next attempt started
from an empty context and began the same alignment again.

Alignment loads wav2vec2 and walks every section's audio; it is the most
expensive thing in the edit stage that is not a render. It is also purely a
function of two inputs — the narration audio, and the words it was aligned
against — so the result now records a fingerprint of both and a later run
compares it.

WHAT MUST NOT HAPPEN is the other failure: a SKIPPED alignment that should
have run. Timings for words that are no longer in the script are how run #1
ended up with the recogniser's spelling burnt into the picture. So every
test below that proves the skip is matched by one that proves it does not
happen — a changed wav, a changed line of script, a deleted transcript, and
an alignment_qa.json written before fingerprints existed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "align_narration.py"

spec = importlib.util.spec_from_file_location("align_narration", SCRIPT)
align = importlib.util.module_from_spec(spec)
sys.modules["align_narration"] = align
spec.loader.exec_module(align)


SCRIPT_JSON = {"sections": [
    {"id": "cold_open", "text": "One. Two three."},
    {"id": "act1", "text": "Four five six. Seven."},
]}


@pytest.fixture
def film(tmp_path):
    """A project with narration audio, transcripts and a QA file."""
    project = tmp_path / "a-film"
    (project / "artifacts").mkdir(parents=True)
    (project / "assets" / "audio").mkdir(parents=True)
    (project / "artifacts" / "script.json").write_text(json.dumps(SCRIPT_JSON))
    for section in SCRIPT_JSON["sections"]:
        sid = section["id"]
        (project / "assets" / "audio" / f"{sid}.wav").write_bytes(
            b"RIFF" + sid.encode() + b"\0" * 64)
        out = project / "assets" / "captions" / sid
        out.mkdir(parents=True)
        (out / "transcript.json").write_text(json.dumps(
            [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4}
             for i, w in enumerate(section["text"].split())]))

    def write_qa(fingerprint=None):
        blob = {"sections": {}, "words": 5, "unplaced": 0}
        if fingerprint is not None:
            blob["inputs"] = fingerprint
        (project / "artifacts" / "alignment_qa.json").write_text(
            json.dumps(blob))

    fingerprint = align.narration_fingerprint(project, SCRIPT_JSON)
    write_qa(fingerprint)
    return project, write_qa


class TestTheFingerprint:
    def test_it_covers_every_section_that_has_audio(self, film):
        project, _ = film
        fingerprint = align.narration_fingerprint(project, SCRIPT_JSON)
        assert sorted(fingerprint) == ["act1", "cold_open"]

    def test_a_section_with_no_audio_is_not_in_it(self, film):
        project, _ = film
        (project / "assets" / "audio" / "act1.wav").unlink()
        fingerprint = align.narration_fingerprint(project, SCRIPT_JSON)
        assert sorted(fingerprint) == ["cold_open"]

    def test_it_hashes_the_audio_and_the_words_separately(self, film):
        project, _ = film
        fingerprint = align.narration_fingerprint(project, SCRIPT_JSON)
        row = fingerprint["cold_open"]
        assert row["audio_sha256"] == hashlib.sha256(
            (project / "assets" / "audio" / "cold_open.wav").read_bytes()
        ).hexdigest()
        assert row["text_sha256"] == hashlib.sha256(
            b"One. Two three.").hexdigest()
        assert row["audio_bytes"] == len(b"RIFF") + len(b"cold_open") + 64

    def test_asking_for_one_section_fingerprints_one_section(self, film):
        project, _ = film
        assert sorted(align.narration_fingerprint(
            project, SCRIPT_JSON, ["act1"])) == ["act1"]


class TestItSkipsWhenNothingChanged:
    def test_unchanged_inputs_are_current(self, film):
        project, _ = film
        fingerprint = align.narration_fingerprint(project, SCRIPT_JSON)
        current, why = align.alignment_is_current(project, fingerprint)
        assert current, why
        assert "2 section(s) unchanged" in why

    def test_a_subset_of_sections_is_current_too(self, film):
        """A resume asking for one section must not be told the whole film
        changed."""
        project, _ = film
        fingerprint = align.narration_fingerprint(project, SCRIPT_JSON,
                                                  ["act1"])
        current, why = align.alignment_is_current(project, fingerprint)
        assert current, why


class TestItRealignsWhenAnythingChanged:
    """Each of these is a reason the alignment on disk is a lie."""

    def test_a_changed_wav_is_not_current(self, film):
        project, _ = film
        (project / "assets" / "audio" / "act1.wav").write_bytes(b"different")
        current, why = align.alignment_is_current(
            project, align.narration_fingerprint(project, SCRIPT_JSON))
        assert not current
        assert "act1: the narration audio changed" in why

    def test_a_changed_script_line_is_not_current(self, film):
        """THE CASE THE OWNER DID NOT ASK FOR, and the one that produced
        run #1's captions: same audio, different words."""
        project, _ = film
        edited = {"sections": [
            dict(SCRIPT_JSON["sections"][0]),
            {"id": "act1", "text": "Four five six. Seven. Eight."},
        ]}
        current, why = align.alignment_is_current(
            project, align.narration_fingerprint(project, edited))
        assert not current
        assert "act1: the script text changed" in why

    def test_a_vanished_transcript_is_not_current(self, film):
        project, _ = film
        (project / "assets" / "captions" / "act1" / "transcript.json").unlink()
        current, why = align.alignment_is_current(
            project, align.narration_fingerprint(project, SCRIPT_JSON))
        assert not current
        assert "transcript.json is gone" in why

    def test_a_new_section_is_not_current(self, film):
        project, _ = film
        grown = {"sections": SCRIPT_JSON["sections"] + [
            {"id": "act2", "text": "Nine."}]}
        (project / "assets" / "audio" / "act2.wav").write_bytes(b"RIFFact2")
        current, why = align.alignment_is_current(
            project, align.narration_fingerprint(project, grown))
        assert not current
        assert "act2 is not in the recorded alignment" in why

    def test_a_qa_file_with_no_fingerprints_is_not_current(self, film):
        """Every alignment_qa.json written before 2026-11-14, including the
        one run #5 left on disk. Re-aligning is minutes; trusting it is a
        caption track that drifts."""
        project, write_qa = film
        write_qa(None)
        current, why = align.alignment_is_current(
            project, align.narration_fingerprint(project, SCRIPT_JSON))
        assert not current
        assert "predates" in why

    def test_a_missing_qa_file_is_not_current(self, film):
        project, _ = film
        (project / "artifacts" / "alignment_qa.json").unlink()
        current, why = align.alignment_is_current(
            project, align.narration_fingerprint(project, SCRIPT_JSON))
        assert not current
        assert why == "no alignment_qa.json"

    def test_an_unreadable_qa_file_is_not_current(self, film):
        project, _ = film
        (project / "artifacts" / "alignment_qa.json").write_text("{not json")
        current, why = align.alignment_is_current(
            project, align.narration_fingerprint(project, SCRIPT_JSON))
        assert not current
        assert "unreadable" in why

    def test_no_audio_at_all_is_not_current(self, film):
        """Nothing to compare is not the same as nothing to do."""
        project, _ = film
        for section in SCRIPT_JSON["sections"]:
            (project / "assets" / "audio" / f"{section['id']}.wav").unlink()
        current, why = align.alignment_is_current(project, {})
        assert not current
        assert "no narration audio" in why


class TestItIsWiredIntoTheScript:
    def test_force_exists_so_the_skip_can_always_be_overridden(self):
        assert '"--force"' in SCRIPT.read_text()

    def test_the_skip_happens_before_whisperx_is_imported(self):
        """The import IS the cost. A skip that still loads wav2vec2 saves
        nothing worth having."""
        body = SCRIPT.read_text()
        skip = body.index("if current and not args.force:")
        model = body.index("model, metadata = whisperx.load_align_model")
        assert skip < model

    def test_the_result_records_the_fingerprint_it_was_built_from(self):
        body = SCRIPT.read_text()
        assert '"inputs": fingerprint,' in body

    def test_a_skipped_run_still_reports_the_word_duration_gate(self):
        """Skipping the work must not skip the verdict: an alignment on disk
        that fails the 40ms floor has to keep failing."""
        body = SCRIPT.read_text()
        skip = body[body.index("if current and not args.force:"):]
        skip = skip[:skip.index("import whisperx")]
        assert "WORD TIMINGS:" in skip
        assert "return 0 if before_short == 0 else 1" in skip

"""A reused mix has to be a mix THIS edit would have built.

WHY THIS TEST EXISTS
--------------------
`build_audio(reuse=True)` meant "mix_final.wav exists". That let an
intermediate and the mix it feeds drift apart, and it did: on easter-island
`bed_eq.wav` is deterministic — two rebuilds give one md5 — but the bed on
disk was not the bed the EDL reproduces. `lib/music_arousal.py` reads
bed_eq.wav, so the blocking music gate was grading a bed that was not in the
film: 8 supported rises against the stale one, 6 and a different set against
the real one.

Nothing failed. Every loudness check passed, because the film was still
-14 LUFS. It is the same shape as the defect the mixer's own comment already
records — a rejected mix reinstated by a re-render while every check stayed
green — and the answer is the same: do not trust a file, trust what built it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib import build_render_props as B


@pytest.fixture
def project(tmp_path, monkeypatch):
    out = tmp_path / "renders"
    aud = tmp_path / "audio"
    out.mkdir(); aud.mkdir()
    for name in B.SECTIONS:
        (aud / f"{name}.wav").write_bytes(b"x" * 100)
    monkeypatch.setattr(B, "OUT", str(out))
    monkeypatch.setattr(B, "AUD", str(aud))
    # The fixture's wavs are bytes, not audio; the hash reads their size and
    # mtime, and only the offsets need a duration.
    monkeypatch.setattr(B, "dur", lambda path: 10.0)
    # The rebuild path shells out to ffmpeg before it reaches the mixer; the
    # question here is WHETHER it rebuilds, not what ffmpeg does with bytes.
    monkeypatch.setattr(B.subprocess, "run", lambda *a, **k: None)
    return out, aud


EDL = {"music": {"beds": [{"name": "a", "track": "T.mp3", "acts": ["act1"]}]}}


class TestTheStampIsAFunctionOfWhatBuildsTheMix:
    def test_the_same_edl_and_narration_hash_the_same(self, project):
        assert B.mix_inputs_hash(EDL) == B.mix_inputs_hash(json.loads(json.dumps(EDL)))

    def test_a_changed_bed_changes_the_hash(self, project):
        other = json.loads(json.dumps(EDL))
        other["music"]["beds"][0]["track"] = "DIFFERENT.mp3"
        assert B.mix_inputs_hash(EDL) != B.mix_inputs_hash(other)

    def test_a_changed_level_changes_the_hash(self, project):
        other = json.loads(json.dumps(EDL))
        other["music"]["levels"] = {"under_speech_lufs": -36}
        assert B.mix_inputs_hash(EDL) != B.mix_inputs_hash(other)

    def test_resynthesised_narration_changes_the_hash(self, project):
        """The other half of the mix, and the half a music-only hash misses."""
        out, aud = project
        before = B.mix_inputs_hash(EDL)
        (aud / "act1.wav").write_bytes(b"y" * 250)
        assert B.mix_inputs_hash(EDL) != before

    def test_a_caption_change_does_not(self, project):
        """Hashing the whole EDL would churn the mix on an unrelated edit."""
        other = json.loads(json.dumps(EDL))
        other["captions"] = ["a different caption"]
        assert B.mix_inputs_hash(EDL) == B.mix_inputs_hash(other)


class TestWhatReuseWillAndWillNotAccept:
    def test_a_mix_with_a_matching_stamp_is_reused(self, project, capsys):
        out, _ = project
        (out / "mix_final.wav").write_bytes(b"mix")
        (out / ".mix_inputs").write_text(B.mix_inputs_hash(EDL) + "\n")
        path, offsets = B.build_audio("", EDL, reuse=True)
        assert path.endswith("mix_final.wav")
        assert "reusing existing" in capsys.readouterr().out

    def test_a_mix_with_a_stale_stamp_is_not(self, project, monkeypatch, capsys):
        out, _ = project
        (out / "mix_final.wav").write_bytes(b"mix")
        (out / ".mix_inputs").write_text("0000000000000000\n")
        monkeypatch.setattr(B, "music_spans",
                            lambda *a, **k: (_ for _ in ()).throw(SystemExit("rebuilt")))
        with pytest.raises(SystemExit):
            B.build_audio("", EDL, reuse=True)
        assert "NOT reusing" in capsys.readouterr().out

    def test_a_mix_with_no_stamp_at_all_is_not(self, project, monkeypatch, capsys):
        """Every mix built before the stamp existed is suspect by default."""
        out, _ = project
        (out / "mix_final.wav").write_bytes(b"mix")
        monkeypatch.setattr(B, "music_spans",
                            lambda *a, **k: (_ for _ in ()).throw(SystemExit("rebuilt")))
        with pytest.raises(SystemExit):
            B.build_audio("", EDL, reuse=True)
        assert "never recorded" in capsys.readouterr().out

    def test_a_crashed_mix_leaves_no_stamp(self, project, monkeypatch):
        """So the next run rebuilds rather than trusting a half-written file."""
        out, _ = project
        monkeypatch.setattr(B, "music_spans",
                            lambda *a, **k: (_ for _ in ()).throw(SystemExit("boom")))
        with pytest.raises(SystemExit):
            B.build_audio("", EDL, reuse=False)
        assert not (out / ".mix_inputs").exists()

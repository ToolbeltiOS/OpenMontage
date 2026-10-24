"""A rise is allowed only where the music is already rising.

The mood table decides whether the EDIT may lift the bed. Whether the music
supports it is a separate fact, and a bed that is flat or falling does not
become a rise because an edit asked for one — it becomes a fader move, which
is what an audience hears as manipulation.

The fixtures are synthesised so the answer is known: a tone that gets louder
is rising, one that fades is not, one that holds is not. The real bed is
measured in the report, not here.
"""
from __future__ import annotations

import numpy as np
import pytest

from lib import music_arousal as ma

pytest.importorskip("librosa")
pytest.importorskip("soundfile")

SR = 22050


def tone(path, seconds=30.0, shape="flat"):
    """A tone whose loudness and brightness follow a known shape."""
    import soundfile as sf

    t = np.arange(int(SR * seconds)) / SR
    p = t / t[-1]
    if shape == "rising":
        gain, hz = 0.05 + 0.45 * p, 180 + 900 * p
    elif shape == "falling":
        gain, hz = 0.5 - 0.45 * p, 1080 - 900 * p
    else:
        gain, hz = np.full_like(t, 0.3), np.full_like(t, 400.0)
    phase = 2 * np.pi * np.cumsum(hz) / SR
    wave = (gain * np.sin(phase)).astype("float32")
    sf.write(path, wave, SR)
    return str(path)


class TestTheCurve:
    def test_a_rising_tone_rises(self, tmp_path):
        data = ma.curve(tone(tmp_path / "up.wav", shape="rising"))
        assert ma.slope_at(data, 15.0) > ma.RISING_THRESHOLD

    def test_a_falling_tone_does_not(self, tmp_path):
        data = ma.curve(tone(tmp_path / "down.wav", shape="falling"))
        assert ma.slope_at(data, 15.0) < 0

    def test_a_steady_tone_is_not_a_rise(self, tmp_path):
        data = ma.curve(tone(tmp_path / "flat.wav", shape="flat"))
        assert abs(ma.slope_at(data, 15.0)) < ma.RISING_THRESHOLD

    def test_the_curve_covers_the_piece(self, tmp_path):
        data = ma.curve(tone(tmp_path / "f.wav", seconds=20.0))
        assert data["duration"] == pytest.approx(20.0, abs=0.2)
        assert len(data["times"]) == len(data["arousal"])


class TestTheGate:
    def _cut(self, at, rise=True):
        return {"id": f"c{int(at)}", "in_seconds": at, "out_seconds": at + 5,
                "music_rise_allowed": rise}

    def test_a_rise_on_a_rising_bed_passes(self, tmp_path):
        bed = tone(tmp_path / "up.wav", shape="rising")
        problems, measured = ma.check([self._cut(15.0)], bed)
        assert problems == [], problems
        assert measured["rises_the_music_supports"] == 1

    def test_a_rise_on_a_falling_bed_fails(self, tmp_path):
        bed = tone(tmp_path / "down.wav", shape="falling")
        problems, measured = ma.check([self._cut(15.0)], bed)
        assert problems, "a rise was allowed over a bed that is falling"
        assert "falling" in problems[0]
        assert measured["rises_the_music_supports"] == 0

    def test_a_rise_on_a_flat_bed_fails_and_says_flat(self, tmp_path):
        bed = tone(tmp_path / "flat.wav", shape="flat")
        problems, _ = ma.check([self._cut(15.0)], bed)
        assert problems and "flat" in problems[0]

    def test_a_cut_that_asks_for_nothing_is_not_examined(self, tmp_path):
        bed = tone(tmp_path / "down.wav", shape="falling")
        problems, measured = ma.check([self._cut(15.0, rise=False)], bed)
        assert problems == []
        assert measured["rises_asked_for"] == 0


class TestWhatThisIsNot:
    def test_the_three_signals_are_weighted_and_sum_to_one(self):
        assert set(ma.WEIGHTS) == {"loudness", "brightness", "density"}
        assert sum(ma.WEIGHTS.values()) == pytest.approx(1.0)
        assert ma.WEIGHTS["loudness"] >= max(
            ma.WEIGHTS["brightness"], ma.WEIGHTS["density"])

    def test_it_does_not_claim_to_be_essentia(self):
        """The brief named a trained model; this is three signals by hand."""
        assert "Essentia" in ma.__doc__ and "NOT the same thing" in ma.__doc__


class TestReconcilingWhatTheEditAsksAgainstWhatTheBedDoes:
    """The flag is the edit's intent; only the bed knows if it is honourable.

    `music_rise_allowed` comes from the mood table. Whether the music is
    actually rising there is a separate fact, and on easter-island the table
    asked for 21 rises and the bed supported 8. Reconciling in the stage that
    rebuilds matters: a flag cleared by hand on `render_props.json` is
    cleared until the next render, and the gate fails again on the next run
    with no record of why.
    """

    def test_a_rise_the_bed_supports_is_kept(self, tmp_path):
        bed = tone(tmp_path / "r1.wav", shape="rising")
        cuts = [{"id": "c001", "in_seconds": 15.0, "music_rise_allowed": True}]
        report = ma.reconcile(cuts, bed)
        assert report["rises_kept"] == 1, report
        assert cuts[0]["music_rise_allowed"] is True
        assert "music_rise_reason" not in cuts[0]

    def test_a_rise_the_bed_does_not_support_is_cleared_with_its_reason(self, tmp_path):
        bed = tone(tmp_path / "f1.wav", shape="falling")
        cuts = [{"id": "c001", "in_seconds": 15.0, "music_rise_allowed": True}]
        report = ma.reconcile(cuts, bed)
        assert report["rises_cleared"] == 1, report
        assert cuts[0]["music_rise_allowed"] is False
        assert ma.RISE_CLEARED_REASON in cuts[0]["music_rise_reason"]
        assert "sd/s" in cuts[0]["music_rise_reason"], (
            "the reason has to carry the measurement, not just the verdict")

    def test_a_cut_that_never_asked_is_untouched(self, tmp_path):
        bed = tone(tmp_path / "f2.wav", shape="falling")
        cuts = [{"id": "c001", "in_seconds": 15.0}]
        ma.reconcile(cuts, bed)
        assert "music_rise_reason" not in cuts[0]

    def test_reconciling_makes_the_gate_pass(self, tmp_path):
        """The point of it: what survives is what the bed supports."""
        bed = tone(tmp_path / "f3.wav", shape="falling")
        cuts = [{"id": "c001", "in_seconds": 15.0, "music_rise_allowed": True}]
        ma.reconcile(cuts, bed)
        problems, measured = ma.check(cuts, bed)
        assert problems == []
        assert measured["rises_asked_for"] == 0

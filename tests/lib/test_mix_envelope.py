"""The envelope that lifts the music bed, and the three things wrong with it.

1. IT WAS KEYED ON THE WRONG LIST. `gain_envelope`'s second argument was
   called `offsets` and was given `build_narration`'s per-SEGMENT offsets —
   73 of them on easter-island, against 6 acts. Every paragraph start got the
   act-boundary lift, the loudest level in the mix, mid-sentence, under
   speech. 365 seconds of a 1,210-second film.

   Nothing could have caught it from the outside: the film's integrated
   loudness is set by the voice, the bed's integrated loudness still lands on
   its target because 73 brief lifts average out over twenty minutes, and the
   music-rise gate only examines the cuts the EDIT asked to lift under. The
   defect is injected below and measured as a share of the runtime, which is
   the only form in which it is visible.

2. THE GAP RISE WAS NOT CAPPED. It was an absolute target, so dropping the
   bed level silently grew the rise.

3. THE EDGES WERE A ONE-POLE, which cannot be asked for a ramp length.

The fixtures are synthesised so the answer is arithmetic: a voice that is
loud for a known stretch and silent for a known stretch.
"""
from __future__ import annotations

import numpy as np
import pytest

from lib import mix_audio as mx

SR = mx.SR


def voice(pattern: list[tuple[float, bool]]) -> np.ndarray:
    """A two-channel voice track from (seconds, speaking) pairs."""
    parts = []
    for seconds, speaking in pattern:
        n = int(seconds * SR)
        if speaking:
            t = np.arange(n) / SR
            parts.append(0.2 * np.sin(2 * np.pi * 180 * t).astype(np.float32))
        else:
            parts.append(np.zeros(n, dtype=np.float32))
    mono = np.concatenate(parts).astype(np.float32)
    return np.stack([mono, mono], axis=1)


def talking(seconds: float = 60.0) -> np.ndarray:
    """A voice that never stops, so every lift in the envelope is a boundary."""
    return voice([(seconds, True)])


class TestTheEnvelopeIsKeyedOnActs:
    def test_six_boundaries_lift_the_bed_six_times(self):
        v = talking(120.0)
        n = len(v)
        env = mx.gain_envelope(v, [20.0, 40.0, 60.0, 80.0, 100.0], n, -33.0)
        boundary = mx.BOUNDARY_TARGET_LUFS - (-33.0)
        lifted = env >= boundary - 0.001
        # five boundaries, each BOUNDARY_WINDOW either side
        expected = 5 * 2 * mx.BOUNDARY_WINDOW * SR
        assert lifted.sum() == pytest.approx(expected, rel=0.02)

    def test_the_segment_list_is_the_defect_and_it_is_measurable(self):
        """INJECTED: give it a paragraph start every 1.6s, as it used to get.

        The real film has 73 narration segments inside 1,210 seconds, which is
        one every 16.6 seconds against a 5-second boundary window. Scaled down
        here to the same ratio, the share of the film at the act-boundary
        level is the number that matters, and it is enormous.
        """
        v = talking(120.0)
        n = len(v)
        acts = [20.0, 40.0, 60.0, 80.0, 100.0]
        segments = [float(x) for x in np.arange(2.0, 120.0, 7.2)]
        boundary = mx.BOUNDARY_TARGET_LUFS - (-33.0)

        right = mx.gain_envelope(v, acts, n, -33.0)
        wrong = mx.gain_envelope(v, segments, n, -33.0)

        share_right = float((right >= boundary - 0.001).mean())
        share_wrong = float((wrong >= boundary - 0.001).mean())
        assert share_right < 0.25, share_right
        assert share_wrong > 0.60, (
            f"the injected defect only lifted {share_wrong:.0%} of the film; "
            f"the fixture no longer reproduces it")
        assert share_wrong > 2.5 * share_right

    def test_build_narration_reports_boundaries_separately_from_offsets(self):
        """The two lists have to be two arguments, or the bug comes back."""
        import inspect

        sig = inspect.signature(mx.gain_envelope)
        assert "boundaries" in sig.parameters, (
            "the parameter is named `boundaries` on purpose: `offsets` was "
            "true of both lists, which is how the wrong one got passed")
        src = inspect.getsource(mx.build_narration)
        assert "boundaries" in src and "section_id" in src


class TestTheGapRiseIsCapped:
    def test_a_gap_rises_by_the_cap_and_no_further(self):
        v = voice([(10.0, True), (6.0, False), (10.0, True)])
        env = mx.gain_envelope(v, [], len(v), -33.0)
        assert env.max() == pytest.approx(mx.GAP_RISE_DB_MAX, abs=0.01)

    def test_the_cap_binds_when_the_absolute_target_asks_for_more(self):
        """A lower bed must not grow the rise to reach a fixed target."""
        v = voice([(10.0, True), (6.0, False), (10.0, True)])
        deep = mx.gain_envelope(v, [], len(v), -60.0)
        assert deep.max() == pytest.approx(mx.GAP_RISE_DB_MAX, abs=0.01), (
            "at -60 the absolute gap target is +30 away; the cap is the "
            "authority and it is +3")

    def test_the_two_statements_of_the_gap_level_agree_at_the_bed_level(self):
        """-33 + 3 == -30. If either moves without the other, this fails."""
        bed = mx.playbook_under_speech_lufs()
        assert mx.GAP_TARGET_LUFS - bed == pytest.approx(mx.GAP_RISE_DB_MAX)

    def test_a_short_pause_is_not_a_gap(self):
        v = voice([(10.0, True), (0.5, False), (10.0, True)])
        env = mx.gain_envelope(v, [], len(v), -33.0)
        assert env.max() == pytest.approx(0.0, abs=0.01)

    def test_a_short_pause_the_music_is_rising_into_takes_the_gap_level(self):
        v = voice([(10.0, True), (0.8, False), (10.0, True)])
        env = mx.gain_envelope(v, [], len(v), -33.0, rises=[10.4])
        assert env.max() == pytest.approx(mx.GAP_RISE_DB_MAX, abs=0.01)


class TestTheEdgesAreExplicitRamps:
    def _long_gap(self):
        return voice([(10.0, True), (12.0, False), (10.0, True)])

    def test_a_ramp_reaches_the_plateau_and_holds_it(self):
        v = self._long_gap()
        env = mx.shape_envelope(v, [], len(v), -33.0)
        assert env.max() == pytest.approx(mx.GAP_RISE_DB_MAX, abs=0.05)

    def test_the_measured_edge_is_what_a_raised_cosine_gives(self):
        """0.59 of the authored length, not the authored length itself."""
        v = self._long_gap()
        env = mx.shape_envelope(v, [], len(v), -33.0)
        edges = mx.edge_times(env)
        want = 0.59 * mx.RISE_RAMP_SECONDS
        assert edges["rise_10_90_s_median"] == pytest.approx(want, abs=0.15)
        assert edges["fall_90_10_s_median"] == pytest.approx(want, abs=0.15)

    def test_the_ramp_out_finishes_before_the_voice_returns(self):
        """Anticipatory, not a release afterwards."""
        v = self._long_gap()
        env = mx.shape_envelope(v, [], len(v), -33.0)
        resumes = int(22.0 * SR)
        assert env[resumes] == pytest.approx(0.0, abs=0.3), (
            "the bed is still up when the voice comes back")

    def test_a_region_shorter_than_two_ramps_still_reaches_the_plateau(self):
        """Touched by the level, not held at it."""
        target = np.zeros(int(8 * SR), dtype=np.float32)
        target[int(3 * SR):int(4.3 * SR)] = 3.0
        out = mx.ramp_rises(target)
        assert out.max() == pytest.approx(3.0, abs=0.01)
        # A raised cosine is flat at its peak, so it does spend a moment
        # there; what it must not do is hold the level for the whole 1.3s.
        held = float((out > 2.9).sum()) / SR
        assert held < 0.3, (
            f"a 1.3s pause is being HELD at the gap level for {held:.2f}s, "
            f"not touched by it")

    def test_a_corner_free_ramp_starts_and_ends_flat(self):
        ramp = mx._cosine_ramp(int(1.5 * SR))
        d = np.diff(ramp)
        assert abs(d[0]) < abs(d[len(d) // 2]) / 50
        assert abs(d[-1]) < abs(d[len(d) // 2]) / 50

    def test_the_one_pole_no_longer_owns_the_edge(self):
        """It is a de-zipper now, and the module says why."""
        assert mx.DEZIPPER_MS <= 50
        assert mx.SUPERSEDED_RELEASE_MS == 900
        assert "2.64" in mx.__doc__ or "2.64" in open(
            mx.__file__, encoding="utf-8").read(), (
            "the measurement that retired the one-pole has to stay written "
            "down, or somebody will put it back")


class TestTheFloorIsReferencedToTheUnduckedBed:
    """Both layers ride the same envelope, so the offset is set before it.

    `build_sound_design` was handed `bed_ducked` and the layer it returns is
    then multiplied by the SAME envelope a few lines later, so the floor was
    ducked twice relative to its own reference. The envelope is 0 dB under
    speech and +3 dB in a gap and +6 dB at an act boundary — which is exactly
    where the impacts and the stings are placed — so every one-shot arrived 3
    to 6 dB louder than the playbook asked for, and nowhere else did.

    Measured on the film: the sting at 52s came out at -32.3 LUFS against a
    -38.3 target, +6.0 dB, the boundary boost to the decibel.

    The arithmetic below is the defect in four lines. It does not need the
    mixer to run.
    """

    def _levels(self, reference_is_ducked: bool):
        lift_db = mx.BOUNDARY_TARGET_LUFS - (-33.0)      # +6 at the boundary
        bed_db = -36.8                                   # the bed, un-ducked
        offset = -2.0                                    # e.g. sting_peak
        reference = bed_db + lift_db if reference_is_ducked else bed_db
        placed = reference + offset
        # both layers are then multiplied by the envelope
        return (placed + lift_db) - (bed_db + lift_db)

    def test_referencing_the_unducked_bed_keeps_the_offset(self):
        assert self._levels(reference_is_ducked=False) == pytest.approx(-2.0)

    def test_referencing_the_ducked_bed_loses_it_by_the_whole_lift(self):
        """INJECTED: the defect, and it is the size of the boundary boost."""
        lift = mx.BOUNDARY_TARGET_LUFS - (-33.0)
        assert self._levels(reference_is_ducked=True) == \
            pytest.approx(-2.0 + lift)
        assert lift == pytest.approx(6.0), (
            "the boundary boost moved; the 6.0 dB in the mix report's "
            "explanation needs rechecking")

    def test_the_mixer_passes_the_unducked_bed(self):
        import inspect

        src = inspect.getsource(mx.main)
        assert "build_sound_design(total, bed)" in src, (
            "the floor is being referenced to the ducked bed again")
        assert "build_sound_design(total, bed_ducked)" not in src

    def test_and_says_why_in_the_source(self):
        import inspect

        src = inspect.getsource(mx.build_sound_design)
        assert "ducked twice" in src

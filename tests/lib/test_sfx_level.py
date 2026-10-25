"""Is the sound-design layer under the music bed, measured?

The owner's rule, 2026-10-25: "everything below the bed's level in its
moment … no SFX event louder than the bed at that instant, measured."

THREE THINGS THIS TEST FILE PINS DOWN
-------------------------------------
1. K-WEIGHTING, NOT RMS. The elements are deliberately spread across the
   spectrum: this film's sting has a 59 Hz centroid, its impact 75 Hz, its sea
   ambience 1,647 Hz. Measured, the curve puts 30 Hz 9.0 dB down on 1 kHz and
   1.6 kHz 1.6 dB up, at equal RMS — so about 4 dB between a low impact and a
   bright hiss, in the direction the ear agrees with. Four decibels, not the
   "far above" the first draft of this file asserted: enough to change a
   verdict near the line, not enough to rescue a one-shot 8 dB too loud. The
   decisive reason for the unit is that the offset table and the ceiling are
   now in ONE of them.

2. EVENTS AND CONTINUOUS LAYERS ARE DIFFERENT. The rule is written about
   events. Ambience and room tone are beds that run for whole acts.

3. A HOLE IN THE BED IS THE BED'S DEFECT, NOT THE FLOOR'S. If every window
   where the music drops out counted against the floor, the only way to pass
   would be to duck the room tone into every dip in the score, which is
   audible as the room breathing. Those windows are excluded AND COUNTED, so
   a bed full of holes cannot hide behind the exclusion.
"""
from __future__ import annotations

import numpy as np
import pytest

from lib import verify_sfx_level as sfx

SR = 48000


def tone(hz: float, seconds: float, amp: float = 0.1) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    return (amp * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def bed(seconds: float = 40.0, amp: float = 0.1) -> np.ndarray:
    """A steady mid bed, as a stereo layer."""
    mono = tone(400.0, seconds, amp)
    return np.stack([mono, mono], axis=1)


def layer(seconds: float = 40.0, amp: float = 0.0) -> np.ndarray:
    mono = tone(300.0, seconds, amp) if amp else np.zeros(int(seconds * SR),
                                                          dtype=np.float32)
    return mono[:, None]


def place(base: np.ndarray, event: np.ndarray, at: float) -> np.ndarray:
    out = base.copy()
    i = int(at * SR)
    n = min(len(event), len(out) - i)
    out[i:i + n, 0] += event[:n]
    return out


SPEC = {"room_tone": {"path": "rt.wav"},
        "ambience": [{"act": "act1", "palette": "stone",
                      "start_seconds": 0.0, "end_seconds": 40.0,
                      "path": "a.wav"}],
        "impacts": [{"at_seconds": 20.0, "path": "i.wav"}],
        "stings": [], "risers": []}

#: The same film with no one-shots in it. The continuous checks need this:
#: with an impact declared at 20s, a loud floor is reported as the impact
#: being over the bed — which is correct, and is not what those tests are
#: about.
NO_EVENTS = {**SPEC, "impacts": []}


class TestTheUnit:
    def test_k_weighting_rejects_the_wrong_sample_rate(self):
        with pytest.raises(ValueError, match="48 kHz"):
            sfx.k_weight(np.zeros(1000, dtype=np.float32), sr=44100)

    def test_a_low_tone_measures_quieter_than_a_bright_one_at_the_same_rms(self):
        """The reason the gate is in LUFS and not in dBFS — with the real size.

        30 Hz against 1 kHz is 9 dB on this curve. The film's own elements are
        75 Hz against 1,647 Hz, which is about 4 dB. Both are asserted so a
        change to the weighting shows up as a number and not as a vibe.
        """
        rms = lambda a: 20 * np.log10(np.sqrt(np.mean(a.astype(np.float64) ** 2)))
        low, ref = tone(30.0, 3.0), tone(1000.0, 3.0)
        assert rms(low) == pytest.approx(rms(ref), abs=0.1)
        assert sfx.short_term(low)[1].max() < \
            sfx.short_term(ref)[1].max() - 8.0

        impact, hiss = tone(75.0, 3.0), tone(1647.0, 3.0)
        assert rms(impact) == pytest.approx(rms(hiss), abs=0.1)
        gap = sfx.short_term(hiss)[1].max() - sfx.short_term(impact)[1].max()
        assert 3.0 < gap < 6.0, (
            f"{gap:.1f} dB between this film's impact and its brightest "
            f"ambience at equal RMS; the measurement has moved")

    def test_the_window_is_the_momentary_one(self):
        assert sfx.WINDOW_S == pytest.approx(0.400)

    def test_there_is_no_tolerance(self):
        """"Below the bed" is the rule; how far below is not the gate's call."""
        assert sfx.TOLERANCE_DB == 0.0


class TestEvents:
    def test_an_event_under_the_bed_passes(self):
        b = bed()
        d = place(layer(), tone(300.0, 1.5, amp=0.004), 20.0)
        problems, measured = sfx.check(d, b, SR, SPEC)
        assert problems == [], problems
        assert measured["events_checked"] == 1
        assert measured["events_over_the_bed"] == 0

    def test_an_event_over_the_bed_fails_and_names_itself(self):
        b = bed()
        d = place(layer(), tone(300.0, 1.5, amp=0.5), 20.0)
        problems, measured = sfx.check(d, b, SR, SPEC)
        assert problems, "an event at five times the bed's amplitude passed"
        assert "impact at 20.00s" in problems[0]
        assert measured["events_over_the_bed"] == 1
        assert measured["worst_event"]["excess_db"] > 0

    def test_the_window_for_a_riser_sits_before_its_time(self):
        """A riser ENDS on the first word of the line it leads to."""
        rows = sfx.events({"risers": [{"at_seconds": 30.0}], "impacts": [],
                           "stings": []})
        assert rows[0]["to"] <= 30.5 and rows[0]["from"] < 29.0

    def test_and_for_an_impact_it_starts_on_it(self):
        rows = sfx.events({"impacts": [{"at_seconds": 30.0}], "risers": [],
                           "stings": []})
        assert rows[0]["from"] <= 30.0 < rows[0]["to"]

    def test_ambience_and_room_tone_are_not_events(self):
        assert sfx.events(SPEC) == [
            {"kind": "impact", "at_seconds": 20.0, "from": 19.8, "to": 22.0,
             "path": "i.wav"}]


class TestContinuousLayers:
    def test_a_floor_under_the_bed_passes(self):
        b = bed()
        d = layer(amp=0.01)
        problems, measured = sfx.check(d, b, SR, NO_EVENTS)
        assert problems == [], problems
        assert measured["continuous_windows_over_the_bed"] == 0

    def test_a_floor_over_the_bed_fails(self):
        b = bed()
        d = layer(amp=0.3)
        problems, measured = sfx.check(d, b, SR, NO_EVENTS)
        assert problems, "a floor three times the bed's amplitude passed"
        assert measured["continuous_seconds_over_the_bed"] > 1.0
        assert "the room the film is in" in problems[0]

    def test_the_failure_names_the_layer_that_is_playing(self):
        problems, _ = sfx.check(layer(amp=0.3), bed(), SR, NO_EVENTS)
        assert "stone ambience" in problems[0], problems[0]

    def test_an_event_window_is_not_also_reported_as_the_floor(self):
        """One sound, one failure. Not two."""
        b = bed()
        d = place(layer(), tone(300.0, 1.5, amp=0.5), 20.0)
        problems, measured = sfx.check(d, b, SR, SPEC)
        assert measured["continuous_windows_over_the_bed"] == 0, (
            "the impact is being counted as the continuous floor as well")
        assert len(problems) == 1


class TestAHoleInTheBedIsNotTheFloorsFault:
    def _bed_with_a_hole(self, seconds=40.0, at=20.0, width=4.0):
        b = bed(seconds)
        i, j = int(at * SR), int((at + width) * SR)
        b[i:j] *= 0.02          # 34 dB down: the music is gone
        return b

    def test_a_steady_floor_over_a_hole_is_excluded_not_failed(self):
        problems, measured = sfx.check(
            layer(amp=0.005), self._bed_with_a_hole(), SR,
            {"room_tone": {"path": "rt.wav"}, "ambience": [], "impacts": [],
             "stings": [], "risers": []})
        assert problems == [], problems
        assert measured["seconds_excluded_as_a_hole_in_the_bed"] > 1.0

    def test_but_the_exclusion_is_counted_so_it_cannot_hide(self):
        _, measured = sfx.check(
            layer(amp=0.01), self._bed_with_a_hole(width=8.0), SR, None)
        assert measured["seconds_excluded_as_a_hole_in_the_bed"] > 3.0
        assert measured["hole_threshold_lufs"] is not None

    def test_a_long_hole_does_not_define_its_own_floor(self):
        """INJECTED: the percentile version excluded 0.1s of a 20% drop-out.

        A hole across 20% of the runtime puts the bed's 5th percentile INSIDE
        the hole, so almost none of it was recognised as one and the floor was
        blamed for the music being absent. Measured against the MEDIAN, the
        whole hole is seen.
        """
        b = self._bed_with_a_hole(seconds=40.0, at=10.0, width=8.0)
        _, measured = sfx.check(layer(amp=0.01), b, SR, None)
        assert measured["seconds_excluded_as_a_hole_in_the_bed"] > 6.0, (
            measured["seconds_excluded_as_a_hole_in_the_bed"])
        assert measured["hole_below_median_db"] == 6.0

    def test_a_floor_over_a_bed_that_is_present_still_fails(self):
        """The exclusion must not become a general amnesty."""
        problems, _ = sfx.check(layer(amp=0.3), self._bed_with_a_hole(), SR,
                                None)
        assert problems, "the hole exclusion swallowed a genuinely loud floor"


class TestTheOffsetsAndTheGateAreInOneUnit:
    """The table is applied in LUFS because the gate measures in LUFS.

    They were in different units: the playbook stated offsets from the bed and
    `lib/sound_design.py` applied them as broadband RMS, while this gate asks
    the question in K-weighted loudness. On the first run every one of the
    fourteen one-shots came out over the bed while the table said three of
    them were under it.
    """

    def test_sound_design_places_one_shots_by_their_peak(self):
        import inspect

        from lib import sound_design as sd

        src = inspect.getsource(sd.build)
        assert "peak=True" in src, (
            "the playbook keys are named riser_peak / impact_peak / "
            "sting_peak; if they are applied as a whole-file average the "
            "names are a promise the code does not keep")

    def test_and_against_the_bed_in_their_own_moment(self):
        import inspect

        from lib import sound_design as sd

        assert "bed_curve" in inspect.signature(sd.build).parameters
        assert "bed_under(" in inspect.getsource(sd.build)

    def test_the_loudness_helper_measures_peak_or_median_on_request(self):
        from lib import sound_design as sd

        a = np.concatenate([tone(400.0, 2.0, 0.001), tone(400.0, 0.3, 0.5),
                            tone(400.0, 2.0, 0.001)])
        assert sd._loudness(a, peak=True) > sd._loudness(a, peak=False) + 10

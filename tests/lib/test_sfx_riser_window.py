"""THE CONTROL FOR ITEM 8.1: does the riser's reading move when the riser does?

`docs/ITEM_8_HYGIENE.md` recorded the defect. Two full mixes of king-tut
differing ONLY in `riser_peak`, −12 against −14, produced riser rows that
were identical to the decimal — design_lufs −45.2, excess −6.6, both times —
while the build's own placement report showed the riser landing at −52.0 and
−54.0 dB. The gate was reading the summed design layer, in which ambience at
−18 is louder than a riser at −54 for most of a 2.7-second ramp, so `argmax`
found the ambience and reported it as the riser.

"A gate whose number does not move when the thing it names moves is the same
defect as a gate with no consumer — it is just harder to see, because it
prints a plausible figure."

This file is that number, asserted. A 2 dB change to the riser must move the
reported reading by about 2 dB, and the counter-control below is what makes
the assertion mean something: the SAME audio measured the OLD way does not
move at all.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import verify_sfx_level as V  # noqa: E402

SR = 48000
AT = 6.0                     # the riser ends on the word at 6 s
RAMP = 2.7                   # the ramp the old window measured 0.6 s into


def _noise(n: int, seed: int, amp: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(n) * amp).astype(np.float32)


def _scene(riser_gain_db: float) -> dict:
    """A bed, a loud ambience floor, and a riser that ramps into AT.

    The ambience is deliberately LOUDER than the riser, because that is the
    condition under which the defect appeared. A test with a quiet floor
    would pass against the broken gate too.
    """
    n = int(10 * SR)
    bed = _noise(n, 1, 0.20)
    ambience = _noise(n, 2, 0.05)

    ramp_n = int(RAMP * SR)
    shape = np.linspace(0.0, 1.0, ramp_n, dtype=np.float32) ** 2
    riser = _noise(ramp_n, 3, 0.004) * shape * (10 ** (riser_gain_db / 20))

    start = int(AT * SR) - ramp_n
    design = ambience.copy()
    design[start:start + ramp_n] += riser

    stem = {"kind": "riser", "at_seconds": AT, "at_sample": start,
            "target_db": None, "asset": "riser.mp3", "samples": riser}
    spec = {"risers": [{"at_seconds": AT, "path": "riser.mp3"}],
            "ambience": [{"palette": "cave", "act": 1,
                          "start_seconds": 0.0, "end_seconds": 10.0}]}
    return {"design": design, "bed": bed, "spec": spec, "stems": [stem]}


def _riser_row(scene: dict, stems: bool = True) -> dict:
    _, measured = V.check(scene["design"], scene["bed"], SR, scene["spec"],
                          scene["stems"] if stems else None)
    rows = [r for r in measured["events"] if r["kind"] == "riser"]
    assert len(rows) == 1, rows
    return rows[0]


class TestTheReadingMovesWithTheRiser:
    """The control the item was queued for."""

    def test_a_two_decibel_change_moves_the_reading_about_two_decibels(self):
        loud = _riser_row(_scene(0.0))
        quiet = _riser_row(_scene(-2.0))
        delta = loud["design_lufs"] - quiet["design_lufs"]
        assert 1.5 <= delta <= 2.5, (loud["design_lufs"],
                                     quiet["design_lufs"], delta)

    def test_a_six_decibel_change_moves_it_about_six(self):
        """Linear, not merely non-zero: a gate that moved a fixed amount
        for any change would pass the test above."""
        loud = _riser_row(_scene(0.0))
        quiet = _riser_row(_scene(-6.0))
        delta = loud["design_lufs"] - quiet["design_lufs"]
        assert 5.0 <= delta <= 7.0, delta

    def test_the_reading_comes_from_the_stem_and_says_so(self):
        row = _riser_row(_scene(0.0))
        assert row["measured_from"] == "stem"

    def test_it_is_sited_at_the_hit_not_in_the_ramp(self):
        """A riser is loud at its end. The reading must come from there.

        The old window sat 0.6 s into a 2.7 s ramp, roughly 20 dB below the
        riser's own peak.
        """
        row = _riser_row(_scene(0.0))
        assert row["at_measured_seconds"] == pytest.approx(AT, abs=0.5)


class TestTheCounterControl:
    """The old way, on the same audio, to prove the test discriminates.

    Without stems the gate falls back to the loudest window of the SUMMED
    design layer. The ambience is louder than the riser there, so the
    reading is the ambience — and the ambience does not change when the
    riser does. This is the defect, reproduced on demand.
    """

    def test_without_a_stem_the_reading_does_not_move(self):
        loud = _riser_row(_scene(0.0), stems=False)
        quiet = _riser_row(_scene(-6.0), stems=False)
        assert loud["design_lufs"] == quiet["design_lufs"], \
            "the summed-layer fallback moved, so this is no longer a "\
            "counter-control and the test above proves less than it claims"

    def test_and_it_admits_the_number_is_not_the_event(self):
        """The fallback is allowed, but it may not pretend."""
        row = _riser_row(_scene(0.0), stems=False)
        assert "no stem was handed over" in row["measured_from"]
        assert "not necessarily" in row["measured_from"]

    def test_the_fallback_reads_far_louder_than_the_riser(self):
        """The size of the old error, on this scene."""
        with_stem = _riser_row(_scene(0.0))["design_lufs"]
        without = _riser_row(_scene(0.0), stems=False)["design_lufs"]
        assert without > with_stem + 10, (without, with_stem)


class TestTheBedReferenceSpansTheEventItself:
    """Both ends must read the same number, or an offset means nothing.

    `sound_design.build` places an element against the bed's loudest window
    over the ELEMENT'S OWN extent. The gate used a nominal window that for a
    riser ran 0.3 s past the hit, so it could pick up bed the placement
    never saw — and `excess_db` would then not equal the playbook offset,
    which is the bug that once made the layer refuse its own table.
    """

    #: Half a short-term window. A 400 ms window CENTRED on the hit reaches
    #: 200 ms past it, so nothing sited within 200 ms of the hit can be
    #: excluded by any span ending at the hit — and `sound_design`'s
    #: placement, which reads the same curve the same way, straddles
    #: identically. That is agreement, not leakage, and the spike here is
    #: placed clear of it so the test measures the span and not the window.
    HALF_WINDOW = 0.2

    @staticmethod
    def _scene_with_a_spike_after_the_hit() -> dict:
        """A bed spike beginning 0.3 s AFTER the hit.

        Inside the old nominal riser window, which ran to +0.3 s. Outside
        the riser's own extent, which ends on the hit, by more than half a
        short-term window. The fixed gate must not see it.
        """
        scene = _scene(0.0)
        bed = scene["bed"]
        a = int((AT + 0.3) * SR)
        bed[a:a + int(0.4 * SR)] *= 8.0
        scene["bed"] = bed
        return scene

    def test_the_spike_is_clear_of_the_straddle(self):
        """The geometry this class depends on, asserted rather than assumed."""
        assert 0.3 > self.HALF_WINDOW
        assert V.WINDOW_S / 2 == pytest.approx(self.HALF_WINDOW)

    def test_a_bed_spike_past_the_hit_is_not_the_riser_s_reference(self):
        plain = _riser_row(_scene(0.0))
        spiked = _riser_row(self._scene_with_a_spike_after_the_hit())
        assert spiked["bed_lufs"] == pytest.approx(plain["bed_lufs"], abs=0.2)

    def test_and_the_old_nominal_window_did_see_it(self):
        """The counter-control: without a stem the extent is still a guess."""
        plain = _riser_row(_scene(0.0), stems=False)
        spiked = _riser_row(self._scene_with_a_spike_after_the_hit(),
                            stems=False)
        assert spiked["bed_lufs"] > plain["bed_lufs"] + 3, \
            (spiked["bed_lufs"], plain["bed_lufs"])

    def test_the_reference_time_falls_inside_the_riser(self):
        row = _riser_row(self._scene_with_a_spike_after_the_hit())
        assert row["from"] <= AT
        assert row["bed_lufs"] > V.FLOOR_LUFS


class TestNewReportsCarryTheChange:
    """The item's own ruling: correct the NEW report, never the old one."""

    def test_the_note_is_in_the_measurements(self):
        _, measured = V.check(_scene(0.0)["design"], _scene(0.0)["bed"], SR,
                              _scene(0.0)["spec"], _scene(0.0)["stems"])
        note = measured["measurement_window_changed"]
        assert note["date"] == "2026-11-10"
        for key in ("events", "level", "why"):
            assert len(note[key]) > 30, key

    def test_it_names_the_control_that_proves_it(self):
        note = V.MEASUREMENT_WINDOW_CHANGED
        assert "test_sfx_riser_window.py" in note["why"]
        assert "2 dB" in note["why"]

    def test_the_four_delivered_reports_are_untouched(self):
        """Ruled 2026-11-09. Their −6.6 dB riser figures stay.

        They are what the gate measured on the day. A report edited after
        the fact is no longer a record of its run.
        """
        import json
        for film in ("noah", "easter-island",
                     "they-said-it-couldnt-be-built"):
            path = (ROOT / "projects" / film / "renders" / "mix_report.json")
            if not path.exists():
                continue
            report = json.loads(path.read_text())
            blob = json.dumps(report)
            assert "measurement_window_changed" not in blob, film

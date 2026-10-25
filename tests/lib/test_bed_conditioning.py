"""A music bed has to hold still, and three different things stop it.

1. WHERE IT IS TAKEN FROM. `build_bed` took the middle of a track, with the
   comment "take from the middle". On this film the middle was the worst
   available choice: `Spooked` fades out over its last thirty seconds, and the
   middle of a 321-second window inside a 353-second track puts the window's
   tail inside that fade. Measured, the middle gave an 18.7 dB hole and the
   head of the track gave 6.3 dB — and the hole landed on the act 2 boundary,
   where the sting is.

2. HOW MUCH IT MOVES. A 2:1 compressor, with the threshold solved from the
   material rather than typed in.

3. HOW IT IS MEASURED. EBU LRA is the metric the owner named and it cannot
   see a hole: it is the 10th-to-95th percentile above a relative gate, so a
   bed can read 5.7 LU of LRA with a 13 dB drop-out in it. Both were true of
   this film's act 2/3 bed. The gate is the 5th-to-95th spread, which does.
"""
from __future__ import annotations

import subprocess

import numpy as np
import pytest

from lib import mix_audio as mx

SR = mx.SR


#: Seeded, so the fixtures are the same bed every run. An unseeded
#: `anoisesrc` made the margin in `test_the_middle_really_is_worse_on_that_track`
#: flaky: the defect was reproduced every time, by 2.7 to 4 dB depending on
#: the draw.
SEED = 20261025


def wav(path, filt: str, seconds: float = 60.0) -> str:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"anoisesrc=d={seconds}:c=pink:r={SR}:seed={SEED}",
                    "-af", f"lowpass=f=900,{filt}",
                    "-ar", str(SR), "-ac", "2", str(path)], check=True)
    return str(path)


def steady(path, seconds: float = 60.0) -> str:
    return wav(path, "volume=1.0", seconds)


def with_a_fadeout(path, seconds: float = 60.0, fade: float = 15.0) -> str:
    return wav(path, f"afade=t=out:st={seconds - fade}:d={fade}", seconds)


class TestWhereTheBedIsTakenFrom:
    def test_it_avoids_a_fade_out_the_middle_would_have_caught(self, tmp_path):
        track = with_a_fadeout(tmp_path / "f.wav", seconds=60.0, fade=15.0)
        need, src_dur = 40.0, 60.0
        start, report = mx.steadiest_window(track, need, src_dur, step=2.0)
        middle = (src_dur - need) / 2
        assert report["searched"] > 1
        assert start < middle, (
            f"it chose {start:.1f}s; the middle is {middle:.1f}s and the "
            f"track fades out from 45s, so earlier is the right answer")
        assert report["hole_db"] < 6.0, report

    def test_the_middle_really_is_worse_on_that_track(self, tmp_path):
        """INJECTED: score the middle and the chosen window the same way."""
        from verify_sfx_level import short_term

        track = with_a_fadeout(tmp_path / "f.wav", seconds=60.0, fade=25.0)
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", track, "-f", "f32le",
             "-acodec", "pcm_f32le", "-ac", "2", "-ar", str(SR), "-"],
            capture_output=True, check=True).stdout
        y = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
        times, st = short_term(y, SR)
        hop = times[1] - times[0]

        def hole(start_s):
            seg = st[int(start_s / hop):int((start_s + 40.0) / hop)]
            live = seg[seg > -70.0]
            return float(np.median(live) - live.min())

        chosen, _ = mx.steadiest_window(track, 40.0, 60.0, step=2.0)
        assert hole(10.0) > hole(chosen) + 3.0, (  # 25s fade: the gap is ~9 dB
            "the fixture does not reproduce the defect: the middle is no "
            "worse than the chosen window")

    def test_a_track_with_no_slack_is_not_searched(self, tmp_path):
        track = steady(tmp_path / "s.wav", seconds=41.0)
        start, report = mx.steadiest_window(track, 40.0, 41.0, step=5.0)
        assert report["searched"] == 0
        assert start == pytest.approx(0.5, abs=0.01)

    def test_it_never_runs_off_the_end_of_the_track(self, tmp_path):
        track = steady(tmp_path / "s.wav", seconds=60.0)
        start, _ = mx.steadiest_window(track, 40.0, 60.0, step=2.0)
        assert 0.0 <= start <= 20.0


class TestHowMuchItMoves:
    def _hole(self, path, seconds=60.0, at=30.0, depth_db=14.0, width=3.0):
        """A bed with a measured hole punched in it."""
        g = 10 ** (-depth_db / 20)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", f"anoisesrc=d={seconds}:c=pink:r={SR}:seed={SEED}", "-af",
             f"lowpass=f=900,volume=enable='between(t,{at},{at + width})':"
             f"volume={g:.6f}:eval=frame",
             "-ar", str(SR), "-ac", "2", str(path)], check=True)
        return str(path)

    def test_lra_does_not_see_a_hole(self, tmp_path):
        """The reason the gate is not LRA. This is the whole argument."""
        path = self._hole(tmp_path / "h.wav")
        dyn = mx.internal_dynamics(path)
        assert dyn["hole_db"] > 10.0, dyn
        assert dyn["lra_lu"] is not None and dyn["lra_lu"] < 6.0, (
            f"LRA reads {dyn['lra_lu']} on a bed with a "
            f"{dyn['hole_db']:.1f} dB hole — that is the point of the "
            f"second measurement, and if LRA ever catches it this test "
            f"should be revisited rather than deleted")

    def test_the_spread_does_see_it(self, tmp_path):
        path = self._hole(tmp_path / "h.wav", depth_db=20.0, width=8.0)
        dyn = mx.internal_dynamics(path)
        assert dyn["spread_5_95_lu"] > mx.BED_DYNAMICS_MAX_LU, dyn

    def test_a_steady_bed_measures_steady(self, tmp_path):
        dyn = mx.internal_dynamics(steady(tmp_path / "s.wav"))
        assert dyn["spread_5_95_lu"] < mx.BED_DYNAMICS_MAX_LU, dyn
        assert dyn["hole_db"] < mx.BED_HOLE_MAX_DB, dyn

    def test_the_compressor_closes_what_it_can_and_records_the_passes(self, tmp_path):
        src = self._hole(tmp_path / "h.wav", depth_db=16.0, width=10.0)
        dst = str(tmp_path / "cond.wav")
        before = mx.internal_dynamics(src)
        mx.OUT = str(tmp_path)
        rep = mx.condition_bed(src, dst, "t", -33.0)
        assert rep["spread_5_95_lu"] < before["spread_5_95_lu"], (before, rep)
        assert rep["compressor_passes"] >= 1
        assert rep["compressor_threshold_db"] <= (before["lufs"] or 0) + 0.1 \
            if "lufs" in before else True

    def test_conditioning_lands_the_bed_on_its_level(self, tmp_path):
        mx.OUT = str(tmp_path)
        dst = str(tmp_path / "cond.wav")
        mx.condition_bed(steady(tmp_path / "s.wav"), dst, "t", -33.0)
        assert mx.measure(dst)["lufs"] == pytest.approx(-33.0, abs=1.0)


class TestTheCeilingsAreWhatTheOwnerAskedFor:
    def test_six_lu_per_bed(self):
        assert mx.BED_DYNAMICS_MAX_LU == 6.0
        assert mx.BED_LRA_MAX_LU == 6.0

    def test_one_and_a_half_lu_between_beds(self):
        assert mx.BED_SPREAD_MAX_LU == 1.5

    def test_two_to_one_and_gentle(self):
        assert mx.BED_COMPRESSOR_RATIO == 2.0

    def test_the_crossfade_is_equal_power_not_linear(self):
        """`tri` costs 3 dB at every boundary — where the stings are."""
        assert mx.XFADE_CURVE == "qsin"


class TestTheSpreadBetweenBeds:
    def test_beds_at_one_level_measure_no_spread(self, tmp_path):
        mx.OUT = str(tmp_path)
        joined = str(tmp_path / "bed.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                        "-i", f"anoisesrc=d=120:c=pink:r={SR}:seed={SEED}",
                        "-af", "lowpass=f=900", "-ar", str(SR), "-ac", "2",
                        joined], check=True)
        spans = [{"name": "a", "start": 0.0, "end": 60.0},
                 {"name": "b", "start": 60.0, "end": 120.0}]
        spread, per = mx.bed_spread(joined, spans, 2.5)
        assert spread is not None and spread < mx.BED_SPREAD_MAX_LU, per

    def test_beds_at_two_levels_are_caught(self, tmp_path):
        """INJECTED: the second half 4 dB down."""
        mx.OUT = str(tmp_path)
        joined = str(tmp_path / "bed.wav")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", f"anoisesrc=d=120:c=pink:r={SR}:seed={SEED}", "-af",
             "lowpass=f=900,volume=enable='gte(t,60)':volume=0.4:eval=frame",
             "-ar", str(SR), "-ac", "2", joined], check=True)
        spans = [{"name": "a", "start": 0.0, "end": 60.0},
                 {"name": "b", "start": 60.0, "end": 120.0}]
        spread, per = mx.bed_spread(joined, spans, 2.5)
        assert spread > mx.BED_SPREAD_MAX_LU, per

    def test_a_boundary_is_not_measured_as_either_side_of_it(self, tmp_path):
        """The crossfade is trimmed off each span before it is measured."""
        import inspect

        src = inspect.getsource(mx.bed_spread)
        assert "+ crossfade" in src and "- crossfade" in src


class TestTheCrossfadeCurve:
    """`tri` is linear in amplitude, which costs 3 dB on uncorrelated beds.

    At the centre of a `tri` fade both sides sit at 0.5, and two uncorrelated
    signals at 0.5 sum to 0.707 rather than to 1.0. There is one of these at
    every act boundary where two beds meet — which is also where the envelope
    lifts the bed to its loudest level and where the sting lands.

    `qsin` is a quarter-sine fade, which is constant POWER for uncorrelated
    material. The numbers below are the measurement that chose it, pinned so
    that a change to either curve shows up here.
    """

    def _joined(self, tmp_path, curve: str) -> str:
        a, b = tmp_path / "a.wav", tmp_path / "b.wav"
        for path, seed in ((a, 1), (b, 99)):
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                 "-i", f"anoisesrc=d=20:c=pink:r={SR}:seed={seed}",
                 "-af", "lowpass=f=900", "-ar", str(SR), "-ac", "2",
                 str(path)], check=True)
        out = tmp_path / f"x_{curve}.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(a), "-i", str(b),
             "-filter_complex",
             f"[0:a][1:a]acrossfade=d=2.5:c1={curve}:c2={curve}[o]",
             "-map", "[o]", "-ar", str(SR), "-ac", "2", str(out)], check=True)
        return str(out)

    def _dip(self, path: str) -> float:
        import soundfile as sf

        from verify_sfx_level import short_term

        y, sr = sf.read(path, dtype="float32", always_2d=True)
        t, b = short_term(y, sr)
        centre = 20.0 - 1.25            # the fade is centred on the join
        i = int(np.argmin(np.abs(t - centre)))
        steady = float(np.median(b[(t > 3) & (t < 14)]))
        return float(b[i]) - steady

    def test_tri_costs_about_three_decibels(self, tmp_path):
        dip = self._dip(self._joined(tmp_path, "tri"))
        assert -3.6 < dip < -2.2, f"{dip:.2f} dB"

    def test_qsin_costs_nothing(self, tmp_path):
        dip = self._dip(self._joined(tmp_path, "qsin"))
        assert abs(dip) < 0.6, f"{dip:.2f} dB"

    def test_and_the_mixer_uses_qsin_for_both_kinds_of_join(self, tmp_path):
        import inspect

        src = inspect.getsource(mx.build_bed)
        assert "c1=tri" not in src
        assert src.count("XFADE_CURVE") >= 4, (
            "both the loop joins and the span joins take the curve from the "
            "one constant")

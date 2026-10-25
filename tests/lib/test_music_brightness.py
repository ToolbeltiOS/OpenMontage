"""A bed can meet every movement criterion and still be too bright to use.

The three criteria already in the playbook — melodic movement, build, and
rhythmic periodicity — are all about movement over time. None of them says
anything about timbre, so a sustained, unmoving, quiet pad made entirely of
high content passes all three. The fixtures here are synthesised so the answer
is known: pink noise low-passed hard is dark, the same noise high-passed is
bright, and a sine at 300 Hz is darker than a sine at 6 kHz.

THE TEST THAT MATTERS MOST is the vacuous-gate test. The bed EQ low-passes at
5 kHz, so the same measurement taken AFTER the EQ reads a fraction of a
percent on a track made of nothing but hiss. If anybody ever moves the gate
downstream of the EQ to make it tidier, that test fails and says why.
"""
from __future__ import annotations

import subprocess

import pytest

from lib import music_brightness as mb


def tone(path, filt: str, seconds: float = 8.0) -> str:
    """Pink noise through a filter chain, written as a wav."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"anoisesrc=d={seconds}:c=pink:r=22050",
                    "-af", filt, "-ar", "22050", "-ac", "1", str(path)],
                   check=True)
    return str(path)


def sine(path, hz: float, seconds: float = 8.0) -> str:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"sine=frequency={hz}:duration={seconds}:sample_rate=22050",
                    "-ar", "22050", "-ac", "1", str(path)], check=True)
    return str(path)


class TestTheMeasurement:
    def test_a_dark_bed_measures_dark(self, tmp_path):
        row = mb.brightness(tone(tmp_path / "dark.wav", "lowpass=f=500"))
        assert row["energy_above_4k_pct"] < 1.0, row
        assert row["spectral_centroid_hz"] < 1000, row

    def test_a_bright_bed_measures_bright(self, tmp_path):
        row = mb.brightness(tone(tmp_path / "bright.wav", "highpass=f=5000"))
        assert row["energy_above_4k_pct"] > mb.MAX_ENERGY_ABOVE_4K_PCT, row

    def test_the_centroid_follows_the_pitch(self, tmp_path):
        low = mb.brightness(sine(tmp_path / "lo.wav", 300))
        high = mb.brightness(sine(tmp_path / "hi.wav", 6000))
        assert low["spectral_centroid_hz"] < 500 < high["spectral_centroid_hz"]
        assert high["spectral_centroid_hz"] > 5000

    def test_it_is_the_whole_track_not_one_second(self, tmp_path):
        """Half dark, half bright averages between the two."""
        dark = tone(tmp_path / "d.wav", "lowpass=f=400", seconds=6)
        bright = tone(tmp_path / "b.wav", "highpass=f=6000", seconds=6)
        joined = tmp_path / "j.wav"
        lst = tmp_path / "l.txt"
        lst.write_text(f"file '{dark}'\nfile '{bright}'\n")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat",
                        "-safe", "0", "-i", str(lst), str(joined)], check=True)
        both = mb.brightness(str(joined))
        only_bright = mb.brightness(bright)
        assert 0 < both["energy_above_4k_pct"] < only_bright["energy_above_4k_pct"]


class TestTheGate:
    def _beds(self, *paths):
        return [{"name": f"b{i}", "path": p} for i, p in enumerate(paths)]

    def test_a_dark_bed_passes(self, tmp_path):
        problems, measured = mb.check(
            self._beds(tone(tmp_path / "d.wav", "lowpass=f=600")))
        assert problems == [], problems
        assert measured["worst_pct"] <= mb.MAX_ENERGY_ABOVE_4K_PCT

    def test_a_bright_bed_is_refused_and_told_why(self, tmp_path):
        problems, _ = mb.check(
            self._beds(tone(tmp_path / "b.wav", "highpass=f=5000")))
        assert problems, "a bed of pure hiss was accepted"
        assert "above 4 kHz" in problems[0]
        assert "consonant band" in problems[0], (
            "the failure has to say why it matters, not just that it failed")

    def test_the_report_carries_the_after_eq_figure_too(self, tmp_path):
        _, measured = mb.check(
            self._beds(tone(tmp_path / "d.wav", "lowpass=f=600")))
        assert "after_eq" in measured["beds"][0]


class TestWhyTheGateRunsBeforeTheEq:
    """A gate after the bed EQ certifies the EQ, not the bed.

    MEASURED, and the first version of this docstring was wrong. The claim was
    that the EQ would make anything pass; it does not — pink noise high-passed
    at 5 kHz still reads 38% above 4 kHz after the EQ, because the figure is a
    RATIO and what survives the low-pass is concentrated just under it.

    What the EQ does is divide the ratio by about eight, which is enough to
    move a realistically bad bed across the line: a pad with moderate hiss
    over it reads 65% before the EQ and 8% after. That is the bed somebody
    would actually choose and the gate would actually have to catch, and after
    the EQ it would be certified clean.
    """

    def _pad_with_hiss(self, tmp_path, gain_db):
        return tone(tmp_path / f"hiss{gain_db}.wav",
                    f"highshelf=f=4000:g={gain_db}")

    def test_a_pad_with_hiss_fails_before_the_eq(self, tmp_path):
        pre = mb.brightness(self._pad_with_hiss(tmp_path, 16))
        assert pre["energy_above_4k_pct"] > mb.MAX_ENERGY_ABOVE_4K_PCT, pre

    def test_and_the_same_bed_passes_after_it(self, tmp_path):
        """This is the forgiving verdict the gate must not be allowed to give."""
        post = mb.brightness(self._pad_with_hiss(tmp_path, 16), mb.BED_EQ)
        assert post["energy_above_4k_pct"] <= mb.MAX_ENERGY_ABOVE_4K_PCT, post

    def test_the_eq_divides_the_ratio_by_roughly_eight(self, tmp_path):
        bed = self._pad_with_hiss(tmp_path, 16)
        pre = mb.brightness(bed)["energy_above_4k_pct"]
        post = mb.brightness(bed, mb.BED_EQ)["energy_above_4k_pct"]
        assert 4 < pre / max(post, 0.01) < 20, (pre, post)

    def test_pure_hiss_fails_either_way_which_is_the_eqs_limit(self, tmp_path):
        """The EQ cannot rescue a bed with no body; it only makes it quiet."""
        hiss = tone(tmp_path / "pure.wav", "highpass=f=5000")
        assert mb.brightness(hiss)["energy_above_4k_pct"] > \
            mb.MAX_ENERGY_ABOVE_4K_PCT
        assert mb.brightness(hiss, mb.BED_EQ)["energy_above_4k_pct"] > \
            mb.MAX_ENERGY_ABOVE_4K_PCT


class TestTheEqIsAShelfNotABell:
    """-6 dB from 3.5 kHz means everything above it, not one band of it."""

    def test_the_chain_names_a_high_shelf(self):
        assert "highshelf=f=3500" in mb.BED_EQ
        assert "equalizer=f=3500" not in mb.BED_EQ

    def test_and_low_passes_at_five_not_seven(self):
        assert "lowpass=f=5000" in mb.BED_EQ
        assert "lowpass=f=7000" not in mb.BED_EQ

    def test_the_shelf_actually_attenuates_above_its_corner(self, tmp_path):
        flat = tone(tmp_path / "f.wav", "anull")
        before = mb.brightness(flat)
        after = mb.brightness(flat, mb.BED_EQ)
        assert after["spectral_centroid_hz"] < before["spectral_centroid_hz"]


class TestRanking:
    def test_softest_puts_the_darkest_first(self):
        rows = [{"energy_above_4k_pct": 5.0, "spectral_centroid_hz": 900},
                {"energy_above_4k_pct": 0.1, "spectral_centroid_hz": 240},
                {"energy_above_4k_pct": 0.1, "spectral_centroid_hz": 520}]
        order = mb.softest(rows)
        assert order[0]["spectral_centroid_hz"] == 240
        assert order[1]["spectral_centroid_hz"] == 520
        assert order[-1]["energy_above_4k_pct"] == 5.0

    def test_the_centroid_breaks_a_tie(self):
        """Two beds can share a high-band share and not sit in one place."""
        rows = [{"energy_above_4k_pct": 0.1, "spectral_centroid_hz": 700},
                {"energy_above_4k_pct": 0.1, "spectral_centroid_hz": 200}]
        assert mb.softest(rows)[0]["spectral_centroid_hz"] == 200

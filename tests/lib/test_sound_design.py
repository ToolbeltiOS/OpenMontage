"""The sound-design layer: levels follow the bed, and a missing sound is loud.

The two failure modes worth pinning:

- a level written as an absolute would be wrong the moment the music bed moves,
  and the bed is about to be auditioned at three settings;
- an asset that is not on disk becoming silence, which in a mix report is
  indistinguishable from never having asked for it.
"""
from __future__ import annotations

import json
import subprocess

import numpy as np
import pytest
import yaml

from lib import sound_design

PLAYBOOK = yaml.safe_load(open("styles/wak3up-documentary.yaml", encoding="utf-8"))


@pytest.fixture
def tone(tmp_path):
    """A one-second tone, written as a real file so ffmpeg decodes it."""
    path = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=220:duration=1", "-ar", "48000", "-ac", "1",
         str(path)], check=True)
    return path


def entry(path, **kw):
    return {"path": str(path), "provider": "test", "url": "https://example.test/x",
            "licence": "CC0", **kw}


class TestLevels:
    def test_every_level_follows_the_music_bed(self, tone):
        """The same spec at two bed levels produces two layers 6 dB apart."""
        spec = {"room_tone": entry(tone)}
        quiet, _ = sound_design.build(spec, 4.0, -42.0, PLAYBOOK, "")
        loud, _ = sound_design.build(spec, 4.0, -36.0, PLAYBOOK, "")
        delta = sound_design._rms_db(loud) - sound_design._rms_db(quiet)
        assert delta == pytest.approx(6.0, abs=0.2)

    def test_room_tone_sits_the_playbook_offset_under_the_bed(self, tone):
        """IN LUFS, which is a change: it used to be asserted in RMS.

        The offsets are applied as K-weighted loudness since 2026-10-25,
        because that is the unit the gate in `lib/verify_sfx_level.py`
        measures in and an offset table in one unit cannot be checked by a
        ceiling in another. This tone lands at -47.1 dB RMS and -48.0 LUFS —
        a decibel apart on a 220 Hz tone, and several on the film's real
        elements, which is the whole reason the unit matters.
        """
        off = PLAYBOOK["audio"]["sound_design"]["levels_relative_to_music_bed_db"]
        layer, report = sound_design.build(
            {"room_tone": entry(tone)}, 4.0, -36.0, PLAYBOOK, "")
        want = -36 + off["room_tone"]
        assert sound_design._loudness(layer, peak=False) == \
            pytest.approx(want, abs=0.3)
        assert report["elements"][0]["licence"] == "CC0"
        assert report["unit"].startswith("LUFS")

    def test_the_two_units_are_not_interchangeable(self, tone):
        """So that nobody reverts the assertion above as a rounding fix."""
        layer, _ = sound_design.build(
            {"room_tone": entry(tone)}, 4.0, -36.0, PLAYBOOK, "")
        rms = sound_design._rms_db(layer)
        lufs = sound_design._loudness(layer, peak=False)
        assert abs(rms - lufs) > 0.5, (rms, lufs)

    def test_a_one_shot_is_placed_by_its_peak_not_its_average(self, tone):
        """`impact_peak` is a promise about the loudest moment."""
        off = PLAYBOOK["audio"]["sound_design"]["levels_relative_to_music_bed_db"]
        layer, _ = sound_design.build(
            {"impacts": [dict(entry(tone), at_seconds=2.0)]},
            6.0, -36.0, PLAYBOOK, "")
        want = -36 + off["impact_peak"]
        assert sound_design._loudness(layer, peak=True) == \
            pytest.approx(want, abs=0.5)

    def test_a_riser_ends_on_the_word_it_leads_to(self, tone):
        """It leads INTO the landing line; it must not cross it."""
        layer, _ = sound_design.build(
            {"risers": [dict(entry(tone), at_seconds=3.0, seconds=1.0)]},
            6.0, -36.0, PLAYBOOK, "")
        after = layer[int(3.05 * sound_design.SR):]
        assert np.max(np.abs(after)) < 1e-6
        before = layer[int(2.2 * sound_design.SR):int(2.95 * sound_design.SR)]
        assert np.max(np.abs(before)) > 1e-4

    def test_a_riser_longer_than_the_cap_is_trimmed_from_its_head(self, tone):
        cap = PLAYBOOK["audio"]["sound_design"]["riser"]["max_seconds"]
        layer, _ = sound_design.build(
            {"risers": [dict(entry(tone), at_seconds=5.0, seconds=1.0)]},
            8.0, -36.0, PLAYBOOK, "")
        sounding = np.flatnonzero(np.abs(layer) > 1e-5)
        assert (sounding[-1] - sounding[0]) / sound_design.SR <= cap + 0.05

    def test_ambience_only_covers_its_own_act(self, tone):
        layer, _ = sound_design.build(
            {"ambience": [dict(entry(tone), act=2, palette="wind",
                               start_seconds=4.0, end_seconds=8.0)]},
            12.0, -36.0, PLAYBOOK, "")
        assert np.max(np.abs(layer[:int(3.5 * sound_design.SR)])) < 1e-6
        assert np.max(np.abs(layer[int(5 * sound_design.SR):int(7 * sound_design.SR)])) > 1e-5
        assert np.max(np.abs(layer[int(9 * sound_design.SR):])) < 1e-6


class TestItRefusesToBeQuietlyWrong:
    def test_a_missing_asset_raises_rather_than_becoming_silence(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="missing"):
            sound_design.build({"room_tone": entry(tmp_path / "nope.wav")},
                               2.0, -36.0, PLAYBOOK, "")

    def test_a_sound_without_a_licence_is_rejected(self, tone):
        spec = {"room_tone": {"path": str(tone), "provider": "test",
                              "url": "https://example.test/x"}}
        problems = sound_design.check_spec(spec, PLAYBOOK)
        assert any("licence" in p for p in problems)

    def test_no_room_tone_is_rejected(self):
        problems = sound_design.check_spec({"ambience": []}, PLAYBOOK)
        assert any("room tone" in p for p in problems)

    def test_three_impacts_in_one_act_is_rejected(self, tone):
        spec = {
            "room_tone": entry("x"),
            "ambience": [dict(entry("a"), act=1, palette="wind"),
                         dict(entry("b"), act=2, palette="sea")],
            "impacts": [dict(entry("i"), act=1, at_seconds=t) for t in (10, 20, 30)],
        }
        problems = sound_design.check_spec(spec, PLAYBOOK)
        assert any("three is a trailer" in p for p in problems)

    def test_an_unknown_ambience_palette_is_rejected(self):
        spec = {"room_tone": entry("x"),
                "ambience": [dict(entry("a"), act=1, palette="forest"),
                             dict(entry("b"), act=2, palette="sea")]}
        problems = sound_design.check_spec(spec, PLAYBOOK)
        assert any("palette" in p for p in problems)


class TestLooping:
    def test_a_short_bed_turns_over_rather_than_restarting(self, tone):
        """A hard loop point reads as the sound starting again."""
        a = sound_design._read(str(tone))
        out = sound_design._fit(a, len(a) * 3, crossfade_s=0.25)
        assert len(out) == len(a) * 3
        seam = int(0.95 * len(a))
        window = out[seam - 2000:seam + 2000]
        assert np.max(np.abs(np.diff(window))) < 0.5


class TestAnAmbienceBedHasToHoldStill:
    """An ambience is a bed, and the same argument applies as to the music.

    `ambience_stone.mp3` peaks 17.0 dB over its own median and
    `ambience_sea.mp3` 11.8 dB. Placed by their median, as the playbook's
    offset asks, their PEAKS poke through the music — which is what the owner
    heard as the floor being a layer of its own rather than the room the film
    is in.

    THE DEFECT THIS CLASS EXISTS FOR is the version that solved the gain curve
    once and reported the limit it was asked for rather than the one it
    reached: asking for 3 dB in a single pass delivered 3.5 to 6.9 dB across
    this film's five ambience beds, and the worst of them then failed the SFX
    gate by 1.2 dB. A function that reports a limit it did not reach is worse
    than one that reports the number it got.
    """

    def _peaky(self, tmp_path, crest_db=14.0):
        """A steady bed with a loud passage in it, by a known amount."""
        path = tmp_path / "peaky.wav"
        g = 10 ** (crest_db / 20)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", f"anoisesrc=d=40:c=pink:r={sound_design.SR}:seed=7", "-af",
             f"lowpass=f=900,volume=enable='between(t,20,24)':"
             f"volume={g:.6f}:eval=frame",
             "-ar", str(sound_design.SR), "-ac", "1", str(path)], check=True)
        return sound_design._read(str(path))

    def test_a_peaky_bed_is_held_inside_the_limit(self, tmp_path):
        held, rep = sound_design._hold_still(self._peaky(tmp_path))
        assert rep["crest_db"] > 10.0, rep
        assert rep["inside_the_limit"], rep
        assert rep["crest_after_db"] <= \
            sound_design.CONTINUOUS_CREST_MAX_DB + 0.1, rep

    def test_one_pass_is_not_enough_which_is_why_it_iterates(self, tmp_path):
        """INJECTED: the single-pass version, reconstructed."""
        import numpy as np

        a = self._peaky(tmp_path)
        _, st = sound_design.short_term_of(a)
        live = st[st > -70.0]
        median = float(np.median(live))
        crest = float(live.max() - median)
        limit = sound_design.CONTINUOUS_CREST_MAX_DB
        k = 1.0 - limit / crest
        gain = np.where(st > median, -(st - median) * k, 0.0)
        hop = max(1, len(a) // max(len(gain), 1))
        g = np.repeat(gain.astype(np.float32), hop)
        g = np.pad(g, (0, max(0, len(a) - len(g))), mode="edge")[:len(a)]
        once = (a * (10 ** (g / 20))).astype(np.float32)
        _, st2 = sound_design.short_term_of(once)
        live2 = st2[st2 > -70.0]
        after_once = float(live2.max() - np.median(live2))
        assert after_once > limit + 0.3, (
            f"one pass reached {after_once:.1f} dB against a {limit} dB "
            f"limit; if it ever lands inside, the iteration is no longer "
            f"load-bearing and this test should be revisited, not deleted")

        _, rep = sound_design._hold_still(a)
        assert rep["crest_after_db"] < after_once

    def test_a_bed_already_inside_the_limit_is_not_touched(self, tmp_path):
        import numpy as np

        a = self._peaky(tmp_path, crest_db=0.0)
        held, rep = sound_design._hold_still(a)
        assert rep["passes"] == 0
        assert np.array_equal(held, a)

    def test_the_report_carries_the_number_it_reached(self, tmp_path):
        _, rep = sound_design._hold_still(self._peaky(tmp_path))
        assert set(rep) >= {"crest_db", "crest_after_db", "passes",
                            "inside_the_limit", "limit_db"}

    def test_the_crest_limit_is_tighter_than_the_music_beds(self):
        """The bed may sit 3 dB under its median legitimately; the floor cannot
        be allowed 6 dB over its own or it would be level with the music."""
        from lib import mix_audio as mx

        assert sound_design.CONTINUOUS_CREST_MAX_DB < mx.BED_DYNAMICS_MAX_LU

    def test_the_loop_stops_on_its_own_condition_not_on_the_cap(self, tmp_path):
        """The cap must not be load-bearing.

        It was: the loop converges on the limit from above, so a break on
        `crest <= limit` exactly never fired and all five of this film's
        ambience beds burned every available pass to land on 3.0 dB. An asset
        slightly worse than the worst one here would then have fallen out of
        the loop still outside its limit.
        """
        _, rep = sound_design._hold_still(self._peaky(tmp_path, crest_db=17.0))
        assert rep["inside_the_limit"], rep
        assert rep["passes"] < rep["passes_available"], (
            f"{rep['passes']} of {rep['passes_available']} passes — the cap "
            f"is what stopped the loop, not the limit")

    def test_a_bed_that_cannot_be_held_refuses_the_mix(self, tmp_path, tone):
        """Rather than reporting a limit it did not reach."""
        import pytest as _pytest

        a = self._peaky(tmp_path, crest_db=14.0)
        _, rep = sound_design._hold_still(a, limit_db=0.0001)
        assert rep["inside_the_limit"] is False, rep

        src = __import__("inspect").getsource(sound_design.build)
        assert "could not be held" in src
        assert "raise SystemExit" in src

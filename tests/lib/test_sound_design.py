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
        off = PLAYBOOK["audio"]["sound_design"]["levels_relative_to_music_bed_db"]
        layer, report = sound_design.build(
            {"room_tone": entry(tone)}, 4.0, -36.0, PLAYBOOK, "")
        assert sound_design._rms_db(layer) == pytest.approx(-36 + off["room_tone"], abs=0.2)
        assert report["elements"][0]["licence"] == "CC0"

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

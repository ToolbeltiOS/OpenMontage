"""Every shipped style playbook must actually load.

`list_playbooks()` advertises a playbook as selectable, `pipeline_defs/*.yaml`
offer them by name, and `lib.checkpoint._validate_style_playbook` fails closed
on anything `load_playbook()` rejects. So a playbook that is listed but does not
validate is not a cosmetic problem — it blocks `init_project()`/`write_checkpoint()`
outright, taking the whole pipeline down for that style.

These tests iterate the catalog rather than a hardcoded list, which is how
`anime-ghibli` and `premium-minimalist` slipped through: the pre-existing
coverage in tests/qa/test_07_playbook_intelligence.py names three playbooks
that were the only ones in the repo when it was written.
"""

import pytest

from lib.checkpoint import init_project
from styles.playbook_loader import list_playbooks, load_playbook

PLAYBOOK_NAMES = sorted(list_playbooks())

# The overlay types remotion-composer actually renders, from the `Overlay`
# union in remotion-composer/src/Explainer.tsx. A playbook must be able to
# style any of them.
RENDERER_OVERLAY_TYPES = (
    "section_title",
    "stat_reveal",
    "hero_title",
    "provider_chip",
)


def test_catalog_is_not_empty() -> None:
    assert PLAYBOOK_NAMES, "list_playbooks() found no playbooks at all"


@pytest.mark.parametrize("name", PLAYBOOK_NAMES)
def test_listed_playbook_loads_and_validates(name: str) -> None:
    """A playbook offered by the catalog must pass its own schema."""
    playbook = load_playbook(name)
    assert playbook["identity"]["name"]


@pytest.mark.parametrize("name", PLAYBOOK_NAMES)
def test_listed_playbook_is_accepted_by_init_project(name: str, tmp_path) -> None:
    """The checkpoint writer validates style_playbook fail-closed.

    Regression: `anime-ghibli` was listed and offered by pipeline_defs/animation.yaml
    but raised CheckpointValidationError here, so no run using that style could
    write a checkpoint.
    """
    init_project(
        f"catalog-{name}",
        title="Catalog probe",
        pipeline_type="animation",
        pipeline_dir=tmp_path,
        style_playbook=name,
    )


@pytest.mark.parametrize("overlay_type", RENDERER_OVERLAY_TYPES)
def test_schema_allows_every_renderer_overlay_type(overlay_type: str) -> None:
    """The playbook schema's overlay vocabulary must track the renderer's.

    Regression: the schema allowed only stat_card/key_term/code_block — none of
    the four overlay types Explainer renders — so styling `section_title` made
    the whole playbook invalid.
    """
    import json
    from pathlib import Path

    schema_path = (
        Path(__file__).resolve().parents[2]
        / "schemas"
        / "styles"
        / "playbook.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    allowed = schema["properties"]["overlays"]["properties"]
    assert overlay_type in allowed


class TestOneLevelOneNumber:
    """The bed level is stated twice in wak3up-documentary.yaml — once where
    the mixer reads it, once in the `music_authority` block that states the
    blocking check. They were -30 and -36: 6 dB apart, against a +/-1.5 LU
    gate, so the compose gate would fail on whichever one the mixer did not
    use. The playbook schema already refuses a bed stated as both a ratio and
    a LUFS figure, for exactly this reason; this is the same mistake in the
    prose half.
    """

    def test_the_mixer_s_number_and_the_blocking_check_agree(self):
        import re

        import yaml

        pb = yaml.safe_load(
            open("styles/wak3up-documentary.yaml", encoding="utf-8"))
        mixed = pb["audio"]["music_under_speech_lufs"]
        authority = pb["music_authority"]["bed_under_speech_lufs"]
        assert mixed == authority, (
            f"the mixer mixes to {mixed} and music_authority binds "
            f"{authority} — the compose gate fails on one of them")

        stated = re.search(r"(-?\d+(?:\.\d+)?)\s*LUFS",
                           pb["music_authority"]["blocking_check"])
        assert stated and float(stated.group(1)) == float(mixed), (
            f"blocking_check says {stated and stated.group(1)}, "
            f"the mixer mixes to {mixed}")

    def test_the_mixer_named_by_the_playbook_is_the_one_that_reads_it(self):
        """A number nothing reads is a number that drifts."""
        from pathlib import Path

        import yaml

        pb = yaml.safe_load(
            open("styles/wak3up-documentary.yaml", encoding="utf-8"))
        mixer = Path(pb["music_authority"]["mixer"])
        assert mixer.exists(), f"{mixer} does not exist"
        assert "music_under_speech_lufs" in mixer.read_text()


class TestTheAudioRevisionIsStatedOnce:
    """Every number the owner set on 2026-10-25 is in two places or more.

    The playbook is the decision and the module is what runs; when the two
    drift, the gate fails on whichever one the mixer did not use. That has
    already happened once here with the bed level, 6 dB apart against a
    1.5 LU check, which is what `TestOneLevelOneNumber` above is for. These
    are the same guard for the rest of the revision.
    """

    @staticmethod
    def _playbook():
        import yaml

        return yaml.safe_load(
            open("styles/wak3up-documentary.yaml", encoding="utf-8"))

    def test_the_gap_cap_and_the_absolute_gap_level_agree(self):
        pb = self._playbook()["audio"]
        assert pb["music_under_speech_lufs"] + pb["music_gap_rise_db_max"] == \
            pb["music_in_gaps_lufs"], (
            "the gap is stated as a cap on the rise AND as an absolute level; "
            "at this bed level they have to come to the same number")

    def test_the_mixer_uses_the_playbook_s_gap_numbers(self):
        from lib import mix_audio as mx

        pb = self._playbook()["audio"]
        assert mx.GAP_RISE_DB_MAX == pb["music_gap_rise_db_max"]
        assert mx.GAP_TARGET_LUFS == pb["music_in_gaps_lufs"]
        assert mx.BOUNDARY_TARGET_LUFS == pb["music_at_act_boundaries_lufs"]

    def test_the_boundary_level_is_minus_27_not_minus_22(self):
        assert self._playbook()["audio"]["music_at_act_boundaries_lufs"] == -27

    def test_the_ramp_is_stated_the_same_in_both_places(self):
        from lib import mix_audio as mx

        pb = self._playbook()["audio"]
        assert pb["music_rise_ramp_seconds"] == mx.RISE_RAMP_SECONDS
        assert pb["duck"]["rise_ramp_seconds"] == mx.RISE_RAMP_SECONDS
        assert pb["duck"]["dezipper_ms"] == mx.DEZIPPER_MS

    def test_the_bed_dynamics_ceilings_agree(self):
        from lib import mix_audio as mx

        bd = self._playbook()["audio"]["bed_dynamics"]
        assert bd["loudness_range_max_lu"] == mx.BED_DYNAMICS_MAX_LU
        assert bd["spread_between_beds_max_lu"] == mx.BED_SPREAD_MAX_LU
        assert bd["attack_ms"] == mx.BED_COMPRESSOR_ATTACK_MS
        assert bd["release_ms"] == mx.BED_COMPRESSOR_RELEASE_MS
        assert "2:1" in bd["compressor"]
        assert mx.BED_COMPRESSOR_RATIO == 2.0

    def test_the_eq_in_the_playbook_is_the_chain_that_runs(self):
        from lib.music_brightness import BED_EQ

        eq = self._playbook()["audio"]["music_eq"]
        assert f"lowpass=f={eq['low_pass_hz']}" in BED_EQ
        assert f"highpass=f={eq['high_pass_hz']}" in BED_EQ
        assert "highshelf=f=3500" in BED_EQ
        assert "3.5 kHz" in eq["high_shelf"] and "-6 dB" in eq["high_shelf"]

    def test_the_brightness_ceiling_agrees(self):
        from pathlib import Path

        from lib import music_brightness as mb

        mbk = self._playbook()["audio"]["music_brightness"]
        assert mbk["max_energy_above_high_pct"] == mb.MAX_ENERGY_ABOVE_4K_PCT
        assert mbk["high_hz"] == mb.HIGH_HZ
        assert Path(mbk["gate"]).exists()

    def test_the_brightness_ceiling_records_what_it_did_not_catch(self):
        """A gate credited with a find it did not make is worse than no gate."""
        note = self._playbook()["audio"]["music_brightness"]["what_it_did_not_catch"]
        assert "ambience_sea" in note and "1,647" in note
        assert "every track passes" in note

    def test_every_one_shot_sits_under_the_bed(self):
        """The gate's rule, expressed in the table the gate checks."""
        off = self._playbook()["audio"]["sound_design"][
            "levels_relative_to_music_bed_db"]
        for key in ("riser_peak", "impact_peak", "sting_peak"):
            assert off[key] < 0, (
                f"{key} is {off[key]:+d}: an event at or above the bed cannot "
                f"pass lib/verify_sfx_level.py, which the playbook names as "
                f"a blocking check")

    def test_the_owner_s_spacing_between_the_one_shots_is_preserved(self):
        """They were shifted as a group, by the 10 dB the gate measured.

        riser -2, impact +4, sting +8 was the owner's table; the gate refused
        it and the three moved down together. The SPACING is the owner's
        decision and must survive the shift.
        """
        off = self._playbook()["audio"]["sound_design"][
            "levels_relative_to_music_bed_db"]
        assert off["impact_peak"] - off["riser_peak"] == 6
        assert off["sting_peak"] - off["impact_peak"] == 4

    def test_the_ambience_and_room_tone_are_the_owner_s_numbers_untouched(self):
        off = self._playbook()["audio"]["sound_design"][
            "levels_relative_to_music_bed_db"]
        assert off["ambience"] == -10          # -6 shipped, the owner cut 4
        assert off["room_tone"] == -12         # never asked to move

    def test_the_sfx_gate_is_named_as_a_blocking_check(self):
        pb = self._playbook()
        checks = " ".join(pb["music_authority"]["bed_blocking_checks"])
        assert "louder than the bed" in checks
        assert "4 kHz" in checks
        assert "6 LU" in checks and "1.5 LU" in checks
        assert "mix_audio" in pb["music_authority"]["where_they_run"]

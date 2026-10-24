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

"""The cut the instructions tell a stage to author must validate.

WHY THIS TEST EXISTS
--------------------
`schemas/artifacts/edit_decisions.schema.json` closes the cut object: it is
a set of EDITORIAL decisions, and an authored scene's component props live
under `scene`. A cut carrying those props flat fails the artifact's own
schema, and validation happens in `lib/checkpoint.py` when a stage
COMPLETES — so the edit is lost at the end of the stage that made it.

That is not hypothetical. It is why the schema was loosened in the first
place: `lib/build_render_props.py` records that carrying component props
flat "made the artifact fail its own schema — so an edit stage could not be
checkpointed at all."

Closing it again is only safe if the instructions tell the stage the new
shape. On 2026-11-09 they did not: `STAGE_CONTRACT.md` mentioned "scene"
five times and every one meant `scene_plan.json`, and the edit director
skill's 192 lines never mentioned the sub-object at all.

So this test reads the example OUT OF THE INSTRUCTIONS and validates it. If
someone edits the documentation into something a stage could not author,
this fails — rather than Friday failing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "pipelines" / "narrated-documentary" / "edit-director.md"
CONTRACT = ROOT / "docs" / "STAGE_CONTRACT.md"
SCHEMA = ROOT / "schemas" / "artifacts" / "edit_decisions.schema.json"


def documented_cut() -> dict:
    """The worked example, parsed out of the skill the stage is told to read."""
    text = SKILL.read_text()
    blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
    assert blocks, "the edit director skill carries no JSON example"
    for block in blocks:
        parsed = json.loads(block)
        if isinstance(parsed, dict) and "scene" in parsed:
            return parsed
    pytest.fail("no example cut with a `scene` sub-object in the skill")


def schema() -> dict:
    return json.loads(SCHEMA.read_text())


def as_artifact(cut: dict) -> dict:
    # `render_runtime` is the RENDERER'S NAME, not a duration — the schema
    # says so with an enum, and it caught this fixture putting 1226.0 there.
    return {"version": "1.0", "render_runtime": "remotion", "cuts": [cut]}


def cut_is_closed() -> bool:
    """Has the closed-cut schema landed yet?

    The instructions and this test go in BEFORE the schema that needs them,
    on purpose: closing the cut is only safe once a stage has been told the
    new shape. Until then the `scene`-aware assertions skip with a reason
    rather than fail for a condition nobody has created yet.
    """
    items = schema()["properties"]["cuts"]["items"]
    return "scene" in items.get("properties", {})


class TestTheInstructionsDescribeAnAuthorableCut:
    def test_the_skill_carries_an_example(self):
        cut = documented_cut()
        assert cut["id"] and cut["scene"]["type"]

    def test_it_validates_against_the_schema(self):
        import jsonschema
        if not cut_is_closed():
            pytest.skip("the schema does not define `scene` yet — it lands "
                        "with the asset-library merge")
        errors = list(jsonschema.Draft7Validator(schema()).iter_errors(
            as_artifact(documented_cut())))
        assert errors == [], [
            f"{list(e.absolute_path)}: {e.message}" for e in errors]

    def test_it_puts_component_props_under_scene_and_not_flat(self):
        """The invariant the instructions teach, asserted directly so this
        test means something even while the schema is still open."""
        if not cut_is_closed():
            pytest.skip("the schema does not define `scene` yet — it lands "
                        "with the asset-library merge")
        cut = documented_cut()
        allowed = set(schema()["properties"]["cuts"]["items"]["properties"])
        stray = set(cut) - allowed
        assert not stray, (
            f"the documented example puts {sorted(stray)} flat on the cut; "
            f"component props belong under `scene`")
        assert "claim" in cut["scene"] or len(cut["scene"]) > 1

    def test_source_is_the_slot_id_for_an_authored_cut(self):
        """Required on every cut. An authored cut has no file, so it carries
        the slot id — which is how noah's 159 authored cuts satisfy it."""
        cut = documented_cut()
        assert cut["source"] and not Path(cut["source"]).suffix

    def test_layer_is_a_string(self):
        """Two earlier films wrote it as an integer and their artifacts no
        longer match the schema. The instructions say so; this pins it."""
        assert documented_cut()["layer"] in ("primary", "overlay", "background")


class TestTheFlatShapeIsRefusedOnceTheCutIsClosed:
    """The control. Flattening the example must FAIL — otherwise the
    documentation is describing a distinction the schema does not make."""

    def test_a_flattened_cut_is_refused(self):
        import jsonschema
        blob = schema()
        if blob["properties"]["cuts"]["items"].get("additionalProperties") is not False:
            pytest.skip(
                "the cut object is still open (additionalProperties is not "
                "false), so flattening cannot be refused yet — this becomes "
                "live when the closed-cut schema lands")
        cut = documented_cut()
        flat = {k: v for k, v in cut.items() if k != "scene"}
        flat.update(cut["scene"])
        errors = list(jsonschema.Draft7Validator(blob).iter_errors(
            as_artifact(flat)))
        assert errors, "a flat cut passed a schema that claims to close it"


class TestBothSurfacesSayIt:
    def test_the_stage_contract_says_it(self):
        text = CONTRACT.read_text()
        assert "under `scene`" in text
        assert "cannot be checkpointed" in text

    def test_the_skill_says_why_not_just_what(self):
        text = SKILL.read_text()
        assert "closed set of EDITORIAL decisions" in text
        assert "cannot be checkpointed at all" in text

    def test_the_contract_points_at_this_test(self):
        """So the next person changing the shape finds the thing that
        checks it."""
        assert "test_authored_cut_shape.py" in CONTRACT.read_text()

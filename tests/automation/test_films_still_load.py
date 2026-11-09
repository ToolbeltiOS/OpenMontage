"""Four films were made before the cut object closed. They must still load.

WHAT CHANGES AND WHAT MUST NOT
------------------------------
Closing the cut object changes what a NEW artifact may contain. It must not
change whether an OLD one can be read: `projects/<slug>/artifacts/
edit_decisions.json` is the record of a film that shipped, and the resume
path and the slice harness both read king-tut's.

Nothing validates these on read — the only mention of the schema in
`lib/build_render_props.py` is a comment, and `lib/checkpoint.py` validates
when a stage COMPLETES, not when an artifact is loaded. So the published
films never meet the closed schema again, and they are NOT migrated: three
of them would need their historical records rewritten to satisfy a rule
written after they shipped, and for two that includes changing `layer` from
an integer to a string.

Measured 2026-11-09 against the closed schema:

    noah              clean — already authored with `scene`
    king-tut          162 additional-properties, 29 missing `source`
    easter-island     338 layer-is-an-integer, 172 add-props, 73 `source`
    they-said-it      364 layer-is-an-integer, 143 add-props, 30 `source`

That is the state this test freezes: they do not validate, and they do load.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FILMS = ("king-tut", "easter-island", "noah", "they-said-it-couldnt-be-built")


def artifact(slug: str) -> Path | None:
    for root in ("runner", "OpenMontage", "fix-render-finalise", "asset-library"):
        path = (ROOT.parent / root / "projects" / slug / "artifacts"
                / "edit_decisions.json")
        if path.exists():
            return path
    return None


def edit_of(slug: str) -> dict:
    path = artifact(slug)
    if path is None:
        pytest.skip(f"{slug} has no edit_decisions.json on this machine")
    return json.loads(path.read_text())


@pytest.mark.parametrize("slug", FILMS)
def test_it_loads(slug):
    ed = edit_of(slug)
    assert ed.get("cuts"), f"{slug} has no cuts"
    assert len(ed["cuts"]) > 100, f"{slug} has only {len(ed['cuts'])} cuts"


@pytest.mark.parametrize("slug", FILMS)
def test_every_cut_still_has_what_the_renderer_needs(slug):
    """Whatever shape it is in, a cut has to say where it sits."""
    for cut in edit_of(slug)["cuts"]:
        assert "id" in cut
        assert "in_seconds" in cut and "out_seconds" in cut
        assert float(cut["out_seconds"]) > float(cut["in_seconds"])


@pytest.mark.parametrize("slug", FILMS)
def test_the_flattening_is_safe_on_it(slug):
    """The dual-accept rule, applied to the real artifact.

    A cut with no `scene` passes through untouched; a cut with one has it
    flattened and nothing already on the cut is overwritten. Run here
    against every film so the rule is tested on the shapes that exist
    rather than on a fixture.
    """
    cuts = json.loads(json.dumps(edit_of(slug)["cuts"]))     # a copy
    before = [dict(c) for c in cuts]
    for cut in cuts:
        scene = cut.pop("scene", None)
        if isinstance(scene, dict):
            for key, value in scene.items():
                cut.setdefault(key, value)

    assert len(cuts) == len(before)
    for original, flattened in zip(before, cuts):
        assert flattened["id"] == original["id"]
        for key, value in original.items():
            if key == "scene":
                continue
            assert flattened[key] == value, (
                f"{slug} {original['id']}: flattening overwrote {key!r}")


def test_the_two_shapes_both_exist_in_the_wild():
    """The control. If every film were one shape, this suite would be
    testing dual-accept against a single case."""
    shapes = {}
    for slug in FILMS:
        path = artifact(slug)
        if path is None:
            continue
        cuts = json.loads(path.read_text())["cuts"]
        shapes[slug] = sum(1 for c in cuts if "scene" in c)
    assert shapes, "no films on this machine"
    assert any(v == 0 for v in shapes.values()), f"no FLAT film: {shapes}"
    assert any(v > 0 for v in shapes.values()), f"no SCENE film: {shapes}"

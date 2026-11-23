"""Props the composer cannot draw must not reach a render.

THE BUG THIS HOLDS SHUT
-----------------------
On 2026-11-22 the Pearl Harbor render died at frame 21867 of 36705 with

    Error: inputRange must contain only finite numbers, but got [NaN,NaN]
        at src/components/MapRoute.tsx:181

Cut c112 carried `distance_callout: true`. `MapRoute` reads
`distance_callout.at`, which is `undefined` on a boolean, and `undefined *
fps` is `NaN`, so `interpolate` was handed `[NaN, NaN]`. This was the
SECOND render killed in two nights by a prop the composer could not draw —
`callout_type: "note"` was the first — and the two share a shape: a value
whose TYPE is wrong in a field the component indexes into.

WHY IT COST ANYTHING AT ALL
---------------------------
`remotion-composer/src/schemas/docComponents.ts` has carried a zod schema
per scene type since the buildability check was written. It encodes exactly
the rule that would have caught this — `distance_callout: z.object({text,
at}).optional()` — and NOTHING IMPORTED IT. The fourth gate in this
pipeline found defining a rule nobody enforced.

It was unusable for a second reason. Those schemas describe what a
COMPONENT receives; a CUT is not that, because `Explainer` maps one onto
the other. Pointed at cuts, they reported 85 failures on a film that
rendered perfectly well — 75 of them because `AnnotatedStill` is handed
`image={cut.backgroundImage ?? cut.image}` and no cut carries `image`. A
check that cries wolf is a check nobody can turn on, so `DOC_CUT_SCHEMAS`
states the cut contract separately and declares every divergence.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import build_render_props as B                          # noqa: E402


# c112's real geometry, from projects/attack-on-pearl-harbor. Oahu to
# Niihau: the route the film draws while the narration says a Zero came
# down there.
C112_ROUTE = [[-157.98, 21.47], [-159.5, 21.75], [-160.15, 21.9]]


def map_route(**over) -> dict:
    cut = {"id": "c112", "type": "map_route", "route": C112_ROUTE,
           "draw_seconds": 3.0, "draw_at": 1.2, "title": "Niihau"}
    cut.update(over)
    return cut


def props_of(*cuts, overlays=None) -> dict:
    return {"cuts": list(cuts), "overlays": list(overlays or [])}


def refusal(props) -> str:
    with pytest.raises(SystemExit) as caught:
        B.check_scene_props(props)
    return str(caught.value)


class TestTheCutThatKilledTheRender:

    def test_c112_as_it_was_last_night_is_refused(self):
        why = refusal(props_of(map_route(distance_callout=True)))
        assert "c112" in why
        assert "distance_callout" in why

    def test_the_refusal_names_the_rule_not_just_the_field(self):
        why = refusal(props_of(map_route(distance_callout=True)))
        assert "object" in why and "boolean" in why

    def test_the_patched_c112_passes(self):
        report = B.check_scene_props(
            props_of(map_route(distance_callout={"text": "≈ 229 km",
                                                 "at": 4.4})))
        assert report["failures"] == []
        assert report["checked"] == 1

    def test_a_callout_missing_its_timing_is_still_refused(self):
        # The half-formed version: an object, but without the field the
        # component multiplies by fps. Still NaN, still fatal.
        why = refusal(props_of(map_route(distance_callout={"text": "229 km"})))
        assert "distance_callout.at" in why

    def test_the_refusal_says_where_the_fix_belongs(self):
        # render_props.json is rebuilt from edit_decisions.json on every
        # render, so a patch applied to the props alone evaporates.
        why = refusal(props_of(map_route(distance_callout=True)))
        assert "edit stage" in why


class TestTheCutContractIsNotTheComponentContract:
    """The 85-failures-on-a-good-film problem, held shut."""

    def test_a_still_with_backgroundimage_passes(self):
        report = B.check_scene_props(props_of(
            {"id": "c001", "type": "annotated_still",
             "backgroundImage": "assets/stills/arizona.jpg"}))
        assert report["failures"] == []

    def test_a_still_with_image_also_passes(self):
        report = B.check_scene_props(props_of(
            {"id": "c001", "type": "annotated_still",
             "image": "assets/stills/arizona.jpg"}))
        assert report["failures"] == []

    def test_a_still_with_no_plate_at_all_is_refused(self):
        # Explainer draws this scene type only when a plate resolves, so a
        # cut with neither silently draws nothing.
        why = refusal(props_of({"id": "c001", "type": "annotated_still"}))
        assert "backgroundImage" in why

    def test_a_numeric_seed_passes_because_the_component_interpolates_it(self):
        report = B.check_scene_props(props_of(
            {"id": "c010", "type": "texture_field",
             "kind": "depth_field", "seed": 1207, "density": 60}))
        assert report["failures"] == []

    def test_a_density_that_rounds_to_zero_is_refused(self):
        # Math.round(0.4) is 0, so the texture beat draws no elements at
        # all. Four cuts in the Pearl Harbor film carry this.
        why = refusal(props_of(
            {"id": "c010", "type": "texture_field",
             "kind": "depth_field", "seed": 1207, "density": 0.4}))
        assert "density" in why


class TestTheTypesThatHadNoSchema:
    """stat_card and callout were unchecked entirely until 2026-11-22."""

    def test_stat_card_is_checked_now(self):
        report = B.check_scene_props(props_of(
            {"id": "c044", "type": "stat_card", "stat": "Two warnings"}))
        assert report["checked"] == 1
        assert "stat_card" not in (report["unchecked"] or {})

    def test_a_stat_card_with_no_figure_is_refused(self):
        why = refusal(props_of({"id": "c044", "type": "stat_card",
                                "stat": ""}))
        assert "stat" in why

    def test_callout_is_checked_now(self):
        report = B.check_scene_props(props_of(
            {"id": "c047", "type": "callout", "text": "The Ward sank one.",
             "callout_type": "warning"}))
        assert report["checked"] == 1
        assert "callout" not in (report["unchecked"] or {})

    def test_the_callout_schema_does_not_restate_the_style_list(self):
        # check_callout_types owns that set, read out of the component. Two
        # copies of a list is how `note` survived.
        src = (ROOT / "remotion-composer" / "src" / "schemas"
               / "docComponents.ts").read_text(encoding="utf-8")
        block = re.search(r"export const CalloutSchema = z\.object\(\{(.*?)\}\);",
                          src, re.S)
        assert block, "CalloutSchema not found"
        assert "callout_type" not in block.group(1)

    def test_an_unscheduled_scene_type_is_reported_not_silently_passed(self):
        report = B.check_scene_props(props_of(
            {"id": "c900", "type": "hero_title", "text": "Pearl Harbor"}))
        assert report["unchecked"].get("hero_title") == 1


class TestTheGateIsWiredIntoTheBuild:
    """The defect was a schema with no consumer. This is the consumer."""

    def test_the_schemas_are_imported_by_the_validator(self):
        src = (ROOT / "remotion-composer" / "src" / "schemas"
               / "validate_cut_props_cli.ts").read_text(encoding="utf-8")
        assert "./docComponents" in src

    def test_the_check_runs_before_the_props_are_written(self):
        src = (ROOT / "lib" / "build_render_props.py").read_text(encoding="utf-8")
        bare = "\n".join(line for line in src.splitlines()
                         if not line.lstrip().startswith("#"))
        assert "check_scene_props(props)" in bare, \
            "the gate is not called at all — a schema with no consumer is " \
            "what this whole file exists to prevent"
        gate = bare.index("check_scene_props(props)")
        write = bare.index('json.dump(props, open(out')
        assert gate < write, "the gate must run before render_props.json is written"

    def test_a_missing_validator_refuses_rather_than_passing(self, monkeypatch):
        monkeypatch.setattr(B, "SCENE_VALIDATOR", "nope/not_here.ts")
        why = refusal(props_of(map_route(distance_callout=True)))
        assert "refuses rather than passing" in why

    def test_a_missing_esbuild_refuses_rather_than_passing(self, monkeypatch):
        monkeypatch.setattr(B, "ESBUILD", "nope/no_esbuild")
        why = refusal(props_of(map_route()))
        assert "refuses rather than passing" in why

    def test_a_validator_that_prints_rubbish_refuses(self, monkeypatch, tmp_path):
        broken = tmp_path / "broken.ts"
        broken.write_text('process.stdout.write("not json at all");\n')
        monkeypatch.setattr(B, "SCENE_VALIDATOR", str(broken))
        monkeypatch.setattr(B, "ROOT", "/")
        why = refusal(props_of(map_route()))
        assert "refuses rather than passing" in why

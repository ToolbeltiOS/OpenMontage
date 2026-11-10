"""The illustration slot class, end to end: can a drawing reach a film?

WHY THIS EXISTS
---------------
It could not. Before 2026-11-09 the renderer had `Illustration.tsx` and
`Explainer.tsx` dispatched on `cut.type === "illustration"`, the generator and
the quota ledger existed, the approval gate wrote `approved.json`, and
`demote_unapproved` and `verify_approved_use` both read it — and an
illustration still could not reach a film, because:

  * the component was absent from `remotion-composer/component-contract.json`,
    so `buildability.check_slot` refused any slot naming it; and
  * `scene-director.md` and `edit-director.md` mentioned illustrations ZERO
    times, so nothing authored one.

That is the shape of this project's recurring fault, inverted: not a gate
nobody consumes, but a CONSUMER nobody can reach. The owner approved three
illustrations for noah on 2026-10-31, they appeared in no cut, and the
approvals were revoked on 2026-11-01 — "the illustration route ends at the
gate".

So this file checks the chain rather than any one link, because every link
already existed and the chain still did not carry anything.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

CONTRACT = ROOT / "remotion-composer" / "component-contract.json"
SCENE_DIRECTOR = (ROOT / "skills" / "pipelines" / "narrated-documentary"
                  / "scene-director.md")
EDIT_DIRECTOR = (ROOT / "skills" / "pipelines" / "narrated-documentary"
                 / "edit-director.md")
ILLUSTRATION_TSX = (ROOT / "remotion-composer" / "src" / "scenes"
                    / "Illustration.tsx")
EXPLAINER_TSX = ROOT / "remotion-composer" / "src" / "Explainer.tsx"


def contract() -> dict:
    return json.loads(CONTRACT.read_text())["components"]


class TestTheComponentIsInTheContract:
    def test_illustration_exists(self):
        assert "illustration" in contract(), (
            "buildability refuses any slot naming a component the contract "
            "does not list, so an illustration slot cannot be authored")

    def test_image_and_subject_are_both_required(self):
        spec = contract()["illustration"]
        assert set(spec["required"]) == {"image", "subject"}

    def test_the_contract_says_why_both_fields_exist(self):
        """A required field with no reason gets relaxed by the next person."""
        spec = contract()["illustration"]
        subject = spec.get("subject_note", "")
        assert "40 characters" in subject
        assert "truncated" in subject.lower() or "ellipsis" in subject.lower()
        prompt = spec.get("prompt_note", "")
        assert "never receives it" in prompt
        assert "licence" in prompt.lower()

    def test_the_prompt_is_slot_level_and_not_a_prop(self):
        """It is provenance, not something the component draws.

        Declaring it as a prop would make it a prop the renderer ignores,
        which is this project's oldest fault — a `texture` field that was
        authored, screened, reported on and never forwarded.
        """
        spec = contract()["illustration"]
        assert spec.get("slot_required") == ["prompt"]
        assert "prompt" not in spec["required"]
        assert "prompt" not in spec["optional"]

    def test_every_prop_it_declares_is_one_the_component_takes(self):
        """The contract is a promise about `Illustration.tsx`.

        A prop in the contract that the component does not accept is a slot
        the planner may author and the renderer will ignore — the
        gate-without-consumer fault in its original form, a `texture` field
        that was never forwarded.
        """
        source = ILLUSTRATION_TSX.read_text()
        props = re.search(r"export interface IllustrationProps \{(.*?)\n\}",
                          source, re.S)
        assert props, "IllustrationProps is no longer declared"
        accepted = set(re.findall(r"^\s*(\w+)\??:", props.group(1), re.M))
        spec = contract()["illustration"]
        chrome = set(json.loads(CONTRACT.read_text())["_chrome"]["props"])
        declared = set(spec["required"]) | set(spec["optional"])
        unknown = declared - accepted - chrome
        assert not unknown, (
            f"the contract declares props Illustration.tsx does not take: "
            f"{sorted(unknown)}")

    def test_the_renderer_dispatches_on_the_type(self):
        source = EXPLAINER_TSX.read_text()
        assert 'cut.type === "illustration"' in source


class TestBuildabilityEnforcesIt:
    def setup_method(self):
        from buildability import load_contract
        self.contract = load_contract()

    def slot(self, prompt="a thing, in full, as the generator was asked",
             **props):
        out = {"slot_id": "s1", "treatment": "graphic",
               "component": "illustration", "props": props}
        if prompt is not None:
            out["prompt"] = prompt
        return out

    def test_a_complete_slot_is_buildable(self):
        from buildability import check_slot
        found = check_slot(self.slot(image="a.png", subject="A thing"),
                           self.contract)
        assert not found, found

    def test_a_slot_with_no_prompt_is_refused(self):
        from buildability import check_slot
        found = check_slot(
            self.slot(prompt=None, image="a.png", subject="A thing"),
            self.contract)
        assert any("prompt" in p for p in found), found

    def test_a_slot_with_no_subject_is_refused(self):
        from buildability import check_slot
        found = check_slot(self.slot(image="a.png"), self.contract)
        assert any("subject" in p for p in found), found

    def test_a_slot_with_no_image_is_refused(self):
        from buildability import check_slot
        found = check_slot(self.slot(subject="A thing"), self.contract)
        assert any("image" in p for p in found), found


class TestThePlannerIsToldAboutIt:
    """Instructions, because a slot class nothing authors is unreachable.

    `b17f841` is the precedent and the reason this is a test: the closed-cut
    schema was safe only once the instructions described the shape, and
    landing it first would have had the edit stage author the old shape and
    fail validation at the end of the stage that made it.
    """

    def test_the_scene_director_describes_the_slot(self):
        text = SCENE_DIRECTOR.read_text()
        assert "illustration" in text
        assert '"component": "illustration"' in text, (
            "the scene director has no worked example of an illustration slot")

    def test_it_teaches_the_two_fields_apart(self):
        text = SCENE_DIRECTOR.read_text()
        assert "40 characters" in text
        assert "`prompt`" in text
        assert "TIMBER FRA" in text, (
            "the scene director no longer shows what truncation looked like, "
            "which is the only reason the split is believable")

    def test_it_states_the_three_refusals(self):
        """What an illustration may NOT be is the whole safety of the class."""
        text = SCENE_DIRECTOR.read_text().lower()
        assert "not evidence" in text
        assert "stills_of_record" in text
        assert "not a person who existed" in text

    def test_it_names_the_approval_and_the_demotion(self):
        text = SCENE_DIRECTOR.read_text()
        assert "demote_unapproved" in text
        assert "verify_approved_use" in text

    def test_it_names_the_budget(self):
        text = SCENE_DIRECTOR.read_text()
        assert "600" in text and "pixazo_quota" in text

    def test_the_edit_director_carries_the_cut_shape(self):
        text = EDIT_DIRECTOR.read_text()
        assert '"type": "illustration"' in text, (
            "the edit director has no worked example of an illustration cut")
        assert '"subject"' in text

    def test_the_edit_director_says_not_to_promote_a_cut_itself(self):
        text = EDIT_DIRECTOR.read_text()
        assert "Do not promote a cut to `illustration` yourself" in text

    def test_the_worked_examples_validate_against_the_schema(self):
        """The example in the instructions is the shape, so it has to be real.

        `tests/automation/test_authored_cut_shape.py` does this for the
        evidence_card example; an illustration example that does not validate
        would teach the stage a cut the schema refuses.
        """
        import jsonschema

        schema = json.loads(
            (ROOT / "schemas" / "artifacts"
             / "edit_decisions.schema.json").read_text())
        blocks = re.findall(r"```json\n(.*?)\n```", EDIT_DIRECTOR.read_text(),
                            re.S)
        cuts = []
        for block in blocks:
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and \
                    (parsed.get("scene") or {}).get("type") == "illustration":
                cuts.append(parsed)
        assert cuts, "no illustration cut example in the edit director"
        cut_schema = schema["properties"]["cuts"]["items"]
        for cut in cuts:
            jsonschema.validate(cut, cut_schema)

    def test_the_example_cut_names_both_required_props(self):
        """And under `scene`, where the closed cut puts component props."""
        blocks = re.findall(r"```json\n(.*?)\n```", EDIT_DIRECTOR.read_text(),
                            re.S)
        for block in blocks:
            try:
                cut = json.loads(block)
            except json.JSONDecodeError:
                continue
            if not isinstance(cut, dict):
                continue
            scene = cut.get("scene") or {}
            if scene.get("type") != "illustration":
                continue
            assert scene.get("image"), cut
            assert scene.get("subject"), cut
            for key in ("image", "subject"):
                assert key not in cut, (
                    f"{key} is flat on the cut; component props go under "
                    f"`scene` or the cut fails its own schema")
            return
        pytest.fail("no illustration cut example to check")


class TestTheBudgetIsReal:
    def test_the_cap_is_600_a_month(self):
        import pixazo_quota

        assert (pixazo_quota.MONTHLY_FREE_IMAGES
                * pixazo_quota.CEILING) == 600.0

    def test_asking_for_more_than_the_cap_is_refused(self):
        import pixazo_quota

        ok, why = pixazo_quota.check(10_000)
        assert not ok
        assert "600" in why or "reaches" in why, why


class TestTheRefusalsAreEnforcedAndNotJustDocumented:
    def test_an_evidence_slot_may_not_be_an_illustration(self):
        import illustration_spec

        ok, why = illustration_spec.allowed({"tags": ["evidence"]})
        assert not ok
        assert "evidence" in why

    def test_a_stills_of_record_slot_may_not_be_either(self):
        import illustration_spec

        ok, why = illustration_spec.allowed({"tags": ["stills_of_record"]})
        assert not ok

    def test_an_ordinary_slot_is_allowed(self):
        import illustration_spec

        ok, why = illustration_spec.allowed({"tags": ["context"]})
        assert ok, why


class TestAnUnapprovedCutFallsBack:
    """The consumer that already existed, asserted against the new class."""

    def test_an_unapproved_illustration_with_a_path_becomes_a_still(self, tmp_path):
        import illustration_spec

        (tmp_path / "assets" / "library" / "illustrations").mkdir(parents=True)
        (tmp_path / "assets" / "library" / "illustrations"
         / "approved.json").write_text(json.dumps({"approved": []}))
        cuts = [{"id": "c041", "type": "illustration",
                 "subject": "a thing nobody approved", "source": "act2_s014",
                 "backgroundImage": "x.png"}]
        changed = illustration_spec.demote_unapproved(cuts, tmp_path)
        assert changed and changed[0]["fell_to"] == "still"
        assert cuts[0]["type"] == "annotated_still"
        assert cuts[0]["illustration_refused"]

    def test_and_without_one_becomes_a_text_card(self, tmp_path):
        import illustration_spec

        (tmp_path / "assets" / "library" / "illustrations").mkdir(parents=True)
        (tmp_path / "assets" / "library" / "illustrations"
         / "approved.json").write_text(json.dumps({"approved": []}))
        cuts = [{"id": "c041", "type": "illustration", "subject": "a thing"}]
        changed = illustration_spec.demote_unapproved(cuts, tmp_path)
        assert changed and changed[0]["fell_to"] == "text_card"
        assert cuts[0]["type"] == "text_card"


class TestTheStripNeverTruncates:
    """`subject` is what the viewer reads, so it has to fit on screen.

    Until 2026-11-09 `subject` was the full descriptive sentence and the
    strip rendered it with `whiteSpace: nowrap` and `textOverflow: ellipsis`.
    A delivered frame of the illustration slice read

        ILLUSTRATION — A VERY LARGE WOODEN VESSEL UNDER CONSTRUCTION ON DRY
        LAND, TIMBER FRA…

    The label is the one thing an illustration must communicate, and it was
    being cut off mid-word. The field is now split: `subject` is a short
    on-screen label and the sentence lives in `prompt`.

    THE BOUND IS THE WIDEST GLYPH, NOT THE AVERAGE. The font is a woff2 and
    this machine has no brotli to decompress it, so the measurement uses an
    UPPER BOUND on advance width: every character is priced as the widest
    uppercase glyph a sans face is likely to carry. Passing therefore
    GUARANTEES the line fits, whatever the font does — an average-width
    model could pass a line of all W's that truncates in the render.
    """

    #: From Illustration.tsx and design/system.ts, read rather than guessed.
    FONT_PX = 22 - 2                 # TYPE.labelSm - 2
    TRACKING_EM = 0.16               # TRACK
    FRAME_W = 1920                   # Root.tsx
    MAX_FRACTION = 0.7               # maxWidth: width * 0.7
    PADDING_X = 18 * 2               # padding: "7px 18px"
    #: An upper bound on one uppercase advance, in em. A wide sans caps `W`
    #: is about 0.82em; 0.9 leaves room for a face this test cannot read.
    WIDEST_EM = 0.9
    PREFIX = "ILLUSTRATION — "

    @classmethod
    def widest_px(cls, subject: str) -> float:
        line = cls.PREFIX + subject.upper()
        per_char = cls.FONT_PX * cls.WIDEST_EM + cls.FONT_PX * cls.TRACKING_EM
        return len(line) * per_char

    @classmethod
    def budget_px(cls) -> float:
        return cls.FRAME_W * cls.MAX_FRACTION - cls.PADDING_X

    def test_the_constants_still_match_the_component(self):
        """If the strip is restyled, this test must be restyled with it."""
        tsx = ILLUSTRATION_TSX.read_text()
        assert "fontSize: TYPE.labelSm - 2" in tsx
        assert "letterSpacing: TRACK" in tsx
        assert "maxWidth: width * 0.7" in tsx
        assert 'padding: "7px 18px"' in tsx
        assert 'textOverflow: "ellipsis"' in tsx, (
            "the strip no longer truncates, so this whole class is measuring "
            "a constraint that has gone away")
        system = (ROOT / "remotion-composer" / "src" / "design"
                  / "system.ts").read_text()
        assert "labelSm: 22" in system
        assert 'export const TRACK = "0.16em"' in system

    def test_every_manifest_subject_fits(self):
        """The real pictures, measured."""
        manifest = json.loads(
            (ROOT / "assets" / "library" / "illustrations"
             / "manifest.json").read_text())
        for asset in manifest["assets"]:
            subject = asset["subject"]
            width = self.widest_px(subject)
            assert width <= self.budget_px(), (
                f"{Path(asset['path']).name}: {subject!r} is {width:.0f}px at "
                f"its widest against a {self.budget_px():.0f}px strip — it "
                f"would render with an ellipsis")

    def test_every_manifest_subject_is_within_forty_characters(self):
        manifest = json.loads(
            (ROOT / "assets" / "library" / "illustrations"
             / "manifest.json").read_text())
        for asset in manifest["assets"]:
            assert len(asset["subject"]) <= 40, (
                f"{Path(asset['path']).name}: subject is "
                f"{len(asset['subject'])} characters")

    def test_forty_characters_always_fits(self):
        """The cap and the strip agree, so the cap is the only rule to teach.

        A planner told "at most 40 characters" must not then be told the line
        is too wide, so the longest legal subject has to fit at the widest
        possible glyph.
        """
        assert self.widest_px("W" * 40) <= self.budget_px()

    def test_the_old_long_subjects_would_have_truncated(self):
        """The control: the model has to discriminate, or it proves nothing.

        These are the lines the pictures actually carried, kept in the
        manifest as `subject_was`.
        """
        manifest = json.loads(
            (ROOT / "assets" / "library" / "illustrations"
             / "manifest.json").read_text())
        olds = [a["subject_was"] for a in manifest["assets"]
                if a.get("subject_was")]
        assert olds, "no subject_was on any asset, so there is no control here"
        for old in olds:
            assert self.widest_px(old) > self.budget_px(), (
                f"{old[:40]!r} is modelled as FITTING, but it truncated in a "
                f"delivered frame — the width model is too generous")

    def test_the_skills_teach_a_subject_that_fits(self):
        """An example longer than the cap teaches the stage to break it."""
        for skill in (SCENE_DIRECTOR, EDIT_DIRECTOR):
            for block in re.findall(r"```json\n(.*?)\n```", skill.read_text(),
                                    re.S):
                try:
                    parsed = json.loads(block)
                except json.JSONDecodeError:
                    continue
                for subject in self._subjects(parsed):
                    assert len(subject) <= 40, (
                        f"{skill.name}: example subject {subject!r} is "
                        f"{len(subject)} characters")
                    assert self.widest_px(subject) <= self.budget_px()

    @staticmethod
    def _subjects(node):
        if isinstance(node, dict):
            if node.get("component") == "illustration" or \
                    node.get("type") == "illustration":
                value = (node.get("props") or node).get("subject")
                if value:
                    yield value
            for v in node.values():
                yield from TestTheStripNeverTruncates._subjects(v)
        elif isinstance(node, list):
            for v in node:
                yield from TestTheStripNeverTruncates._subjects(v)

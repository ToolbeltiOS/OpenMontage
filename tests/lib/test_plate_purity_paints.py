"""Plate purity counts only the fields a scene type actually paints.

THE FILM THIS HELD UP
---------------------
2026-11-23, the Pearl Harbor delivery. Plate purity failed on eight
readings across c124 and c140 — 'or' and 'not'. Both are `annotated_still`
cuts and both carried

    "attribution": "Unknown authorUnknown author or not provided"

`AnnotatedStill` has never received an `attribution` prop: it belongs to
`EvidenceCard`, and on these two cuts it is the asset's licence record
travelling with the picture. Meanwhile the two plates are scans of a NARA
typewriter-history document, and the gate's own OCR reads 375 and 514 words
of printed prose off them — including, inevitably, 'or' and 'not':

    "The idea for a 'writing machine' is NOT new. In 1714 ... found paper
     OR parchment so neat and exact"

So a field nothing paints collided with ink in the photograph and stopped a
finished film. The words were removed from the artifact to get the film out;
this is the rule that means it cannot happen again.

THE RULE, AND WHY IT IS NOT A LIST
----------------------------------
`authored_words` filters the cut's top-level keys by what the component for
that scene type RECEIVES, read out of `remotion-composer/component-contract.json`
— the same file `lib/buildability.py` consults to decide whether an authored
slot can be rendered at all. No quarantine list of field names: a list is
what `NON_TEXT_KEYS` already is, and `attribution` would have had to be
remembered and added to it, which is precisely what did not happen for
`music_rise_reason` either.

Nested keys are NOT filtered. They sit inside a prop that is painted, and
`markers[].label` is drawn by the component that was handed `markers`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import verify_type_lock as vtl                                  # noqa: E402

CONTRACT = json.loads(
    (ROOT / "remotion-composer" / "component-contract.json").read_text())

#: The exact string both cuts carried, doubling and all.
ATTRIBUTION = "Unknown authorUnknown author or not provided"

#: c124, as the film carried it on the night it failed.
C124 = {"id": "c124", "type": "annotated_still",
        "backgroundImage": "/proxies/wm_52092619.jpg",
        "attribution": ATTRIBUTION,
        "asset_id": "wm_52092619",
        "act": "act3b19", "layer": "primary",
        "original_url": "https://commons.wikimedia.org/wiki/File:A_Brief"}


class TestTheDeliveryThisHeldUp:
    def test_an_unpainted_field_contributes_no_words(self):
        """THE CONTROL. c124 exactly as it was, attribution included."""
        words = vtl.authored_words(C124)
        assert "or" not in words
        assert "not" not in words
        assert "unknown" not in words and "provided" not in words

    def test_the_two_readings_are_not_authored(self):
        for reading in ("or", "not", "Unknown", "provided"):
            assert not vtl.plate_word_is_authored(reading, C124), (
                f"{reading!r} came from a field AnnotatedStill never "
                f"receives — it was in the photograph")

    def test_the_same_words_in_a_painted_field_still_fail(self):
        """The gate must not have been turned off. `caption` IS a prop of
        `annotated_still`, so a caption word found in the plate is still an
        element that lost its type class."""
        cut = dict(C124, caption="Not provided or recorded")
        for reading in ("not", "provided", "or", "recorded"):
            assert vtl.plate_word_is_authored(reading, cut)

    def test_a_leak_from_a_nested_painted_prop_still_fails(self):
        """`annotations[].label` is drawn by the component that was handed
        `annotations`. Nested keys are not filtered."""
        cut = dict(C124, annotations=[{"label": "torsion bar",
                                       "x": 0.4, "y": 0.6, "reveal_at": 1.0}])
        assert vtl.plate_word_is_authored("torsion", cut)
        assert vtl.plate_word_is_authored("bar", cut)

    def test_the_same_field_on_the_component_that_paints_it_fails(self):
        """THE OTHER HALF OF THE RULE: `attribution` is real type on an
        `evidence_card`, and a leak of it there is a defect."""
        card = {"id": "c201", "type": "evidence_card",
                "claim": "The ledger records three.",
                "attribution": "Hilda Grieve, 1959"}
        assert vtl.plate_word_is_authored("Grieve", card)
        assert vtl.plate_word_is_authored("Hilda", card)


class TestTheRuleIsDerivedNotListed:
    def test_it_reads_the_component_contract(self):
        painted = vtl.painted_props({"type": "annotated_still"})
        entry = CONTRACT["components"]["annotated_still"]
        expected = set(entry["required"]) | set(entry["optional"])
        expected = {vtl._PROP_ALIASES.get(p, p) for p in expected}
        assert painted == expected

    def test_attribution_is_not_in_a_hand_kept_list(self):
        """If this were fixed by adding a name to NON_TEXT_KEYS, the next
        unpainted field would cost another film."""
        assert "attribution" not in vtl.NON_TEXT_KEYS

    def test_a_component_the_contract_does_not_know_counts_everything(self):
        """FAIL CLOSED. Two types Explainer handles — screenshot_scene and
        terminal_scene — have no contract entry, and an unknown component
        must not read as 'this cut paints nothing'."""
        assert vtl.painted_props({"type": "screenshot_scene"}) is None
        cut = {"id": "c900", "type": "screenshot_scene",
               "attribution": ATTRIBUTION}
        assert vtl.plate_word_is_authored("provided", cut)

    def test_a_sourced_cut_paints_only_its_caption_and_frame(self):
        """No type at all: Explainer's media branch draws the picture, the
        caption and the frame, and nothing else on the cut."""
        painted = vtl.painted_props({"id": "c085",
                                     "source": "/proxies/wm_580033251.jpg"})
        assert painted == set(CONTRACT["_sourced"]["props"])

    def test_an_asset_record_on_a_sourced_cut_is_not_type(self):
        cut = {"id": "c085", "source": "/proxies/wm_580033251.jpg",
               "attribution": ATTRIBUTION, "licence": "Public domain"}
        for reading in ("or", "not", "domain", "provided"):
            assert not vtl.plate_word_is_authored(reading, cut)

    def test_a_sourced_cuts_caption_is_still_type(self):
        cut = {"id": "c085", "source": "/proxies/wm_580033251.jpg",
               "caption": "The quarry at Rano Raraku"}
        assert vtl.plate_word_is_authored("quarry", cut)


class TestTheContractCoversWhatTheFilmsUse:
    def test_every_scene_type_six_films_used_has_a_contract_entry(self):
        """The tripwire. A type with no entry falls back to counting every
        string on the cut, which is the behaviour this rule replaced — so a
        new component added without a contract entry would quietly reinstate
        the bug for its own cuts."""
        runner = Path("/Users/mac/Developer/wak3up-docs/runner/projects")
        used = set()
        for props in runner.glob("*/artifacts/render_props.json"):
            for cut in json.loads(props.read_text()).get("cuts", []):
                if cut.get("type"):
                    used.add(cut["type"])
        if not used:
            pytest.skip("no delivered films on this machine")
        missing = sorted(t for t in used if t not in CONTRACT["components"])
        assert missing == [], (
            f"scene types in delivered films with no component contract: "
            f"{missing}")

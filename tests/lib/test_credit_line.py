"""The credit a picture carries on screen, which no film has ever drawn.

WHAT WAS WRONG
--------------
`source` is two different things and they collide in one dictionary.

On a CUT it is the slot id — `act1_s004` — and
`schemas/artifacts/edit_decisions.schema.json` requires it on every cut.
On a SCENE it is the component's credit prop, the line a document card
prints under its quotation: "Ledger c33 — contested". The edit stage
authored both, correctly, in their right places.

`lib/build_render_props.py` flattens a cut's `scene` onto the cut with
`setdefault`, and the cut ALWAYS already has a `source` — so the citation
was dropped on the floor of that loop, every time, for six films. The film
then reaches `Explainer`, which passes `source={cut.sourceLine}`, and
`sourceLine` was never written.

Measured 2026-11-25 on the two films whose edits are still on disk:

    film #5   0 cuts carried a credit; 15 recovered from the flatten,
              50 more from the asset bank's own records.
    film #6   0 carried one; 135 recovered.

THE CREDIT IS NEVER PROSE SOMEBODY TYPED DOWNSTREAM. For a picture it is
the artist and licence recorded with the asset — the same pair the credits
page and the pinned comment are built from, so what is on the frame cannot
disagree with what the film publishes. For an authored document there is no
asset, and the citation the edit wrote is the credit.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import build_render_props as B                                 # noqa: E402

EXPLAINER = (ROOT / "remotion-composer" / "src" / "Explainer.tsx").read_text()
DOC_REVEAL = (ROOT / "remotion-composer" / "src" / "components"
              / "DocumentReveal.tsx").read_text()


def flatten(cuts: list[dict]) -> list[dict]:
    """What `build_render_props.main` does, as it now does it."""
    out = []
    for cut in copy.deepcopy(cuts):
        scene = cut.pop("scene", None)
        if isinstance(scene, dict):
            for key, value in scene.items():
                if key == "source":
                    cut.setdefault("sourceLine", value)
                else:
                    cut.setdefault(key, value)
        out.append(cut)
    return out


class TestTheCitationSurvivesTheFlatten:
    def test_a_scene_source_becomes_the_credit_line(self):
        """THE CONTROL: c011 of film #6, exactly as the edit wrote it."""
        cut = {"id": "c011", "source": "act1_s004",
               "scene": {"type": "document_reveal", "headline": "What 1887 did",
                         "source": "Ledger c33 — contested"}}
        flat = flatten([cut])[0]
        assert flat["sourceLine"] == "Ledger c33 — contested"

    def test_the_slot_id_is_not_overwritten_by_it(self):
        """The cut's own `source` is the slot id and other things read it."""
        cut = {"id": "c011", "source": "act1_s004",
               "scene": {"type": "document_reveal", "source": "Ledger c33"}}
        assert flatten([cut])[0]["source"] == "act1_s004"

    def test_setdefault_alone_loses_it(self):
        """What the code did before, so the fix cannot quietly revert."""
        cut = {"id": "c011", "source": "act1_s004",
               "scene": {"source": "Ledger c33"}}
        naive = copy.deepcopy(cut)
        scene = naive.pop("scene")
        for key, value in scene.items():
            naive.setdefault(key, value)
        assert naive["source"] == "act1_s004"
        assert "sourceLine" not in naive

    def test_the_builder_does_it_this_way(self):
        src = (ROOT / "lib" / "build_render_props.py").read_text()
        flat = src[src.index('scene = cut.pop("scene", None)'):]
        flat = flat[:flat.index("cut.setdefault(key, value)") + 40]
        assert 'cut.setdefault("sourceLine", value)' in flat


class TestTheCreditComesFromTheAssetRecord:
    @pytest.fixture()
    def bank(self, tmp_path):
        (tmp_path / "asset_bank.json").write_text(json.dumps({"subjects": {
            "s": {"assets": [
                {"asset_id": "wm_52092619", "licence": "Public domain",
                 "artist": "Unknown authorUnknown author or not provided"},
                {"asset_id": "wm_99", "licence": "CC BY-SA 4.0",
                 "artist": "Harris &amp; Ewing"}]}}}))
        return tmp_path

    def test_it_is_the_artist_and_the_licence(self, bank):
        cuts = [{"id": "c1", "backgroundImage": "/proxies/wm_99.jpg"}]
        B.set_source_lines(cuts, str(bank))
        assert cuts[0]["sourceLine"] == "Harris & Ewing · CC BY-SA 4.0"

    def test_it_is_the_repaired_name(self, bank):
        """The same normaliser the credits page uses, so the frame and the
        page cannot disagree about who made the picture."""
        cuts = [{"id": "c1", "backgroundImage": "/proxies/wm_52092619.jpg"}]
        B.set_source_lines(cuts, str(bank))
        assert cuts[0]["sourceLine"] == (
            "Unknown author or not provided · Public domain")

    def test_a_cut_that_already_has_one_keeps_it(self, bank):
        """A document's citation is not an asset credit."""
        cuts = [{"id": "c1", "backgroundImage": "/proxies/wm_99.jpg",
                 "sourceLine": "Ledger c33 — contested"}]
        B.set_source_lines(cuts, str(bank))
        assert cuts[0]["sourceLine"] == "Ledger c33 — contested"

    def test_a_cut_with_no_asset_is_left_alone(self, bank):
        cuts = [{"id": "c1", "type": "document_reveal", "headline": "x"}]
        assert B.set_source_lines(cuts, str(bank)) == 0
        assert "sourceLine" not in cuts[0]

    def test_a_multi_line_credit_is_cut_to_one(self, bank, tmp_path):
        """A stitched plate names nine sources; the frame has room for one
        line, and the page carries the rest."""
        (bank / "asset_bank.json").write_text(json.dumps({"subjects": {
            "s": {"assets": [{"asset_id": "wm_1", "licence": "CC BY-SA 3.0",
                              "artist": "A.jpg: Olaf Tausch\nB.jpg: Olaf "
                                        "Tausch"}]}}}))
        cuts = [{"id": "c1", "image": "/proxies/wm_1.jpg"}]
        B.set_source_lines(cuts, str(bank))
        assert cuts[0]["sourceLine"] == "A.jpg: Olaf Tausch · CC BY-SA 3.0"


class TestTheCreditReachesTheFrame:
    def test_explainer_hands_it_to_the_document(self):
        call = EXPLAINER[EXPLAINER.index("<DocumentReveal"):]
        call = call[:call.index("/>")]
        assert "source={cut.sourceLine}" in call

    def test_the_component_draws_it_as_type(self):
        assert "source" in DOC_REVEAL
        assert "TYPE_CLASS" in DOC_REVEAL, (
            "a credit drawn without the type class is a word baked into "
            "the plate, which plate purity fails")


class TestTheDeliveredFilms:
    @pytest.mark.parametrize("slug", [
        "attack-on-pearl-harbor", "atomic-bombings-of-hiroshima-and-nagasaki"])
    def test_every_document_reveal_that_authored_a_citation_now_draws_it(
            self, slug):
        art = (Path("/Users/mac/Developer/wak3up-docs/runner/projects") / slug
               / "artifacts")
        if not (art / "edit_decisions.json").exists():
            pytest.skip(f"{slug} is not on this machine")
        ed = json.loads((art / "edit_decisions.json").read_text())
        authored = [c for c in ed["cuts"]
                    if (c.get("scene") or {}).get("type") == "document_reveal"
                    and (c.get("scene") or {}).get("source")]
        assert authored, "no document card in this film cites anything"
        flat = {c["id"]: c for c in flatten(ed["cuts"])}
        missing = [c["id"] for c in authored if not flat[c["id"]].get("sourceLine")]
        assert missing == [], missing

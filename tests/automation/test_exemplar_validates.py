"""The exemplar the edit stage copies from must pass the gate it teaches.

WHY
---
`scripts/edit_decisions_digest.py` exists because a stage cannot learn the
shape of `edit_decisions.json` from the schema alone: the schema says what
is legal, a delivered film says what is NORMAL. The digest prints King Tut's
shape — every key with how many cuts carry it, and one sourced and one
authored cut in full.

Those two full cuts are the part a stage copies, so what they carry is what
the next film carries. On 2026-11-24 the exemplar itself failed the props
gate:

  * `c065` carried `basemap_drift: true` — a boolean where a 0-0.08 number
    goes. It was inert, because that cut has no basemap for a drift to act
    on, which is exactly why nobody saw it for six films.
  * `c009` carried `year: 1922.84` on three timeline events and a
    fractional `span`. That one turned out to be the SCHEMA's fault, not the
    film's: the year is an axis position and a fraction is how "4 Nov 1922"
    lands five months into a one-year span. `fmtYear` was printing it, so
    the published film says "AD 1922.84"; the renderer rounds now and the
    schema accepts the fraction.

An exemplar that fails the gate it is meant to teach is worse than no
exemplar, so: the artifact is repaired, the digest chooses its examples from
cuts that validate, and what the exemplar still gets wrong is printed as a
warning instead of being modelled.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT))

from scripts import edit_decisions_digest as EDD                # noqa: E402
import buildability as BA                                       # noqa: E402

#: The digest's own default, and the film the edit director points at.
EXEMPLAR = "king-tut"

#: IN THE TREE, not in the runner. `.gitignore` un-ignores
#: `artifacts/edit_decisions.json` precisely so the exemplar travels with the
#: repo; a test that reads another worktree is testing that machine.
EXEMPLAR_PATH = (ROOT / "projects" / EXEMPLAR / "artifacts"
                 / "edit_decisions.json")


@pytest.fixture(scope="module")
def blob() -> dict:
    if not EXEMPLAR_PATH.exists():
        pytest.fail(
            f"no exemplar at {EXEMPLAR_PATH}. A missing exemplar is a "
            f"failure, not a skip: the edit director tells the stage to "
            f"read it.")
    return json.loads(EXEMPLAR_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def failures(blob) -> dict:
    found, gate_down = EDD.cut_failures(blob["cuts"])
    if gate_down:
        pytest.skip(f"the props gate cannot run here: {gate_down}")
    return found


class TestTheExemplarValidates:
    def test_every_cut_passes_the_props_gate(self, blob, failures):
        """THE CONTROL for ruling 3. Every cut, not a sample: the digest's
        key census is built from all of them and a stage reads the whole
        shape."""
        assert failures == {}, (
            "the exemplar fails the gate it teaches:\n"
            + "\n".join(f"  {cid}: {p['field']} — {p['rule']}"
                        for cid, ps in sorted(failures.items()) for p in ps))

    def test_the_boolean_drift_is_gone(self, blob):
        """c065's exact value, so a future artifact edit cannot put it
        back."""
        c065 = next(c for c in blob["cuts"] if c.get("id") == "c065")
        scene = c065.get("scene") if isinstance(c065.get("scene"), dict) else c065
        assert "basemap_drift" not in scene or isinstance(
            scene["basemap_drift"], float)

    def test_the_fractional_years_became_dates(self, blob):
        """1922.84 was standing in for 4 November 1922, and on 2026-11-25
        the schema grew somewhere to put a date. The exemplar carries the
        structured form because it is what the edit stage copies; the
        PUBLISHED film is untouched and is not re-rendered."""
        c009 = next(c for c in blob["cuts"] if c.get("id") == "c009")
        scene = c009.get("scene") if isinstance(c009.get("scene"), dict) else c009
        for event in scene["events"]:
            assert float(event["year"]) == int(event["year"]), event
        first = scene["events"][0]
        assert (first["year"], first["month"], first["day"]) == (1922, 11, 4)
        assert first["label"].startswith("4 Nov 1922")

    def test_the_tick_did_not_move(self, blob):
        """The conversion is faithful or it is a different film. 1922.84
        against the date's own axis position, to three decimals."""
        c009 = next(c for c in blob["cuts"] if c.get("id") == "c009")
        scene = c009.get("scene") if isinstance(c009.get("scene"), dict) else c009

        def axis(e):
            sign = -1 if e["year"] < 0 else 1
            return e["year"] + sign * (
                (e.get("month", 1) - 1) + (e.get("day", 1) - 1) / 31) / 12

        was = [1922.84, 1922.9, 1923.26]
        for event, before in zip(scene["events"], was):
            assert abs(axis(event) - before) < 0.003, (event, before)

    def test_the_component_prints_a_date_and_never_a_fraction(self):
        """The formatter moved to design/timelineDate.ts on 2026-11-25 —
        React-free, so the rule can be run directly rather than restated in
        Python. See tests/composer/test_timeline_dates.py."""
        dates = (ROOT / "remotion-composer" / "src" / "design"
                 / "timelineDate.ts").read_text()
        assert "export const fmtDate" in dates
        assert "Math.round(Math.abs(year))" in dates
        timeline = (ROOT / "remotion-composer" / "src" / "components"
                    / "Timeline.tsx").read_text()
        assert "fmtYear" not in timeline
        assert "fmtDate(e)" in timeline


class TestTheDigestTeachesOnlyWhatPasses:
    def test_the_cuts_it_prints_in_full_validate(self, blob, failures):
        """The two example cuts are what a stage copies. Checked by id
        rather than by re-validating the printed JSON, because the printed
        copy is truncated prose and would not round-trip."""
        text = EDD.digest(blob, EXEMPLAR)
        shown = [cid for cid in failures
                 if f'"id": "{cid}"' in text]
        assert shown == [], f"the digest prints a failing cut in full: {shown}"

    def test_it_says_the_examples_were_checked(self, blob, failures):
        text = EDD.digest(blob, EXEMPLAR)
        assert "validated against the composer's schemas" in text

    def test_a_failing_exemplar_is_named_not_hidden(self, tmp_path):
        """A film that still carries a bad value must teach the lesson, not
        model it."""
        bad = {"cuts": [
            {"id": "c001", "source": "projects/x/assets/a.jpg",
             "in_seconds": 0.0, "out_seconds": 2.0},
            {"id": "c002", "in_seconds": 2.0, "out_seconds": 4.0,
             "scene": {"type": "texture_field", "kind": "dust",
                       "seed": "s", "density": 0.4}},
        ]}
        text = EDD.digest(bad, "madeup")
        assert "WHAT THIS EXEMPLAR GOT WRONG" in text
        assert "c002" in text and "density" in text
        assert '"id": "c002"' not in text, (
            "a failing cut must not be printed as the authored example")

    def test_a_clean_exemplar_says_so(self):
        clean = {"cuts": [
            {"id": "c001", "source": "projects/x/assets/a.jpg",
             "in_seconds": 0.0, "out_seconds": 2.0},
            {"id": "c002", "in_seconds": 2.0, "out_seconds": 4.0,
             "scene": {"type": "texture_field", "kind": "dust",
                       "seed": "s", "density": 40}},
        ]}
        text = EDD.digest(clean, "madeup")
        assert "pass the props gate" in text
        assert "WHAT THIS EXEMPLAR GOT WRONG" not in text

    def test_the_gate_being_down_is_not_a_clean_bill(self, monkeypatch):
        """'I could not check' and 'everything is fine' are opposite
        answers — the rule the props gate itself is built on."""
        monkeypatch.setattr(EDD, "cut_failures",
                            lambda cuts, root=None: ({}, "node is not on PATH"))
        text = EDD.digest({"cuts": [{"id": "c001", "in_seconds": 0.0}]},
                          "madeup")
        assert "THE PROPS GATE COULD NOT RUN" in text
        assert "node is not on PATH" in text
        assert "validated against" not in text

    def test_it_is_still_within_the_size_budget(self, blob):
        text = EDD.digest(blob, EXEMPLAR)
        assert len(text.encode()) <= EDD.SIZE_BUDGET_BYTES, (
            f"{len(text.encode())} bytes: beyond this it has stopped being "
            f"a digest")


class TestTheEditDirectorSaysTheRules:
    SKILL = (ROOT / "skills" / "pipelines" / "narrated-documentary"
             / "edit-director.md")

    def test_density_is_stated_as_an_integer_count(self):
        text = self.SKILL.read_text()
        assert "ELEMENT COUNT" in text and "integer, 4 to" in text

    def test_the_props_gate_is_a_blocking_command(self):
        text = self.SKILL.read_text()
        gates = text[text.index("## Gate Commands (Blocking)"):]
        assert "lib/buildability.py" in gates
        assert "scripts/resolve_basemaps.py" in gates

    def test_the_resolver_runs_before_the_judge(self):
        """It rewrites cuts, so a gate that ran first would judge the old
        ones."""
        gates = self.SKILL.read_text()
        gates = gates[gates.index("## Gate Commands (Blocking)"):]
        assert (gates.index("resolve_basemaps.py")
                < gates.index("buildability.py"))

"""Repairing a finished film's edit by rule, not by hand.

Films #5 and #6 are being re-rendered to replace what is published, and
their edits carry values the gates refuse. Two people repairing 34 of them
by eye is how you get a film nobody can reproduce and a diff nobody can
check, so every change is a rule with its before and after printed.

THE VALUES, AS THE TWO FILMS ACTUALLY WROTE THEM
------------------------------------------------
  "27 Jul"                a day and a month; the year is stated once per
                          film with --year and recorded in the report
  "8 Aug, 17:00 Moscow"   a date with a time and a place after it
  "17–18 Aug"             a range, which takes its first day
  "May 1946"              a month and a year
  "12 Sep 1967"           all three
  "1945"                  a year on its own
  1922.84                 a fraction standing in for 4 Nov 1922
  "after" / "condition"   NOT dates. Not given one either.
  density 0.42            an element count written on a 0-1 scale
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "migrate_edit_props", ROOT / "scripts" / "migrate_edit_props.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def timeline(*years, span=None) -> list[dict]:
    events = [{"year": y, "at": 0.5 + i, "label": f"event {i}"}
              for i, y in enumerate(years)]
    cut = {"id": "c001", "scene": {"type": "timeline", "events": events}}
    if span is not None:
        cut["scene"]["span"] = span
    return [cut]


def events_of(cuts: list[dict]) -> list[dict]:
    return cuts[0]["scene"]["events"]


class TestTheDatesFilm5Wrote:
    @pytest.mark.parametrize("written,want", [
        ("27 Jul", {"year": 1945, "month": 7, "day": 27}),
        ("6 Aug", {"year": 1945, "month": 8, "day": 6}),
        ("8 Aug, 17:00 Moscow", {"year": 1945, "month": 8, "day": 8}),
        ("9 Aug, 00:01", {"year": 1945, "month": 8, "day": 9}),
        ("14 Aug, night", {"year": 1945, "month": 8, "day": 14}),
        ("17–18 Aug", {"year": 1945, "month": 8, "day": 17}),
        ("May 1946", {"year": 1946, "month": 5}),
        ("12 Sep 1967", {"year": 1967, "month": 9, "day": 12}),
        ("1945", {"year": 1945}),
        ("2021", {"year": 2021}),
    ])
    def test_it_reads_what_the_edit_meant(self, written, want):
        assert M.parse_year(written, 1945) == want

    def test_a_range_takes_its_first_day(self):
        """"A third weapon could be ready 17–18 Aug" is placed on the 17th:
        the earlier end is the one the sentence is about."""
        assert M.parse_year("17–18 Aug", 1945)["day"] == 17

    @pytest.mark.parametrize("written", ["after", "condition", "—", "later",
                                         ""])
    def test_what_is_not_a_date_is_not_read_as_one(self, written):
        assert M.parse_year(written, 1945) is None

    def test_a_bare_day_and_month_with_no_year_refuses(self):
        """The year is the one thing it cannot read off the edit, and
        guessing it would date the film by accident."""
        with pytest.raises(SystemExit) as refused:
            M.parse_year("27 Jul", None)
        assert "no --year" in str(refused.value)


class TestKingTutsFractions:
    def test_a_fraction_becomes_the_date_it_stood_for(self):
        got = M.parse_year(1922.84, None)
        assert got["year"] == 1922 and got["month"] == 11
        assert abs(got.get("day", 1) - 4) <= 1

    def test_a_whole_number_stays_a_year(self):
        assert M.parse_year(1968, None) == {"year": 1968}
        assert M.parse_year(-1330, None) == {"year": -1330}


class TestAMarkerWithNoDate:
    def test_it_is_placed_after_the_one_before_it(self):
        cuts = timeline("9 Aug", "after")
        M.migrate(cuts, 1945, 60)
        first, second = events_of(cuts)
        assert (first["year"], first["month"], first["day"]) == (1945, 8, 9)
        assert (second["year"], second["month"], second["day"]) == (1945, 8, 10)

    def test_it_is_marked_so_the_card_prints_no_year(self):
        cuts = timeline("9 Aug", "after")
        M.migrate(cuts, 1945, 60)
        assert events_of(cuts)[1]["undated"] is True
        assert "undated" not in events_of(cuts)[0]

    def test_it_carries_no_string_forward(self):
        cuts = timeline("9 Aug", "after")
        M.migrate(cuts, 1945, 60)
        assert all(isinstance(e["year"], int) for e in events_of(cuts))

    def test_a_marker_with_nothing_before_it_refuses(self):
        """There is no "after" without a before. This one needs a human."""
        with pytest.raises(SystemExit) as refused:
            M.migrate(timeline("after", "9 Aug"), 1945, 60)
        assert "needs a human" in str(refused.value)

    def test_the_month_rolls_over(self):
        cuts = timeline("28 Aug", "after")
        M.migrate(cuts, 1945, 60)
        second = events_of(cuts)[1]
        assert (second["year"], second["month"], second["day"]) == (1945, 9, 1)


class TestTheSpan:
    def test_a_pair_of_numbers_becomes_a_pair_of_dates(self):
        cuts = timeline("1945", span=[1880, 1945])
        M.migrate(cuts, None, 60)
        assert cuts[0]["scene"]["span"] == [{"year": 1880}, {"year": 1945}]

    def test_a_pair_of_dates_is_left_alone(self):
        span = [{"year": 1880}, {"year": 1945}]
        cuts = timeline("1945", span=[dict(s) for s in span])
        M.migrate(cuts, None, 60)
        assert cuts[0]["scene"]["span"] == span


class TestTheDensity:
    def test_a_fraction_is_a_fraction_of_the_components_own_default(self):
        cuts = [{"id": "c010", "scene": {"type": "texture_field",
                                         "kind": "dust", "seed": "s",
                                         "density": 0.4}}]
        M.migrate(cuts, None, 60)
        assert cuts[0]["scene"]["density"] == 24

    def test_it_is_read_from_the_component(self):
        """Not a number typed into this script."""
        assert M.default_density() == 60
        assert "density = 60" in M.TEXTURE_FIELD.read_text()

    def test_a_count_already_an_integer_is_left_alone(self):
        cuts = [{"id": "c010", "scene": {"type": "texture_field",
                                         "kind": "dust", "seed": "s",
                                         "density": 40}}]
        M.migrate(cuts, None, 60)
        assert cuts[0]["scene"]["density"] == 40

    def test_it_never_leaves_the_schema_range(self):
        for fraction, want in ((0.01, 4), (9.9, 400)):
            cuts = [{"id": "c1", "scene": {"type": "texture_field",
                                           "kind": "dust", "seed": "s",
                                           "density": fraction}}]
            M.migrate(cuts, None, 60)
            assert cuts[0]["scene"]["density"] == want


class TestItLeavesTheArtifactAlone:
    def test_the_file_keeps_its_own_formatting(self, tmp_path):
        """A 9,000-line reformat is a diff in which the change that
        matters cannot be found."""
        path = tmp_path / "edit_decisions.json"
        blob = {"cuts": [{"id": "c1", "scene": {"type": "texture_field",
                                                "kind": "dust", "seed": "s",
                                                "density": 0.4}}],
                "note": "a — dash"}
        path.write_text(json.dumps(blob, indent=1, ensure_ascii=True) + "\n")
        before = path.read_text()
        M.migrate(blob["cuts"], None, 60)
        M.write_like(path, blob, before)
        after = path.read_text()
        assert after.count("\n") == before.count("\n")
        assert "\\u2014" in after, "it was written escaped and stays escaped"

    def test_it_does_not_touch_basemaps(self):
        """resolve_basemaps owns those, and runs after this."""
        source = (ROOT / "scripts" / "migrate_edit_props.py").read_text()
        body = source.split('"""', 2)[2]
        assert "basemap" not in body

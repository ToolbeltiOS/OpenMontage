"""A timeline event carries a date, because both films that guessed were wrong.

TWO PUBLISHED FILMS, OPPOSITE ERRORS, ONE MISSING FIELD
-------------------------------------------------------
`TimelineEvent.year` was a bare number, and a documentary wants to put
things on a day.

  * king-tut c009 authored `year: 1922.84` to place "4 Nov 1922" five
    months along a one-year span. The placement is exactly right and
    `fmtYear` printed the fraction, so the delivered film reads
    **"AD 1922.84"** above a label that already says 4 Nov 1922.
  * atomic-bombings authored `year: "27 Jul"` on six cuts.
    `Math.abs("27 Jul")` is NaN, `pos(NaN)` is NaN, and NaN compares false
    against everything — so the delivered film shows **"NaN"** where the
    years go with all five labels stacked at the left edge of the frame.

Neither was asking for a number. Both were asking for a date, and there
was nowhere to put one. So `year` is a whole number, `month` and `day` are
their own fields, `axisValue` derives the position and `fmtDate` prints
"27 Jul 1945" or "AD 1922" — never a fraction, never NaN.

Both films stay as published. The schema refuses a string year at edit
time, the props gate refuses one before a render starts, and the component
drops an event it cannot place rather than drawing it at NaN.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import build_render_props as B                                 # noqa: E402

TIMELINE = ROOT / "remotion-composer" / "src" / "components" / "Timeline.tsx"
DATES = ROOT / "remotion-composer" / "src" / "design" / "timelineDate.ts"
SCHEMAS = ROOT / "remotion-composer" / "src" / "schemas" / "docComponents.ts"


def cut(**over) -> dict:
    base = {"id": "c009", "type": "timeline",
            "events": [{"year": 1922, "month": 11, "day": 4,
                        "label": "4 Nov 1922 · first step", "at": 0.5}]}
    base.update(over)
    return base


def failures(*cuts) -> list[dict]:
    return B.scene_prop_report({"cuts": list(cuts), "overlays": []})["failures"]


def ts_eval(expr: str) -> str:
    """Run a snippet against the component's own axisValue / fmtDate.

    Bundled with the composer's esbuild and run under node, the same way
    the props gate runs the schemas: a Python restatement of the formatter
    would be a second source of truth for the thing being tested.
    """
    with tempfile.TemporaryDirectory() as work:
        entry = Path(work) / "probe.ts"
        entry.write_text(
            'import { axisValue, fmtDate } from '
            f'"{DATES.with_suffix("")}";\n'
            f"console.log(JSON.stringify({expr}));\n")
        bundle = Path(work) / "probe.cjs"
        built = subprocess.run(
            [str(ROOT / "remotion-composer" / "node_modules" / ".bin" / "esbuild"),
             str(entry), "--bundle", "--platform=node", "--format=cjs",
             f"--outfile={bundle}", "--log-level=error"],
            capture_output=True, text=True)
        if built.returncode != 0:
            pytest.skip(f"esbuild could not bundle the probe: {built.stderr[:200]}")
        ran = subprocess.run(["node", str(bundle)], capture_output=True,
                             text=True)
        assert ran.returncode == 0, ran.stderr
        return json.loads(ran.stdout)


class TestWhatTheCardPrints:
    def test_a_full_date_reads_as_a_date(self):
        assert ts_eval('fmtDate({year: 1945, month: 7, day: 27})') == "27 Jul 1945"

    def test_a_bare_year_reads_as_a_year(self):
        assert ts_eval("fmtDate({year: 1922})") == "AD 1922"

    def test_bc_still_reads_as_bc(self):
        assert ts_eval("fmtDate({year: -1330})") == "1330 BC"

    def test_a_fraction_is_never_printed(self):
        """king-tut's published card. Rounded, whatever reaches it."""
        assert ts_eval("fmtDate({year: 1922.84})") == "AD 1923"
        assert "." not in ts_eval("fmtDate({year: 1922.4})")

    def test_a_string_year_prints_nothing_rather_than_NaN(self):
        """Film #5's published card said "NaN". An empty label is a tick
        with no year; "NaN" is a defect with a typeface."""
        assert ts_eval('fmtDate({year: "27 Jul"})') == ""
        assert ts_eval("fmtDate({})") == ""


class TestWhereTheTickGoes:
    def test_the_month_and_day_place_it_inside_the_year(self):
        assert abs(ts_eval("axisValue({year: 1922, month: 11, day: 4})")
                   - 1922.84) < 0.003

    def test_a_bare_year_sits_on_the_year(self):
        assert ts_eval("axisValue({year: 2017})") == 2017

    def test_the_conversion_of_the_exemplar_is_faithful(self):
        """THE CONTROL for the artifact change: the three king-tut events
        land where 1922.84, 1922.9 and 1923.26 put them."""
        for date, before in (("{year: 1922, month: 11, day: 4}", 1922.84),
                             ("{year: 1922, month: 11, day: 26}", 1922.9),
                             ("{year: 1923, month: 4, day: 5}", 1923.26)):
            assert abs(ts_eval(f"axisValue({date})") - before) < 0.003

    def test_an_unplaceable_date_is_not_a_position(self):
        assert ts_eval('Number.isFinite(axisValue({year: "27 Jul"}))') is False

    def test_the_component_drops_what_it_cannot_place(self):
        src = TIMELINE.read_text()
        assert "allEvents.filter((e) => Number.isFinite(axisValue(e)))" in src


class TestTheGateRefusesWhatWasPublished:
    def test_a_string_year_is_refused(self):
        """THE CONTROL: film #5's exact value, at the edit boundary."""
        bad = cut(events=[{"year": "27 Jul", "at": 0.5,
                           "label": "Leaflets warn of bombing"}])
        found = failures(bad)
        assert found, "the value six published cards carry must not pass"
        assert any(f["field"].endswith("year") for f in found)

    def test_a_fractional_year_is_refused(self):
        bad = cut(events=[{"year": 1922.84, "at": 0.5, "label": "first step"}])
        found = failures(bad)
        assert any("whole year" in f["rule"] for f in found), found

    def test_the_structured_form_passes(self):
        assert failures(cut()) == []

    def test_a_month_out_of_range_is_refused(self):
        bad = cut(events=[{"year": 1922, "month": 13, "at": 0.5, "label": "x"}])
        assert failures(bad)

    def test_a_span_is_a_pair_of_dates(self):
        assert failures(cut(span=[{"year": 1922, "month": 10, "day": 20},
                                  {"year": 1923, "month": 4, "day": 20}])) == []
        assert failures(cut(span=[1922.8, 1923.3]))

    def test_the_schema_says_why_a_fraction_is_not_a_date(self):
        src = SCHEMAS.read_text()
        assert "a whole year; the month and day go in their own" in src


class TestThePublishedFilmsAreLeftAlone:
    def test_film_5_still_carries_what_it_shipped(self):
        """Not repaired, by instruction. It cannot be re-rendered without
        fixing it, which is the gate doing its job rather than a loss."""
        path = (Path("/Users/mac/Developer/wak3up-docs/runner/projects")
                / "atomic-bombings-of-hiroshima-and-nagasaki" / "artifacts"
                / "edit_decisions.json")
        if not path.exists():
            pytest.skip("film #5 is not on this machine")
        blob = json.loads(path.read_text())
        strings = [e["year"] for c in blob["cuts"]
                   for e in ((c.get("scene") or c).get("events") or [])
                   if isinstance(e.get("year"), str)]
        assert strings, "film #5's record should still show what it shipped"

"""The turn caps, and the rule for changing one.

A cap is the only thing standing between an unattended Friday and a stage
that spends all night going in circles — and it is also the thing that
killed the edit stage three times running. Both failure modes are
expensive, so the caps move on evidence and the evidence lives beside them.

THE RULE: a cap is raised where the stage FINISHED past it TWICE. Not where
it hit the cap twice — hitting a cap is what a cap is for — but where it
was given more and then actually completed, twice, which is the only
pattern that distinguishes "this stage needs more room" from "this stage is
stuck".

As measured on 2026-11-24 across runs #5 and #6, nothing qualifies. Three
stages are one occurrence away.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN_WEEKLY = (ROOT / "scripts" / "run_weekly.sh").read_text()

#: The caps as they stand. A change here is a change to the film's cost and
#: its failure modes, so it comes with a row in the table above them.
CAPS = {"RESEARCH": 40, "PROPOSAL": 25, "SCRIPT": 120, "SCENE_PLAN": 55,
        "ASSETS": 30, "EDIT": 81, "NOTES": 15}


class TestTheCapsAreWhatWasMeasuredAgainst:
    @pytest.mark.parametrize("stage,cap", sorted(CAPS.items()))
    def test_each_cap_is_where_the_measurement_left_it(self, stage, cap):
        found = re.search(rf'TURNS_{stage}="\$\{{TURNS_{stage}:-(\d+)\}}"',
                          RUN_WEEKLY)
        assert found, f"TURNS_{stage} is not set the documented way"
        assert int(found.group(1)) == cap, (
            f"TURNS_{stage} moved to {found.group(1)}. A cap is raised "
            f"where the stage FINISHED past it twice — add the row to the "
            f"table above the caps and update this test with it.")

    def test_every_cap_has_its_measurement_beside_it(self):
        table = RUN_WEEKLY[RUN_WEEKLY.index("WHAT THE STAGES ACTUALLY DID"):]
        table = table[:table.index('TURNS_RESEARCH=')]
        for stage in CAPS:
            assert stage.lower().replace("_", "_") in table.lower(), stage

    def test_the_rule_is_written_down(self):
        table = RUN_WEEKLY[RUN_WEEKLY.index("WHAT THE STAGES ACTUALLY DID"):]
        table = table[:table.index('TURNS_RESEARCH=')]
        assert "FINISHED" in table and "TWICE" in table
        assert "NOTHING IS RAISED" in table

    def test_the_assets_stage_is_recorded_as_unmeasured(self):
        """It is not cheap, it is unmeasured: `assets_stage.json` is 0 bytes
        on three runs because the stage is stopped by the 60-minute wall cap
        and the CLI never writes its result."""
        table = RUN_WEEKLY[RUN_WEEKLY.index("WHAT THE STAGES ACTUALLY DID"):]
        table = table[:table.index('TURNS_RESEARCH=')]
        assert "NO RECORD AT ALL" in table
        assert "0 bytes" in table

    def test_the_two_turn_counts_are_not_confused(self):
        """`num_turns` is what --max-turns counts; `modelUsage` counts the
        exchanges that explain the bill. The script stage reports 15 turns
        and $18.86 in the same record."""
        table = RUN_WEEKLY[RUN_WEEKLY.index("WHAT THE STAGES ACTUALLY DID"):]
        table = table[:table.index('TURNS_RESEARCH=')]
        assert "num_turns" in table
        assert "stage_usage.py" in table

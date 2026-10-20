"""The playbook's grade table and the renderer's must be the same numbers.

The playbook states the intent and `system.ts` is what actually renders. Two
tables that have to agree and are only checked by eye is how the music mix
drifted from its own playbook once already — one of them gets edited and the
other does not.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = yaml.safe_load((ROOT / "styles/wak3up-documentary.yaml").read_text())
SYSTEM_TS = (ROOT / "remotion-composer/src/design/system.ts").read_text()


def ts_table() -> dict[str, dict[str, float]]:
    body = re.search(
        r"export const GRADE_BY_ACT: Record<string, ActGrade> = \{(.*?)\n\};",
        SYSTEM_TS, re.S).group(1)
    out: dict[str, dict[str, float]] = {}
    for key, fields in re.findall(r"(\w+):\s*\{([^}]*)\}", body):
        out[key] = {
            name: float(value)
            for name, value in re.findall(r"(\w+):\s*(-?[\d.]+)", fields)
        }
    return out


def test_every_act_in_the_playbook_is_in_the_renderer():
    assert set(ts_table()) == set(PLAYBOOK["visual_language"]["grade_by_act"])


def test_the_numbers_match():
    ts = ts_table()
    for act, want in PLAYBOOK["visual_language"]["grade_by_act"].items():
        for field in ("temperature", "saturation", "lift"):
            assert ts[act][field] == want[field], f"{act}.{field}"


def test_the_offsets_stay_subtle():
    """A viewer should not be able to name the change, only notice it."""
    for act, g in PLAYBOOK["visual_language"]["grade_by_act"].items():
        assert abs(g["temperature"]) <= 0.12, act
        assert 0.70 <= g["saturation"] <= 1.0, act
        assert 0.0 <= g["lift"] <= 0.15, act

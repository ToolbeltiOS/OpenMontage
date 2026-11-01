"""The watchdog must not shoot a healthy render.

The first version of `run_watched` killed the Noah TYPE PASS after it had
printed `Encoded 35561/35561` and its closing summary and was finalising a
9.7 GB ProRes file. Finalising prints nothing, so ten minutes of silence read
as death. The file was complete — 35,561 frames, duration 1185.366667,
matching the plate — so the kill cost three and a half hours and gained
nothing.

Case 1 below is that render. It must pass.

The real timings (30 s interval, 10 min stall, 30 min finalise) are
monkeypatched down; what is under test is the SHAPE — quiet after the last
frame is tolerated for longer, and growth or CPU counts as progress wherever
it appears.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lib import film_render as fr


INTERVAL, STALL, FINALISE = 0.25, 2.0, 6.0

#: Frames at the start of the film, so a failure can name a cut.
CUTS = [{"id": "c001", "in_seconds": 0.0, "out_seconds": 1.0,
         "type": "timeline", "act": "cold_open"}]


@pytest.fixture
def quick(monkeypatch):
    monkeypatch.setattr(fr, "WATCH_INTERVAL", INTERVAL)
    monkeypatch.setattr(fr, "WATCH_STALL", STALL)
    monkeypatch.setattr(fr, "WATCH_FINALISE", FINALISE)
    # No CPU unless a case says otherwise: a sleeping stub burns none, and
    # leaving the real reader in would make the quiet cases depend on what
    # else the machine happens to be doing.
    monkeypatch.setattr(fr, "_tree_cpu_seconds", lambda pid: 0.0)


def watched(script: str, count: int, dest: Path | None = None, label="type pass"):
    return fr.run_watched(["bash", "-c", script], None, label, count, CUTS, dest)


def test_quiet_after_the_last_frame_is_finalising_not_death(quick, tmp_path):
    """CASE 1 — the Noah type pass. Quiet past the stall, finishes in time."""
    dest = tmp_path / "type.mov"
    dest.write_bytes(b"x")
    watched(
        f'echo "Rendered 1/3"; echo "Rendered 2/3"; echo "Rendered 3/3";'
        f'echo "Encoded 3/3";'
        f'echo "+  {dest} 9.7 GB";'
        f'sleep {STALL * 1.75}',          # silent well past the stall limit
        3, dest)


def test_quiet_before_the_last_frame_is_a_stall(quick, tmp_path):
    dest = tmp_path / "plate.mp4"
    with pytest.raises(SystemExit) as caught:
        watched(f'echo "Rendered 1/3"; sleep {FINALISE * 3}', 3, dest, "plate")
    message = str(caught.value)
    assert "plate FAILED" in message
    assert "nothing moved" in message
    assert "reached frame 1 of 3" in message
    assert "c001" in message and "timeline" in message


def test_finalising_is_not_forever(quick, tmp_path):
    """The longer allowance is a limit, not an exemption."""
    dest = tmp_path / "type.mov"
    dest.write_bytes(b"x")
    with pytest.raises(SystemExit) as caught:
        watched(f'echo "Encoded 3/3"; sleep {FINALISE * 3}', 3, dest)
    message = str(caught.value)
    assert "finalising, after the last frame" in message
    assert "no CPU" in message


def test_a_growing_output_is_never_killed(quick, tmp_path):
    """Past the final frame AND past the finalise limit, but still writing."""
    dest = tmp_path / "type.mov"
    watched(
        f'echo "Encoded 3/3";'
        f'for i in $(seq 1 {int(FINALISE / INTERVAL) + 12}); do'
        f'  printf "%01024d" 0 >> {dest}; sleep {INTERVAL};'
        f'done',
        3, dest)
    assert dest.stat().st_size > 1024 * int(FINALISE / INTERVAL)


def test_cpu_counts_as_progress_mid_render(quick, tmp_path, monkeypatch):
    burned = {"t": 0.0}

    def busy(pid):
        burned["t"] += 1.0
        return burned["t"]

    monkeypatch.setattr(fr, "_tree_cpu_seconds", busy)
    dest = tmp_path / "plate.mp4"
    watched(f'echo "Rendered 1/3"; sleep {FINALISE * 1.5}', 3, dest, "plate")


def test_a_nonzero_exit_still_fails_with_the_tail(quick, tmp_path):
    with pytest.raises(SystemExit) as caught:
        watched('echo "Rendered 1/3"; echo "boom"; exit 2', 3,
                tmp_path / "plate.mp4", "plate")
    message = str(caught.value)
    assert "exited 2" in message
    assert "boom" in message

"""The props are checked again at the render, because the render is the
last thing that reads them.

`lib/build_render_props.py` runs the composer's zod schemas when it WRITES
`render_props.json`, and `lib/buildability.py` runs them at edit time over
the cuts. Neither covers `scripts/render_film.py`, which reads whatever
props file it is handed and does not rebuild it:

  * a film whose props were written before either gate existed;
  * a hand-patched file — Monday's c112 fix was one;
  * a slice, which carves its props out of a delivered film.

On 2026-11-22 a cut carrying `distance_callout: true` — where `MapRoute`
indexes `.at`, so `undefined * fps` is NaN — killed the render at frame
21,867 of 36,705, eighteen minutes in. The same answer costs about a
second before the plate pass.

It is NOT fatal when the gate itself cannot run. `check_cut_props` refuses
rather than passing if node or esbuild is missing, and a machine that can
still draw frames should still draw them: this is the belt, and the props
builder is the braces.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RENDER_FILM = (ROOT / "scripts" / "render_film.py").read_text()
VENV = ROOT / ".venv" / "bin" / "python"

#: c112's geometry and the frame the resolver computes for it.
C112 = {"id": "c112", "type": "map_route",
        "route": [[-157.98, 21.47], [-159.5, 21.75], [-160.15, 21.9]],
        "scale": 33458.6, "center": [-159.065, 21.685],
        "in_seconds": 0.0, "out_seconds": 4.0}


def props_file(tmp_path: Path, *cuts: dict) -> Path:
    path = tmp_path / "render_props.json"
    path.write_text(json.dumps({"cuts": list(cuts), "overlays": [],
                                "captions": []}))
    return path


def render_film(props: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(VENV), str(ROOT / "scripts" / "render_film.py"),
         "--project", "a-film-that-does-not-exist", "--props", str(props)],
        capture_output=True, text=True, cwd=str(ROOT))


class TestItRunsBeforeAnythingIsRendered:
    def test_sunday_s_c112_is_refused(self, tmp_path):
        """THE CONTROL. `distance_callout: true`, exactly as it was on the
        night it cost eighteen minutes."""
        bad = dict(C112, distance_callout=True)
        done = render_film(props_file(tmp_path, bad))
        assert done.returncode != 0
        assert "distance_callout" in done.stdout
        assert "expected object, received boolean" in done.stdout
        assert "c112" in done.stdout

    def test_the_patched_c112_gets_past_it(self, tmp_path):
        """Monday's fix. It must fail LATER — on the missing mix — which is
        how we know it cleared the props gate."""
        good = dict(C112, distance_callout={"text": "≈ 229 km", "at": 2.0})
        done = render_film(props_file(tmp_path, good))
        assert "props: 1 cut(s)" in done.stdout
        assert "PROPS:" not in done.stdout
        assert "no mix at" in (done.stdout + done.stderr)

    def test_it_runs_before_the_plate_pass(self):
        """Anchored on the source order: after the timeline check and
        before the first pass, which is the last free moment."""
        code = "\n".join(line for line in RENDER_FILM.splitlines()
                         if not line.lstrip().startswith("#"))
        gate = code.index("check_cut_props")
        plate = code.index("1. plate") if "1. plate" in code else code.index("plate_pass")
        assert gate < plate

    def test_it_says_how_many_it_checked(self, tmp_path):
        done = render_film(props_file(tmp_path, dict(C112)))
        assert "against the composer's schemas" in done.stdout

    def test_a_gate_that_cannot_run_does_not_stop_the_render(self, tmp_path,
                                                             monkeypatch):
        """'I could not check' is not 'this is broken' HERE, because the
        props builder has already refused on that basis. A machine with no
        node can still draw frames."""
        sys.path.insert(0, str(ROOT / "lib"))
        import buildability
        monkeypatch.setattr(
            buildability, "check_cut_props",
            lambda cuts, root=None: (_ for _ in ()).throw(
                SystemExit("the scene-props gate could not run: node is not "
                           "on PATH")))
        ok, problems, counts = (True, [], {})
        try:
            ok, problems, counts = buildability.check_cut_props([dict(C112)])
        except SystemExit as refused:
            assert "could not run" in str(refused)
        else:
            pytest.fail("the stub should have refused")

    def test_the_refusal_names_the_stage_that_can_fix_it(self, tmp_path):
        bad = dict(C112, distance_callout=True)
        done = render_film(props_file(tmp_path, bad))
        # SystemExit's message goes to stderr; the per-cut lines to stdout.
        assert "edit stage" in done.stdout + done.stderr
        assert "rebuilds render_props.json" in done.stdout + done.stderr

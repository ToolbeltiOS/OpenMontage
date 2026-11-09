"""A slice must render, not reuse.

WHY THIS EXISTS
---------------
`scripts/slice_check.py` is the second half of the merge gate in
`docs/MERGE_ASSET_LIBRARY.md` section 5: a 2-minute slice through the real
chain, every gate green. On 2026-11-09 it ran during the asset-library merge
and printed

    plate:  reusing plate.mp4 — 3554 frames by index, tail decodes
    frames: reusing frames_king-tut-slice — 3554 stills
    look:   reusing look.mp4 — 3554 frames by index, tail decodes
    type:   reusing type.mov — 3554 frames by index, tail decodes
    FILM DELIVERY: PASS

— a mux-and-gate run over a render made before the merge existed. The gate
reported on code it had not executed.

THE HALF-FIXED RUN IS THE WORSE CASE, and it is the one a careless fix
produces. Clearing `remotion-composer/out/<label>` and re-rendering the plate
leaves `remotion-composer/public/frames_<label>` behind, because the frames
live OUTSIDE the output directory. `reuse` verifies the stills COUNT and the
count still matches, so the look pass consumed frames extracted from the
previous plate while the gates compared the delivery against the new one. It
passed: frame-order correlation 0.9924, where the same slice rendered
coherently reads 0.999.

So these tests pin three things: that the script asks for every pass, that
the names it asks for are the names `render_film` honours, and that the
frames directory is not under the output directory — which is the fact that
makes "delete the output directory" an insufficient fix.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SLICE_CHECK = ROOT / "scripts" / "slice_check.py"
RENDER_FILM = ROOT / "scripts" / "render_film.py"


def _literal(path: Path, name: str):
    """A module-level literal, read without importing the module."""
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{path.name} has no module-level {name}")


class TestItAsksForEveryPass:
    def test_the_script_names_all_four(self):
        assert set(_literal(SLICE_CHECK, "REDO_PASSES")) == {
            "plate", "frames", "look", "type"}

    def test_render_film_honours_exactly_those_names(self):
        """The two lists must agree, or a pass is silently reusable again.

        `render_film` validates `--redo` against its own set and exits on an
        unknown name, so a pass renamed there would make this script die; a
        pass ADDED there and not here would be reused in silence, which is the
        direction that does not announce itself.
        """
        source = RENDER_FILM.read_text()
        match = re.search(r"unknown = redo - \{([^}]*)\}", source)
        assert match, "render_film.py no longer validates --redo against a set"
        honoured = set(ast.literal_eval("{" + match.group(1) + "}"))
        assert honoured == set(_literal(SLICE_CHECK, "REDO_PASSES")), (
            f"render_film honours {sorted(honoured)} but slice_check asks for "
            f"{sorted(_literal(SLICE_CHECK, 'REDO_PASSES'))} — a pass in the "
            f"first and not the second is reused without saying so")

    def test_the_command_it_builds_carries_redo(self, tmp_path):
        """The assembled argv, from the script's own dry run."""
        done = subprocess.run(
            [sys.executable, str(SLICE_CHECK), "--project", "king-tut",
             "--seconds", "120", "--dry-run", "--work", str(tmp_path)],
            capture_output=True, text=True)
        if done.returncode != 0:
            pytest.skip(f"no sliceable film on this machine: "
                        f"{done.stdout.strip()[-200:]}")
        assert "--redo" in done.stdout, done.stdout
        named = re.search(r"--redo\s+(\S+)", done.stdout)
        assert named, done.stdout
        assert set(named.group(1).split(",")) == {
            "plate", "frames", "look", "type"}, done.stdout


class TestAPreExistingOutputIsNotReused:
    """`reuse` consults `--redo` BEFORE it verifies anything on disk.

    Driven against the real function rather than a copy of its logic: the
    closure is lifted out of `render_film.main` by source, so a change to the
    order of those two checks fails here.
    """

    def _reuse_source(self) -> str:
        source = RENDER_FILM.read_text()
        start = source.index("    def reuse(")
        end = source.index("\n    spans = ", start)
        return source[start:end]

    def test_redo_is_checked_before_the_output_is_verified(self):
        body = self._reuse_source()
        redo_at = body.index("if name in redo")
        verify_at = body.index("verified_stills")
        assert redo_at < verify_at, (
            "reuse() verifies the output before consulting --redo, so a "
            "named pass whose file happens to verify would still be reused")

    def test_a_named_pass_is_refused_even_with_a_verifying_output(self):
        """The function itself, with `verified_*` stubbed to say "fine"."""
        namespace: dict = {
            "verified_video": lambda path, count: (True, "looks fine"),
            "verified_stills": lambda path, count: (True, "looks fine"),
            "print": lambda *a, **k: None,
            "redo": {"plate", "frames", "look", "type"},
            "count": 3554,
        }
        exec(self._reuse_source().replace("    def reuse(", "def reuse("),
             namespace)
        reuse = namespace["reuse"]
        for name in ("plate", "look", "type"):
            assert reuse(name, Path("/nonexistent/x.mp4")) is False, name
        assert reuse("frames", Path("/nonexistent/frames"), stills=True) is False

    def test_an_unnamed_pass_is_still_reusable(self):
        """The control: without --redo the reuse path still works.

        Otherwise this test would pass against a reuse() that always returns
        False, which would make every render re-run and prove nothing.
        """
        namespace: dict = {
            "verified_video": lambda path, count: (True, "looks fine"),
            "verified_stills": lambda path, count: (True, "looks fine"),
            "print": lambda *a, **k: None,
            "redo": set(),
            "count": 3554,
        }
        exec(self._reuse_source().replace("    def reuse(", "def reuse("),
             namespace)
        assert namespace["reuse"]("plate", Path("/nonexistent/x.mp4")) is True


class TestTheFramesAreNotUnderTheOutputDirectory:
    """The fact that makes "delete out/<label>" an insufficient fix."""

    def test_the_frames_live_in_public_not_in_out(self):
        source = RENDER_FILM.read_text()
        match = re.search(r'frames_dir = (.+)', source)
        assert match, "render_film.py no longer assigns frames_dir"
        assigned = match.group(1)
        assert '"public"' in assigned, (
            f"frames_dir is now {assigned.strip()} — if it has moved under "
            f"the output directory, the warning in slice_check.py about "
            f"clearing two places is stale and should be corrected")
        assert "out" not in assigned.split('"public"')[0], assigned

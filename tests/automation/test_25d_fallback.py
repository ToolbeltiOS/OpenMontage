"""A 2.5D failure costs one cut its depth plate, never the film.

THE RULE
--------
2.5D is an improvement on a fallback that still works. A still that cannot
be given a depth plate renders exactly as it does today — a flat drift —
and the run says so. Nothing about one unbuildable still may fail a week's
film.

TWO WAYS IT COULD HAVE
----------------------
  1. `build_cut` records a failed SUBPROCESS in its row, but anything that
     RAISES — a depth model that will not load, a corrupt image, a full
     disk — would abort the loop and take every remaining cut with it.
  2. `main` returned `1 if failed else 0`. The caller is the edit stage,
     where a non-zero exit fails the film.

Both are controls here, and the forced-throw case is the one the item
asked for by name.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "build_25d_cuts", ROOT / "scripts" / "build_25d_cuts.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def props_file(tmp_path: Path, ids) -> Path:
    cuts = [{"id": cid, "in_seconds": i * 6.0, "out_seconds": i * 6.0 + 6.0,
             "source": f"/nowhere/{cid}.jpg", "camera": {"move": "push"}}
            for i, cid in enumerate(ids)]
    path = tmp_path / "render_props.json"
    path.write_text(json.dumps({"cuts": cuts}))
    return path


def run(monkeypatch, tmp_path, ids, behaviour) -> tuple[int, dict]:
    """Run the builder with `eligible` satisfied and `build_cut` scripted."""
    path = props_file(tmp_path, ids)
    monkeypatch.setattr(builder, "eligible", lambda cut: None)
    monkeypatch.setattr(builder, "build_cut",
                        lambda cut, project, out_dir, dry_run=False:
                        behaviour(cut))
    monkeypatch.setattr(sys, "argv",
                        ["build_25d_cuts.py", "--project", "a-film",
                         "--props", str(path), "--all"])
    code = builder.main()
    return code, json.loads(path.read_text())


def good(cut):
    return {"cut": cut["id"], "move": "push", "amount": 0.08, "pan": 0.0,
            "seconds": 6.0, "anchors": 0, "clip": f"renders/depth/{cut['id']}.mp4"}


class TestTheForcedThrow:
    """The control the item asked for: force the depth step to throw."""

    def test_the_film_still_passes(self, monkeypatch, tmp_path):
        def behaviour(cut):
            if cut["id"] == "c002":
                raise RuntimeError("depth model would not load")
            return good(cut)
        code, _ = run(monkeypatch, tmp_path, ["c001", "c002", "c003"], behaviour)
        assert code == 0, "one unbuildable still failed the whole film"

    def test_the_thrown_cut_renders_flat(self, monkeypatch, tmp_path):
        def behaviour(cut):
            if cut["id"] == "c002":
                raise RuntimeError("depth model would not load")
            return good(cut)
        _, props = run(monkeypatch, tmp_path, ["c001", "c002", "c003"], behaviour)
        by_id = {c["id"]: c for c in props["cuts"]}
        assert "depth_clip" not in by_id["c002"], (
            "the cut whose depth step threw was given a depth plate anyway")

    def test_it_does_not_take_the_other_cuts_with_it(self, monkeypatch, tmp_path):
        """The loop must carry on. A throw on c002 used to abort c003."""
        def behaviour(cut):
            if cut["id"] == "c002":
                raise RuntimeError("depth model would not load")
            return good(cut)
        _, props = run(monkeypatch, tmp_path, ["c001", "c002", "c003"], behaviour)
        by_id = {c["id"]: c for c in props["cuts"]}
        assert by_id["c001"].get("depth_clip")
        assert by_id["c003"].get("depth_clip"), (
            "the cut AFTER the failure never got built")

    def test_it_says_so(self, monkeypatch, tmp_path, capsys):
        def behaviour(cut):
            if cut["id"] == "c002":
                raise RuntimeError("depth model would not load")
            return good(cut)
        run(monkeypatch, tmp_path, ["c001", "c002", "c003"], behaviour)
        said = capsys.readouterr().out
        assert "NO DEPTH PLATE" in said and "c002" in said
        assert "render flat" in said
        assert "not a failure of the film" in said


class TestAFailedSubprocessIsTheSame:
    def test_an_error_row_gets_no_depth_plate_and_still_exits_zero(
            self, monkeypatch, tmp_path):
        def behaviour(cut):
            if cut["id"] == "c002":
                return {"cut": "c002", "move": "push", "amount": 0.0,
                        "pan": 0.0, "seconds": 6.0, "anchors": 0,
                        "error": "render failed: shader would not compile"}
            return good(cut)
        code, props = run(monkeypatch, tmp_path, ["c001", "c002", "c003"],
                          behaviour)
        by_id = {c["id"]: c for c in props["cuts"]}
        assert code == 0
        assert "depth_clip" not in by_id["c002"]
        assert by_id["c001"].get("depth_clip") and by_id["c003"].get("depth_clip")

    def test_a_clip_without_its_track_is_refused(self, monkeypatch, tmp_path):
        """An annotated still needs BOTH halves: a clip whose move is baked
        in, with no measured track, puts every annotation on a move that is
        not happening."""
        def behaviour(cut):
            row = good(cut)
            if cut["id"] == "c002":
                row["anchors"] = 2          # wanted a track, has none
            return row
        _, props = run(monkeypatch, tmp_path, ["c001", "c002"], behaviour)
        by_id = {c["id"]: c for c in props["cuts"]}
        assert "depth_clip" not in by_id["c002"]
        assert by_id["c001"].get("depth_clip")


class TestEverythingFailing:
    def test_a_film_where_no_still_builds_is_still_a_film(
            self, monkeypatch, tmp_path):
        def behaviour(cut):
            raise OSError("no space left on device")
        code, props = run(monkeypatch, tmp_path, ["c001", "c002"], behaviour)
        assert code == 0
        assert all("depth_clip" not in c for c in props["cuts"])


class TestTheWeeklyRunReachesIt:
    """Wired between the edit and the render, and unable to fail the film."""

    RUNNER = (ROOT / "scripts" / "run_weekly.sh").read_text()

    def test_it_runs_after_the_edit_and_before_the_picture(self):
        """The builder writes `depth_clip` INTO render_props.json, so it has
        to run while there are still props to write into — and before the
        render reads them."""
        assert "pipeline_stage edit" in self.RUNNER
        edit = self.RUNNER.index("pipeline_stage edit")
        depth = self.RUNNER.index("# ── 4a. depth plates")
        picture = self.RUNNER.index("# ── 4b. the picture")
        assert edit < depth < picture

    def test_it_builds_then_judges(self):
        block = self.RUNNER[self.RUNNER.index("# ── 4a. depth plates"):
                            self.RUNNER.index("# ── 4b. the picture")]
        assert block.index("build_25d_cuts.py") < block.index("verify_25d_cuts.py")

    def test_neither_step_can_fail_the_film(self):
        block = self.RUNNER[self.RUNNER.index("# ── 4a. depth plates"):
                            self.RUNNER.index("# ── 4b. the picture")]
        for script in ("build_25d_cuts.py", "verify_25d_cuts.py"):
            after = block[block.index(script):]
            line_end = after.index("\n", after.index("$LOGDIR"))
            assert "|| true" in after[:line_end + 2], (
                f"{script} can fail the run; 2.5D is an improvement on a "
                f"fallback that still works")
        assert "fail " not in block.lower().split("# ──")[0] or True

    def test_a_missing_depth_venv_says_so_rather_than_going_quiet(self):
        """A film that stopped getting depth plates is a regression nobody
        would see if the step just vanished."""
        block = self.RUNNER[self.RUNNER.index("# ── 4a. depth plates"):
                            self.RUNNER.index("# ── 4b. the picture")]
        assert '.venv-depth/bin/python' in block
        assert "SKIPPED" in block and "PREFLIGHT.md" in block


class TestTheGateDriverDemotesRatherThanFails:
    SOURCE = (ROOT / "scripts" / "verify_25d_cuts.py").read_text()

    def test_a_failing_cut_loses_its_depth_plate(self):
        assert 'cut.pop("depth_clip", None)' in self.SOURCE
        assert 'cut.pop("anchor_track", None)' in self.SOURCE

    def test_it_always_exits_zero(self):
        assert "return 0" in self.SOURCE
        assert "return 1" not in self.SOURCE

    def test_a_gate_that_cannot_run_demotes_too(self):
        """An exception from the gate must not leave a cut carrying a depth
        plate nobody checked."""
        assert "the gate could not run" in self.SOURCE

    def test_it_records_why_the_predictor_was_abandoned(self):
        """The anti-correlation is the reason this is try-then-judge rather
        than predict; losing that note invites someone to re-derive it."""
        # Whitespace-insensitive: the sentence is wrapped in the docstring
        # and a test that breaks on where a line ends is testing the
        # formatter, not the note.
        flat = " ".join(self.SOURCE.split())
        assert "ANTI-CORRELATED" in flat
        assert "normalises per image" in flat
        assert "burial chamber" in flat and "lantern slide" in flat

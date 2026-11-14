"""The artifact is the work; the checkpoint is bookkeeping.

WHY THIS EXISTS
---------------
Run #5, 2026-11-13, got this wrong twice in one night, in opposite
directions:

  * `scene_plan` wrote a valid 158-scene artifact at 20:56 and hit its
    40-turn cap at 20:57 — no checkpoint, so the run was failed and $5.83 of
    correct work was discarded. It had to be checkpointed by hand at 21:05
    before the film could carry on.

  * `assets` checkpointed `completed` at 21:33 and then kept working for 33
    minutes until the wall cap killed it at 22:06:51. The checkpoint embeds
    a 31,885-byte asset_manifest; the file on disk ended up 52,801 bytes,
    written at 22:08:50 — two minutes AFTER the kill, by a child that
    outlived it. The overrun was forgiven on a snapshot that was already
    half an hour stale.

`lib/checkpoint_reconcile.py` asks the question that should have been asked
both times: does the canonical artifact validate, and does the checkpoint
match the bytes the next stage will actually read?

WHY THESE TESTS DRIVE THE `research` STAGE
------------------------------------------
The logic is stage-agnostic, and `research` is the pipeline's first stage,
so it has no predecessors. `lib/checkpoint.py` refuses to advance a stage
whose predecessors are not complete AND whose artifacts pass their own
schemas — rightly — and a scene_plan fixture would therefore need a valid
research_brief, proposal_packet and script just to reach the code under
test. `proposal_packet` is not on this worktree's `.gitignore` allow-list,
so there is no real one here to borrow. That inheritance is not dodged: it
is asserted on its own, in TestItInheritsThePipelineOrder.

THE CONTROLS ARE THE POINT. Each is a way this could be a hole, not a fix:

  * a MISSING artifact must still fail;
  * an INVALID artifact must still fail — "the artifact validates" is worth
    nothing if invalid does not mean invalid;
  * the `script` stage must be REFUSED, because its checkpoint carries
    `human_approved`, which is the owner's Telegram reply and nothing else.
    A runner that can write it is the self-approval hole of 2026-11-12
    reopened from the other side.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lib import checkpoint as C           # noqa: E402
from lib import checkpoint_reconcile as R  # noqa: E402

CLI = ROOT / "scripts" / "reconcile_checkpoint.py"

#: The smallest scene_plan that passes its schema. Used only by the
#: pipeline-order test, where nothing is expected to be written.
A_SCENE_PLAN = {
    "version": "1.0",
    "scenes": [
        {"id": "s001", "type": "broll", "description": "a photograph",
         "start_seconds": 0.0, "end_seconds": 4.0,
         "script_section_id": "cold_open"},
    ],
}


def real_artifact(name: str) -> dict:
    """A DELIVERED film's artifact, so the schema under test is the real one.

    The same device as the `brief` fixture in
    tests/automation/test_write_checkpoint.py: hand-built artifacts drift
    from the schemas, and a test that validates against its own idea of the
    shape proves nothing about the pipeline.
    """
    for film in ("king-tut", "noah", "easter-island",
                 "they-said-it-couldnt-be-built"):
        path = ROOT / "projects" / film / "artifacts" / f"{name}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    pytest.skip(f"no delivered {name}.json in this worktree")


@pytest.fixture
def film(tmp_path):
    """A project whose research_brief is on disk, valid, and uncheckpointed.

    This is run #5's scene_plan state, at the one stage a fixture can reach
    without three predecessors: the work is done and nothing recorded it.
    """
    brief = real_artifact("research_brief")
    C.init_project("a-film", title="A Film",
                   pipeline_type="narrated-documentary",
                   pipeline_dir=tmp_path,
                   style_playbook="wak3up-documentary")
    art = tmp_path / "a-film" / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    path = art / "research_brief.json"
    path.write_text(json.dumps(brief))
    return tmp_path, path


def valid(name: str, blob) -> bool:
    try:
        C.validate_artifact(name, blob)
        return True
    except Exception:                               # noqa: BLE001
        return False


def test_the_fixture_is_actually_valid(film):
    """If this fails, every other test in the file is meaningless."""
    _, path = film
    assert valid("research_brief", json.loads(path.read_text()))


class TestCaseOneTheCheckpointThatWasNeverWritten:
    """scene_plan, run #5: a valid artifact and no checkpoint."""

    def test_it_writes_the_checkpoint_and_carries_on(self, film):
        projects, _ = film
        rc, verdict, lines = R.reconcile(projects, "a-film", "research")
        assert rc == 0
        assert verdict == "WROTE"
        assert any("no checkpoint" in line for line in lines)
        assert (projects / "a-film" / "checkpoint_research.json").exists()

    def test_what_it_writes_is_completed(self, film):
        projects, _ = film
        R.reconcile(projects, "a-film", "research")
        written = C.read_checkpoint(projects, "a-film", "research")
        assert written["status"] == "completed"
        assert "research_brief" in written["artifacts"]

    def test_resume_state_can_then_read_it(self, film):
        """The whole purpose: the next stage must see this stage as done."""
        projects, _ = film
        R.reconcile(projects, "a-film", "research")
        assert "research" in C.get_completed_stages(projects, "a-film")

    def test_it_records_that_the_runner_wrote_it(self, film):
        """Provenance, so nobody later reads this as the stage's own word."""
        projects, _ = film
        R.reconcile(projects, "a-film", "research")
        written = C.read_checkpoint(projects, "a-film", "research")
        assert written["metadata"]["reconciled_by"].startswith("the runner")

    def test_it_is_idempotent(self, film):
        projects, _ = film
        R.reconcile(projects, "a-film", "research")
        rc, verdict, lines = R.reconcile(projects, "a-film", "research")
        assert (rc, verdict) == (0, "FRESH")
        assert any("byte for byte" in line for line in lines)


class TestCaseTwoTheCheckpointWrittenTooEarly:
    """assets, run #5: a `completed` checkpoint 33 minutes stale."""

    @staticmethod
    def _rewrite_same_meaning(path: Path) -> int:
        """Change the artifact's BYTES while keeping it valid.

        Which is the assets failure in miniature: the stage kept writing,
        the artifact stayed legal, and the checkpoint's embedded copy
        stopped being the thing the next stage would read.
        """
        blob = json.loads(path.read_text())
        path.write_text(json.dumps(blob, indent=2))
        return path.stat().st_size

    def test_a_changed_artifact_makes_the_checkpoint_stale(self, film):
        projects, path = film
        R.reconcile(projects, "a-film", "research")
        before = path.stat().st_size
        after = self._rewrite_same_meaning(path)
        assert after != before, "the fixture did not change the bytes"

        rc, verdict, lines = R.reconcile(projects, "a-film", "research")
        assert rc == 0
        assert verdict == "REWROTE"
        assert any("MID-STAGE" in line for line in lines)
        assert any(str(before) in line and str(after) in line
                   for line in lines), lines

    def test_the_rewrite_carries_the_artifacts_FINAL_bytes(self, film):
        """Not the snapshot. Anything reading run #5's assets checkpoint saw
        31,885 bytes of a file that ended up 52,801."""
        projects, path = film
        R.reconcile(projects, "a-film", "research")
        self._rewrite_same_meaning(path)
        R.reconcile(projects, "a-film", "research")
        written = C.read_checkpoint(projects, "a-film", "research")
        assert R.recorded_fingerprints(written)["research_brief"] == \
            R.fingerprint(path)
        assert written["artifacts"]["research_brief"] == \
            json.loads(path.read_text())

    def test_a_checkpoint_with_no_fingerprint_is_rewritten(self, film):
        """Every checkpoint written before 2026-11-14, including the four
        run #5 left behind. Unknowable is not the same as matching."""
        projects, path = film
        C.write_checkpoint(projects, "a-film", "research", "completed",
                           {"research_brief": json.loads(path.read_text())},
                           pipeline_type="narrated-documentary",
                           human_approval_required=True, human_approved=True)
        assert not R.recorded_fingerprints(
            C.read_checkpoint(projects, "a-film", "research"))
        rc, verdict, lines = R.reconcile(projects, "a-film", "research")
        assert (rc, verdict) == (0, "REWROTE")
        assert any("records no fingerprint" in line for line in lines)

    def test_write_checkpoint_stamps_one_so_FRESH_is_reachable(self, film):
        """The CLI the stages use has to co-operate, or every checkpoint is
        rewritten forever and the staleness signal means nothing."""
        projects, path = film
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "write_checkpoint.py"),
             "--project", "a-film", "--stage", "research",
             "--artifact", "research_brief", "--human-approved",
             "--projects-dir", str(projects)],
            capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        written = C.read_checkpoint(projects, "a-film", "research")
        assert R.recorded_fingerprints(written)["research_brief"] == \
            R.fingerprint(path)
        assert R.reconcile(projects, "a-film", "research")[:2] == (0, "FRESH")


class TestTheControls:
    def test_a_missing_artifact_still_fails(self, film):
        projects, path = film
        path.unlink()
        rc, verdict, _ = R.reconcile(projects, "a-film", "research")
        assert (rc, verdict) == (1, "MISSING")
        assert not (projects / "a-film" / "checkpoint_research.json").exists()

    def test_an_invalid_artifact_still_fails(self, film):
        """THE CONTROL THE OWNER ASKED FOR. The rule is "the artifact
        validates", so an artifact that does not must be worth nothing."""
        projects, path = film
        broken = {"version": "1.0"}
        assert not valid("research_brief", broken), "choose a worse artifact"
        path.write_text(json.dumps(broken))
        rc, verdict, lines = R.reconcile(projects, "a-film", "research")
        assert (rc, verdict) == (1, "INVALID")
        assert any("does not validate" in line for line in lines)
        assert not (projects / "a-film" / "checkpoint_research.json").exists()

    def test_the_failure_quotes_the_validator(self, film):
        """So the run log says what is wrong with it, not merely that
        something is."""
        projects, path = film
        path.write_text(json.dumps({"version": "1.0"}))
        _, _, lines = R.reconcile(projects, "a-film", "research")
        assert any("required property" in line for line in lines), lines

    def test_half_written_json_still_fails(self, film):
        """A stage killed mid-write leaves a truncated file, which is the
        state the old comment assumed was ALWAYS the case."""
        projects, path = film
        path.write_text(json.dumps(json.loads(path.read_text()))[:120])
        rc, verdict, _ = R.reconcile(projects, "a-film", "research")
        assert (rc, verdict) == (1, "UNREADABLE")

    def test_failing_does_not_destroy_a_good_checkpoint(self, film):
        projects, path = film
        R.reconcile(projects, "a-film", "research")
        before = (projects / "a-film"
                  / "checkpoint_research.json").read_text()
        path.write_text(json.dumps({"version": "1.0"}))
        rc, _, _ = R.reconcile(projects, "a-film", "research")
        assert rc == 1
        assert (projects / "a-film"
                / "checkpoint_research.json").read_text() == before

    def test_the_script_stage_is_refused_by_name(self, film):
        """THE SELF-APPROVAL HOLE, FROM THE OTHER SIDE. The script
        checkpoint's human_approved is the owner's reply at the Telegram
        gate. A runner that writes it means a --resume skips the only human
        gate in the pipeline on the strength of nobody's approval — which
        happened on 2026-11-12 and cost $24.55."""
        projects, _ = film
        art = projects / "a-film" / "artifacts"
        (art / "script.json").write_text(json.dumps(real_artifact("script")))
        rc, verdict, lines = R.reconcile(projects, "a-film", "script")
        assert (rc, verdict) == (1, "REFUSED")
        assert any("human_approved" in line for line in lines)
        assert not (projects / "a-film" / "checkpoint_script.json").exists()

    def test_script_is_refused_even_though_its_artifact_is_perfect(self, film):
        """The refusal is about WHOSE word the checkpoint is, not about the
        artifact. A valid script must not be enough."""
        projects, _ = film
        art = projects / "a-film" / "artifacts"
        script = real_artifact("script")
        (art / "script.json").write_text(json.dumps(script))
        assert valid("script", script)
        assert R.reconcile(projects, "a-film", "script")[0] == 1

    def test_it_will_not_touch_a_stage_at_a_gate(self, film):
        projects, path = film
        C.write_checkpoint(projects, "a-film", "research", "awaiting_human",
                           {"research_brief": json.loads(path.read_text())},
                           pipeline_type="narrated-documentary",
                           human_approval_required=True)
        rc, verdict, _ = R.reconcile(projects, "a-film", "research")
        assert (rc, verdict) == (1, "AWAITING HUMAN")
        assert C.read_checkpoint(projects, "a-film",
                                 "research")["status"] == "awaiting_human"

    def test_a_stage_with_no_canonical_artifact_is_refused(self, film):
        projects, _ = film
        rc, verdict, _ = R.reconcile(projects, "a-film", "not-a-stage")
        assert (rc, verdict) == (1, "UNKNOWN STAGE")


class TestItInheritsThePipelineOrder:
    """A checkpoint written out of order would be a worse hole than the one
    this fixes: a stage marked done on a film whose script was never
    approved. `lib/checkpoint.py` refuses that, and the reconciler must not
    find a way around it.
    """

    def test_it_cannot_checkpoint_a_stage_whose_predecessors_are_missing(
            self, tmp_path):
        C.init_project("bare", title="Bare",
                       pipeline_type="narrated-documentary",
                       pipeline_dir=tmp_path,
                       style_playbook="wak3up-documentary")
        art = tmp_path / "bare" / "artifacts"
        art.mkdir(parents=True, exist_ok=True)
        (art / "scene_plan.json").write_text(json.dumps(A_SCENE_PLAN))
        assert valid("scene_plan", A_SCENE_PLAN), "the artifact must be good"
        rc, verdict, lines = R.reconcile(tmp_path, "bare", "scene_plan")
        assert rc == 1
        assert verdict == "REFUSED BY THE CHECKPOINT RULES"
        assert any("PREREQUISITE VIOLATION" in line for line in lines), lines
        assert not (tmp_path / "bare" / "checkpoint_scene_plan.json").exists()

    def test_the_refusal_is_reported_and_not_raised(self, tmp_path):
        """It used to propagate, which put a traceback in the run log and
        made the verdict depend on WHICH of the two `checkpoint` module
        objects was imported first — `checkpoint` or `lib.checkpoint`. The
        test passed alone and failed in the suite."""
        C.init_project("bare2", title="Bare",
                       pipeline_type="narrated-documentary",
                       pipeline_dir=tmp_path,
                       style_playbook="wak3up-documentary")
        art = tmp_path / "bare2" / "artifacts"
        art.mkdir(parents=True, exist_ok=True)
        (art / "scene_plan.json").write_text(json.dumps(A_SCENE_PLAN))
        rc, _, lines = R.reconcile(tmp_path, "bare2", "scene_plan")
        assert rc == 1
        assert any("Nothing was written" in line for line in lines)


class TestTheCLI:
    def test_it_exists_and_is_executable(self):
        assert CLI.exists()
        assert CLI.stat().st_mode & 0o111

    def test_it_exits_zero_and_names_the_verdict(self, film):
        projects, _ = film
        done = subprocess.run(
            [sys.executable, str(CLI), "--project", "a-film",
             "--stage", "research", "--projects-dir", str(projects)],
            capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        assert "reconcile: WROTE" in done.stdout

    def test_it_exits_one_on_a_missing_artifact(self, film):
        projects, path = film
        path.unlink()
        done = subprocess.run(
            [sys.executable, str(CLI), "--project", "a-film",
             "--stage", "research", "--projects-dir", str(projects)],
            capture_output=True, text=True)
        assert done.returncode == 1
        assert "MISSING" in done.stdout

    def test_quiet_prints_the_verdict_word_only(self, film):
        projects, _ = film
        done = subprocess.run(
            [sys.executable, str(CLI), "--project", "a-film", "--quiet",
             "--stage", "research", "--projects-dir", str(projects)],
            capture_output=True, text=True)
        assert done.stdout.strip() == "WROTE"

    def test_the_runner_calls_it(self):
        weekly = (ROOT / "scripts" / "run_weekly.sh").read_text()
        assert "scripts/reconcile_checkpoint.py" in weekly
        assert "reconcile_stage() {" in weekly

    def test_the_runner_reconciles_a_stage_that_ended_well_too(self):
        """"Written only after the artifact stops changing" is only enforced
        if EVERY stage is reconciled once it has exited. A stage that
        checkpoints early and then exits 0 is the assets failure without
        the wall cap."""
        weekly = (ROOT / "scripts" / "run_weekly.sh").read_text()
        body = weekly[weekly.index("pipeline_stage() {"):]
        body = body[:body.index("\n}\n")]
        assert "reconcile_stage" in body
        assert "MID-STAGE" in body or "mid-stage" in body.lower()

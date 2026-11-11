"""Every stage is told to checkpoint. There must be a command that does it.

`lib/checkpoint.py` had no command line, and nothing in the production path
called `init_project` — only the Backlot simulation scripts. The stage
preamble meanwhile told every stage to "write your checkpoint completed with
human_approved=True".

The 2026-11-11 research stage shows the bill: brief finished at transcript
turn 44 of 62 with 33 sourced data points, then turns 46–62 — 27% of its cap
— spent failing to write a checkpoint, and it never wrote one. It tried a
heredoc into /tmp (denied), then authored
projects/<slug>/write_checkpoint_once.py, quoting STAGE_CONTRACT's own
"acceptable when nothing fits" while doing it. It was right. Nothing fitted.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "write_checkpoint.py"
PY_BIN = sys.executable


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY_BIN, str(CLI), *args],
                          capture_output=True, text=True, cwd=str(ROOT))


@pytest.fixture
def brief() -> dict:
    """A schema-valid research brief, taken from a real one if present."""
    for film in ("king-tut", "noah", "easter-island"):
        p = ROOT / "projects" / film / "artifacts" / "research_brief.json"
        if p.exists():
            return json.loads(p.read_text())
    pytest.skip("no real research brief in this worktree to validate against")


class TestTheCommandExists:
    """THE TEST THE OWNER ASKED FOR: a stage prompt names a command that
    exists, for every checkpoint it is asked to write."""

    def test_the_cli_is_there_and_executable(self):
        assert CLI.exists()
        assert CLI.stat().st_mode & 0o111

    def test_the_stage_preamble_names_it(self):
        weekly = (ROOT / "scripts" / "run_weekly.sh").read_text()
        preamble = weekly[weekly.index("stage_preamble() {"):
                          weekly.index("pipeline_stage() {")]
        assert "scripts/write_checkpoint.py" in preamble

    def test_the_contract_names_it(self):
        assert "scripts/write_checkpoint.py" in (
            ROOT / "docs" / "STAGE_CONTRACT.md").read_text()

    def test_every_command_the_preamble_names_exists_on_disk(self):
        """A prompt that names a script that is not there costs the stage
        turns discovering that, which is the whole failure this fixes."""
        weekly = (ROOT / "scripts" / "run_weekly.sh").read_text()
        named = set(re.findall(r"scripts/[a-z_0-9]+\.py", weekly))
        assert named, "the runner names no scripts at all — check the regex"
        missing = [n for n in named if not (ROOT / n).exists()]
        assert missing == [], missing

    def test_every_stage_with_a_canonical_artifact_can_be_checkpointed(self):
        """Each stage the runner drives must be a --stage this CLI accepts."""
        sys.path.insert(0, str(ROOT))
        from lib.checkpoint import (ALL_KNOWN_STAGES,
                                    CANONICAL_STAGE_ARTIFACTS)
        weekly = (ROOT / "scripts" / "run_weekly.sh").read_text()
        driven = {s for s in ("research", "proposal", "script", "scene_plan",
                              "assets", "edit")
                  if f'pipeline_stage {s} ' in weekly
                  or f'claude_stage "{s}"' in weekly}
        assert driven, "no stages found in the runner"
        for stage in driven:
            assert stage in ALL_KNOWN_STAGES, stage
            assert stage in CANONICAL_STAGE_ARTIFACTS, stage


class TestItWrites:
    def test_a_research_checkpoint_from_a_bare_artifact_name(self, tmp_path,
                                                             brief):
        proj = tmp_path / "film"
        (proj / "artifacts").mkdir(parents=True)
        (proj / "artifacts" / "research_brief.json").write_text(
            json.dumps(brief))
        r = run("--project", "film", "--stage", "research",
                "--artifact", "research_brief", "--human-approved",
                "--projects-dir", str(tmp_path))
        assert r.returncode == 0, r.stderr
        written = json.loads((proj / "checkpoint_research.json").read_text())
        assert written["stage"] == "research"
        assert written["status"] == "completed"
        assert written["human_approved"] is True
        assert "research_brief" in written["artifacts"]

    def test_it_initialises_the_project_when_nothing_has(self, tmp_path,
                                                        brief):
        proj = tmp_path / "film"
        (proj / "artifacts").mkdir(parents=True)
        (proj / "artifacts" / "research_brief.json").write_text(
            json.dumps(brief))
        assert not (proj / "project.json").exists()
        r = run("--project", "film", "--stage", "research",
                "--artifact", "research_brief", "--title", "A Film",
                "--projects-dir", str(tmp_path))
        assert r.returncode == 0, r.stderr
        marker = json.loads((proj / "project.json").read_text())
        assert marker["title"] == "A Film"
        assert marker["pipeline_type"] == "narrated-documentary"

    def test_it_adds_the_canonical_artifact_you_forgot(self, tmp_path, brief):
        """Forgetting it is a validation error the stage would otherwise
        have to read and work out."""
        proj = tmp_path / "film"
        (proj / "artifacts").mkdir(parents=True)
        (proj / "artifacts" / "research_brief.json").write_text(
            json.dumps(brief))
        r = run("--project", "film", "--stage", "research",
                "--projects-dir", str(tmp_path))
        assert r.returncode == 0, r.stderr
        assert "adding the canonical artifact" in r.stdout
        written = json.loads((proj / "checkpoint_research.json").read_text())
        assert "research_brief" in written["artifacts"]

    def test_an_explicit_path_is_honoured(self, tmp_path, brief):
        proj = tmp_path / "film"
        (proj / "artifacts").mkdir(parents=True)
        other = tmp_path / "elsewhere.json"
        other.write_text(json.dumps(brief))
        r = run("--project", "film", "--stage", "research",
                "--artifact", f"research_brief={other}",
                "--projects-dir", str(tmp_path))
        assert r.returncode == 0, r.stderr

    def test_resume_state_can_read_what_it_wrote(self, tmp_path, brief):
        """The point of a checkpoint: the next stage must see it as done."""
        proj = tmp_path / "film"
        (proj / "artifacts").mkdir(parents=True)
        (proj / "artifacts" / "research_brief.json").write_text(
            json.dumps(brief))
        assert run("--project", "film", "--stage", "research",
                   "--artifact", "research_brief", "--human-approved",
                   "--projects-dir", str(tmp_path)).returncode == 0
        sys.path.insert(0, str(ROOT / "scripts"))
        import importlib
        import resume_state
        importlib.reload(resume_state)
        written = json.loads((proj / "checkpoint_research.json").read_text())
        assert written["stage"] == "research"
        assert written["status"] == "completed"


class TestItRefusesRatherThanWritingSomethingUnreadable:
    def test_a_schema_invalid_artifact_is_refused_with_the_validators_words(
            self, tmp_path):
        proj = tmp_path / "film"
        (proj / "artifacts").mkdir(parents=True)
        (proj / "artifacts" / "research_brief.json").write_text(
            json.dumps({"not": "a brief"}))
        r = run("--project", "film", "--stage", "research",
                "--artifact", "research_brief",
                "--projects-dir", str(tmp_path))
        assert r.returncode == 1
        assert "REFUSED" in r.stderr
        assert "required property" in r.stderr

    def test_and_writes_nothing(self, tmp_path):
        proj = tmp_path / "film"
        (proj / "artifacts").mkdir(parents=True)
        (proj / "artifacts" / "research_brief.json").write_text('{"x":1}')
        run("--project", "film", "--stage", "research",
            "--artifact", "research_brief", "--projects-dir", str(tmp_path))
        assert not (proj / "checkpoint_research.json").exists()

    def test_a_missing_artifact_file_says_where_it_looked(self, tmp_path):
        (tmp_path / "film" / "artifacts").mkdir(parents=True)
        r = run("--project", "film", "--stage", "proposal",
                "--artifact", "proposal_packet",
                "--projects-dir", str(tmp_path))
        assert r.returncode == 2
        assert "no artifact 'proposal_packet' at" in r.stderr

    def test_malformed_json_is_refused_not_crashed(self, tmp_path):
        proj = tmp_path / "film"
        (proj / "artifacts").mkdir(parents=True)
        (proj / "artifacts" / "research_brief.json").write_text("{nope")
        r = run("--project", "film", "--stage", "research",
                "--artifact", "research_brief",
                "--projects-dir", str(tmp_path))
        assert r.returncode == 2
        assert "not valid JSON" in r.stderr

    def test_an_unknown_stage_is_refused(self, tmp_path):
        (tmp_path / "film" / "artifacts").mkdir(parents=True)
        r = run("--project", "film", "--stage", "nonsense",
                "--projects-dir", str(tmp_path))
        assert r.returncode != 0


class TestTheThrowawayRuleIsStatedCorrectly:
    """The correction. The contract's rule stands; /tmp is what is refused."""

    @property
    def contract(self) -> str:
        return " ".join((ROOT / "docs" / "STAGE_CONTRACT.md").read_text()
                        .split())

    @property
    def director(self) -> str:
        return " ".join((ROOT / "skills" / "pipelines" /
                         "narrated-documentary" /
                         "script-director.md").read_text().split())

    def test_the_contract_still_permits_a_throwaway_under_the_project(self):
        assert ("A throwaway script in `projects/<slug>/` is acceptable when "
                "nothing fits") in self.contract

    def test_the_contract_refuses_tmp_and_says_why(self):
        assert "never in `/tmp`" in self.contract
        assert "leaves nothing behind" in self.contract

    def test_the_director_no_longer_says_the_contract_forbids_scripts(self):
        """It did, and that was wrong: the research stage was obeying the
        contract when it wrote one, and quoted the line."""
        assert "forbids a stage authoring programs" not in self.director
        assert "the rule is not that a stage may never write a script" in \
            self.director

    def test_both_say_checkpointing_no_longer_qualifies(self):
        for doc in (self.contract, self.director):
            assert 'no longer qualifies as "nothing fits"' in doc


class TestTheCapDerivationIsInSdkUnits:
    """The owner's test: the derivation text must say SDK turns."""

    @property
    def flat(self) -> str:
        body = (ROOT / "scripts" / "run_weekly.sh").read_text()
        return " ".join(body.replace("#:", " ").split())

    def test_it_says_sdk_turns(self):
        assert "SDK TURNS" in self.flat or "SDK turns" in self.flat

    def test_it_records_that_the_first_derivation_used_the_wrong_unit(self):
        assert "FIRST DERIVATION OF THEM WAS WRONG" in self.flat
        assert "transcript turns" in self.flat

    def test_it_records_the_observed_ratio(self):
        assert "99 transcript turns to 61 SDK" in self.flat
        assert "62 to 31" in self.flat

    def test_it_records_the_measured_need_per_stage(self):
        assert "~24 SDK turns of real work" in self.flat
        assert "13 x 6 = 78" in self.flat

    def test_the_caps_were_not_raised(self):
        body = (ROOT / "scripts" / "run_weekly.sh").read_text()
        assert 'TURNS_RESEARCH="${TURNS_RESEARCH:-30}"' in body
        assert 'TURNS_PROPOSAL="${TURNS_PROPOSAL:-25}"' in body
        assert 'TURNS_SCRIPT="${TURNS_SCRIPT:-120}"' in body

    def test_the_untested_cap_is_named_as_untested(self):
        """proposal has never run on its own. Saying so is the honest part."""
        assert "the one number still untested" in self.flat

"""A stage writes its film. It does not write the code that makes films.

WHY THIS TEST EXISTS
--------------------
On 2026-11-06 both `claude -p` stages edited shared code while making a film:
seven files under schemas/, lib/, scripts/ and remotion-composer/src/,
between 20:00 and 22:48. Nothing said so. The signal arrived twelve hours
later, as the NEXT run refusing to start —

    == 10:10:27 == REFUSED: 7 uncommitted change(s) to code on automation

— with no author, no reason and no file list, and with the week's approved
film one render away from done.

Two defences, and they are not the same kind of thing:

  1. `.claude/settings.json` DENIES Edit and Write under those directories in
     the runner worktree. This is a tool boundary, and a stage that must run
     arbitrary commands to make a film can step around it with `sed -i`,
     `cat >` or a python script. It is the first line, not the guarantee.

  2. `assert_code_clean` in run_weekly.sh asks GIT at the END of every stage.
     That is the guarantee, because it does not care how the file changed.

Both are asserted here, and the second is asserted by RUNNING IT.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER_WORKTREE = "/Users/mac/Developer/wak3up-docs/runner"
SETTINGS = ROOT / ".claude" / "settings.json"
RUNNER = ROOT / "scripts" / "run_weekly.sh"

#: Every directory the runner's own guard calls code, plus the instruction
#: surfaces a stage reads. schemas/ is here because two of the seven files
#: the 2026-11-06 stages dirtied were under it — a list without schemas/
#: would leave the actual offenders writable.
PROTECTED = ["lib", "scripts", "schemas", "styles", "remotion-composer/src",
             "skills", "pipeline_defs", "docs"]


@pytest.fixture(scope="module")
def settings() -> dict:
    # A malformed settings.json SILENTLY DISABLES EVERY SETTING IN IT,
    # including every deny rule here, so this is the first assertion.
    return json.loads(SETTINGS.read_text())


@pytest.fixture(scope="module")
def runner() -> str:
    return RUNNER.read_text()


class TestTheDenyRules:
    @pytest.mark.parametrize("directory", PROTECTED)
    def test_each_protected_directory_is_denied(self, settings, directory):
        rule = f"Edit(//{RUNNER_WORKTREE.lstrip('/')}/{directory}/**)"
        assert rule in settings["permissions"]["deny"], (
            f"{directory}/ is writable in the runner worktree. Expected "
            f"{rule!r} in permissions.deny.")

    def test_config_yaml_and_the_settings_file_itself_are_denied(self, settings):
        deny = settings["permissions"]["deny"]
        base = f"//{RUNNER_WORKTREE.lstrip('/')}"
        assert f"Edit({base}/config.yaml)" in deny
        assert f"Edit({base}/.claude/**)" in deny, (
            "a stage that can edit .claude/settings.json can lift its own "
            "restrictions.")

    def test_the_rules_are_written_as_Edit_not_Write(self, settings):
        """The form that is actually matched.

        Per the settings schema: path rules in `permissions` use `Edit(path)`
        for EVERY file-writing tool — Write, Edit and NotebookEdit — and
        `Write(path)` / `NotebookEdit(path)` rules are NOT matched by file
        permission checks. A deny list written as `Write(...)` would read as
        protection and be none.
        """
        for rule in settings["permissions"]["deny"]:
            assert not re.match(r"^(Write|NotebookEdit|Glob)\(", rule), (
                f"{rule!r} is a rule form file permission checks do not "
                f"match. Use Edit(path), which covers Write and "
                f"NotebookEdit too.")

    def test_the_rules_name_the_runner_worktree_absolutely(self, settings):
        """So a development checkout stays writable.

        .claude/settings.json is tracked, so this same file is checked out in
        every worktree. The rules are absolute paths into the runner, which
        is why they restrict the unattended runner and not the checkout a
        person is working in.
        """
        mine = [r for r in settings["permissions"]["deny"]
                if any(f"/{d}/" in r or r.endswith(f"/{d}/**)")
                       for d in PROTECTED)]
        assert mine, "no protected-directory deny rules at all"
        for rule in mine:
            assert RUNNER_WORKTREE.lstrip("/") in rule, (
                f"{rule!r} is not pinned to the runner worktree, so it also "
                f"restricts development checkouts.")

    def test_the_film_is_still_writable(self, settings):
        """A stage that cannot write projects/<slug>/ cannot make a film."""
        deny = settings["permissions"]["deny"]
        base = f"//{RUNNER_WORKTREE.lstrip('/')}"
        for writable in (f"{base}/projects/**", f"{base}/artifacts/**",
                         f"{base}/reports/**", f"{base}/logs/**"):
            assert f"Edit({writable})" not in deny, writable
            assert f"Edit({writable})" in settings["permissions"]["allow"]

    def test_the_published_film_stays_protected(self, settings):
        """An older, narrower deny must survive the new broad ones."""
        assert any("they-said-it-couldnt-be-built" in rule
                   for rule in settings["permissions"]["deny"])


class TestTheEndOfStageCheck:
    def test_it_runs_at_the_end_of_every_model_stage(self, runner):
        body = runner[runner.index("claude_stage() {"):]
        body = body[:body.index("\nstage_done()")]
        assert "assert_code_clean" in body, (
            "the check must run inside claude_stage, so every model stage is "
            "covered without anyone remembering to add it.")

    def test_it_runs_before_the_exit_code_is_trusted(self, runner):
        """A stage that dirtied the tree stops the run whatever it returns."""
        body = runner[runner.index("claude_stage() {"):]
        assert body.index("assert_code_clean") < body.index("[[ $rc -eq 0 ]]")

    def test_it_runs_after_the_render_and_the_publish_too(self, runner):
        assert runner.count("assert_code_clean") >= 4

    def test_it_names_the_files(self, runner):
        block = runner[runner.index("assert_code_clean() {"):]
        block = block[:block.index("\n# ── power")]
        assert "$dirty" in block, "the failure must list what changed"
        assert "code_dirty" in block

    def test_it_does_not_revert_anything(self, runner):
        """All seven of the edits it would have discarded were real fixes."""
        block = runner[runner.index("assert_code_clean() {"):]
        block = block[:block.index("\n# ── power")]
        for destructive in ("git checkout", "git restore", "git reset",
                            "git stash", "git clean"):
            assert destructive not in block, (
                f"assert_code_clean would {destructive}. The 2026-11-06 "
                f"stages made seven such edits and all seven were defects "
                f"worth committing — discarding them would have destroyed "
                f"good work and hidden three live bugs.")

    def test_RUN_CODE_is_set_before_the_first_call(self, runner):
        """`set -u` plus an unbound array in `${...[@]}` ABORTS THE SHELL.

        That exact shape cost this runner a whole weekly run once:
        MAX_RESUMES was used four times and never defined, and under `set -u`
        the error printed, neither branch ran, nothing after it ran, and the
        exit status was 0 — a silent death indistinguishable from success.
        """
        assigned = runner.index("RUN_CODE=(")
        first_call = min(
            m.start() for m in re.finditer(r"^\s*assert_code_clean ", runner,
                                           re.M))
        assert assigned < first_call, (
            "RUN_CODE is used by code_dirty before it is assigned. Under "
            "set -u that aborts the shell and reports success.")

    def test_every_RUN_CODE_directory_has_a_deny_rule(self, runner, settings):
        """The two lists must not drift apart.

        The git check and the deny rules answer the same question. A
        directory in one and not the other is a hole on one side or a
        surprise on the other.
        """
        line = re.search(r"^RUN_CODE=\(([^)]*)\)", runner, re.M).group(1)
        deny = " ".join(settings["permissions"]["deny"])
        for entry in line.split():
            stem = entry.rstrip("/")
            assert stem in deny, (
                f"run_weekly.sh calls {stem!r} code and will refuse to start "
                f"when it is dirty, but no deny rule protects it.")


class TestAnAttemptedLibEditIsRefused:
    """The behavioural half: the real function, run against a dirty lib/.

    Extracted from run_weekly.sh by text and evaluated, so this exercises the
    shipped code rather than a copy of it that could drift.
    """

    @staticmethod
    def _functions() -> str:
        text = RUNNER.read_text()
        start = text.index("code_dirty() {")
        end = text.index("\n# ── power")
        return text[start:end]

    @staticmethod
    def _harness(repo: Path) -> str:
        return f"""
set -uo pipefail
REPO="{repo}"
RUN_CODE=(lib scripts schemas styles remotion-composer/src config.yaml)
say() {{ printf '== %s\\n' "$*"; }}
notify() {{ :; }}
fail() {{ printf 'FAILED at %s\\n%s\\n' "$1" "$2"; exit 1; }}
{TestAnAttemptedLibEditIsRefused._functions()}
assert_code_clean "scene_plan"
echo "CLEAN"
"""

    @pytest.fixture
    def repo(self, tmp_path):
        """A git repo shaped like the runner, committed clean."""
        for directory in ("lib", "scripts", "projects/king-tut/artifacts"):
            (tmp_path / directory).mkdir(parents=True)
        (tmp_path / "lib" / "asset_bank.py").write_text("ORIGINAL\n")
        (tmp_path / "scripts" / "run_weekly.sh").write_text("#!/bin/bash\n")
        for args in (["init", "-q"],
                     ["config", "user.email", "t@example.com"],
                     ["config", "user.name", "t"],
                     ["add", "-A"],
                     ["commit", "-qm", "clean"]):
            subprocess.run(["git", *args], cwd=tmp_path, check=True,
                           capture_output=True)
        return tmp_path

    def _run(self, repo: Path):
        return subprocess.run(["bash", "-c", self._harness(repo)],
                              capture_output=True, text=True)

    def test_a_clean_tree_passes(self, repo):
        done = self._run(repo)
        assert done.returncode == 0, done.stdout + done.stderr
        assert "CLEAN" in done.stdout

    def test_an_edited_lib_file_fails_the_stage(self, repo):
        (repo / "lib" / "asset_bank.py").write_text("EDITED BY THE STAGE\n")
        done = self._run(repo)
        assert done.returncode == 1, done.stdout + done.stderr
        assert "EDITED THE CODE TREE" in done.stdout
        assert "lib/asset_bank.py" in done.stdout, (
            "the failure must name the file — the 2026-11-06 refusal said "
            "only '7 uncommitted change(s)'.")
        assert "CLEAN" not in done.stdout

    def test_a_new_untracked_script_also_fails(self, repo):
        """`sed -i` is not the only way in; a new file is a change too."""
        (repo / "scripts" / "helper.py").write_text("print('mine')\n")
        done = self._run(repo)
        assert done.returncode == 1
        assert "scripts/helper.py" in done.stdout

    def test_writing_the_film_does_not_fail_the_stage(self, repo):
        """The whole point: a stage must be free to write its own project."""
        art = repo / "projects" / "king-tut" / "artifacts"
        (art / "scene_plan.json").write_text('{"scenes": []}\n')
        done = self._run(repo)
        assert done.returncode == 0, done.stdout + done.stderr
        assert "CLEAN" in done.stdout

    def test_it_does_not_revert_the_edit(self, repo):
        """The diff must survive for a human to judge."""
        (repo / "lib" / "asset_bank.py").write_text("EDITED BY THE STAGE\n")
        self._run(repo)
        assert (repo / "lib" / "asset_bank.py").read_text() == \
            "EDITED BY THE STAGE\n"

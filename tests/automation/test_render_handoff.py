"""The model is never open while a render runs, and no stage is uncapped.

WHY THIS TEST EXISTS
--------------------
The 2026-11-06 render stage was one `claude -p` call told to start the render
detached and then poll for it. It did start it detached. Then it polled —
1,222 turns over 2h45m, 29 Monitor calls, 458 Bash calls, a context grown to
842,269 tokens, 388,077,078 cache-read tokens, $212.43 — and hit the
five-hour usage window one minute after the audio mix finished, with the
picture never started. Of the $212.43, $194.04 was re-reading its own
conversation.

Nothing in those turns needed a language model. The stage ran `ls -lt`,
tailed a log, and waited.

Three properties keep that from coming back, and all three are the kind that
decay quietly if nothing asserts them:

  1. The compose stage has NO MODEL. If `claude_stage "render"` or
     `claude_stage "compose"` ever reappears in the runner, this fails.
  2. Every model stage has a TURN CAP, so a loop costs tens of turns and not
     twelve hundred. The cost of a stage is its context size times its turn
     count — quadratic in turns — so an uncapped stage has an unbounded bill.
  3. The waiter makes NO API CALLS, so it cannot hit a usage limit and
     cannot cost anything however long the render takes.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_weekly.sh"
WAITER = ROOT / "scripts" / "await_render.py"
CONTRACT = ROOT / "docs" / "STAGE_CONTRACT.md"


def _imports_and_commands(path: Path) -> tuple[set[str], list[list[object]]]:
    """(top-level module names imported, argv lists handed to a subprocess).

    Reading the source as text cannot tell a call from an explanation, and
    these scripts explain themselves at length on purpose — the docstrings
    are where the measured reasons live. So the tests that care about what a
    script DOES read the tree, not the characters.
    """
    import ast

    tree = ast.parse(path.read_text())
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])

    def as_argv(node: "ast.AST") -> list[object] | None:
        if not isinstance(node, (ast.List, ast.Tuple)) or not node.elts:
            return None
        return [element.value if isinstance(element, ast.Constant)
                else ast.unparse(element) for element in node.elts]

    # Every argv-shaped list in the module, whether it is handed to
    # subprocess inline or built into a name first — `cmd = [...]` then
    # `subprocess.run(cmd)` is the normal shape when one argument is
    # conditional, and a test that only read the call site would pass a
    # script that shelled out to anything it liked.
    commands: list[list[object]] = []
    for node in ast.walk(tree):
        argv = None
        if isinstance(node, ast.Call) and node.args:
            target = node.func
            name = (f"{getattr(target.value, 'id', '')}.{target.attr}"
                    if isinstance(target, ast.Attribute) else
                    getattr(target, "id", ""))
            if name in ("subprocess.run", "subprocess.Popen",
                        "subprocess.check_output", "subprocess.call",
                        "os.execv", "os.execvp", "run", "Popen"):
                argv = as_argv(node.args[0]) or [ast.unparse(node.args[0])]
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            candidate = as_argv(node.value)
            if candidate and any(
                    str(part).endswith((".sh", ".py")) or "scripts" in str(part)
                    for part in candidate):
                argv = candidate
        if argv:
            commands.append(argv)
    return imports, commands


@pytest.fixture(scope="module")
def runner() -> str:
    return RUNNER.read_text()


class TestTheComposeStageHasNoModel:
    def test_no_claude_stage_renders_the_film(self, runner):
        """The exact shape that cost $212.43 must not be reachable."""
        for forbidden in ('claude_stage "render"', 'claude_stage "compose"',
                          "pipeline_stage compose"):
            assert forbidden not in runner, (
                f"{forbidden} is back in run_weekly.sh. The compose stage is "
                f"scripts/await_render.py and has no model: a render is a "
                f"loop with a sleep in it, and a loop with a sleep in it "
                f"costs nothing.")

    def test_the_runner_waits_with_the_waiter(self, runner):
        assert "scripts/await_render.py" in runner
        assert "--timeout-hours" in runner

    def test_the_waiter_opens_no_model(self):
        """No API call, by what it RUNS and IMPORTS — not what it mentions.

        The docstring and the argparse help both talk about `claude -p` and
        render_film.py, because explaining why this script exists means
        naming them. So the assertion is on the AST: which modules it
        imports, and what it hands to a subprocess.
        """
        imports, commands = _imports_and_commands(WAITER)
        assert "anthropic" not in imports, (
            "await_render.py imports the SDK. The waiter exists so the hours "
            "a render takes cost nothing and cannot exhaust a usage window.")
        for command in commands:
            assert not any("claude" in str(part) for part in command), (
                f"await_render.py runs {command!r}. A waiter that calls a "
                f"model is the thing this replaced: 1,222 turns of `ls -lt` "
                f"and `tail`.")

    def test_the_waiter_starts_the_render_detached(self):
        """Not as a child of the waiter: a background task is killed at 2h."""
        _, commands = _imports_and_commands(WAITER)
        started = [c for c in commands
                   if any("render_detached.sh" in str(p) for p in c)]
        assert started, (
            "await_render.py must start the render through "
            "render_detached.sh, which re-execs itself into its own session "
            "so the render is nobody's child.")
        for command in commands:
            assert not any("render_film.py" in str(p) for p in command), (
                "the waiter must not run render_film.py itself — that makes "
                "the render its child. The Noah plate was launched three "
                "times as a child process and killed three times, the last "
                "at 33,055 of 35,561 frames, leaving no file and no error.")

    def test_a_timeout_does_not_kill_the_render(self):
        text = WAITER.read_text()
        assert "LEAVING IT" in text or "left running" in text.lower()
        for killer in ("kill(pid, signal.SIGKILL", "SIGTERM", "pkill"):
            assert killer not in text, (
                f"await_render.py would {killer} the render. A render killed "
                f"near the end leaves no file and no error — that is how six "
                f"hours and three attempts were lost once.")


class TestEveryModelStageIsCapped:
    #: The owner's caps. research/proposal/script replaced a single
    #: `script: 60` on 2026-11-11, after the rehearsal that measured where
    #: those 60 turns went: research 7–34, proposal 36–66, first script at
    #: 77, cap at 61 with two of six sections written. 120 is six sections
    #: at the ~20 turns each that rehearsal actually took.
    CAPS = {"research": 40, "proposal": 25, "script": 120,
            "scene_plan": 40, "assets": 30, "edit": 30}

    @pytest.mark.parametrize("stage,cap", sorted(CAPS.items()))
    def test_the_cap_is_defined(self, runner, stage, cap):
        name = f"TURNS_{stage.upper()}"
        assert re.search(rf'^{name}="\$\{{{name}:-{cap}\}}"', runner, re.M), (
            f"{name} must default to {cap}. An uncapped stage has an "
            f"unbounded bill: cost is context times turns, and turns went to "
            f"1,222 once.")

    @pytest.mark.parametrize("stage", sorted(CAPS))
    def test_the_cap_is_passed_to_the_stage(self, runner, stage):
        name = f"TURNS_{stage.upper()}"
        # Either as the 4th argument to claude_stage, or via pipeline_stage.
        assert re.search(rf'(claude_stage "{stage}".*|pipeline_stage {stage} )'
                         rf'[^\n]*\$\{{?{name}', runner, re.S | re.M) or \
               f'"${name}"' in runner, (
            f"{name} is defined but never reaches the {stage} stage.")

    def test_the_cli_is_actually_given_max_turns(self, runner):
        assert "--max-turns" in runner, (
            "the cap must be enforced by the CLI, not only described in the "
            "prompt. A prompt that asks for restraint is not a budget.")

    def test_hitting_the_cap_fails_unless_the_stage_had_finished(self, runner):
        """A stage given a budget will spend it again — UNLESS it already
        checkpointed `completed`, which since 2026-11-11 is a warning.

        The whole decision is executed, both ways, by
        tests/automation/test_cap_hit_after_finishing.py. This asserts the
        shape of it here, where the cap rule lives, and the slice is taken
        to the END marker rather than to the first `fi` — the branch now has
        a nested `if`, and slicing to the first `fi` stopped before the
        failing path and silently tested nothing.
        """
        assert "max_turns" in runner
        block = runner[runner.index('if [[ "$kind" == "max_turns" ]]'):
                       runner.index("# ── END MAX_TURNS DECISION ──")]
        assert "FAILING" in block and "not resuming" in block
        assert "stage_finished_anyway" in block, (
            "the cap rule no longer consults the checkpoint, so a stage that "
            "finished and overran would be failed again")
        assert "sleep" not in block, (
            "a turn cap must not be slept on. Re-entering a stage that spent "
            "its budget spends it again.")


class TestTheStagesReadTheShortContract:
    def test_the_contract_exists_and_is_small(self):
        assert CONTRACT.exists(), "docs/STAGE_CONTRACT.md is the stage's contract"
        size = CONTRACT.stat().st_size
        guide = (ROOT / "AGENT_GUIDE.md").stat().st_size
        assert size < guide / 4, (
            f"STAGE_CONTRACT.md is {size}b against AGENT_GUIDE.md's {guide}b. "
            f"It exists to be small: a stage re-reads it on every turn.")

    def test_every_stage_is_pointed_at_it(self, runner):
        assert runner.count("docs/STAGE_CONTRACT.md") >= 2
        assert "INSTEAD OF AGENT_GUIDE.md" in runner or \
               "INSTEAD of\nAGENT_GUIDE.md" in runner or \
               "INSTEAD of AGENT_GUIDE.md" in runner

    def test_the_guide_sends_single_stage_runs_away(self):
        """CLAUDE.md makes AGENT_GUIDE.md mandatory, so the exit is in it."""
        head = (ROOT / "AGENT_GUIDE.md").read_text()[:3000]
        assert "STAGE_CONTRACT.md" in head, (
            "a stage that must read AGENT_GUIDE.md first needs the pointer "
            "near the top, or it pays for all 48 KB before finding it.")

    def test_the_stages_are_told_to_use_the_digests(self, runner):
        assert "playbook_digest.py" in runner
        assert "brief_digest.py" in runner

    def test_the_stages_are_told_not_to_edit_shared_code(self, runner):
        assert "DO NOT edit lib/" in runner, (
            "the 2026-11-06 stages left seven shared files modified and the "
            "next run refused to start with '7 uncommitted change(s) to "
            "code'.")


class TestTheGatesStillRun:
    def test_the_gates_are_in_the_render_path_not_the_agent(self):
        """render_film.py runs them, so removing the agent removed nothing."""
        text = (ROOT / "scripts" / "render_film.py").read_text()
        assert "gates(" in text and "report(" in text, (
            "the compose stage lost its agent on the understanding that "
            "render_film.py runs the delivery gates itself.")

    def test_the_waiter_reports_the_gate_report(self):
        assert "film_delivery" in WAITER.read_text()


class TestItAllStillParses:
    def test_the_runner_is_valid_bash(self):
        done = subprocess.run(["bash", "-n", str(RUNNER)],
                              capture_output=True, text=True)
        assert done.returncode == 0, done.stderr

    @pytest.mark.parametrize("script", [
        "await_render.py", "unfinished_film.py", "brief_digest.py",
        "playbook_digest.py", "usage_limit.py", "stage_usage.py",
        "resume_state.py",
    ])
    def test_the_scripts_are_valid_python(self, script):
        done = subprocess.run(
            [sys.executable, "-c",
             f"import ast,pathlib;ast.parse(pathlib.Path('{ROOT}/scripts/{script}').read_text())"],
            capture_output=True, text=True)
        assert done.returncode == 0, done.stderr

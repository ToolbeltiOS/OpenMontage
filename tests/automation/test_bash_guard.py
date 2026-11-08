"""The deny list has to hold for the second command on the line, not the first.

WHAT HAPPENED
-------------
2026-11-08. `Bash(git push:*)` had been in `permissions.deny` for a week,
and this went through:

    cd /Users/mac/Developer/wak3up-docs/credits-site && git push -u origin main

Not a bug in the rule — that IS prefix matching. The same two characters
disarm every entry in the list, and so do `/usr/bin/git push`, `git -C dir
push`, `bash -c 'git push'` and `$(git push)`. The rules stay as a first
line; `.claude/hooks/bash_guard.py` is the one that has to be sound, and it
parses the command instead of matching its front.

The allowed cases matter as much as the denied ones: this hook runs in
front of every Bash call the pipeline makes, and a guard that blocks the
render is a guard someone turns off.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".claude" / "hooks" / "bash_guard.py"
SETTINGS = ROOT / ".claude" / "settings.json"

spec = importlib.util.spec_from_file_location("bash_guard", HOOK)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def denied(command: str) -> str | None:
    """The hook's own verdict on a whole command line."""
    patterns = guard.deny_patterns()
    for segment in guard.segments(command):
        why = guard.offence(segment, patterns)
        if why:
            return why
    return None


#: Every shape that hid a denied command, including the one that actually
#: got through. If a form is added here it must be added to the live probe.
MUST_DENY = [
    "cd /tmp && git push",
    "true; git push",
    'bash -c "git push"',
    "sh -c 'git push'",
    'zsh -c "git push"',
    "/usr/bin/git push",
    "git -C /tmp push",
    "git -c user.name=x -C /tmp push origin HEAD",
    "cd /tmp && rm -rf /tmp/x",
    "rm -fr /tmp/x",
    "rm --recursive --force /tmp/x",
    "echo $(git push)",
    "echo `git push`",
    "( cd /tmp; git push )",
    "nohup env FOO=1 /usr/bin/git push origin main &",
    "xargs git push",
    "eval 'git push'",
    r"find . -name x -exec rm -rf {} \;",
    "git reset --hard HEAD~1",
    "git clean -fd",
    "git branch -D main",
    "git checkout -- .",
    "sudo launchctl list",
    "pip install requests",
    "npm install left-pad",
    "ls && cd /tmp && echo hi && git push",
]

#: What the pipeline and the stages actually run. Taken from run_weekly.sh,
#: render_detached.sh and this session's own commands.
MUST_ALLOW = [
    ".venv/bin/python scripts/render_film.py --project king-tut",
    "PYTHONUNBUFFERED=1 nohup .venv/bin/python scripts/publish_doc.py --project king-tut",
    "scripts/render_detached.sh king-tut --force --redo look,type",
    "cd /Users/mac/Developer/wak3up-docs/runner && .venv/bin/python -m pytest tests -q",
    "npx remotion render src/index.tsx Explainer out.mp4 --frames=0-100",
    "ffmpeg -v error -y -i a.mp4 -vf scale=480:270 -f rawvideo -",
    "git status --porcelain && git log --oneline -1",
    "git merge --ff-only fix/render-finalise",
    'git add -A && git commit -q -m "a message with && and ; in it"',
    'echo "git push is only words here"',
    "bash -n scripts/run_weekly.sh",
    "ls -la projects/king-tut | head -20",
    "grep -rn 'git push' scripts/ | head",
    'find . -name "*.log" -delete',
    "tail -f render.log | grep --line-buffered FAIL",
    "curl -s -o /dev/null -w '%{http_code}' https://example.invalid/x",
    ".venv/bin/python scripts/build_credits_page.py --all",
]


@pytest.mark.parametrize("command", MUST_DENY, ids=range(len(MUST_DENY)))
def test_a_hidden_command_is_still_denied(command):
    assert denied(command), f"NOT denied: {command}"


@pytest.mark.parametrize("command", MUST_ALLOW, ids=range(len(MUST_ALLOW)))
def test_the_pipeline_still_runs(command):
    why = denied(command)
    assert why is None, f"the guard blocks a command the pipeline needs: {command} -> {why}"


class TestTheParser:
    def test_it_splits_on_every_operator(self):
        assert guard.segments("a && b || c; d | e & f") == [
            "a", "b", "c", "d", "e", "f"]

    def test_an_operator_inside_quotes_is_not_an_operator(self):
        assert guard.segments('echo "a && b"') == ['echo "a && b"']
        assert guard.segments("echo 'a; b'") == ["echo 'a; b'"]

    def test_it_looks_inside_command_substitution(self):
        assert "git push" in guard.segments("echo $(git push)")
        assert "git push" in guard.segments("echo `git push`")

    def test_it_strips_env_assignments_and_wrappers(self):
        assert guard.words_of("FOO=1 BAR=2 nohup env nice -n 5 git push")[0] == "git"

    def test_it_strips_the_path_from_the_binary(self):
        why = guard.offence("/usr/local/bin/git push", guard.deny_patterns())
        assert why and "git push" in why

    def test_git_C_does_not_hide_the_subcommand(self):
        assert guard.git_subcommand(
            ["git", "-C", "/tmp", "-c", "a=b", "push", "origin"]) == (
            "push", ["origin"])


class TestItFailsClosed:
    def test_unreadable_input_is_denied(self, tmp_path):
        done = subprocess.run([sys.executable, str(HOOK)], input="not json",
                              capture_output=True, text=True)
        assert done.returncode == 2, done.stdout + done.stderr
        assert "could not read its input" in done.stderr

    def test_a_denial_names_the_offending_segment(self):
        payload = json.dumps({"tool_name": "Bash", "tool_input": {
            "command": "ls && cd /tmp && git push"}})
        done = subprocess.run([sys.executable, str(HOOK)], input=payload,
                              capture_output=True, text=True)
        assert done.returncode == 2
        assert "git push" in done.stderr
        assert "ls && cd /tmp && git push" in done.stderr

    def test_a_tool_that_is_not_bash_is_not_this_hooks_business(self):
        payload = json.dumps({"tool_name": "Edit", "tool_input": {
            "file_path": "/x", "new_string": "git push"}})
        done = subprocess.run([sys.executable, str(HOOK)], input=payload,
                              capture_output=True, text=True)
        assert done.returncode == 0


class TestItIsWiredUp:
    @pytest.fixture(scope="class")
    def settings(self):
        return json.loads(SETTINGS.read_text())

    def test_the_hook_is_registered_on_bash(self, settings):
        hooks = settings["hooks"]["PreToolUse"]
        bash = [h for h in hooks if h.get("matcher") == "Bash"]
        assert bash, "no PreToolUse hook on Bash"
        assert any("bash_guard.py" in c.get("command", "")
                   for h in bash for c in h["hooks"])

    def test_it_runs_by_absolute_path(self, settings):
        """A hook's working directory is not guaranteed."""
        command = [c["command"] for h in settings["hooks"]["PreToolUse"]
                   for c in h["hooks"] if "bash_guard" in c["command"]][0]
        assert all(part.startswith("/") for part in command.split()[:2])

    def test_the_prefix_rules_are_still_there(self, settings):
        """Belt and braces: the hook is the sound one, the rules are free."""
        deny = settings["permissions"]["deny"]
        for rule in ("Bash(git push:*)", "Bash(rm -rf:*)", "Bash(sudo:*)"):
            assert rule in deny

    def test_a_stage_cannot_edit_the_hook(self, settings):
        """`.claude/**` is denied, which covers hooks/ — a guard a stage can
        rewrite is not a guard."""
        assert ("Edit(//Users/mac/Developer/wak3up-docs/runner/.claude/**)"
                in settings["permissions"]["deny"])

    def test_the_credits_push_is_out_of_reach_of_a_stage(self, settings):
        """publish_credits_page.sh keeps its push because launchd runs it,
        not an agent. A stage cannot edit it and cannot run git itself."""
        deny = settings["permissions"]["deny"]
        assert ("Edit(//Users/mac/Developer/wak3up-docs/runner/scripts/**)"
                in deny)
        assert denied("scripts/publish_credits_page.sh king-tut") is None, (
            "the pipeline step must still be runnable")
        assert denied("git push -q origin HEAD"), (
            "a stage must not be able to do by hand what that script does")


class TestWhatAStageActuallySees:
    """The unit cases above are this file's own reading of the hook. This
    runs the hook the way a stage meets it: a real `claude -p` in the runner
    worktree, with the settings and the hook loaded by the CLI itself.

    Skipped unless OPENMONTAGE_ALLOW_NETWORK=1, like every `live_api` test:

        OPENMONTAGE_ALLOW_NETWORK=1 pytest -m live_api \
            tests/automation/test_bash_guard.py

    One caveat carried over from the Edit-deny probe: a rule or hook added
    to .claude/ does NOT apply to an interactive session already running. A
    fresh `claude -p` honours it, which is what the runner starts.
    """

    RUNNER = "/Users/mac/Developer/wak3up-docs/runner"
    SENTINEL = Path("/tmp/bash_guard_probe/keep_me.txt")

    #: Run in one session, so the probe costs one call rather than six.
    DENIED_FORMS = [
        "cd /tmp && git push",
        "true; git push",
        'bash -c "git push"',
        "/usr/bin/git push",
        "git -C /tmp push",
        "cd /tmp/bash_guard_probe && rm -rf /tmp/bash_guard_probe",
    ]

    ALLOWED_FORMS = [
        "ls -la /tmp/bash_guard_probe | head -3",
        "cd /tmp/bash_guard_probe && cat keep_me.txt",
        'echo "git push is only words here" && echo done',
        "/usr/bin/env python3 -c 'print(1+1)'",
    ]

    def _run(self, prompt: str) -> dict:
        import os
        done = subprocess.run(
            ["claude", "-p", prompt, "--permission-mode", "acceptEdits",
             "--output-format", "json"],
            cwd=self.RUNNER, capture_output=True, text=True,
            env={**os.environ}, timeout=600)
        assert done.returncode == 0, done.stderr[:2000]
        return json.loads(done.stdout)

    @pytest.fixture(autouse=True)
    def sentinel(self):
        self.SENTINEL.parent.mkdir(parents=True, exist_ok=True)
        self.SENTINEL.write_text("a file the probe must not be able to delete\n")
        yield
        self.SENTINEL.unlink(missing_ok=True)

    #: The hook's own signature in a transcript. NOT "was the command
    #: refused": a non-interactive `claude -p` refuses anything that is not
    #: allowlisted, so "REFUSED" says nothing about which guard did it. The
    #: first version of this probe conflated the two and failed on commands
    #: the hook had allowed.
    BLOCKED = "Blocked by .claude/hooks/bash_guard.py"

    @pytest.mark.live_api
    def test_every_hidden_form_is_refused_in_a_real_session(self):
        numbered = "\n".join(f"{i+1}. {c}"
                             for i, c in enumerate(self.DENIED_FORMS))
        record = self._run(
            "Run each of these commands with the Bash tool, exactly as "
            "written, one at a time. Some will be refused; that is expected "
            "and is what is being measured. Do not try to work around a "
            "refusal, do not rewrite a command, and do not use any other "
            "tool. After all of them, reply with one line per command: the "
            "number, then the FIRST LINE of any error message you received, "
            "verbatim.\n\n" + numbered)
        blob = json.dumps(record)
        assert self.BLOCKED in blob, (
            f"the hook never fired at all:\n{record.get('result')}")

        # Per form, from the record's own denial list rather than from the
        # model's summary of it.
        denied_commands = {d.get("tool_input", {}).get("command")
                           for d in (record.get("permission_denials") or [])}
        missing = [c for c in self.DENIED_FORMS if c not in denied_commands]
        assert not missing, (
            f"these forms were not refused: {missing}\n"
            f"{record.get('result')}")
        assert self.SENTINEL.exists(), (
            "the probe deleted the sentinel: rm -rf got through")

    @pytest.mark.live_api
    def test_the_commands_the_pipeline_needs_still_run(self):
        """The half that decides whether anyone leaves the guard switched on.

        What is asserted is that THIS hook did not block them. A
        non-interactive session may still refuse a command for wanting
        approval, which is the allowlist's business and not this guard's.
        """
        numbered = "\n".join(f"{i+1}. {c}"
                             for i, c in enumerate(self.ALLOWED_FORMS))
        record = self._run(
            "Run each of these commands with the Bash tool, exactly as "
            "written, one at a time. Do not rewrite them and do not use "
            "another tool. Then reply with one line per command: the "
            "number, then the FIRST LINE of any error message you received, "
            "verbatim, or RAN if it ran.\n\n" + numbered)
        blob = json.dumps(record)
        assert self.BLOCKED not in blob, (
            f"the guard blocked something the pipeline needs:\n"
            f"{record.get('result')}")

"""What a stage is allowed to run, rehearsed against the real guard.

THE PRACTICE THIS REPLACES
--------------------------
`.claude/hooks/bash_guard.py` carries two bespoke exemptions — "form A", a
`for` loop over `projects/` with a read-only body, and "form B", a
`python -I -c` whose code is audited for writes. Both exist because a stage
improvised a shape to look at a FINISHED film's artifact, got blocked, and
the guard learned that shape afterwards. That is per-incident
allow-listing: the list grows one entry per incident, and every entry is a
parser for something a stage made up.

`scripts/inspect_project.py` is the entry point instead. Three questions —
what a film has, one slice of one artifact, how many scenes and cuts — under
one name already covered by `Bash(scripts/:*)`. A stage that uses it needs
no new exemption, and the guard has nothing to parse.

This file is the rehearsal: every command the contract tells a stage to run,
through the real hook, with the DENIED count asserted.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / ".claude" / "hooks" / "bash_guard.py"
CONTRACT = ROOT / "docs" / "STAGE_CONTRACT.md"

#: Everything a stage is told to run, for looking at itself or at a
#: delivered film. If one of these is denied, a stage spends turns
#: recovering — the 2026-11-11 rehearsal did exactly that.
WHAT_A_STAGE_RUNS = [
    ".venv/bin/python scripts/resume_state.py --project king-tut",
    ".venv/bin/python scripts/playbook_digest.py --stage edit",
    ".venv/bin/python scripts/brief_digest.py --project king-tut",
    ".venv/bin/python scripts/proposal_digest.py --project king-tut",
    ".venv/bin/python scripts/edit_decisions_digest.py --project king-tut",
    ".venv/bin/python scripts/check_claims.py --project king-tut",
    ".venv/bin/python scripts/build_narration_lexicon.py --project king-tut",
    ".venv/bin/python lib/verify_rhythm.py artifacts/edit_decisions.json",
    # the three forms this item adds
    ".venv/bin/python scripts/inspect_project.py artifacts king-tut",
    ".venv/bin/python scripts/inspect_project.py show king-tut "
    "edit_decisions --path cuts.0",
    ".venv/bin/python scripts/inspect_project.py scenes king-tut",
]

#: What a stage must never get through, whatever it wraps it in.
WHAT_IT_MUST_NOT = [
    "git push -u origin main",
    "cd /tmp && git push",
    "rm -rf projects/king-tut",
    "sudo launchctl list",
    "bash -c 'git push'",
    "eval 'rm -rf .'",
]


def guard(command: str) -> tuple[int, str]:
    """The real hook's verdict on one command."""
    done = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": command}}),
        capture_output=True, text=True, timeout=60)
    return done.returncode, (done.stderr or "") + (done.stdout or "")


def rehearse() -> dict[str, list[str]]:
    """The DENIED count, as a measurement rather than a claim."""
    denied = [c for c in WHAT_A_STAGE_RUNS if guard(c)[0] != 0]
    allowed = [c for c in WHAT_A_STAGE_RUNS if c not in denied]
    return {"denied": denied, "allowed": allowed}


class TestTheStageCanRunWhatItIsToldToRun:
    def test_nothing_the_contract_asks_for_is_denied(self):
        """THE REHEARSAL. Zero, or a stage pays turns to find out why."""
        result = rehearse()
        assert result["denied"] == [], (
            f"{len(result['denied'])} of {len(WHAT_A_STAGE_RUNS)} denied:\n"
            + "\n".join(result["denied"]))

    @pytest.mark.parametrize("command", [
        ".venv/bin/python scripts/inspect_project.py artifacts king-tut",
        ".venv/bin/python scripts/inspect_project.py show king-tut script "
        "--path sections.0.id",
        ".venv/bin/python scripts/inspect_project.py scenes king-tut",
    ])
    def test_the_inspector_needs_no_exemption(self, command):
        """Not form A, not form B — an ordinary script call."""
        code, _ = guard(command)
        assert code == 0
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "bg", str(GUARD))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.inspection_allowance(command) is None, (
            "the inspector should pass as a plain command, not as one of "
            "the improvised forms the guard had to learn")


class TestTheGuardStillGuards:
    @pytest.mark.parametrize("command", WHAT_IT_MUST_NOT)
    def test_it_is_denied(self, command):
        code, said = guard(command)
        assert code == 2, f"{command!r} was allowed: {said}"


class TestTheContractNamesTheInspector:
    def test_it_is_named(self):
        assert "inspect_project.py" in CONTRACT.read_text(), (
            "a tool a stage is not told about is a tool a stage improvises "
            "around")

    def test_it_is_named_where_reading_is_discussed(self):
        text = CONTRACT.read_text()
        assert text.index("inspect_project.py") > text.index("Read these")


class TestTheInspectorOnlyReads:
    def test_it_writes_nothing(self):
        source = (ROOT / "scripts" / "inspect_project.py").read_text()
        for forbidden in ("write_text(", "open(", "unlink(", "mkdir(",
                          "rmtree", "os.remove"):
            assert forbidden not in source, (
                f"{forbidden} in an inspector is a stage editing a prior "
                f"film")

    def test_every_subcommand_is_read_only_in_practice(self, tmp_path):
        """Run all three against a real film and prove the tree is
        unchanged, byte for byte."""
        import hashlib

        art = ROOT / "projects" / "king-tut" / "artifacts"
        if not art.is_dir():
            pytest.skip("king-tut's artifacts are not in this checkout")

        def fingerprint() -> str:
            h = hashlib.sha256()
            for path in sorted(art.glob("*.json")):
                h.update(path.name.encode())
                h.update(str(path.stat().st_size).encode())
                h.update(str(path.stat().st_mtime_ns).encode())
            return h.hexdigest()

        before = fingerprint()
        for argv in (["artifacts", "king-tut"],
                     ["show", "king-tut", "script", "--path", "title"],
                     ["scenes", "king-tut"]):
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "inspect_project.py"),
                 *argv], capture_output=True, text=True, timeout=120)
        assert fingerprint() == before

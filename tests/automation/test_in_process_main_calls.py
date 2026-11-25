"""A main() that another module calls in process must accept argv.

Written 2026-11-25, after `replace_published_film.py` was found calling
`publish_doc.main(["--project", slug, "--now"])` against a
`def main() -> int:` that takes nothing. It would have raised TypeError at
the one moment it mattered — a film rendered, gated and ready to upload —
and the script's own tests never saw it because they stub the uploader.

`scripts/*.py` mostly run as scripts, and 87 of them take no argv. That is
fine: argparse reads sys.argv and there is nobody else to pass. The rule is
not "every main takes argv", it is the narrower true one — if some OTHER
module calls your main with arguments, those arguments have to be able to
arrive. A main() called with a list and declaring no parameter is a
TypeError that only fires in production.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCES = sorted(ROOT.glob("scripts/*.py")) + sorted(ROOT.glob("lib/*.py"))


def _main_arity(path: Path) -> int | None:
    """How many positional parameters this file's module-level main takes."""
    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return len(node.args.args) + len(node.args.posonlyargs)
    return None


def in_process_main_calls() -> list[tuple[Path, str, int, int]]:
    """Every `<module>.main(<something>)` written in our own sources."""
    found = []
    for path in SOURCES:
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not (isinstance(fn, ast.Attribute) and fn.attr == "main"):
                continue
            if not isinstance(fn.value, ast.Name):
                continue
            passed = len(node.args)
            if passed == 0:
                continue        # main() with nothing to deliver is fine
            found.append((path, fn.value.id, passed, node.lineno))
    return found


CALLS = in_process_main_calls()


def test_there_are_such_calls_to_check():
    """If this ever finds none, the scan broke rather than the risk going."""
    assert CALLS, "no in-process main(...) calls found — the AST scan is wrong"


@pytest.mark.parametrize(
    "caller,module,passed,line",
    CALLS,
    ids=[f"{c.name}:{line}->{mod}" for c, mod, _, line in CALLS])
def test_the_callee_can_receive_what_is_passed(caller, module, passed, line):
    target = ROOT / "scripts" / f"{module}.py"
    if not target.exists():
        target = ROOT / "lib" / f"{module}.py"
    if not target.exists():
        pytest.skip(f"{module} is not one of ours")
    arity = _main_arity(target)
    assert arity is not None, (
        f"{caller.relative_to(ROOT)}:{line} calls {module}.main() with "
        f"{passed} argument(s), but {target.relative_to(ROOT)} defines no "
        f"module-level main")
    assert arity >= passed, (
        f"{caller.relative_to(ROOT)}:{line} calls {module}.main() with "
        f"{passed} argument(s), but {target.relative_to(ROOT)}'s main takes "
        f"{arity} — a TypeError that fires only when this path runs for "
        f"real. Give it `def main(argv: list[str] | None = None)` and "
        f"`ap.parse_args(argv)`.")

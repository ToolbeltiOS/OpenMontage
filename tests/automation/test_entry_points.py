"""A script's entry point is the last thing in its file.

THE BUG THIS CATCHES, WHICH THE SUITE COULD NOT
-----------------------------------------------
On 2026-11-24 a reordering of constants in `scripts/resolve_basemaps.py`
left four function definitions — `mercator_bounds` among them — BELOW the
`if __name__ == "__main__": raise SystemExit(main())` guard.

Imported, the file is fine: Python executes every `def` in it whatever the
order, so `import resolve_basemaps` binds all of them and 40 tests passed
against the module. RUN, the guard is reached first, `main()` is called
while four names do not exist yet, and the script dies with

    NameError: name 'mercator_bounds' is not defined

The edit stage runs it as a script. It would have failed on Friday, in an
unattended stage, on a film — found instead on 2026-11-25 by running it by
hand against a real project.

So: nothing but comments and blank lines may follow the guard, in any
script. The rule is cheap and it is the only thing that tells the two
cases apart.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = sorted(p for p in (ROOT / "scripts").glob("*.py")
                 if not p.name.startswith("_"))
LIBS = sorted(p for p in (ROOT / "lib").glob("*.py")
              if not p.name.startswith("_"))


def guard_is_last(path: Path) -> tuple[bool, list[str]]:
    """Is the `__main__` guard the last statement? What follows it?"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for index, node in enumerate(tree.body):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        names = ast.dump(test)
        if "__name__" not in names or "__main__" not in names:
            continue
        after = tree.body[index + 1:]
        return (not after,
                [f"line {n.lineno}: {type(n).__name__} "
                 f"{getattr(n, 'name', '')}".strip() for n in after])
    return True, []          # no guard at all is fine


@pytest.mark.parametrize("path", SCRIPTS + LIBS,
                         ids=[p.name for p in SCRIPTS + LIBS])
def test_nothing_follows_the_entry_point(path):
    ok, after = guard_is_last(path)
    assert ok, (
        f"{path.relative_to(ROOT)} defines things AFTER its `__main__` "
        f"guard, so running it calls main() before they exist — while "
        f"importing it in a test works perfectly:\n  "
        + "\n  ".join(after))


def test_the_rule_can_fail(tmp_path):
    """The control. A guard-then-def file has to be detected."""
    bad = tmp_path / "bad.py"
    bad.write_text('def main():\n    return helper()\n\n\n'
                   'if __name__ == "__main__":\n    raise SystemExit(main())\n'
                   '\n\ndef helper():\n    return 0\n')
    ok, after = guard_is_last(bad)
    assert not ok
    assert any("helper" in line for line in after)


def test_a_file_with_no_guard_is_not_a_failure(tmp_path):
    fine = tmp_path / "lib_only.py"
    fine.write_text("def helper():\n    return 1\n")
    assert guard_is_last(fine) == (True, [])

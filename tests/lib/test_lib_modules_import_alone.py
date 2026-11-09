"""Every module in lib/ imports without help from whoever imported it.

WHAT HAPPENED
-------------
`verify_frame_order` was given `from buildability import js_round` with no
path setup, and `render_acts` was given the same import under a line that
puts the REPO ROOT on `sys.path` — but `buildability.py` is a sibling in
lib/, which the root does not reach.

Both worked, because the things that imported them had already put lib/ on
the path. Then a test module was collected first and:

    ModuleNotFoundError: No module named 'buildability'

in a file that had nothing to do with the cause. A module that depends on
its caller having arranged `sys.path` works until the day something imports
it earliest.

BOTH WAYS, because the codebase uses both: scripts do
`sys.path.insert(0, ROOT / "lib")` and then `import verify_frame_order`,
while tests do `from lib import verify_frame_order`. A module that works
one way and not the other is the bug this catches.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Modules that cannot be imported for a reason that is not this defect.
#: Each needs its reason, so the list cannot quietly grow.
QUARANTINE: dict[str, str] = {
    # none today
}

#: Modules that legitimately need the REPO ROOT on the path as well as
#: lib/, because they import a repo package rather than a sibling. They are
#: exempt from the flat check and NOT from the package one — which is the
#: check that caught the real defect.
NEEDS_REPO_ROOT = {
    "checkpoint": "imports `schemas`, a package at the repo root",
    "events": "imports `lib`, so it needs the root rather than lib/",
}


def lib_modules() -> list[str]:
    return sorted(p.stem for p in (ROOT / "lib").glob("*.py")
                  if not p.stem.startswith("_")
                  and p.stem not in QUARANTINE)


PROBE = r'''
import importlib, sys, json
root, style, names = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
# The repo must not be reachable by accident — but site-packages must stay,
# or every module that imports numpy "fails" for a reason that is this
# probe's doing. So: run from a temp cwd, no PYTHONPATH, and drop only the
# repo's own source directories, never the interpreter's own paths.
sys.path = [p for p in sys.path
            if p and not p.startswith(root + "/lib")
            and p.rstrip("/") != root.rstrip("/")]
if style == "flat":
    sys.path.insert(0, root + "/lib")
else:
    sys.path.insert(0, root)
bad = {}
for name in names:
    target = name if style == "flat" else "lib." + name
    try:
        importlib.import_module(target)
    except Exception as e:
        bad[name] = f"{type(e).__name__}: {e}"
print(json.dumps(bad))
'''


def failures(style: str) -> dict[str, str]:
    import json
    import os
    import tempfile
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    with tempfile.TemporaryDirectory() as elsewhere:
        done = subprocess.run(
            [sys.executable, "-c", PROBE, str(ROOT), style,
             json.dumps(lib_modules())],
            capture_output=True, text=True, cwd=elsewhere, env=env)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def flat() -> dict[str, str]:
    return failures("flat")


@pytest.fixture(scope="module")
def package() -> dict[str, str]:
    return failures("package")


def test_there_are_modules_to_check():
    """The control: an empty list passes everything below it."""
    assert len(lib_modules()) > 20, lib_modules()


def test_every_module_imports_with_lib_on_the_path(flat):
    """How scripts import them. Modules that import a repo-root package are
    exempt — see NEEDS_REPO_ROOT, which names each one's reason."""
    flat = {k: v for k, v in flat.items() if k not in NEEDS_REPO_ROOT}
    assert flat == {}, (
        "these fail when lib/ is on sys.path and nothing else has been "
        f"arranged: {flat}")


def test_every_module_imports_as_part_of_the_lib_package(package):
    """How the tests import them — and how the defect surfaced."""
    assert package == {}, (
        "these fail when imported as lib.<name> from the repo root, which "
        f"is what a test module does: {package}")


def test_the_exempt_modules_really_do_need_the_root(flat):
    """A quarantine that stops being true is a quarantine that hides a
    defect: if one of these starts importing flat, it should leave the
    list."""
    for name, why in NEEDS_REPO_ROOT.items():
        assert name in flat, (
            f"{name} now imports with only lib/ on the path — remove it "
            f"from NEEDS_REPO_ROOT ({why})")


def test_the_two_modules_that_broke_are_covered(flat, package):
    for name in ("verify_frame_order", "render_acts"):
        assert name in lib_modules(), f"{name} is no longer being checked"
        assert name not in flat and name not in package

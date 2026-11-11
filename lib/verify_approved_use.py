"""Did the thing the owner approved actually reach the film?

WHY THIS EXISTS
---------------
Three times now a gate has proved an INTENTION and nothing has checked that
the renderer ever read it:

  1. `cut.texture` was authored, screened and reported on, and the field was
     never forwarded to the component. The first style-frame before/after
     was byte-identical on four of six pairs, because both sides were the
     "after".
  2. `AnnotatedStill` was given camera props the renderer never read. A gate
     that reads intent proves nothing about the render.
  3. The three Noah illustrations were generated, posted to the Telegram
     script gate, approved by the owner at 09:20:42 on 2026-10-31 — and
     appear in no cut. `approved.json` is read by `telegram_gate.py`,
     `illustration_spec.py` and `make_illustration.py`, and by nothing in
     the scene planner, the asset bank or the render path. `render_props.json`
     contains zero references to any of them.

An approval that no cut consumes is worse than no approval: the owner spent
attention on a decision that had no effect, and the report said the
illustrations were in a film they were not in.

So this is a HARD FAILURE of the scene plan, in both directions:

  - an illustration approved for this project that no cut references
  - a cut referencing an illustration that was not approved for it, which is
    the owner's standing rule — an illustration not approved at the gate is
    not used, and the slot falls back to a still or an authored graphic

Matching is by FILE BASENAME, not by full path, because the props pass the
staging step in `props_for_layer` and an asset referenced as
`assets/library/illustrations/ark-build.png` in the plan is referenced as
`assets_noah/ark-build.png` by the time the renderer sees it. The basename
is what survives, so the basename is what is checked.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "assets" / "library" / "illustrations" / "manifest.json"

#: APPROVALS ARE PER-FILM AND LIVE WITH THE FILM, since 2026-11-11. There was
#: one shared tracked file for every film ever made, and approving one film's
#: script approved every picture in the library under that film's name. See
#: lib/illustration_spec.APPROVALS.


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def approved_for(project: str, approved_path: Path | None = None,
                 manifest_path: Path | None = None,
                 root: Path | None = None) -> list[dict[str, Any]]:
    """The illustrations THIS FILM's owner approved, with their files.

    An approval carries the subject line the owner read, not a path, because
    that is what they were shown. The manifest is what turns a subject into a
    file; an approved subject with no manifest entry is itself a fault, and
    comes back with `path: None` rather than being dropped.

    It reads only this film's own record now. `approved_path` is still
    accepted so a test can point at a fixture, and when it is given it is
    read as a film's approvals file rather than as the old shared one.
    """
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import illustration_spec

    base = root or ROOT
    if approved_path is not None:
        blob = _load(approved_path) or {}
        rows = blob.get("verdicts") or []
        subjects = {r["subject"] for r in rows
                    if r.get("verdict") == "ok" and r.get("subject")}
        when = {r["subject"]: r.get("at") for r in rows if r.get("subject")}
    else:
        subjects = illustration_spec.approved_subjects(project, base)
        when = {r["subject"]: r.get("at")
                for r in illustration_spec.verdicts(project, base)
                if r.get("subject")}
    manifest = _load(manifest_path or MANIFEST_PATH) or {}
    # A PICTURE ANSWERS TO EVERY NAME IT HAS HAD. `subject` became a short
    # on-screen label on 2026-11-09 and the full line it used to carry moved
    # to `prompt` and `subject_was`; an approval records the text the owner
    # was shown AT THE TIME, so one taken before the split names the long
    # line. Keyed on only the current subject, a real approval would read as
    # "approved illustration has no manifest entry" and fail the delivery.
    by_subject = {}
    for a in (manifest.get("assets") or []):
        for key in ("subject", "subject_was", "prompt"):
            name = a.get(key)
            if name:
                by_subject.setdefault(name, a.get("path"))
    out = []
    for subject in sorted(subjects):
        out.append({"subject": subject, "path": by_subject.get(subject),
                    "approved_at": when.get(subject)})
    return out


def referenced_basenames(props: dict[str, Any]) -> set[str]:
    """Every illustration-looking file the props mention, anywhere in them.

    Deliberately crude: the whole blob is searched as text rather than a
    known set of fields, because the last two faults of this kind were a
    field that was never forwarded. A check that looks only where the asset
    is SUPPOSED to be cannot see it missing.
    """
    blob = json.dumps(props)
    found = set()
    for name in _illustration_files():
        if name in blob:
            found.add(name)
    return found


def _illustration_files(manifest_path: Path | None = None) -> set[str]:
    manifest = _load(manifest_path or MANIFEST_PATH) or {}
    return {Path(a["path"]).name for a in (manifest.get("assets") or [])
            if a.get("path")}


def check(project: str, props_path: Path | None = None,
          approved_path: Path | None = None,
          manifest_path: Path | None = None):
    """Returns (ok, problems, summary)."""
    # Coerced, because a blocking gate that dies on `str` instead of `Path`
    # fails the delivery with an AttributeError rather than a verdict.
    props_path = Path(props_path) if props_path else (
        ROOT / "projects" / project / "artifacts" / "render_props.json")
    problems: list[str] = []
    if not props_path.exists():
        return False, [f"no render props at {props_path}"], {}

    props = json.loads(props_path.read_text(encoding="utf-8"))
    approved = approved_for(project, approved_path, manifest_path)
    used = referenced_basenames(props)

    for row in approved:
        if not row["path"]:
            problems.append(
                f"approved illustration has no manifest entry, so it is not "
                f"on disk under any name: {row['subject'][:70]!r}")
            continue
        name = Path(row["path"]).name
        if name not in used:
            problems.append(
                f"{name} was approved for {project} at "
                f"{row['approved_at']} and NO CUT REFERENCES IT — the "
                f"approval had no effect on the film")

    approved_names = {Path(r["path"]).name for r in approved if r["path"]}
    for name in sorted(used - approved_names):
        problems.append(
            f"{name} is used by a cut but was not approved for {project} — "
            f"an illustration not approved at the gate is not used; the slot "
            f"falls back to a still or an authored graphic")

    summary = {"approved": len(approved), "referenced": len(used),
               "unused_approvals": sum(1 for r in approved if r["path"]
                                       and Path(r["path"]).name not in used),
               "unapproved_uses": len(used - approved_names)}
    return (not problems), problems, summary


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: verify_approved_use.py <project> [render_props.json]")
        raise SystemExit(2)
    proj = sys.argv[1]
    path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    ok, probs, summary = check(proj, path)
    print(f"project {proj}: {summary.get('approved', 0)} approved "
          f"illustration(s), {summary.get('referenced', 0)} referenced by a cut")
    for p in probs:
        print("  -", p)
    print("APPROVED-ASSET USE:", "PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)

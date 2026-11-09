"""The gate that asks whether what the owner approved reached the film.

WHY THIS TEST EXISTS
--------------------
`lib/verify_approved_use.py` arrived on `asset-library` with its six cases
proved by hand and written into a table in `reports/asset_library_branch.md`.
Proved by hand is not proved: the gate is now BLOCKING from `gates()` in
`lib/film_render.py`, and a blocking gate with no control is the fourth
member of the family it was written to end — a check that proves an
intention while nothing checks the check.

So the table is a test. The six rows below are that table, in order.

THE NOAH ROW IS NOT "EXPECTED FAIL"
-----------------------------------
The branch report says "On `noah` as it stands it reads FAIL, naming all
three files." That sentence was true when it was written and was not true
four hours later. On 2026-11-01T15:35:52 the three noah approvals were
REVOKED — see `projects/noah/artifacts/illustration_approvals.json` — so
that this gate "passes by being TRUE and not by being excused". The film is
delivered without illustrations, which is what it always was; what changed
is that the record no longer claims otherwise.

That makes the real noah state the LAST test here, and it asserts the
revocation, not a failure: nothing approved, nothing used, gate green. The
FAIL direction the report cared about is pinned by
`test_approved_and_not_used` on a synthetic project, which is where a
control belongs — it cannot be quietly satisfied by someone re-approving
three illustrations, and it cannot go stale when the film does.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import verify_approved_use as V  # noqa: E402

ARK = "assets/library/illustrations/ark-build.png"
TIRYNS = "assets/library/illustrations/pausanias-at-tiryns.png"


@pytest.fixture
def bank(tmp_path):
    """An approvals file, a manifest and a props file, all writable.

    The real ones are read from `ROOT`; everything here is injected, so the
    test says nothing about the state of this checkout and cannot be broken
    by a film being made.
    """
    def build(approved: list[tuple[str, str]], props: dict,
              manifest: list[tuple[str, str]] | None = None):
        manifest = manifest if manifest is not None else [
            ("ark", ARK), ("tiryns", TIRYNS)]
        approved_path = tmp_path / "approved.json"
        manifest_path = tmp_path / "manifest.json"
        props_path = tmp_path / "render_props.json"
        approved_path.write_text(json.dumps({"approved": [
            {"project": project, "subject": subject,
             "approved_at": "2026-10-31T09:20:42"}
            for project, subject in approved]}))
        manifest_path.write_text(json.dumps({"assets": [
            {"subject": subject, "path": path} for subject, path in manifest]}))
        props_path.write_text(json.dumps(props))
        return lambda project: V.check(
            project, props_path=props_path, approved_path=approved_path,
            manifest_path=manifest_path)
    return build


# The six cases of reports/asset_library_branch.md, in its order.

def test_approved_and_used(bank):
    check = bank([("noah", "ark")], {"cuts": [{"backgroundImage": ARK}]})
    ok, problems, summary = check("noah")
    assert ok, problems
    assert summary == {"approved": 1, "referenced": 1,
                       "unused_approvals": 0, "unapproved_uses": 0}


def test_approved_and_staged_under_a_different_directory(bank):
    """The basename is what survives `props_for_layer`'s staging step.

    The plan says `assets/library/illustrations/ark-build.png`; by the time
    the renderer sees it, it is `assets_noah/ark-build.png`. A check on the
    full path would call every staged film a failure.
    """
    check = bank([("noah", "ark")],
                 {"cuts": [{"backgroundImage": "assets_noah/ark-build.png"}]})
    ok, problems, _ = check("noah")
    assert ok, problems


def test_approved_and_not_used(bank):
    """THE FAIL DIRECTION THE WHOLE GATE IS FOR.

    This is the noah fault of 2026-10-31 as a control: approved at the gate,
    referenced by no cut. It is held here rather than against the real
    project so that it keeps failing after the real project stops.
    """
    check = bank([("noah", "ark")], {"cuts": [{"backgroundImage": "photo.jpg"}]})
    ok, problems, summary = check("noah")
    assert not ok
    assert summary["unused_approvals"] == 1
    assert len(problems) == 1
    assert "ark-build.png" in problems[0]
    assert "NO CUT REFERENCES IT" in problems[0]


def test_used_but_not_approved(bank):
    """The owner's standing rule, in the other direction."""
    check = bank([], {"cuts": [{"backgroundImage": ARK}]})
    ok, problems, summary = check("noah")
    assert not ok
    assert summary["unapproved_uses"] == 1
    assert "was not approved" in problems[0]


def test_two_approved_one_used(bank):
    check = bank([("noah", "ark"), ("noah", "tiryns")],
                 {"cuts": [{"backgroundImage": ARK}]})
    ok, problems, summary = check("noah")
    assert not ok
    assert summary == {"approved": 2, "referenced": 1,
                       "unused_approvals": 1, "unapproved_uses": 0}
    assert "pausanias-at-tiryns.png" in problems[0]


def test_nothing_approved_nothing_used(bank):
    check = bank([], {"cuts": [{"backgroundImage": "photo.jpg"}]})
    ok, problems, _ = check("noah")
    assert ok, problems


# Two faults that are not either direction of the main rule.

def test_an_approval_with_no_manifest_entry_is_itself_a_fault(bank):
    """Approved by subject line, and no file of that subject on disk.

    The owner approves the sentence they were shown, not a path, so a
    subject that the manifest cannot turn into a file is an approval of
    nothing — and it must not come back as a silent PASS by being dropped.
    """
    check = bank([("noah", "a subject nobody filed")],
                 {"cuts": [{"backgroundImage": ARK}]}, manifest=[("ark", ARK)])
    ok, problems, _ = check("noah")
    assert not ok
    assert any("no manifest entry" in p for p in problems)


def test_another_projects_approval_is_not_this_films_problem(bank):
    check = bank([("easter-island", "tiryns")],
                 {"cuts": [{"backgroundImage": "photo.jpg"}]})
    ok, problems, summary = check("noah")
    assert ok, problems
    assert summary["approved"] == 0


def test_a_missing_props_file_fails_rather_than_passes(bank, tmp_path):
    """A gate that cannot read the render is not a gate that approves it."""
    ok, problems, _ = V.check("noah", props_path=tmp_path / "absent.json")
    assert not ok
    assert "no render props" in problems[0]


# The real state of this repository, which is the revocation and not a FAIL.

class TestTheRealStateOnThisBranch:
    def test_the_noah_approvals_are_revoked_not_waived(self):
        """`approved.json` is empty, and that is the fix of 2026-11-01.

        If this list ever refills, it is because someone re-approved
        illustrations the planner still cannot consume — which is the fault,
        not the fix. Merge-week item 1 is an illustration slot class in the
        scene planner; until that exists, an approval cannot reach a film.
        """
        approved = json.loads(V.APPROVED_PATH.read_text(encoding="utf-8"))
        assert approved["approved"] == [], (
            "illustrations are approved again while the planner has no "
            "illustration slot class — see projects/noah/artifacts/"
            "illustration_approvals.json")
        assert "REVOKED" in approved["note"]

    def test_the_revocation_keeps_its_reasoning_and_its_pictures(self):
        """Revoked is not deleted: the provenance of the three files stays."""
        record = json.loads(
            (ROOT / "projects" / "noah" / "artifacts"
             / "illustration_approvals.json").read_text(encoding="utf-8"))
        assert record["revoked_at"].startswith("2026-11-01")
        assert len(record["illustrations"]) == 3
        assert all(row["referenced_by_any_cut"] is False
                   for row in record["illustrations"])
        manifest = json.loads(V.MANIFEST_PATH.read_text(encoding="utf-8"))
        filed = {a["path"] for a in manifest["assets"]}
        for row in record["illustrations"]:
            assert row["path"] in filed, (
                f"{row['path']} lost its provenance when the approval was "
                f"revoked — the record says it is kept in manifest.json")

    def test_noah_is_green_by_being_true(self, tmp_path):
        """Nothing approved, nothing used: the sixth row, on the real files.

        Not an expected FAIL. The gate reads PASS on noah because the claim
        it checks is no longer made, which is what revoking it was for. The
        props are a stand-in because `render_props.json` is rebuilt every
        render and is not in git; the approvals and the manifest, which are
        the part under test, are the real committed files.
        """
        assert V.approved_for("noah") == []
        props = tmp_path / "render_props.json"
        props.write_text(json.dumps({"cuts": [{"backgroundImage": "photo.jpg"}]}))
        ok, problems, summary = V.check("noah", props_path=props)
        assert ok, problems
        assert summary["approved"] == 0 and summary["referenced"] == 0

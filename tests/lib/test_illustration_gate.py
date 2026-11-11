"""Illustrations get their own gate, per picture, and it never blocks.

WHAT WAS WRONG, MEASURED 2026-11-11 BY APPROVING A REHEARSAL'S SCRIPT
---------------------------------------------------------------------
Approvals lived in one tracked shared file,
assets/library/illustrations/approved.json, and the script gate posted
EVERY picture in the shared library because `illustrations_for` read the
directory and filtered by nothing. One "ok" on the Lighthouse rehearsal's
script approved noah's "Ark under construction" and they-said-it's
"Unworked blocks at Tiryns", recorded under the rehearsal's name. There was
no way to refuse one picture without refusing the script — and every
approval dirtied a tracked file in the runner, which is a pull-only deploy
target.

The script gate also ran BEFORE the edit stage, so at that moment no
illustration had been authored for the film at all.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "scripts"))

import illustration_spec as I   # noqa: E402
import illustration_gate as G   # noqa: E402


class TestApprovalsArePerFilm:
    def test_the_path_is_under_the_film(self, tmp_path):
        p = I.approvals_path("king-tut", tmp_path)
        assert p == tmp_path / "projects" / "king-tut" / "artifacts" / \
            "illustration_approvals.json"

    def test_a_verdict_for_one_film_is_invisible_to_another(self, tmp_path):
        I.record_verdicts("film-a", [{"subject": "a picture",
                                      "verdict": "ok"}], tmp_path)
        assert I.approved_subjects("film-a", tmp_path) == {"a picture"}
        assert I.approved_subjects("film-b", tmp_path) == set()

    def test_usable_is_asked_per_film(self, tmp_path):
        I.record_verdicts("film-a", [{"subject": "a picture",
                                      "verdict": "ok"}], tmp_path)
        assert I.usable("a picture", "film-a", tmp_path)[0] is True
        assert I.usable("a picture", "film-b", tmp_path)[0] is False

    def test_a_no_is_recorded_and_does_not_approve(self, tmp_path):
        I.record_verdicts("f", [{"subject": "x", "verdict": "no"}], tmp_path)
        assert I.approved_subjects("f", tmp_path) == set()
        assert len(I.verdicts("f", tmp_path)) == 1

    def test_the_latest_verdict_wins(self, tmp_path):
        I.record_verdicts("f", [{"subject": "x", "verdict": "no"}], tmp_path)
        I.record_verdicts("f", [{"subject": "x", "verdict": "ok"}], tmp_path)
        assert I.approved_subjects("f", tmp_path) == {"x"}
        assert len(I.verdicts("f", tmp_path)) == 2, "history is appended"

    def test_every_verdict_carries_who_and_when(self, tmp_path):
        I.record_verdicts("f", [{"subject": "x", "verdict": "ok"}], tmp_path)
        row = I.verdicts("f", tmp_path)[0]
        assert row["at"] and row["by"]
        assert "Telegram" in row["by"]

    def test_noahs_revocation_holds_by_construction(self):
        """Not by a special case. noah's file records three illustrations
        approved at the 2026-10-31 script gate and then revoked; that list
        is history and `approved_subjects` reads only `verdicts`."""
        assert I.approved_subjects("noah", ROOT) == set()
        blob = I.approvals("noah", ROOT)
        assert blob["revoked_at"].startswith("2026-11-01")
        assert len(blob["illustrations"]) == 3

    def test_recording_a_verdict_does_not_erase_the_revocation(self, tmp_path):
        """`record_verdicts` appends and rewrites only `note`. The old
        `record_approval` rewrote the note that carried the reasoning."""
        target = I.approvals_path("noah", tmp_path)
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(
            {"project": "noah", "revoked_at": "2026-11-01T15:35:52",
             "why": "the reasoning", "illustrations": [{"subject": "s"}]}))
        I.record_verdicts("noah", [{"subject": "new", "verdict": "ok"}],
                          tmp_path)
        blob = I.approvals("noah", tmp_path)
        assert blob["revoked_at"] == "2026-11-01T15:35:52"
        assert blob["why"] == "the reasoning"
        assert len(blob["illustrations"]) == 1


class TestTheScriptGateNoLongerTouchesIllustrations:
    @pytest.fixture(scope="class")
    def gate(self) -> str:
        return (ROOT / "scripts" / "telegram_gate.py").read_text()

    def test_it_posts_none(self, gate):
        code = "\n".join(l for l in gate.splitlines()
                         if not l.lstrip().startswith("#"))
        assert "send_photo" in code, "it still posts the style frames"
        assert "illustrations_for" not in code
        assert "record_approval" not in code
        assert "illustrations_shown" not in code

    def test_the_flag_is_gone(self, gate):
        assert "--illustrations" not in gate

    def test_the_runner_stopped_passing_it(self):
        runner = (ROOT / "scripts" / "run_weekly.sh").read_text()
        block = runner[runner.index("telegram_gate.py"):]
        block = block[:block.index("GATE=$?")]
        assert "--illustrations" not in block

    def test_it_says_why_in_the_source(self, gate):
        assert "ILLUSTRATIONS ARE NOT APPROVED HERE" in gate


class TestTheReplyParser:
    @pytest.mark.parametrize("text,count,want", [
        ("ok all", 3, {1: "ok", 2: "ok", 3: "ok"}),
        ("no all", 2, {1: "no", 2: "no"}),
        ("ok 2", 3, {2: "ok"}),
        ("no 3", 3, {3: "no"}),
        ("ok 1 2 5", 5, {1: "ok", 2: "ok", 5: "ok"}),
        ("OK 2", 3, {2: "ok"}),
        ("yes 1", 2, {1: "ok"}),
        ("nope 1", 2, {1: "no"}),
        ("ok", 1, {1: "ok"}),
    ])
    def test_it_reads_what_it_should(self, text, count, want):
        assert G.parse(text, count) == want

    @pytest.mark.parametrize("text,count", [
        ("okay then but not the third", 3),
        ("maybe later", 3),
        ("", 3),
        ("ok", 3),
        ("ok 9", 3),
        ("looks good to me, ship it", 3),
    ])
    def test_it_refuses_to_guess(self, text, count):
        """THE DANGEROUS CASE. "okay then but not the third" read as an
        approval of everything is exactly the failure worth avoiding, and a
        bare "ok" with three pictures up does not say which."""
        assert G.parse(text, count) == {}

    def test_an_out_of_range_number_is_not_silently_clamped(self):
        assert G.parse("ok 9", 3) == {}

    def test_a_bare_ok_is_unambiguous_with_one_picture(self):
        assert G.parse("ok", 1) == {1: "ok"}


class TestItNeverBlocksTheFilm:
    @staticmethod
    def source() -> str:
        return (ROOT / "scripts" / "illustration_gate.py").read_text()

    def test_no_props_exits_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv",
                            ["illustration_gate.py", "--project", "nothing",
                             "--props", str(tmp_path / "absent.json")])
        assert G.main() == 0

    def test_no_illustration_cuts_exits_zero(self, tmp_path, monkeypatch):
        props = tmp_path / "p.json"
        props.write_text(json.dumps({"cuts": [{"type": "annotated_still"}]}))
        monkeypatch.setattr(sys, "argv",
                            ["illustration_gate.py", "--project", "x",
                             "--props", str(props)])
        assert G.main() == 0

    def test_every_exit_from_main_is_zero(self):
        """A gate that can fail here turns "I was asleep" into "no film".

        Scoped to main() and _apply(): the helpers return parsed values, and
        collecting every `return` in the file reads `return {}` from the
        reply parser as an exit code.
        """
        body = self.source()
        main = body[body.index("def main()"):]
        returns = {l.strip() for l in main.splitlines()
                   if l.strip().startswith("return ")}
        assert returns <= {"return 0",
                           "return _apply(args, props, props_path)"}, returns

    def test_and_apply_itself_only_returns_zero(self):
        body = self.source()
        apply_fn = body[body.index("def _apply("):]
        returns = {l.strip() for l in apply_fn.splitlines()
                   if l.strip().startswith("return ")}
        assert returns == {"return 0"}, returns

    def test_the_runner_cannot_fail_on_it_either(self):
        runner = (ROOT / "scripts" / "run_weekly.sh").read_text()
        block = runner[runner.index("# ── 4a. the illustration gate"):
                       runner.index("# ── 4b. depth plates")]
        assert "illustration_gate.py" in block
        assert "fail " not in block, (
            "the runner can fail the film on the illustration gate; a "
            "refusal is supposed to demote a cut, not stop the film")
        assert "|| say" in block

    def test_it_runs_after_the_edit_and_before_the_picture(self):
        runner = (ROOT / "scripts" / "run_weekly.sh").read_text()
        edit = runner.index("pipeline_stage edit")
        gate = runner.index("# ── 4a. the illustration gate")
        picture = runner.index("# ── 4c. the picture")
        assert edit < gate < picture

    def test_the_edit_stage_no_longer_demotes(self):
        """It generates the pictures, so at that point nothing is approved
        and demoting there would refuse every illustration before the gate
        ever posted it."""
        props = (ROOT / "lib" / "build_render_props.py").read_text()
        code = "\n".join(l for l in props.splitlines()
                         if not l.lstrip().startswith("#"))
        assert "demote_unapproved" not in code


class TestDemotionIsPerFilm:
    def test_an_unapproved_cut_falls_back_to_its_own_fallback(self, tmp_path):
        cuts = [{"id": "c1", "type": "illustration", "subject": "s",
                 "source": "a.jpg"},
                {"id": "c2", "type": "illustration", "subject": "t"}]
        changed = I.demote_unapproved(cuts, "f", tmp_path)
        assert {c["cut"]: c["fell_to"] for c in changed} == {
            "c1": "still", "c2": "text_card"}
        assert cuts[0]["type"] == "annotated_still"
        assert cuts[1]["type"] == "text_card"

    def test_an_approved_cut_is_left_alone(self, tmp_path):
        I.record_verdicts("f", [{"subject": "s", "verdict": "ok"}], tmp_path)
        cuts = [{"id": "c1", "type": "illustration", "subject": "s"}]
        assert I.demote_unapproved(cuts, "f", tmp_path) == []
        assert cuts[0]["type"] == "illustration"

    def test_another_films_approval_does_not_save_it(self, tmp_path):
        I.record_verdicts("other", [{"subject": "s", "verdict": "ok"}],
                          tmp_path)
        cuts = [{"id": "c1", "type": "illustration", "subject": "s"}]
        assert len(I.demote_unapproved(cuts, "f", tmp_path)) == 1


class TestARunLeavesNoTrackedFileDirty:
    """THE OWNER'S TEST. Every approval used to modify a tracked file."""

    def test_the_approvals_path_is_untracked_by_default(self):
        """It is allow-listed so it CAN be committed deliberately, but
        writing one does not touch a file git already knows about."""
        tracked = subprocess.run(
            ["git", "ls-files", "assets/library/illustrations/approved.json"],
            cwd=ROOT, capture_output=True, text=True).stdout.strip()
        assert tracked == "", "the shared approvals file is tracked again"

    def test_the_gate_writes_only_under_projects(self):
        body = (ROOT / "scripts" / "illustration_gate.py").read_text()
        assert "assets/library/illustrations/approved.json" not in body
        assert "record_verdicts" in body

    def test_nothing_writes_the_shared_file_any_more(self):
        """Code, not comments. lib/illustration_spec.py explains in prose
        why the shared file is gone, and that sentence has to name it."""
        hits = subprocess.run(
            ["git", "grep", "-n", "illustrations/approved.json", "--",
             "lib", "scripts"],
            cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
        code = [h for h in hits
                if not h.split(":", 2)[-1].lstrip().startswith(("#", '"', "*"))]
        assert code == [], code

    def test_the_manifest_stays_shared_and_read_only(self):
        """A picture is a file in a library; permission to use it is a fact
        about one film. Only the second moved."""
        for module in ("lib/illustration_spec.py",
                       "lib/verify_approved_use.py"):
            body = (ROOT / module).read_text()
            assert "manifest.json" in body

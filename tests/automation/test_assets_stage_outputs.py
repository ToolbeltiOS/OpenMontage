"""The assets stage owes beds, and a failed stage owes evidence.

THREE THINGS THAT WERE TRUE ON 2026-11-24
-----------------------------------------
1. The shared bed library held TWO beds and all six delivered films were
   mixed from them. Nothing was broken: nothing ever asked for anything
   new, so the music of the channel stopped moving. A checkpoint says the
   hand-off is complete, so "complete" now includes the thing that is
   easiest to skip.
2. Rhythm repair was code each edit stage wrote for itself, in the project
   directory, differently every time — the shape docs/STAGE_CONTRACT.md
   describes as "a program being developed" and says to promote.
3. A stage that died at its turn cap produced an EMPTY failure message.
   `stage_usage.py --report` wrote `<stage>_stage.log` only when the agent
   left a closing report, and a stage that runs out of turns leaves
   `result: null`. On 2026-11-20 the edit stage stopped at
   error_max_turns after 141 turns and $7.74 with no `.log` and a 0-byte
   `.err`, so the run reported the most expensive failure of the week as
   nothing at all.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import checkpoint as C                                         # noqa: E402
import checkpoint_reconcile as CR                              # noqa: E402


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SU = _load("stage_usage")
RR = _load("repair_rhythm")

RUN_WEEKLY = (ROOT / "scripts" / "run_weekly.sh").read_text()


def project(tmp_path: Path, intake: dict | None) -> Path:
    proj = tmp_path / "projects" / "film"
    (proj / "artifacts").mkdir(parents=True)
    (proj / "artifacts" / "asset_manifest.json").write_text('{"assets": []}')
    if intake is not None:
        (proj / "artifacts" / "bed_intake.json").write_text(json.dumps(intake))
    return tmp_path / "projects"


class TestTheAssetsStageOwesBeds:
    def test_it_is_a_declared_output(self):
        declared = dict(C.STAGE_OUTPUTS["assets"])
        assert "artifacts/bed_intake.json" in declared
        assert declared["artifacts/bed_intake.json"] == "beds"

    def test_no_record_at_all_is_incomplete(self, tmp_path):
        short = CR.missing_outputs(project(tmp_path, None), "film", "assets")
        assert any("bed_intake.json" in m for m in short)
        assert any("ingest_bed.py" in m for m in short), (
            "the message has to say what writes it")

    def test_one_new_bed_is_not_two(self, tmp_path):
        """THE CONTROL. One is a coincidence."""
        where = project(tmp_path, {"new_to_the_library": [{"track": "a.wav"}]})
        short = CR.missing_outputs(where, "film", "assets")
        assert any("1 bed(s) new to the library, 2 owed" in m for m in short)

    def test_two_new_beds_complete_the_stage(self, tmp_path):
        where = project(tmp_path, {"new_to_the_library": [{"track": "a.wav"},
                                                          {"track": "b.wav"}]})
        assert CR.missing_outputs(where, "film", "assets") == []

    def test_re_ingesting_what_is_already_there_is_not_fetching(self, tmp_path):
        """`already_in_the_library` does not count — which is the whole
        point, because the two beds six films used are already there."""
        where = project(tmp_path, {
            "new_to_the_library": [],
            "already_in_the_library": ["Ancient Civilisations.wav",
                                       "Lake Jupiter.wav"]})
        short = CR.missing_outputs(where, "film", "assets")
        assert any("0 bed(s) new to the library" in m for m in short)

    def test_a_refusal_is_an_answer_but_not_a_bed(self, tmp_path):
        where = project(tmp_path, {
            "new_to_the_library": [],
            "refused": [{"source": "small_drama.mp3",
                         "why": "no steady 90s at any ceiling"}]})
        short = CR.missing_outputs(where, "film", "assets")
        assert any("refused by the ingest" in m for m in short)

    def test_an_unreadable_record_is_not_a_pass(self, tmp_path):
        where = project(tmp_path, None)
        (where / "film" / "artifacts" / "bed_intake.json").write_text("{nope")
        short = CR.missing_outputs(where, "film", "assets")
        assert any("cannot be read" in m for m in short)


class TestRhythmRepairIsAScript:
    PLAYBOOK = None

    @pytest.fixture(scope="class")
    def playbook(self):
        import verify_rhythm as VR
        return VR.load_playbook()

    def metronome(self, n: int = 60, length: float = 7.0) -> list[dict]:
        """Run #1's defect in miniature: every shot the same length."""
        return [{"id": f"c{i:03d}", "in_seconds": 0.0, "out_seconds": length,
                 "layer": "primary", "source": f"/stills/{i}.jpg"}
                for i in range(n)]

    def test_the_film_does_not_get_longer(self, playbook):
        """THE INVARIANT. Every move is pairwise with a neighbour, because
        the film's length is the narration's length."""
        cuts = self.metronome()
        before = sum(RR.length_of(c) for c in cuts)
        RR.repair(cuts, playbook)
        assert abs(sum(RR.length_of(c) for c in cuts) - before) < 0.002

    def test_the_metronome_is_broken_up(self, playbook):
        import verify_rhythm as VR
        cuts = self.metronome()
        before = VR.distribution(VR.timeline(cuts))["pct_in_fullest_2s_band"]
        RR.repair(cuts, playbook)
        after = VR.distribution(VR.timeline(cuts))["pct_in_fullest_2s_band"]
        assert before == 100.0
        assert after < before, (before, after)

    def test_no_shot_falls_below_the_floor(self, playbook):
        cuts = self.metronome()
        RR.repair(cuts, playbook)
        assert min(RR.length_of(c) for c in cuts) >= RR.MIN_SHOT_SECONDS

    def test_a_beat_band_is_respected(self, playbook):
        """A `transition` is 1.5-3.5s in the playbook, and the repair may
        not push one outside its own band to fix the distribution."""
        cuts = self.metronome()
        for cut in cuts[::5]:
            cut["beat"] = "transition"
            cut["out_seconds"] = 3.0
        RR.repair(cuts, playbook)
        lo, hi = playbook["rhythm"]["targets"]["transition"]["shot_seconds"]
        for cut in cuts:
            if cut.get("beat") == "transition":
                assert lo <= RR.length_of(cut) <= hi

    def test_a_video_clip_is_never_stretched(self, playbook):
        """A still holds as long as you like; a clip runs out. The script
        cannot measure the file, so it does not lengthen one."""
        cuts = self.metronome()
        cuts[3]["source"] = "/clips/pathe_1941.mp4"
        was = RR.length_of(cuts[3])
        RR.repair(cuts, playbook)
        assert RR.length_of(cuts[3]) <= was + 1e-9

    def test_what_a_boundary_cannot_fix_is_said_so(self, playbook):
        """The cuts-per-minute curve cannot be reached by nudging
        boundaries — flow across each one is capped — and claiming
        otherwise would be worse than the gate."""
        cuts = self.metronome()
        notes = RR.repair(cuts, playbook)
        blocked = [n for n in notes if n.startswith("NOT REPAIRABLE")]
        assert blocked and "cuts-per-minute" in blocked[0]
        assert "scene plan" in blocked[0]

    def test_it_lives_in_scripts_not_in_a_project(self):
        assert (ROOT / "scripts" / "repair_rhythm.py").exists()
        strays = list((ROOT / "projects").glob("*/repair*.py"))
        assert strays == [], f"a stage is still authoring this: {strays}"


class TestAFailedStageLeavesEvidence:
    MAX_TURNS = {"subtype": "error_max_turns", "is_error": True,
                 "num_turns": 82, "result": None,
                 "terminal_reason": "max_turns",
                 "total_cost_usd": 7.742878,
                 "errors": ["Reached maximum number of turns (81)"],
                 "permission_denials": [{"tool_name": "Bash"},
                                        {"tool_name": "Bash"}]}

    def row(self, blob):
        return SU.summarise(blob, "edit", 1623.0, 1)

    def test_a_stage_that_said_nothing_still_reports_how_it_ended(self):
        """THE CONTROL: 2026-11-20's edit stage, which reported nothing."""
        text = SU.report_text(self.MAX_TURNS, self.row(self.MAX_TURNS))
        assert text.strip(), "an empty failure message is what this fixes"
        assert "error_max_turns" in text
        assert "max_turns" in text
        assert "$7.74" in text

    def test_it_names_the_denials_and_the_errors(self):
        text = SU.report_text(self.MAX_TURNS, self.row(self.MAX_TURNS))
        assert "2 permission request(s)" in text
        assert "Reached maximum number of turns" in text

    def test_a_closing_report_is_still_preferred(self):
        blob = dict(self.MAX_TURNS, result="I finished the edit. Here is what")
        text = SU.report_text(blob, self.row(blob))
        assert text == "I finished the edit. Here is what"

    def test_it_says_a_capped_stage_has_not_finished(self):
        text = SU.report_text(self.MAX_TURNS, self.row(self.MAX_TURNS))
        assert "has NOT finished" in text

    def test_the_report_is_always_written(self, tmp_path):
        result = tmp_path / "edit_stage.json"
        result.write_text(json.dumps(self.MAX_TURNS))
        report = tmp_path / "edit_stage.log"
        SU.main.__globals__["sys"].argv = [
            "stage_usage.py", str(result), "--stage", "edit",
            "--seconds", "1623", "--report", str(report)]
        SU.main()
        assert report.exists() and report.stat().st_size > 0


class TestTheRunnerReadsTheFileThatExists:
    def test_the_three_failure_sites_use_the_helper(self):
        assert RUN_WEEKLY.count("stage_evidence \"$LOGDIR/") == 3

    def test_no_failure_message_tails_a_lone_log(self):
        assert "_stage.log\" 2>/dev/null" not in RUN_WEEKLY, (
            "that is the pattern that produced an empty message")

    def test_the_helper_tries_json_last_and_says_which_it_read(self):
        helper = RUN_WEEKLY[RUN_WEEKLY.index("stage_evidence() {"):]
        helper = helper[:helper.index("\nfail() {")]
        assert '"$base.log" "$base.err" "$base.json"' in helper
        assert "from $(basename" in helper


class TestTheWallCapLetsAStageReport:
    """Three runs of the assets stage measured nothing at all.

    `assets_stage.json` was 0 bytes on 2026-11-11, -13 and -20, and the
    ledger rows read "1h00m wall, None turns, $0.00" — which looks like a
    cheap stage and is an unmeasured one. The watchdog sent TERM, slept ten
    seconds and sent KILL, and the CLI never got to flush its result
    record, so the stage's turn cap has never been compared with anything.

    Thirty seconds now, and the condition is the process EXITING rather
    than the file appearing: a file that is non-empty may still be
    half-written, and the only moment the record is certainly complete is
    after its writer is gone.
    """

    def test_the_watchdog_waits_for_the_writer(self):
        watchdog = RUN_WEEKLY[RUN_WEEKLY.index("THE WALL CAP."):]
        watchdog = watchdog[:watchdog.index('wait "$cpid"')]
        assert "kill -TERM" in watchdog and "kill -KILL" in watchdog
        assert "seq 1 30" in watchdog, "thirty seconds to write a result"
        assert 'kill -0 "$cpid" 2>/dev/null || break' in watchdog
        assert "sleep 10\n" not in watchdog, (
            "the blind ten-second sleep is what produced 0-byte records")

    def test_term_still_comes_before_kill(self):
        watchdog = RUN_WEEKLY[RUN_WEEKLY.index("THE WALL CAP."):]
        watchdog = watchdog[:watchdog.index('wait "$cpid"')]
        assert watchdog.index("kill -TERM") < watchdog.index("kill -KILL")

    def test_the_cap_is_passed_to_the_reporter(self):
        assert '--wall-min "$wall_min"' in RUN_WEEKLY

    def test_an_empty_record_beside_the_marker_is_named(self, tmp_path):
        """THE CONTROL: the assets stage's own shape — a 0-byte result and
        the watchdog's marker beside it."""
        result = tmp_path / "assets_stage.json"
        result.write_text("")
        (tmp_path / "assets_stage.timedout").write_text("")
        blob = SU.load(result)
        assert SU.killed_by_wall_cap(result, blob)
        row = SU.summarise(blob, "assets", 3600.0, 1, 60)
        assert "KILLED BY THE WALL CAP at 60 min" in SU.line(row)
        assert "no figures" in SU.line(row)

    def test_the_report_says_the_figures_were_never_written(self, tmp_path):
        result = tmp_path / "assets_stage.json"
        result.write_text("")
        (tmp_path / "assets_stage.timedout").write_text("")
        row = SU.summarise(SU.load(result), "assets", 3600.0, 1, 60)
        text = SU.report_text({}, row)
        assert "KILLED BY THE WALL CAP at 60 minutes" in text
        assert "not because the stage was cheap" in text

    def test_a_stage_that_wrote_its_record_is_not_blamed_on_the_cap(self,
                                                                    tmp_path):
        """Running over the clock having finished is a different thing and
        keeps its real figures."""
        result = tmp_path / "edit_stage.json"
        result.write_text(json.dumps({"subtype": "success", "num_turns": 12,
                                      "total_cost_usd": 1.5}))
        (tmp_path / "edit_stage.timedout").write_text("")
        blob = SU.load(result)
        assert not SU.killed_by_wall_cap(result, blob)

    def test_no_marker_means_no_claim(self, tmp_path):
        """An empty record with no marker is a stage that wrote nothing for
        some other reason, and saying "the wall cap" would be a guess."""
        result = tmp_path / "x_stage.json"
        result.write_text("")
        assert not SU.killed_by_wall_cap(result, SU.load(result))

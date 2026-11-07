"""What a stage cost, and why it stopped, read from the right fields.

WHY THIS TEST EXISTS
--------------------
The 2026-11-06 render stage was recorded in the run log as

    usage: render, 2h45m wall, 1 turns, $212.43, 0 out, ERROR (success)

and the runner then FAILED THE RUN instead of sleeping and resuming. Two
separate defects, both in how a result record was read:

  1. `scripts/usage_limit.py` matched only prose, and only prose with the
     word session, usage or rate against "limit". The message was "You've
     hit your 5-hour limit · resets 2:20am (America/Toronto)" — the window
     is named after its length now — while the JSON said
     `"api_error": "usage_limit_reached"` in as many words. The reset time
     parsed perfectly. The whole resume machinery was intact and was never
     reached, and the film was lost for the sake of five regexes.

  2. `scripts/stage_usage.py` read `usage` and `num_turns`, which on a
     result record that ends in an api_error describe the LAST EXCHANGE —
     the one that got the 429 and did nothing. The session was in
     `modelUsage`: 1,222 turns, 404K output, 388,077,078 cache-read tokens.
     So the most expensive stage ever run was logged as a no-op, with the
     word "success" next to it.

The real record is the fixture. A test written against a hand-made shape
would not have caught either defect, because both were about the shape a
real failure actually has.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts import stage_usage as su
from scripts import usage_limit as ul

TORONTO = ZoneInfo("America/Toronto")
ROOT = Path(__file__).resolve().parents[2]

#: The result record the runner actually read that night.
REAL_RECORD = ROOT / "logs" / "2026-11-06" / "render_stage.json"

#: The 2026-11-06 render stage's result record, trimmed to the fields that
#: matter. Every number here is measured, not invented.
THE_RENDER_THAT_COST_212 = {
    "type": "result",
    "subtype": "success",          # yes: "success", on a 429
    "is_error": True,
    "num_turns": 1,                # the session was 1,222
    "duration_api_ms": 5455386,
    "total_cost_usd": 212.4325989999998,
    "session_id": "c90d406e-9dfe-4fc9-b2e0-ec30ef6932fe",
    "api_error_status": 429,
    "api_error": "usage_limit_reached",
    "terminal_reason": "api_error",
    "result": "You've hit your 5-hour limit · resets 2:20am (America/Toronto)",
    "permission_denials": [],
    # All zero, because the failed exchange sent nothing.
    "usage": {"input_tokens": 0, "output_tokens": 0,
              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
    # The session.
    "modelUsage": {"claude-opus-5": {
        "inputTokens": 1472,
        "outputTokens": 403792,
        "cacheReadInputTokens": 388077078,
        "cacheCreationInputTokens": 829190,
        "thinkingTokens": 102017,
        "costUSD": 212.4325989999998,
    }},
}


class TestTheFiveHourLimitIsAUsageLimit:
    def test_the_message_that_was_missed(self):
        assert ul.is_usage_limit(THE_RENDER_THAT_COST_212["result"]), (
            "'You've hit your 5-hour limit' is a usage limit. Every pattern "
            "missed it because they assumed the word session, usage or rate "
            "sat against 'limit'.")

    @pytest.mark.parametrize("message", [
        "You've hit your 5-hour limit · resets 2:20am (America/Toronto)",
        "You've hit your weekly limit · resets Monday",
        "You've hit your session limit · resets 12am (America/Toronto)",
        "You have reached your 7-day limit",
        'api_error: "usage_limit_reached"',
    ])
    def test_the_window_can_be_named_anything(self, message):
        """The next word for that slot has not been invented yet."""
        assert ul.is_usage_limit(message), message

    def test_the_json_field_is_matched_by_name(self):
        """`api_error: "usage_limit_reached"` — the field, not the sentence.

        This is the one that had to be read. The prose patterns all required
        the word session, usage or rate against "limit"; the field said so
        outright, with underscores that `[- ]` cannot match, and was never
        looked at. A vendor rewords a sentence; it changes a field
        deliberately.
        """
        assert THE_RENDER_THAT_COST_212["api_error"] == "usage_limit_reached"
        assert "usage_limit_reached" in ul.LIMIT_ERRORS

        # With the prose gone entirely, the field alone must still decide.
        no_prose = dict(THE_RENDER_THAT_COST_212, result="stopped")
        assert ul.structured_limit(no_prose)
        assert not ul.is_usage_limit("stopped"), (
            "the prose in this variant must carry no signal, or the test is "
            "not proving the field was read")

    def test_it_classifies_as_a_usage_limit(self, tmp_path):
        result = tmp_path / "render_stage.json"
        result.write_text(json.dumps(THE_RENDER_THAT_COST_212))
        kind, _ = ul.classify([result, tmp_path / "render_stage.err"])
        assert kind == "usage_limit"

    def test_it_would_have_slept_2h47m_and_resumed_at_0221(self):
        """The timing was always there. Nothing reached it.

        The stage died at 23:33:55 saying "resets 2:20am
        (America/Toronto)". That is 2h46m05s away, plus the 60-second grace
        the module adds so a resume lands after the window opens rather than
        on its exact second: 10,025 seconds, 2h47m05s, back at 02:21.
        """
        died = datetime(2026, 11, 6, 23, 33, 55, tzinfo=TORONTO)
        seconds, source = ul.seconds_until_reset(
            THE_RENDER_THAT_COST_212["result"], now=died)
        assert source == "resets 2:20am (America/Toronto)"
        assert seconds == 10_025, (
            f"expected 2h46m05s to the reset plus {ul.GRACE_SECONDS}s grace "
            f"= 10025s, got {seconds}")
        assert su.hms(seconds) == "2h47m"
        back = died + timedelta(seconds=seconds)
        assert back.strftime("%H:%M") == "02:21"
        assert seconds < ul.MAX_WAIT_SECONDS, (
            "and it is under the six-hour clamp, so the real sleep is the "
            "one the message asked for and not the ceiling")

    @pytest.mark.skipif(not REAL_RECORD.exists(),
                        reason="needs the 2026-11-06 logs on this machine")
    def test_the_actual_record_on_disk_classifies_as_a_usage_limit(self):
        """The file the runner read that night, through the CLI it calls.

        An embedded fixture proves the logic; this proves the file. The
        runner invokes `usage_limit.py --classify <base>.json <base>.err`,
        and .err was zero bytes — every signal was in the JSON.
        """
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "usage_limit.py"),
             "--classify", str(REAL_RECORD),
             str(REAL_RECORD.with_suffix(".err"))],
            capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        assert "KIND=usage_limit" in done.stdout, done.stdout
        assert "RESETS=resets 2:20am (America/Toronto)" in done.stdout

        # And the plain form the runner used before --classify existed:
        # exit 0 means "sleep on this".
        legacy = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "usage_limit.py"),
             str(REAL_RECORD), str(REAL_RECORD.with_suffix(".err"))],
            capture_output=True, text=True)
        assert legacy.returncode == 0, (
            "this is the exact call that returned 1 on 2026-11-06 and failed "
            "the run instead of sleeping")


class TestAFailureIsStillAFailure:
    """Six sleeps on a broken render buries the reason under six more logs."""

    def test_a_crash_is_an_error(self, tmp_path):
        path = tmp_path / "r.json"
        path.write_text(json.dumps({"is_error": True, "result": "KeyError 'cuts'",
                                    "subtype": "error_during_execution"}))
        assert ul.classify([path])[0] == "error"

    def test_a_turn_cap_is_not_a_usage_limit(self, tmp_path):
        """It must not be slept on: the stage would spend the cap again."""
        path = tmp_path / "r.json"
        path.write_text(json.dumps({"is_error": True,
                                    "subtype": "error_max_turns",
                                    "result": "Reached max turns (40)"}))
        assert ul.classify([path])[0] == "max_turns"

    def test_being_overloaded_is_not_a_usage_limit(self, tmp_path):
        """A bare 429 is also what a burst of requests gets."""
        path = tmp_path / "r.json"
        path.write_text(json.dumps({"is_error": True, "api_error_status": 429,
                                    "api_error": "overloaded_error",
                                    "result": "Overloaded"}))
        assert ul.classify([path])[0] == "error"

    def test_a_clean_finish_is_ok(self, tmp_path):
        path = tmp_path / "r.json"
        path.write_text(json.dumps({"is_error": False, "subtype": "success",
                                    "result": "wrote script.json"}))
        assert ul.classify([path])[0] == "ok"


class TestTheCostIsReadFromTheSession:
    @pytest.fixture
    def row(self):
        return su.summarise(THE_RENDER_THAT_COST_212, "render", 9946.0, 1)

    def test_the_turn_count_is_the_sessions_not_the_last_exchanges(self, row):
        # transcript_turns() may find the real 1,222 on this machine; where
        # it cannot, it must not silently report the 1 from the record as if
        # it were the session — both numbers are kept.
        assert row["turns_reported"] == 1
        assert row["turns"] in (1, 1222)

    def test_the_output_tokens_are_not_zero(self, row):
        assert row["output_tokens"] == 403792, (
            "`usage` is zeroed on an api_error result; modelUsage holds the "
            "session. '0 out' made the most expensive stage look like a no-op.")

    def test_the_cache_reads_are_recorded_at_all(self, row):
        assert row["cache_read_tokens"] == 388077078, (
            "cache reads are this pipeline's dominant cost and had never "
            "been written down anywhere.")

    def test_it_says_where_the_money_went(self, row):
        # 388,077,078 tokens at $0.50/MTok.
        assert row["cache_read_usd"] == pytest.approx(194.04, abs=0.02)
        assert row["cache_read_usd"] / row["cost_usd"] > 0.9, (
            "91% of that stage was re-reading its own conversation. If this "
            "ratio is not in the log, nobody can see the problem.")

    def test_it_says_how_big_the_context_was(self, row):
        assert row["context_per_turn"], (
            "cost is context times turns. Without the context size, a cheap "
            "stage and a ruinous one look the same in the log.")

    def test_the_error_is_named_not_called_success(self, row):
        assert row["api_error"] == "usage_limit_reached"
        printed = su.line(row)
        assert "ERROR (usage_limit_reached)" in printed
        assert "ERROR (success)" not in printed, (
            "`subtype` stayed 'success' on a 429, which is how the log came "
            "to read 'ERROR (success)'.")

    def test_the_printed_line_carries_the_whole_story(self, row):
        printed = su.line(row)
        for fragment in ("1222 turns" if row["turns"] == 1222 else "turns",
                         "$212.43", "404K out", "388M cache-read"):
            assert fragment in printed, printed


class TestAHealthyStageStillReadsNormally:
    def test_a_result_with_only_usage_is_still_summarised(self):
        """Not every record has modelUsage; the old field is the fallback."""
        row = su.summarise({
            "num_turns": 12, "total_cost_usd": 1.5, "subtype": "success",
            "is_error": False,
            "usage": {"input_tokens": 10, "output_tokens": 2000,
                      "cache_read_input_tokens": 500000,
                      "cache_creation_input_tokens": 100},
        }, "notes", 60.0, 1)
        assert row["output_tokens"] == 2000
        assert row["cache_read_tokens"] == 500000
        assert row["turns"] == 12
        assert "ERROR" not in su.line(row)


class TestAWeeklyCapIsNotSleptOn:
    """Owner's ruling, 2026-11-07.

    Measured before the fix: EVERY weekly-shaped message fell through to the
    one-hour default, because `RESET_RE` wanted a digit straight after
    "resets" and got a day name — so even "resets Monday 4:00am
    (America/Toronto)", which carries a perfectly good clock, parsed as "no
    reset time in the message". With MAX_RESUMES at 6 that turned a weekly
    exhaustion into six pointless hourly retries and then "giving up": the
    worst of the three available behaviours, and on a subscription with no
    API key there is nothing to fall back to.

    So a weekly cap is its own kind, it fails immediately, and the runner
    Telegrams the reset time and stops.
    """

    @pytest.mark.parametrize("message", [
        "You've hit your weekly limit · resets Monday",
        "You've hit your weekly limit · resets Monday 4:00am (America/Toronto)",
        "You've hit your weekly limit · resets Nov 11 at 2am",
        "Weekly limit reached",
        "You've hit your 7-day limit",
        "You have reached the limit for this week",
    ])
    def test_a_weekly_cap_is_its_own_kind(self, message, tmp_path):
        path = tmp_path / "r.json"
        path.write_text(json.dumps({"is_error": True, "result": message}))
        assert ul.classify([path])[0] == "weekly_limit", message

    def test_a_five_hour_cap_is_still_slept_on(self, tmp_path):
        """The discrimination is the whole point."""
        path = tmp_path / "r.json"
        path.write_text(json.dumps(THE_RENDER_THAT_COST_212))
        assert ul.classify([path])[0] == "usage_limit"

    def test_a_weekly_cap_wins_when_both_sentences_appear(self, tmp_path):
        """One message can carry both; the weekly one is why it cannot go on."""
        path = tmp_path / "r.json"
        path.write_text(json.dumps({"is_error": True, "result":
            "You've hit your 5-hour limit · resets 2:20am. You've also hit "
            "your weekly limit · resets Monday"}))
        assert ul.classify([path])[0] == "weekly_limit"

    def test_it_offers_no_seconds_to_sleep_for(self, tmp_path):
        """A caller that finds SECONDS= will sleep. There must not be one."""
        path = tmp_path / "r.json"
        path.write_text(json.dumps({"is_error": True, "result":
            "You've hit your weekly limit · resets Monday 4:00am"}))
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "usage_limit.py"),
             "--classify", str(path)], capture_output=True, text=True)
        assert "KIND=weekly_limit" in done.stdout
        assert "SECONDS=" not in done.stdout, done.stdout
        assert "RESETS=resets Monday 4:00am" in done.stdout

    def test_the_plain_form_says_do_not_sleep(self, tmp_path):
        """exit 1 — the same answer a fault gets, because both mean stop."""
        path = tmp_path / "r.json"
        path.write_text(json.dumps({"is_error": True, "result":
            "You've hit your weekly limit · resets Monday"}))
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "usage_limit.py"),
             str(path)], capture_output=True, text=True)
        assert done.returncode == 1

    def test_the_runner_fails_without_sleeping(self):
        runner = (ROOT / "scripts" / "run_weekly.sh").read_text()
        block = runner[runner.index('if [[ "$kind" == "weekly_limit" ]]'):]
        block = block[:block.index("\n    fi")]
        # A `sleep` COMMAND, not the word: the branch's own notification
        # says "not sleeping", and matching the substring made the prose
        # fail the test it was describing.
        invocations = [line for line in block.splitlines()
                       if re.match(r"\s*sleep\b", line)]
        assert not invocations, (
            "a weekly cap must not be slept on: " + repr(invocations))
        assert "RESETS=" in block, "the notification must name the reset time"
        assert "kickstart" in block, (
            "and must say how to pick the film back up — every finished "
            "stage is checkpointed, so nothing is lost")


class TestADayNameNoLongerBlocksTheClock:
    """"resets Monday 4:00am" parsed as no time at all."""

    FROZEN = datetime(2026, 11, 7, 23, 33, 55, tzinfo=TORONTO)

    @pytest.mark.parametrize("message", [
        "resets Monday 4:00am (America/Toronto)",
        "resets on Wednesday at 09:30 (America/Toronto)",
        "resets Nov 11 at 2am",
        "resets 11 Nov at 2am",
        "resets tomorrow 1am",
        "resets 2026-11-11 at 3pm",
        "resets 11/11 at 3pm",
        "resets at 3:30pm",
        "resets 09:00",
    ])
    def test_the_clock_is_found(self, message):
        seconds, source = ul.seconds_until_reset(message, now=self.FROZEN)
        assert source != "no reset time in the message", message
        assert 0 < seconds <= ul.MAX_WAIT_SECONDS

    @pytest.mark.parametrize("message", [
        "resets Monday",
        "resets soon",
        "resets when your plan renews",
    ])
    def test_a_message_with_no_clock_still_falls_back(self, message):
        seconds, source = ul.seconds_until_reset(message, now=self.FROZEN)
        assert source == "no reset time in the message"
        assert seconds == ul.DEFAULT_WAIT_SECONDS

    def test_the_day_is_reported_but_not_used_in_the_arithmetic(self):
        """Documented, because it would otherwise be a silent surprise.

        A day that is genuinely days away is a WEEKLY cap, which is never
        slept on, and MAX_WAIT_SECONDS bounds the error at six hours either
        way.
        """
        seconds, _ = ul.seconds_until_reset(
            "resets Monday 4:00am (America/Toronto)", now=self.FROZEN)
        # Saturday 23:33 -> the NEXT 4:00am, which is Sunday's.
        assert seconds < 6 * 3600
        assert ul.reset_phrase("resets Monday 4:00am (America/Toronto)") == \
            "resets Monday 4:00am (America/Toronto)"

"""A usage limit is not a failure, and a failure is not a usage limit.

WHY THIS TEST EXISTS
--------------------
The first attended run's render stage died at 23:30 on one line — "You've hit
your session limit · resets 12am (America/Toronto)" — with nothing wrong
anywhere. The run stalled until credits returned and was resumed by hand.
Unattended that is a lost week.

So the runner sleeps on a usage limit and re-enters the stage. That makes the
DISCRIMINATION the whole safety property: a stage that failed for a real
reason must not be slept on and retried six times, because six sleeps on a
broken render buries the reason under six more logs — the same mistake the
runner already refuses to make with renders.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts import usage_limit as ul

TORONTO = ZoneInfo("America/Toronto")


class TestTellingThemApart:
    @pytest.mark.parametrize("message", [
        "You've hit your session limit · resets 12am (America/Toronto)",
        "Claude usage limit reached. resets at 3pm",
        "You have reached your limit",
        "rate limit exceeded",
        "Upgrade to increase your usage limit",
    ])
    def test_a_usage_limit_is_recognised(self, message):
        assert ul.is_usage_limit(message), message

    @pytest.mark.parametrize("message", [
        "Traceback (most recent call last): KeyError: 'cuts'",
        "no script at projects/x/artifacts/script.json",
        "SystemExit: music beds named in the EDL were not found",
        "ffmpeg: Not allowed to load local resource",
        "FAIL: type lock: c058 at 388.7s: 17 of 23 words move",
        "",
    ])
    def test_a_real_failure_is_not(self, message):
        assert not ul.is_usage_limit(message), (
            f"{message!r} would be slept on and retried six times")


class TestHowLongToWait:
    def test_midnight_from_half_past_eleven_is_half_an_hour(self):
        """The case that actually happened, and the one easiest to get wrong.

        At 23:30 "resets 12am" is thirty minutes away. Read as today's
        midnight it is twenty-three and a half hours in the past.
        """
        now = datetime(2026, 10, 23, 23, 30, tzinfo=TORONTO)
        secs, source = ul.seconds_until_reset(
            "resets 12am (America/Toronto)", now)
        assert 1800 <= secs <= 1800 + ul.GRACE_SECONDS
        assert "12am" in source

    def test_an_afternoon_reset_from_the_morning(self):
        now = datetime(2026, 10, 23, 9, 0, tzinfo=TORONTO)
        secs, _ = ul.seconds_until_reset("resets at 3pm", now)
        assert 6 * 3600 <= secs <= 6 * 3600 + ul.GRACE_SECONDS

    def test_a_reset_already_past_today_is_tomorrow_but_still_capped(self):
        """Tomorrow's 3pm is 23 hours away, and it is NOT slept for.

        The cap wins, and should: waking early costs one resume and a second
        limit message, which is bounded by MAX_RESUMES. Sleeping 23 hours
        costs the weekend and tells nobody. A Claude Code window is about
        five hours, so a reset a day out means the message was misread —
        exactly the case the cap exists for.
        """
        now = datetime(2026, 10, 23, 16, 0, tzinfo=TORONTO)
        secs, _ = ul.seconds_until_reset("resets at 3pm", now)
        assert secs == ul.MAX_WAIT_SECONDS

    def test_no_time_in_the_message_waits_the_default(self):
        secs, source = ul.seconds_until_reset("you have reached your limit")
        assert secs == ul.DEFAULT_WAIT_SECONDS
        assert "no reset time" in source

    def test_a_wait_is_capped_whatever_the_message_claims(self):
        """A parse that goes wrong costs an hour of a Friday, not a weekend."""
        now = datetime(2026, 10, 23, 16, 0, tzinfo=TORONTO)
        secs, _ = ul.seconds_until_reset("resets at 3pm", now)
        assert secs <= ul.MAX_WAIT_SECONDS

    def test_it_comes_back_after_the_window_opens_not_on_it(self):
        now = datetime(2026, 10, 23, 23, 30, tzinfo=TORONTO)
        secs, _ = ul.seconds_until_reset("resets 12am (America/Toronto)", now)
        assert secs > 1800, "returning on the exact second races the reset"


class TestReadingTheStageOutput:
    def test_a_limit_inside_a_json_result_is_found(self, tmp_path):
        """With --output-format json the message is a field, not a line."""
        path = tmp_path / "r.json"
        path.write_text(json.dumps({
            "is_error": True, "subtype": "error",
            "result": "You've hit your session limit · resets 12am (America/Toronto)"}))
        assert ul.is_usage_limit(ul.text_of(path))

    def test_a_plain_stderr_line_is_found(self, tmp_path):
        path = tmp_path / "r.err"
        path.write_text("You've hit your session limit · resets 12am\n")
        assert ul.is_usage_limit(ul.text_of(path))

    def test_a_successful_json_result_is_not_a_limit(self, tmp_path):
        path = tmp_path / "ok.json"
        path.write_text(json.dumps({
            "is_error": False, "num_turns": 47,
            "result": "Done. The pipeline ran research through script."}))
        assert not ul.is_usage_limit(ul.text_of(path))

    def test_a_missing_file_is_not_a_limit(self, tmp_path):
        assert ul.text_of(tmp_path / "nope.json") == ""

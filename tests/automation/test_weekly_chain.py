"""The weekly chain: the joins between stages, and the rules that stop it.

A weekly run is five programs that have never met, agreeing on filenames. The
dry run proves the joins; these pin the rules that are easy to get wrong and
expensive to get wrong at three in the morning.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from lib import telegram


class TestTheGateCannotBeWonBySilence:
    def test_a_timeout_is_not_an_approval(self, monkeypatch):
        """A film that publishes because nobody said no is the thing this
        gate exists to prevent."""
        monkeypatch.setattr(telegram, "updates", lambda *a, **k: [])
        verdict, _ = telegram.await_reply(0, hours=0.0005, poll_seconds=1)
        assert verdict == "timeout"

    @pytest.mark.parametrize("text,expected", [
        ("ok", "ok"), ("OK", "ok"), ("yes", "ok"), ("go", "ok"),
        ("no", "no"), ("NO", "no"), ("stop", "no"), ("abort", "no"),
        ("make act 2 shorter", "notes"), ("the title is wrong", "notes"),
    ])
    def test_the_reply_is_read_as_written(self, monkeypatch, text, expected):
        monkeypatch.setattr(telegram, "updates", lambda *a, **k: [
            {"update_id": 1, "message": {"text": text}}])
        verdict, got = telegram.await_reply(0, hours=0.01, poll_seconds=1)
        assert verdict == expected and got == text

    def test_last_week_s_reply_is_not_this_week_s_answer(self, monkeypatch):
        """drain() marks everything already waiting as read. Without it a
        reply sent to the bot on Tuesday answers Friday's gate."""
        monkeypatch.setattr(telegram, "updates",
                            lambda *a, **k: [{"update_id": 41}, {"update_id": 42}])
        assert telegram.drain() == 43


class TestWhatIsLoadBearing:
    def test_a_notification_that_cannot_be_sent_does_not_raise(self, monkeypatch):
        """A notifier that raises stops a render that was going to finish."""
        monkeypatch.setattr(telegram, "_call", lambda *a, **k: (_ for _ in ()).throw(
            telegram.TelegramNotConfigured("no token")))
        assert telegram.send("anything") is None

    def test_the_gate_itself_does_raise(self, monkeypatch):
        """If the gate cannot be reached the run must stop, not continue."""
        monkeypatch.setattr(telegram, "_call", lambda *a, **k: (_ for _ in ()).throw(
            telegram.TelegramNotConfigured("no token")))
        with pytest.raises(telegram.TelegramNotConfigured):
            telegram.require("the script")

    def test_credentials_come_from_outside_the_repository(self):
        """The repository is pushed and the token is not."""
        assert "wak3up-docs/.env" in str(telegram.ENV_PATH)
        assert "OpenMontage" not in str(telegram.ENV_PATH)


class TestScheduling:
    def test_it_publishes_on_a_monday_at_nine(self):
        from scripts.publish_doc import next_monday

        when = next_monday()
        assert when.weekday() == 0
        local = when.astimezone(__import__("zoneinfo").ZoneInfo("America/Toronto"))
        assert (local.hour, local.minute) == (9, 0)

    def test_a_run_that_finishes_on_monday_waits_a_week(self):
        """Next Monday, not this one: a run finishing Monday morning must not
        schedule for four hours' time."""
        from scripts.publish_doc import next_monday

        assert (next_monday() - datetime.now(timezone.utc)).days >= 0
        assert (next_monday() - datetime.now(timezone.utc)).days <= 7


class TestTheTokenRule:
    def test_seven_days_is_the_testing_mode_limit(self):
        from scripts import publish_doc

        assert publish_doc.TESTING_MODE_DAYS == 7

    def test_a_young_token_is_not_proof(self, monkeypatch, tmp_path):
        """It works today and that does not mean it works next Friday."""
        from scripts import publish_doc

        monkeypatch.setattr(publish_doc, "token_age_days", lambda: 2.0)
        monkeypatch.setattr(publish_doc, "TOKEN", tmp_path / "t.pkl")
        monkeypatch.setattr(publish_doc, "TOKEN_SEEN", tmp_path / "s.json")
        (tmp_path / "t.pkl").write_bytes(b"x")
        monkeypatch.setattr(publish_doc, "pickle", _Pickle())
        ok, message = publish_doc.check_token()
        assert not ok and "does not yet PROVE" in message

    def test_an_old_token_is(self, monkeypatch, tmp_path):
        from scripts import publish_doc

        monkeypatch.setattr(publish_doc, "token_age_days", lambda: 30.0)
        monkeypatch.setattr(publish_doc, "TOKEN", tmp_path / "t.pkl")
        monkeypatch.setattr(publish_doc, "TOKEN_SEEN", tmp_path / "s.json")
        (tmp_path / "t.pkl").write_bytes(b"x")
        (tmp_path / "s.json").write_text(json.dumps({"first_seen": "2026-01-01T00:00:00+00:00"}))
        monkeypatch.setattr(publish_doc, "pickle", _Pickle())
        ok, message = publish_doc.check_token()
        assert ok and "consent screen is published" in message


class _Credentials:
    refresh_token = "r"
    expired = False
    scopes: list[str] = []

    def refresh(self, request):
        return None


class _Pickle:
    @staticmethod
    def loads(data):
        return _Credentials()

    @staticmethod
    def dumps(obj):
        return b"x"


class TestMetricsRefuseToGuess:
    def test_three_films_before_the_picker_weights_anything(self):
        from scripts.pull_metrics import MIN_FILMS_TO_WEIGHT

        assert MIN_FILMS_TO_WEIGHT == 3

    def test_a_missing_scope_is_reported_not_zeroed(self):
        """A metrics file full of zeros is worse than no metrics file."""
        from scripts.pull_metrics import has_analytics_scope

        assert not has_analytics_scope(_Credentials())
        upload_only = _Credentials()
        upload_only.scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        assert not has_analytics_scope(upload_only)

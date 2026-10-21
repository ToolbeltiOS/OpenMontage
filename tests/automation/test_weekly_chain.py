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
    """What actually expires one, established 2026-10-21.

    The first version of this pinned a seven-day testing-mode proof. That
    was the wrong rule: the Mac's client_secrets.json and the droplet's
    carry the SAME client_id in the same project, and the droplet's uploader
    refreshes it daily — which testing mode would kill after a week. The
    consent screen is published, nothing expires on a schedule, and the
    March invalid_grant was six months of disuse.
    """

    def test_the_live_rule_is_inactivity_not_a_schedule(self):
        from scripts import publish_doc

        assert publish_doc.INACTIVITY_MONTHS == 6
        assert publish_doc.WARN_AFTER_MONTHS < publish_doc.INACTIVITY_MONTHS

    def test_a_weekly_run_is_far_inside_it(self):
        from scripts import publish_doc

        assert 7 < publish_doc.INACTIVITY_MONTHS * 30 / 10

    def test_a_working_token_is_ready_rather_than_unproven(self, monkeypatch, tmp_path):
        """It used to refuse a token under seven days old. Nothing about
        this client's token needs proving."""
        from scripts import publish_doc

        monkeypatch.setattr(publish_doc, "TOKEN", tmp_path / "t.pkl")
        monkeypatch.setattr(publish_doc, "TOKEN_SEEN", tmp_path / "s.json")
        (tmp_path / "t.pkl").write_bytes(b"x")
        monkeypatch.setattr(publish_doc, "pickle", _Pickle())
        ok, message = publish_doc.check_token()
        assert ok and "nothing expires on a schedule" in message

    def test_a_long_idle_gap_warns_before_the_cliff(self, monkeypatch, tmp_path):
        from datetime import datetime, timedelta, timezone

        from scripts import publish_doc

        monkeypatch.setattr(publish_doc, "TOKEN", tmp_path / "t.pkl")
        monkeypatch.setattr(publish_doc, "TOKEN_SEEN", tmp_path / "s.json")
        (tmp_path / "t.pkl").write_bytes(b"x")
        stale = (datetime.now(timezone.utc) - timedelta(days=150)).isoformat()
        (tmp_path / "s.json").write_text(
            '{"first_seen": "%s", "last_used": "%s"}' % (stale, stale))
        monkeypatch.setattr(publish_doc, "pickle", _Pickle())
        ok, message = publish_doc.check_token()
        assert ok and "unused" in message and "5.0 months" in message

    def test_a_dead_token_blames_inactivity_when_the_gap_fits(self, monkeypatch, tmp_path):
        from datetime import datetime, timedelta, timezone

        from scripts import publish_doc

        monkeypatch.setattr(publish_doc, "TOKEN", tmp_path / "t.pkl")
        monkeypatch.setattr(publish_doc, "TOKEN_SEEN", tmp_path / "s.json")
        (tmp_path / "t.pkl").write_bytes(b"x")
        stale = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        (tmp_path / "s.json").write_text(
            '{"first_seen": "%s", "last_used": "%s"}' % (stale, stale))

        class _Dead(_Pickle):
            @staticmethod
            def loads(data):
                class _C(_Credentials):
                    def refresh(self, request):
                        raise RuntimeError("invalid_grant")
                return _C()

        monkeypatch.setattr(publish_doc, "pickle", _Dead())
        ok, message = publish_doc.check_token()
        assert not ok and "inactivity limit" in message


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


def facts(**overrides):
    """What `describe` returns, with everything off by default.

    Constructed rather than fetched: the suite blocks the network, and a
    test that passes because Wikidata was unreachable is worse than no test.
    What is being pinned here is the RULE — which combination of properties
    means what — and the rule is mine. The vocabulary itself is checked by
    running the picker, which the briefs in reports/briefs/ are the output of.
    """
    return {"id": "Q1", "label": "A Thing", "description": "",
            "sitelinks": 100, "is_a_class": False,
            "contains_subdivisions": False, "has_coordinates": False,
            "is_a_person": False, "is_dated": False, "instance_of": [],
            **overrides}


class TestFilmSized:
    """A container is a real thing and is not a documentary."""

    def test_something_that_contains_subdivisions_is_a_container(self):
        from lib.entity_check import _verdict

        verdict = _verdict("Japan", "Q17", facts(has_coordinates=True,
                                                 contains_subdivisions=True))
        assert not verdict["subject"] and verdict["container"] is True
        assert "contains the subjects" in verdict["why"]

    @pytest.mark.parametrize("qid,name", [
        ("Q6256", "country"), ("Q5107", "continent"), ("Q578", "century")])
    def test_and_so_is_a_container_class(self, qid, name):
        from lib.entity_check import _verdict

        verdict = _verdict("X", "Q1", facts(instance_of=[qid],
                                            has_coordinates=True))
        assert not verdict["subject"] and verdict["container"] is True
        assert name in verdict["why"]

    def test_a_place_that_contains_nothing_is_film_sized(self):
        """Easter Island is an administrative territorial entity and is
        exactly the size of a film, which is why that class is not on the
        container list — only P150 and a short explicit set are."""
        from lib.entity_check import _verdict

        verdict = _verdict("Easter Island", "Q14452",
                           facts(has_coordinates=True,
                                 instance_of=["Q23442", "Q56061"]))
        assert verdict["subject"] and "somewhere" in verdict["why"]

    def test_a_container_is_split_rather_than_dropped(self, monkeypatch):
        """The audience that watched two Shorts about Japan watched them for
        something inside Japan.

        Patched through sys.modules["entity_check"], not lib.entity_check.
        The repository puts lib/ on sys.path, so a bare `import entity_check`
        inside a function and `from lib import entity_check` at the top of a
        test load TWO module objects, and patching one leaves the other
        untouched — which is also two lru_caches and two rate-limit clocks,
        and is worth knowing about.
        """
        import sys

        from scripts import pick_topic

        sys.path.insert(0, str(pick_topic.ROOT / "lib"))
        import entity_check

        monkeypatch.setattr(entity_check, "article_item",
                            lambda p: ("Q1", "Japan"))
        monkeypatch.setattr(entity_check, "article_links",
                            lambda t, limit=40: ["Mount Fuji", "Himeji Castle"])
        monkeypatch.setattr(entity_check, "is_a_subject",
                            lambda p, *a, **k: {"subject": True, "why": "it is somewhere"})
        parts = pick_topic.split_container({
            "entity": "Japan", "median_views": 428, "shorts": 3,
            "best_views": 800, "mean_engagement": 0.5,
            "titles": [], "urls": []}, limit=2)
        assert [p["entity"] for p in parts] == ["Mount Fuji", "Himeji Castle"]
        for part in parts:
            assert part["derived_from"] == "Japan"
            assert part["median_views"] == 214, "the halving was not applied"
            assert "weaker" in part["note"]

    def test_a_part_ranks_where_its_halved_score_puts_it(self):
        """Two parts of Japan at 214 came above Noah at 366 purely because
        Japan was second in the list."""
        candidates = [{"entity": "Part A", "median_views": 214, "shorts": 2},
                      {"entity": "Noah", "median_views": 366, "shorts": 4}]
        candidates.sort(key=lambda c: (c["median_views"], c["shorts"]),
                        reverse=True)
        assert candidates[0]["entity"] == "Noah"


class TestClusterAndSupportingAreDifferentQuestions:
    """A cluster must carry a film; a supporting entity must only be real."""

    def test_a_script_with_no_coordinates_fails_as_a_cluster(self):
        from lib.entity_check import _verdict

        assert not _verdict("Rongorongo", "Q209764", facts())["subject"]

    def test_and_passes_as_a_supporting_entity(self):
        from lib.entity_check import _verdict

        verdict = _verdict("Rongorongo", "Q209764", facts(sitelinks=40),
                           min_sitelinks=3, as_cluster=False)
        assert verdict["subject"] and "cite" in verdict["why"]

    def test_an_obscure_place_fails_as_a_cluster_and_passes_as_support(self):
        """Orongo has fourteen language editions: too few to carry a film,
        and exactly the right size for an act."""
        from lib.entity_check import _verdict

        orongo = facts(sitelinks=14, has_coordinates=True)
        assert not _verdict("Orongo", "Q1551834", orongo)["subject"]
        assert _verdict("Orongo", "Q1551834", orongo,
                        min_sitelinks=3, as_cluster=False)["subject"]

    def test_a_class_passes_as_support_and_never_as_a_cluster(self):
        """A film is made of moai; a film is not about "moai"."""
        from lib.entity_check import _verdict

        moai = facts(is_a_class=True, sitelinks=40)
        assert not _verdict("Moai", "Q1", moai)["subject"]
        assert _verdict("Moai", "Q1", moai, min_sitelinks=3,
                        as_cluster=False)["subject"]

    def test_a_container_fails_as_either(self):
        from lib.entity_check import _verdict

        japan = facts(contains_subdivisions=True, has_coordinates=True)
        assert not _verdict("Japan", "Q17", japan)["subject"]
        assert not _verdict("Japan", "Q17", japan, min_sitelinks=3,
                            as_cluster=False)["subject"]

    def test_a_named_thing_is_not_a_class_whatever_subclass_of_says(self):
        """`subclass of` alone called rongorongo a kind of thing. Wikidata's
        convention is that a class is lowercase and a proper noun is not, and
        `describe` applies it."""
        from lib.entity_check import SUBCLASS_OF

        claims = {SUBCLASS_OF: [{}]}
        assert (SUBCLASS_OF in claims and "Rongorongo"[:1].islower()) is False
        assert (SUBCLASS_OF in claims and "mountain"[:1].islower()) is True


class TestTheOwnerCanOverrideTheAngle:
    def test_the_constraint_replaces_the_derived_angle(self):
        """The picker cannot know what a previous film already argued."""
        from scripts.pick_topic import angle_of

        angle = angle_of({"entity": "Easter Island",
                          "titles": ["The Walking Statues of Easter Island"]})
        assert "constraint" in angle
        assert "rongorongo" in angle["claim"]
        assert "60 seconds" in angle["claim"]

    def test_the_recap_is_capped_and_placed(self):
        from scripts.pick_topic import ANGLE_CONSTRAINTS

        recap = ANGLE_CONSTRAINTS["easter island"]["recap"]
        assert recap["max_seconds"] == 60 and recap["where"] == "act 1"

    def test_the_spine_entities_are_named_not_parsed(self):
        """Guessing which words in a sentence are subjects would answer a
        different question than "can the film be made as specified"."""
        from scripts.pick_topic import ANGLE_CONSTRAINTS

        named = ANGLE_CONSTRAINTS["easter island"]["entities"]
        assert "Rongorongo" in named and "Orongo" in named

    def test_a_subject_with_no_constraint_keeps_its_derived_angle(self):
        from scripts.pick_topic import angle_of

        angle = angle_of({"entity": "Petra", "titles": ["The Petra Problem"]})
        assert "constraint" not in angle
        assert "keep returning to" in angle["claim"]


class TestDeafnessIsNotSilence:
    """The first live rehearsal returned "no reply in 12h" while the owner
    was looking at their reply on screen.

    Another process — the Shorts command handler, every five minutes from
    cron — was polling the same bot token. Telegram answers the second poller
    with `Conflict: terminated by other getUpdates request` and lets the
    first one CONSUME the message. Every poll failed, the gate called it
    silence, and silence blames the human.
    """

    def test_every_poll_failing_is_not_a_timeout(self, monkeypatch):
        def conflict(*args, **kwargs):
            raise RuntimeError("telegram getUpdates failed: Conflict: "
                               "terminated by other getUpdates request")

        monkeypatch.setattr(telegram, "updates", conflict)
        monkeypatch.setattr(telegram.time, "sleep", lambda s: None)
        verdict, detail = telegram.await_reply(0, hours=0.002, poll_seconds=1)
        assert verdict == "unreadable"
        assert "Conflict" in detail

    def test_real_silence_is_still_a_timeout(self, monkeypatch):
        """A reachable chat that nobody answered is the person's call, and
        aborting is still the right outcome."""
        monkeypatch.setattr(telegram, "updates", lambda *a, **k: [])
        verdict, _ = telegram.await_reply(0, hours=0.002, poll_seconds=1)
        assert verdict == "timeout"

    def test_a_reply_after_a_failed_poll_still_counts(self, monkeypatch):
        """One bad poll must not condemn the whole window."""
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("Conflict: terminated by other getUpdates")
            return [{"update_id": 7, "message": {"text": "ok"}}]

        monkeypatch.setattr(telegram, "updates", flaky)
        monkeypatch.setattr(telegram.time, "sleep", lambda s: None)
        verdict, _ = telegram.await_reply(0, hours=0.05, poll_seconds=1)
        assert verdict == "ok"

    def test_a_webhook_is_caught_before_the_gate_posts(self, monkeypatch):
        """getUpdates cannot be used while a webhook is set, so the gate
        would post and never read."""
        class _Response:
            @staticmethod
            def json():
                return {"result": {"url": "https://example.invalid/hook"}}

        import requests

        monkeypatch.setattr(requests, "get", lambda *a, **k: _Response())
        monkeypatch.setattr(telegram, "credentials", lambda *a, **k: ("t", "c"))
        ok, why = telegram.exclusive()
        assert not ok and "webhook" in why

    def test_a_competing_poller_is_named_when_the_probe_catches_it(self, monkeypatch):
        class _Response:
            @staticmethod
            def json():
                return {"result": {}}

        import requests

        monkeypatch.setattr(requests, "get", lambda *a, **k: _Response())
        monkeypatch.setattr(telegram, "credentials", lambda *a, **k: ("t", "c"))
        monkeypatch.setattr(telegram, "updates", lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("Conflict: terminated by other getUpdates request")))
        ok, why = telegram.exclusive()
        assert not ok
        assert "its own bot" in why

    def test_the_probe_cannot_prove_exclusivity_on_its_own(self):
        """Measured: 995 polls over five minutes against a bot the Shorts
        handler polls every five minutes produced zero conflicts. A probe
        that passes means a webhook is not set and nothing more, and the
        function says so rather than being trusted."""
        import inspect

        source = inspect.getsource(telegram.exclusive)
        assert "zero conflicts" in source
        assert "a webhook is not set and nothing more" in source


class TestTheSharedBotCannotBeMadeSafe:
    """What the rehearsal actually measured, as opposed to what it looked
    like the first time.

    995 polls over five minutes against a bot the Shorts handler polls every
    five minutes produced ZERO conflicts — both pollers return in
    milliseconds, so they rarely overlap. The handler was caught running in
    the same window by watching for the process, and its last-update file
    showed it confirming updates. The theft is silent; the conflict is only
    what made the first one visible.
    """

    def test_a_conflict_backs_off_briefly_and_a_real_error_does_not(self, monkeypatch):
        """Five seconds of backoff is long enough for the other poller to
        read the reply and confirm it."""
        slept = []
        monkeypatch.setattr(telegram.time, "sleep", lambda s: slept.append(s))

        errors = iter([RuntimeError("Conflict: terminated by other getUpdates"),
                       RuntimeError("Connection reset")])

        def failing(*args, **kwargs):
            raise next(errors)

        monkeypatch.setattr(telegram, "updates", failing)
        telegram.await_reply(0, hours=0.0008, poll_seconds=1)
        assert slept[0] < 1, "a conflict must retry almost immediately"
        assert slept[1] == 5, "an ordinary error should still back off"

    def test_the_dedicated_bot_is_declared_not_detected(self, monkeypatch):
        """A competing consumer is invisible: it confirms the update and the
        update is not there, which looks exactly like silence."""
        monkeypatch.delenv(telegram.DOCS_TOKEN_VAR, raising=False)
        monkeypatch.setattr(telegram, "ENV_PATH",
                            __import__("pathlib").Path("/nonexistent"))
        own, why = telegram.dedicated()
        assert not own and "cannot be detected, only avoided" in why

        monkeypatch.setenv(telegram.DOCS_TOKEN_VAR, "123:abc")
        own, why = telegram.dedicated()
        assert own

    def test_the_dedicated_token_wins_over_the_shared_one(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "shared")
        monkeypatch.setenv(telegram.DOCS_TOKEN_VAR, "dedicated")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
        assert telegram.credentials()[0] == "dedicated"

    def test_a_shared_bot_warns_but_does_not_block(self, monkeypatch):
        """The gate still runs on it — refusing outright would have stopped
        a rehearsal that worked."""
        class _Response:
            @staticmethod
            def json():
                return {"result": {}}

        import requests

        monkeypatch.setattr(requests, "get", lambda *a, **k: _Response())
        monkeypatch.setattr(telegram, "credentials", lambda *a, **k: ("t", "c"))
        monkeypatch.setattr(telegram, "updates", lambda *a, **k: [])
        monkeypatch.delenv(telegram.DOCS_TOKEN_VAR, raising=False)
        monkeypatch.setattr(telegram, "ENV_PATH",
                            __import__("pathlib").Path("/nonexistent"))
        ok, why = telegram.exclusive()
        assert ok and "WARNING" in why

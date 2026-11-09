"""Showing the thumbnail must not be able to delay the film.

The script gate blocks on purpose: nothing after it means anything until a
person has read the script. This one is the opposite shape. The thumbnail
is the last thing made, the schedule is the one thing that cannot slip, and
a reply that arrives on Sunday must not decide whether a film goes out on
Monday. So it is posted at delivery, the upload proceeds, and silence
resolves to SETTING IT — because a generated thumbnail beats YouTube's
auto-frame and the worst case of never replying should be the thumbnail you
were shown.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import thumbnail_gate as T  # noqa: E402


class TestTheDeadline:
    """Sunday 20:00 before a Monday 09:00 publish: a whole weekend of
    asking, and thirteen hours in hand."""

    def test_a_monday_publish_falls_back_to_the_sunday_before(self):
        # king-tut's real publish: 2026-11-09T14:00Z = Monday 09:00 EST.
        got = T.deadline_for("2026-11-09T14:00:00+00:00",
                             now=datetime(2026, 11, 6, 20, 0))
        assert got == datetime(2026, 11, 8, 20, 0)

    def test_it_is_before_the_publish_and_after_the_delivery(self):
        delivered = datetime(2026, 11, 6, 23, 0)        # Friday night
        got = T.deadline_for("2026-11-09T14:00:00+00:00", now=delivered)
        assert delivered < got
        assert got < datetime(2026, 11, 9, 9, 0)

    def test_it_is_never_in_the_past(self):
        """A film delivered after its own Sunday — a late re-render — must
        not get a deadline that has already gone, which would set the
        thumbnail before anyone could look at it."""
        late = datetime(2026, 11, 9, 8, 0)              # Monday morning
        got = T.deadline_for("2026-11-09T14:00:00+00:00", now=late)
        assert got > late

    def test_without_a_publish_date_it_is_the_next_sunday(self):
        got = T.deadline_for(None, now=datetime(2026, 11, 4, 12, 0))
        assert got == datetime(2026, 11, 8, 20, 0)
        assert got.weekday() == T.DEADLINE_WEEKDAY


class TestReadingTheReply:
    @pytest.mark.parametrize("word", ["ok", "OK", " okay ", "yes", "y", "good"])
    def test_approval(self, word):
        assert T.classify(word) == "ok"

    @pytest.mark.parametrize("word", ["no", "No", "nope", "n"])
    def test_refusal(self, word):
        assert T.classify(word) == "no"

    def test_anything_else_is_notes(self):
        assert T.classify("title on the right please") == "notes"
        assert T.classify("use the sarcophagus shot") == "notes"

    def test_silence_is_not_approval(self):
        """The deadline is what resolves silence, not this."""
        assert T.classify("") == "none"
        assert T.classify(None) == "none"


class TestResolving:
    @pytest.fixture
    def pending(self, tmp_path, monkeypatch):
        slug = "a-film"
        art = tmp_path / "projects" / slug / "artifacts"
        art.mkdir(parents=True)
        monkeypatch.setattr(T, "ROOT", tmp_path)
        (art / "thumbnail_gate.json").write_text(json.dumps({
            "slug": slug, "state": "waiting", "attempt": 0,
            "variant": {}, "from_cut": "c001", "path": "x.jpg", "offset": 7,
            "posted": "2026-11-06T23:00:00",
            "deadline": "2026-11-08T20:00:00"}))
        return slug, art

    def _telegram(self, monkeypatch, text: str | None):
        class Fake:
            @staticmethod
            def updates(offset=None, timeout=50):
                return ([{"update_id": 8, "message": {"text": text}}]
                        if text is not None else [])

            @staticmethod
            def send(*a, **k):
                return None

            @staticmethod
            def escape(t):
                return t
        monkeypatch.setitem(sys.modules, "telegram", Fake)

    def test_ok_sets_it(self, pending, monkeypatch):
        slug, art = pending
        self._telegram(monkeypatch, "ok")
        calls = []
        monkeypatch.setattr(T, "set_on_video",
                            lambda s, why: calls.append(why) or True)
        assert T.resolve(slug) == "set"
        assert "you said ok" in calls[0]
        assert json.loads((art / "thumbnail_gate.json").read_text())["state"] == "set"

    def test_no_regenerates_rather_than_giving_up(self, pending, monkeypatch):
        slug, _ = pending
        self._telegram(monkeypatch, "no")
        posted = []
        monkeypatch.setattr(T, "post", lambda s, attempt=0, notes=None:
                            posted.append((attempt, notes))
                            or {"attempt": attempt})
        assert "regenerated" in T.resolve(slug)
        assert posted == [(1, None)]

    def test_notes_are_carried_into_the_next_attempt(self, pending, monkeypatch):
        slug, _ = pending
        self._telegram(monkeypatch, "title on the right")
        posted = []
        monkeypatch.setattr(T, "post", lambda s, attempt=0, notes=None:
                            posted.append((attempt, notes))
                            or {"attempt": attempt})
        T.resolve(slug)
        assert posted == [(1, "title on the right")]

    def test_before_the_deadline_silence_waits(self, pending, monkeypatch):
        slug, _ = pending
        self._telegram(monkeypatch, None)
        monkeypatch.setattr(T, "set_on_video",
                            lambda *a: pytest.fail("set it too early"))
        assert "waiting" in T.resolve(slug, now=datetime(2026, 11, 7, 12, 0))

    def test_at_the_deadline_silence_sets_it_anyway(self, pending, monkeypatch):
        """The whole point: not replying costs the film nothing."""
        slug, _ = pending
        self._telegram(monkeypatch, None)
        said = []
        monkeypatch.setattr(T, "set_on_video",
                            lambda s, why: said.append(why) or True)
        assert T.resolve(slug, now=datetime(2026, 11, 8, 20, 1)) == "set"
        assert "no reply" in said[0] and "auto-frame" in said[0]

    def test_a_resolved_gate_is_not_resolved_twice(self, pending, monkeypatch):
        slug, art = pending
        record = json.loads((art / "thumbnail_gate.json").read_text())
        record["state"] = "set"
        (art / "thumbnail_gate.json").write_text(json.dumps(record))
        monkeypatch.setattr(T, "set_on_video",
                            lambda *a: pytest.fail("set twice"))
        assert T.resolve(slug) == "set"


class TestItCannotDelayTheFilm:
    SOURCE = (ROOT / "scripts" / "render_film.py").read_text()

    def test_delivery_posts_it(self):
        assert "from thumbnail_gate import post_quietly" in self.SOURCE

    def test_delivery_does_not_wait_for_an_answer(self):
        after = self.SOURCE[self.SOURCE.index("post_quietly"):]
        for waiting in ("resolve(", "await_reply", "input(", "sleep("):
            assert waiting not in after, (
                f"delivery waits on {waiting!r} — the upload must not depend "
                f"on a reply")

    def test_delivery_calls_the_guarded_entry_point(self):
        assert "from thumbnail_gate import post_quietly" in self.SOURCE
        assert "post_quietly(args.project)" in self.SOURCE


class TestAFailedPostCannotTakeTheFilmDown:
    """THIS WAS A SHAPE TEST AND IT PASSED WHILE THE BEHAVIOUR WAS WRONG.

    It asserted that the source contained `try:` and `except Exception`,
    which it did — and `SystemExit` inherits from `BaseException`, so the
    guard did not catch the most likely failure on this path. Measured: a
    two-minute slice rendered every pass, passed all seven gates, printed
    FILM DELIVERY: PASS, and then exited non-zero because the slice's label
    is not a real project and `build_thumbnail` raises `SystemExit` for
    that. `stage_assets` raises it too, when an asset the props name has
    moved — which is a real film's failure, not a slice's.

    So these call the thing and look at what happens."""

    @pytest.mark.parametrize("error", [
        SystemExit("no render_props.json in any worktree"),
        SystemExit("4 asset(s) in the props do not exist"),
        RuntimeError("telegram is down"),
        OSError("disk full"),
    ], ids=["systemexit-no-props", "systemexit-missing-assets",
            "runtime", "oserror"])
    def test_the_film_survives_it(self, error, monkeypatch):
        def raising(slug, **kw):
            raise error
        monkeypatch.setattr(T, "post", raising)
        said = T.post_quietly("a-film")
        assert "the film is unaffected" in said
        assert type(error).__name__ in said

    def test_a_keyboard_interrupt_still_stops_the_render(self, monkeypatch):
        """Stopping a render by hand must stop it. KeyboardInterrupt is a
        BaseException too, and catching it here would make ctrl-c print a
        note and carry on."""
        def interrupted(slug, **kw):
            raise KeyboardInterrupt()
        monkeypatch.setattr(T, "post", interrupted)
        with pytest.raises(KeyboardInterrupt):
            T.post_quietly("a-film")

    def test_a_working_post_is_reported(self, monkeypatch):
        monkeypatch.setattr(T, "post", lambda slug, **kw: {
            "from_cut": "c001", "deadline": "2026-11-08T20:00:00"})
        said = T.post_quietly("a-film")
        assert "c001" in said and "2026-11-08T20:00:00" in said
        assert "did not run" not in said

    def test_it_only_runs_when_the_film_passed(self):
        source = (ROOT / "scripts" / "render_film.py").read_text()
        assert ("if not problems:\n        from thumbnail_gate import "
                "post_quietly" in source), (
            "a film that FAILED its gates must not post a thumbnail for "
            "approval")

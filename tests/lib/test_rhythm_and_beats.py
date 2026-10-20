"""The rhythm gate has to fail on run #1's edit, and the beats gate on its script.

Run #1 passed every pacing check the repo had — mean hold 6.6s inside the
playbook's 5-8s band, no still over its cap, slideshow risk low — and the film
was still metronomic. A check that cannot fail on the defect is not a check, so
these tests pin the defect itself: a flat cuts-per-minute curve, no long tail,
no short tail, and four fifths of the film inside one two-second band.
"""
from __future__ import annotations

import pytest

from lib import script_beats, verify_rhythm


def metronome(n: int = 182, length: float = 6.6) -> list[dict]:
    """Run #1's shape: every shot the same length, for twenty minutes."""
    return [
        {"id": f"c{i:03d}", "in_seconds": 0.0, "out_seconds": length}
        for i in range(n)
    ]


def varied() -> list[dict]:
    """A film with roughly the same average and an actual distribution.

    Four acts: a burst of 2s shots at each boundary, a body of exposition that
    moves between 6 and 10 seconds rather than sitting on one number, a 20s
    reveal with motion inside it, and a landing held through the air.
    """
    cuts: list[dict] = []
    i = 0

    def add(length: float, beat: str | None = None, **extra) -> None:
        nonlocal i
        cuts.append({"id": f"c{i:03d}", "in_seconds": 0.0, "out_seconds": length,
                     **({"beat": beat} if beat else {}), **extra})
        i += 1

    body = [6.0, 9.0, 7.0, 10.0, 6.5, 8.0, 9.5, 7.5, 6.0, 10.0,
            8.5, 7.0, 9.0, 6.5, 10.0, 7.5]
    for _act in range(4):
        for _ in range(5):                       # a burst at the act boundary
            add(2.0, "transition")
        for length in body:
            add(length, "exposition")
        add(20.0, "reveal", internal_motion=True)
        add(6.0, "landing")
    return cuts


class TestRhythm:
    def test_fails_on_a_metronome(self):
        problems, d = verify_rhythm.check(metronome())
        assert problems, "the gate passed run #1's shape"
        joined = " ".join(problems)
        assert "flat" in joined
        assert "metronome" in joined
        assert d["pct_in_fullest_2s_band"] > 45
        # The tails are reported rather than blocking: an act with no reveal
        # in it is allowed to exist, and a human reads that one.
        notes = " ".join(d["notes"])
        assert "no long tail" in notes
        assert "no short tail" in notes

    def test_the_final_partial_minute_does_not_create_a_spread(self):
        """A film ending at 20:06 has a six-second last minute.

        Counting it as the quietest minute handed run #1 a spread of 10 and a
        pass on a curve that never left 8-10.
        """
        _, d = verify_rhythm.check(metronome())
        assert d["cuts_per_minute_spread"] <= 2
        assert d["whole_minutes_counted"] >= 19

    def test_passes_a_film_with_a_distribution(self):
        problems, d = verify_rhythm.check(varied())
        assert problems == [], problems
        assert d["cuts_per_minute_spread"] >= 4
        assert d["pct_in_fullest_2s_band"] <= 45

    def test_a_long_hold_without_motion_is_rejected(self):
        cuts = varied()
        for c in cuts:
            if c.get("beat") == "reveal":
                c["internal_motion"] = False
        problems, _ = verify_rhythm.check(cuts)
        assert any("internal motion" in p for p in problems)

    def test_source_times_are_not_read_as_timeline_positions(self):
        """in_seconds is a position in the clip, not on the timeline.

        Reading it as a timeline position puts every cut in the first minute.
        """
        cuts = [{"id": "a", "in_seconds": 300.0, "out_seconds": 306.0},
                {"id": "b", "in_seconds": 900.0, "out_seconds": 908.0}]
        shots = verify_rhythm.timeline(cuts)
        assert shots[0]["start"] == 0.0
        assert shots[1]["start"] == pytest.approx(6.0)


SCRIPT_BODY = """[beat: exposition]
{words}

[beat: reveal]
{words}
[air 1.5s]

[beat: landing]
{words}
[air 4.0s]
"""


def script_with(words_per_beat: int, sections: int = 4) -> dict:
    body = SCRIPT_BODY.format(words=" ".join(["word"] * words_per_beat))
    return {
        "sections": [
            {"id": f"act{n + 1}", "text": body} for n in range(sections)
        ]
    }


class TestScriptBeats:
    def test_markers_become_beats_and_air(self):
        beats = script_beats.parse_section(SCRIPT_BODY.format(words="one two three"))
        assert [b["type"] for b in beats] == ["exposition", "reveal", "landing"]
        assert [b["air_after_s"] for b in beats] == [0.0, 1.5, 4.0]

    def test_an_untagged_paragraph_is_exposition(self):
        beats = script_beats.parse_section("A plain paragraph with no marker.")
        assert beats[0]["type"] == "exposition"
        assert beats[0]["tagged"] is False

    def test_duration_is_speech_plus_air(self):
        m = script_beats.measure(script_with(150), wpm=150)
        # 12 beats x 150 words = 1800 words = 720s of speech, plus 4 acts x 5.5s
        assert m["speech_seconds"] == pytest.approx(720.0, abs=1)
        assert m["planned_air_seconds"] == pytest.approx(22.0, abs=0.1)
        assert m["total_seconds"] == pytest.approx(742.0, abs=1)

    def test_an_act_without_its_long_gap_is_rejected(self):
        s = script_with(220)
        s["sections"][2]["text"] = s["sections"][2]["text"].replace("[air 4.0s]", "")
        problems = script_beats.check(s)
        assert any("act3" in p and "4.0s gap" in p for p in problems)

    def test_an_unlisted_air_length_is_rejected(self):
        s = script_with(220)
        s["sections"][0]["text"] = s["sections"][0]["text"].replace("[air 1.5s]", "[air 1.9s]")
        problems = script_beats.check(s)
        assert any("not one of" in p for p in problems)

    def test_a_script_with_no_beat_markers_at_all_is_rejected(self):
        s = {"sections": [{"id": "act1", "text": "Plain prose, no markers."}]}
        problems = script_beats.check(s)
        assert any("no paragraph carries" in p for p in problems)

    def test_the_narration_plan_carries_the_silence(self):
        plan = script_beats.narration_plan(script_with(20, sections=1))
        assert [s["air_after_s"] for s in plan["segments"]] == [0.0, 1.5, 4.0]
        assert all(s["text"] for s in plan["segments"])
        assert "[air" not in " ".join(s["text"] for s in plan["segments"])

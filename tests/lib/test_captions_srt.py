"""The subtitle track: readable cues, and an honest report when it cannot be.

Run #1 burnt word-level captions into the picture, so none of this mattered —
a line that flashed for 30 milliseconds was invisible either way. A sidecar
track has to be correct, so these pin the rules that make it readable and, as
importantly, the one case where the generator refuses to paper over broken
input.
"""
from __future__ import annotations

import pytest

from lib import captions_srt as cap


def words(spec: list[tuple[str, int, int]], breaks: set[int] | None = None):
    breaks = breaks or set()
    return [{"word": w, "startMs": a, "endMs": b,
             **({"pageBreakAfter": True} if i in breaks else {})}
            for i, (w, a, b) in enumerate(spec)]


def even(text: str, start: int = 0, per_word: int = 300, end_break: bool = False, **kw):
    """Evenly timed words. `end_break` marks the LAST word as a sentence end.

    Counting the index by hand is how an earlier version of these tests put
    the break on "broken" instead of "one." and spent a while blaming the
    grouping for it.
    """
    out, t = [], start
    for w in text.split():
        out.append((w, t, t + per_word))
        t += per_word
    if end_break:
        kw["breaks"] = (kw.get("breaks") or set()) | {len(out) - 1}
    return words(out, **kw)


class TestGrouping:
    def test_no_line_is_longer_than_the_limit(self):
        cues = cap.group(even(" ".join(["alpha"] * 40)))
        for cue in cues:
            for line in cue["lines"]:
                assert len(line) <= cap.MAX_CHARS_PER_LINE, line

    def test_no_cue_has_more_than_two_lines(self):
        cues = cap.group(even(" ".join(["beta"] * 60)))
        assert all(len(c["lines"]) <= cap.MAX_LINES for c in cues)

    def test_a_sentence_boundary_closes_the_cue(self):
        w = even("one two three four five six", per_word=400)
        w[2]["pageBreakAfter"] = True
        cues = cap.group(w)
        assert cues[0]["text"] == "one two three"

    def test_a_cue_never_spans_a_pause(self):
        """A cue that straddles written air would hold text through the silence."""
        w = words([("before", 0, 1500), ("after", 6000, 7500)])
        cues = cap.group(w)
        assert len(cues) == 2
        assert cues[1]["startMs"] == 6000
        # It may hold a little into the gap for reading time, but it never
        # reaches the next cue.
        assert cues[0]["endMs"] < cues[1]["startMs"]

    def test_a_readable_cue_leaves_the_gap_alone(self):
        """Written air stays clear where the narration was not rushing."""
        w = words([("one", 0, 1500), ("two", 1500, 3000), ("three", 9000, 10500)])
        cues = cap.group(w)
        assert cues[0]["endMs"] == 3000

    def test_cues_do_not_overlap(self):
        cues = cap.group(even(" ".join(["gamma"] * 50), per_word=120))
        for a, b in zip(cues, cues[1:]):
            assert b["startMs"] >= a["endMs"], (a, b)

    def test_a_short_cue_is_given_room_from_the_silence(self):
        w = words([("Hello.", 0, 200), ("Then", 5000, 5600), ("more.", 5600, 6200)],
                  breaks={0})
        cues = cap.group(w)
        assert (cues[0]["endMs"] - cues[0]["startMs"]) / 1000 >= cap.MIN_CUE_SECONDS

    def test_a_trailing_fragment_is_rebalanced_not_left_alone(self):
        """"lathe." on its own is not a subtitle; the boundary was wrong."""
        w = even(" ".join(["word"] * 18) + " lathe.", per_word=300)
        w[-1]["pageBreakAfter"] = True
        cues = cap.group(w)
        assert not any(c["text"] == "lathe." for c in cues)


class TestItRefusesToPaperOverBrokenInput:
    def test_a_degenerate_cue_is_reported_rather_than_padded(self):
        """58 of run #1's 2,961 word timings are under 40ms.

        One whole eight-word sentence occupies 30 milliseconds. Rebalancing
        around it drags readable words out of a healthy neighbour to pad a cue
        that no amount of words will fix — and split "nine hundred" across a
        boundary doing it. The fix belongs in the alignment, so the generator
        reports it.
        """
        w = (even("It is covered in statues more than nine hundred of them.",
                  per_word=400, end_break=True)
             + words([(x, 8720 + i * 4, 8724 + i * 4) for i, x in
                      enumerate("The heaviest ever raised weighs about eighty-six tonnes.".split())],
                     breaks={7}))  # 8 words, 0-7
        cues = cap.group(w)
        problems = cap.check(cues)
        # It is reported — here as an unreadable rate, because the broken cue
        # is last and could stretch into the silence after it. Mid-film, with
        # a neighbour close behind, it is reported as under the floor instead.
        assert any("characters a second" in p for p in problems)
        # and the healthy neighbour is left intact rather than raided for words
        assert any("nine hundred of them." in c["text"] for c in cues)

    def test_a_degenerate_cue_hemmed_in_on_both_sides_stays_short(self):
        """With speech either side there is no silence to borrow from.

        This is run #1's actual case. The cue cannot be repaired, so it is
        reported rather than padded by raiding its neighbours.
        """
        w = (even("A sentence that runs right up to the broken one.",
                  start=4000, per_word=400, end_break=True)
             + words([(x, 8720 + i * 4, 8724 + i * 4) for i, x in
                      enumerate("The heaviest ever raised weighs tonnes.".split())],
                     breaks={5})  # 6 words, 0-5
             + even("And the next sentence follows immediately after it.",
                    start=8800, per_word=400))
        cues = cap.group(w)
        short = [c for c in cues if (c["endMs"] - c["startMs"]) / 1000 < cap.MIN_CUE_SECONDS]
        assert short, [(c["startMs"], c["endMs"], c["text"]) for c in cues]
        assert any("under the 1.2s floor" in p for p in cap.check(cues))

    def test_an_unreadably_fast_cue_is_reported(self):
        cues = [{"text": "x" * 80, "startMs": 0, "endMs": 1500,
                 "lines": ["x" * 40, "x" * 40]}]
        assert any("characters a second" in p for p in cap.check(cues))

    def test_captions_outlasting_the_film_are_reported(self):
        cues = cap.group(even("one two three four", per_word=600))
        assert any("outlast the film" in p for p in cap.check(cues, media_seconds=1.0))

    def test_a_track_ending_far_early_is_reported(self):
        cues = cap.group(even("one two three four", per_word=600))
        assert any("before the audio" in p for p in cap.check(cues, media_seconds=900.0))


class TestSrtFormat:
    def test_timestamps_use_the_srt_comma(self):
        out = cap.to_srt(cap.group(even("one two three", per_word=600)))
        assert "00:00:00,000 --> " in out

    def test_cues_are_numbered_from_one_and_blank_line_separated(self):
        out = cap.to_srt(cap.group(even(" ".join(["alphabet"] * 24), per_word=400)))
        blocks = [b for b in out.split("\n\n") if b.strip()]
        assert blocks[0].splitlines()[0] == "1"
        assert blocks[1].splitlines()[0] == "2"

    def test_an_hour_long_film_formats_its_hours(self):
        assert cap._ts(3_661_250) == "01:01:01,250"

"""A caption track is uploaded with the film, if it passes its own checker.

Uploading was already there and ungated: `publish_doc` sent
`artifacts/captions.en.srt` whenever the file existed. On 2026-11-15 the
track built for run #6 held 25 cues of 296 over the 20 characters-a-second
ceiling, every one a mid-sentence fragment, and it was held back BY HAND.
Nothing in the chain would have stopped it.

So the default is now: build the track, check the track, upload it on PASS.
On FAIL it is not sent and YouTube's auto-captions stand, because a sidecar
that is precisely unreadable is worse than one that is roughly right — and
the note says which cues and why.

noah, easter-island and they-said-it-couldnt-be-built have no word timings
left at all, so no track is built for them and auto-captions are the honest
state rather than a decision.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "lib"))

import publish_doc as P  # noqa: E402

GOOD = """1
00:00:00,000 --> 00:00:03,000
A line that can be read in the time
it is given.

2
00:00:04,000 --> 00:00:07,000
And a second one, equally unhurried
and within the box.
"""

#: 56 characters in four tenths of a second, on one over-long line: all
#: three rules broken at once.
BAD = """1
00:00:00,000 --> 00:00:00,400
Far too many characters for four tenths of a second here
"""


class TestTheTrackIsReadBackBeforeItIsSent:
    def test_the_cues_come_back_out_of_the_file(self, tmp_path):
        path = tmp_path / "t.srt"
        path.write_text(GOOD)
        cues = P.srt_cues(path)
        assert len(cues) == 2
        assert cues[0]["startMs"] == 0 and cues[0]["endMs"] == 3000
        assert "can be read" in cues[0]["text"]

    def test_it_carries_the_lines_the_file_has(self, tmp_path):
        """`check` measures line length, and a cue with no `lines` raises
        inside it — which is the right answer to an incomplete cue and a
        confusing one to read."""
        path = tmp_path / "t.srt"
        path.write_text(GOOD)
        assert P.srt_cues(path)[0]["lines"] == [
            "A line that can be read in the time", "it is given."]

    def test_what_is_checked_is_what_is_sent(self):
        """Re-deriving from render_props would check the WORDS, and a stale
        SRT beside fresh words would pass and then upload the stale one."""
        source = inspect.getsource(P.caption_verdict)
        assert "srt_cues(captions)" in source


class TestTheVerdictDecidesTheUpload:
    def test_a_good_track_is_cleared(self, tmp_path):
        path = tmp_path / "t.srt"
        path.write_text(GOOD)
        good, why = P.caption_verdict(path, tmp_path / "absent.mp4")
        assert good is True, why
        assert "PASS" in why

    def test_a_bad_track_is_refused_with_its_reasons(self, tmp_path):
        path = tmp_path / "t.srt"
        path.write_text(BAD)
        good, why = P.caption_verdict(path, tmp_path / "absent.mp4")
        assert good is False
        assert "over the 20 ceiling" in why
        assert "under the 1.2s floor" in why

    def test_a_checker_that_cannot_run_is_not_permission(self, tmp_path):
        path = tmp_path / "t.srt"
        path.write_text("this is not an srt at all")
        good, why = P.caption_verdict(path, tmp_path / "absent.mp4")
        assert good is False, why

    def test_the_insert_is_inside_the_cleared_branch(self):
        """The gate has to be load-bearing, not advisory."""
        source = inspect.getsource(P.main)
        cleared = source.index("good, why = caption_verdict(")
        insert = source.index("yt.captions().insert(")
        guard = source.index("if not good:")
        assert cleared < guard < insert, (
            "the upload must sit after the verdict, inside the branch that "
            "passed it")

    def test_a_refusal_says_auto_captions_stand(self):
        source = inspect.getsource(P.main)
        assert "auto-captions stand" in source

    def test_a_missing_track_names_the_films_that_have_no_timings(self):
        """So "no caption file" reads as a fact about those films rather
        than as something nobody got round to."""
        source = inspect.getsource(P.main)
        assert "noah" in source and "easter-island" in source


def code(text: str) -> str:
    """The shell with its comments blanked, for questions about ORDER.

    THE FOURTH TIME THIS TRAP HAS BEEN WALKED INTO TODAY, which is why it
    is a named function here as it already is in
    tests/automation/test_runner_wiring.py. The first `publish_doc.py` in
    run_weekly.sh is in the COMMENT explaining that the publisher refuses
    without a listing — so an `index()` over the raw text puts the publisher
    hundreds of lines before any call to it and calls the order wrong.
    Blank the comments, keep the lines, so indices still mean something.
    """
    return "\n".join("" if line.lstrip().startswith("#") else line
                      for line in text.splitlines())


class TestTheChainBuildsTheTrack:
    RUNNER = code((ROOT / "scripts" / "run_weekly.sh").read_text())

    def test_it_is_built(self):
        assert "captions_srt.py" in self.RUNNER, (
            "publish_doc uploads artifacts/captions.en.srt and nothing in "
            "the chain put one there — the same gap as the listing")

    def test_it_is_built_before_the_publisher_runs(self):
        assert (self.RUNNER.index("captions_srt.py")
                < self.RUNNER.index("publish_doc.py"))

    def test_a_track_that_fails_does_not_fail_the_film(self):
        """Auto-captions are worse than a good sidecar and better than no
        film."""
        at = self.RUNNER.index("captions_srt.py")
        window = self.RUNNER[at - 1200:at + 900]
        assert "auto-captions will stand" in window
        assert 'fail "caption' not in window

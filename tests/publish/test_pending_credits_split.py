"""The backup credits path has to survive a big bank, like the primary one.

WHY THIS EXISTS
---------------
`scripts/publish_doc.py` splits the credits block because YouTube refuses a
comment over about 8,000 characters — measured against the live API, where
7,986 posted, 9,888 came back 400 `processingFailure` and 11,636 came back
400 `commentTextTooLong`.

Then the credits moved. A scheduled film cannot carry a comment at all
(YouTube disables comments on a private video), so the long block is posted
later by `scripts/post_pending_credits.py` — which posted it as ONE comment.
noah's block is 12,502 characters. The split existed, in the one script that
no longer posts the long thing.

Nothing would have failed loudly: the credits are also a hosted page the
description links to, so the attribution is published either way. The comment
would simply have 400'd into the manual list, which is where the credits were
lost the first time this happened.

THE FIXTURE IS 11,000 CHARACTERS, between the 9,888 that failed and the
11,636 that failed, so it is over the limit by a margin the real API has
already refused twice.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "lib"))


def credits_block(chars: int = 11_000) -> str:
    """A credits block of about `chars`, shaped like a real one.

    One asset per line, each with a CC BY attribution and a Commons URL, so
    the lines are long and the split has to fall between them.
    """
    lines = ["Assets, with thanks:"]
    i = 0
    while sum(len(x) + 1 for x in lines) < chars:
        i += 1
        lines.append(
            f"Plate {i:03d} — photograph by Contributor {i:03d}, CC BY-SA 4.0, "
            f"https://commons.wikimedia.org/wiki/File:A_Long_Enough_File_Name_"
            f"To_Be_Realistic_{i:03d}.jpg")
    return "\n".join(lines)


class TestTheSplitItself:
    """`split_comment` is publish_doc's; these pin what the other caller needs."""

    def setup_method(self):
        import publish_doc
        self.P = publish_doc

    def test_an_11k_block_is_split(self):
        text = credits_block()
        assert 9_888 < len(text), len(text)
        parts = self.P.split_comment(text)
        assert len(parts) > 1

    def test_no_part_is_over_the_measured_limit(self):
        parts = self.P.split_comment(credits_block())
        for i, part in enumerate(parts, start=1):
            assert len(part) <= self.P.COMMENT_LIMIT, (
                f"part {i} is {len(part)} chars, over "
                f"{self.P.COMMENT_LIMIT}")

    def test_every_credit_line_survives(self):
        """A lost line is a licence obligation unmet, not a cosmetic loss."""
        text = credits_block()
        parts = self.P.split_comment(text)
        rejoined = "\n".join(
            "\n".join(p.split("\n")[1:]) if p.startswith("(") else p
            for p in parts)
        for line in text.split("\n"):
            assert line in rejoined, line[:60]

    def test_it_never_splits_mid_line(self):
        """Half a credit attributes nothing."""
        text = credits_block()
        originals = set(text.split("\n"))
        for part in self.P.split_comment(text):
            body = part.split("\n")[1:] if part.startswith("(") else \
                part.split("\n")
            for line in body:
                assert line in originals, line[:60]

    def test_a_short_block_is_left_alone(self):
        """The control: no part marker on something that fits."""
        parts = self.P.split_comment("Assets:\nOne line, with thanks.")
        assert len(parts) == 1
        assert not parts[0].startswith("(")


class TestThePendingPosterUsesIt:
    def test_it_calls_split_comment(self):
        """Read as source: importing the module needs google API packages.

        The assertion is on the CALL, because the defect was not a broken
        split — it was a correct split that this script did not reach for.
        """
        source = (ROOT / "scripts" / "post_pending_credits.py").read_text()
        assert "P.split_comment(text)" in source, (
            "post_pending_credits.py posts the credits block without "
            "splitting it; a film with a big asset bank will 400")

    def test_the_first_part_is_what_is_posted(self):
        source = (ROOT / "scripts" / "post_pending_credits.py").read_text()
        assert '"textOriginal": parts[0]' in source, (
            "the top-level comment is not parts[0], so a split block posts "
            "the whole thing again")

    def test_the_rest_go_as_replies_on_our_own_comment(self):
        source = (ROOT / "scripts" / "post_pending_credits.py").read_text()
        assert "topLevelComment\"][\"id\"]" in source or \
               'topLevelComment"]["id"]' in source, source[-400:]
        assert '"parentId": top_id' in source

    def test_idempotency_matches_on_the_posted_head_not_the_whole_block(self):
        """The trap in this fix, and the reason it needed a test.

        A split block's top-level comment begins "(1 of 2)", so a re-run that
        asks `already_ours` about the WHOLE block finds nothing of ours and
        posts the credits a second time — defeating the one guarantee this
        script's docstring makes.
        """
        source = (ROOT / "scripts" / "post_pending_credits.py").read_text()
        assert "already_ours(yt, video_id, parts[0])" in source, (
            "already_ours is asked about the whole block; after a split it "
            "will not recognise our own comment and will post twice")

    def test_a_failed_part_is_recorded_as_owed(self):
        source = (ROOT / "scripts" / "post_pending_credits.py").read_text()
        assert "POST CREDITS PART" in source, (
            "a part that fails to post is swallowed; those lines are a "
            "licence obligation and have to show up as owed")


class TestTheSplitHeadIsStableForIdempotency:
    """`already_ours` compares the first 60 characters. They must not move."""

    def setup_method(self):
        import publish_doc
        self.P = publish_doc

    def test_the_same_block_splits_the_same_way_twice(self):
        text = credits_block()
        first = self.P.split_comment(text)
        second = self.P.split_comment(text)
        assert first == second

    def test_the_head_of_part_one_identifies_the_comment(self):
        """60 characters in, a split block is still distinguishable."""
        text = credits_block()
        parts = self.P.split_comment(text)
        head = parts[0].strip()[:60]
        assert len(head) == 60, head
        assert head != credits_block(400).strip()[:60]

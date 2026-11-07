"""A CSS backdrop does not hold the frame. Remotion's `<Img>` does.

WHY THIS TEST EXISTS
--------------------
king-tut's c006 is a title sequence whose backdrop is a JPEG, painted with
`backgroundImage: url(...)`. Rendering frames 1384-1560 from the same props
on the same machine:

    concurrency 4   all 177 frames match the full render, max 0.2555
    concurrency 1   1385 wrong by 2.518, 1386 by 4.226, 1387 by 5.428

and across three further renders of that range the frame that lost the race
was a different one each time — 3, then 4, then 6. A full render can lose it
too. It simply had not yet, which is the worst way for a defect to be stable:
it made the plate look like the authority on frames it had only been lucky
with.

`useBackdrop` holds the frame with `delayRender` until the bitmap has
decoded, which is the mechanism `<Img>` uses. This reads the source, because
the render that proves it takes minutes and the defect is one unawaited
image.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "remotion-composer" / "src"

#: A CSS backdrop: a style setting `backgroundImage` to a `url(...)` built
#: from a prop. A static gradient is not one — it has nothing to wait for.
CSS_BACKDROP = re.compile(r"backgroundImage:\s*`url\(")


def files_painting_a_css_backdrop() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.tsx")
                  if CSS_BACKDROP.search(p.read_text()))


def test_the_scan_still_finds_the_backdrops():
    """A scanner that matches nothing passes everything."""
    found = files_painting_a_css_backdrop()
    assert len(found) >= 3, [p.name for p in found]
    assert {"TitleSequence.tsx", "ActTitleCard.tsx", "Frame.tsx"} <= {
        p.name for p in found}


@pytest.mark.parametrize("path", files_painting_a_css_backdrop(),
                         ids=lambda p: p.name)
def test_a_css_backdrop_waits_for_its_image(path):
    source = path.read_text()
    assert "useBackdrop(" in source, (
        f"{path.name} paints a CSS backdrop from a prop and never waits for "
        f"it to decode. The frame is captured whenever the renderer is ready, "
        f"so the backdrop is missing from whichever frames lose the race — a "
        f"different one every render.")


class TestTheHookCannotHangARender:
    """A render that never finishes is worse than a bad frame."""

    def source(self) -> str:
        return (SRC / "design" / "useBackdrop.ts").read_text()

    def test_a_failed_image_continues_the_render(self):
        assert "onerror" in self.source(), (
            "an image that 404s would hold delayRender open until Remotion's "
            "timeout and fail the pass")

    def test_an_already_cached_image_continues_the_render(self):
        assert "image.complete" in self.source(), (
            "a cached image may fire no load event at all")

    def test_the_render_is_only_continued_once(self):
        assert "done.current" in self.source(), (
            "continueRender on an already-continued handle is an error")

    def test_a_scene_without_a_backdrop_delays_nothing(self):
        assert re.search(r"src\s*\?\s*delayRender", self.source()), (
            "every scene with no image would pay a delayRender it never "
            "continues")

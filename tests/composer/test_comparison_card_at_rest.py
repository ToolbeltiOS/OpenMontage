"""Whether a comparison card is at rest before it is measured.

A Remotion spring converges on its target without arriving: `leftScale` is
1 - 9.5e-7 two seconds in and 1 - 6.1e-9 three seconds in. Type is rasterised
to whole pixels, so a line whose laid-out position sits on exactly N.5 is
decided by the last bits of the transform above it — and c141's 'casualties',
the bottom line of the card and so the line furthest from the transform
origin, alternated between two glyph images 0.9969px apart for the whole
length of the cut. Type lock read 1.003px and failed the film.

Shrinking the residual cannot fix that. The words that did not flip were not
better damped, they were further from a boundary. Only arriving fixes it.
"""
from __future__ import annotations

import re
from pathlib import Path

from lib import verify_type_lock as vtl

COMPOSER = Path(__file__).resolve().parents[2] / "remotion-composer" / "src"


def code(path: Path) -> str:
    """The source with its comments removed.

    Each fix here explains itself in a comment that names the thing it
    replaced. A scan that reads the comments finds `<Noise>` in the paragraph
    saying why `<Noise>` is gone, and passes or fails for the wrong reason.
    """
    source = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
    return re.sub(r"^\s*//.*$", "", source, flags=re.M)
SETTLE = COMPOSER / "design" / "settle.ts"
COMPARISON = COMPOSER / "components" / "ComparisonCard.tsx"

#: The renderer's frame rate.
FPS = 30


class TestAComparisonCardIsAtRestBeforeItIsMeasured:
    """A spring converges but never arrives.

    `leftScale` is 1 - 9.5e-7 at two seconds and 1 - 6.1e-9 at three. Type is
    rasterised to whole pixels, so a line sitting on exactly N.5 is decided by
    the last bits above it: c141's 'casualties' alternated between two glyph
    images 0.9969px apart for the whole length of the cut, and type lock read
    1.003px. Shrinking the residual cannot fix it — only arriving can.
    """

    def test_every_spring_in_the_card_is_pinned(self):
        source = code(COMPARISON)
        unpinned = [
            m.start() for m in re.finditer(r"= spring\(\{", source)
            if "pinned(frame, " not in source[max(0, m.start() - 24):m.start() + 2]
        ]
        assert not unpinned, (
            f"{len(unpinned)} spring(s) in ComparisonCard are not pinned, so "
            "the card never comes to rest and its type can flip a rounding "
            "boundary on the residual forever")

    def test_the_card_is_pinned_before_type_lock_takes_its_first_sample(self):
        """The invariant that ties the component to the gate.

        type lock samples a cut that declares nothing at `DEFAULT_SETTLE_S`
        and again a second later. If the pin lands after that first sample the
        gate reads the difference between a converging spring and a pinned
        one, which is worse than either — so this is the assertion that would
        have caught the whole class, in either language.
        """
        pinned_at = int(re.search(r"ENTRANCE_PINNED_AT = (\d+)",
                                  code(SETTLE)).group(1))
        first_sample = vtl.DEFAULT_SETTLE_S * FPS
        assert pinned_at < first_sample, (
            f"the card is pinned at frame {pinned_at} but type lock samples "
            f"frame {first_sample:.0f}")

    def test_the_pin_is_late_enough_to_let_the_entrance_play(self):
        """The card's last phase begins at frame 32; a pin before it would
        cut the authored motion off rather than finish it."""
        source = code(COMPARISON)
        starts = [int(m.group(1)) for m in re.finditer(r"frame: frame - (\d+)", source)]
        pinned_at = int(re.search(r"ENTRANCE_PINNED_AT = (\d+)",
                                  code(SETTLE)).group(1))
        assert starts, "no phased springs found — has the card been rewritten?"
        assert pinned_at > max(starts) + 12, (
            f"the pin at frame {pinned_at} lands {pinned_at - max(starts)} frames "
            f"after the last phase begins at {max(starts)}, which is not long "
            "enough for it to be an ending rather than an interruption")

"""Whether type inside a spring is at rest before the gate measures it.

A Remotion spring converges on its target without arriving: `leftScale` is
1 - 9.5e-7 two seconds in and 1 - 6.1e-9 three seconds in. Type is rasterised
to whole pixels, so a line whose laid-out position sits on exactly N.5 is
decided by the last bits of the transform above it — and c141's 'casualties',
the bottom line of a comparison card and so the line furthest from the
transform origin, alternated between two glyph images 0.9969px apart for the
whole length of the cut. Type lock read 1.003px and failed the film.

Shrinking the residual cannot fix that. The words that did not flip were not
better damped, they were further from a boundary. Only arriving fixes it.

WHY THIS FILE COVERS EVERY COMPONENT AND NOT JUST THE ONE THAT FAILED
---------------------------------------------------------------------
`ComparisonCard` was pinned on 2026-11-15 and the rest were not, which left
the fault latent in every other component that puts type inside a spring:
`TextCard` and `StatCard` are used by every film made so far and held still
only because their words happen to sit further from a rounding boundary than
'casualties' did. The parametrised scan below is the point of the file — a
new component is covered the day it is written, and so is an old one that
gains a line of type.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from lib import verify_type_lock as vtl

COMPOSER = Path(__file__).resolve().parents[2] / "remotion-composer" / "src"
SETTLE = COMPOSER / "design" / "settle.ts"

#: The renderer's frame rate.
FPS = 30


def code(path: Path) -> str:
    """The source with its comments removed.

    Each fix here explains itself in a comment that names the thing it
    replaced. A scan that reads the comments finds `<Noise>` in the paragraph
    saying why `<Noise>` is gone, and passes or fails for the wrong reason.
    """
    source = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
    return re.sub(r"^\s*//.*$", "", source, flags=re.M)


def springy() -> list[Path]:
    """Every component or scene that drives anything with a spring."""
    found = []
    for folder in ("components", "scenes"):
        for path in sorted((COMPOSER / folder).glob("*.tsx")):
            if "spring({" in code(path):
                found.append(path)
    return found


SPRINGY = springy()

#: The ones whose type the type pass draws, so type lock can measure them.
TYPED = [p for p in SPRINGY if "TYPE_CLASS" in code(p)]

#: The ones that drive a spring but draw no marked type. They need no pin —
#: there is nothing for a rounding boundary to flip. Listed rather than
#: skipped silently, because the moment one of them gains a line of type it
#: moves into TYPED and must be pinned, and the test below is what says so.
UNTYPED = [p for p in SPRINGY if p not in TYPED]


def unpinned_springs(path: Path) -> list[int]:
    source = code(path)
    return [m.start() for m in re.finditer(r"= spring\(\{", source)
            if "pinned(frame, " not in source[max(0, m.start() - 24):m.start() + 2]
            and "pinned(\n" not in source[max(0, m.start() - 24):m.start() + 2]]


class TestEveryComponentThatPutsTypeInASpringComesToRest:
    def test_the_scan_found_something_to_scan(self):
        """The guard on the parametrisation. An empty list would make every
        test below pass by having nothing to check — which is how a vacuous
        control looks from the outside."""
        assert len(SPRINGY) >= 10, SPRINGY
        assert len(TYPED) >= 4, [p.name for p in TYPED]

    @pytest.mark.parametrize("path", TYPED, ids=lambda p: p.stem)
    def test_every_spring_is_pinned(self, path):
        loose = unpinned_springs(path)
        assert not loose, (
            f"{len(loose)} spring(s) in {path.name} are not pinned, so it "
            f"never comes to rest and its type can flip a rounding boundary "
            f"on the residual for ever")

    @pytest.mark.parametrize("path", UNTYPED, ids=lambda p: p.stem)
    def test_a_component_with_no_marked_type_has_not_quietly_gained_some(
            self, path):
        """The tripwire that keeps this file honest as the composer grows.

        If this fails, the component now draws type inside a spring and
        belongs in TYPED — pin it, do not widen the exemption.
        """
        assert "TYPE_CLASS" not in code(path), (
            f"{path.name} drives a spring and now marks type, so its type "
            f"can flip a rounding boundary. Pin its springs.")


class TestThePinLandsWhereTheGateCanUseIt:
    def test_the_pin_is_before_type_lock_takes_its_first_sample(self):
        """The invariant that ties the components to the gate.

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
            f"components are pinned at frame {pinned_at} but type lock "
            f"samples frame {first_sample:.0f}")

    @pytest.mark.parametrize("path", TYPED, ids=lambda p: p.stem)
    def test_the_pin_is_late_enough_to_let_the_entrance_play(self, path):
        """A pin before the last phase begins would cut the authored motion
        off rather than finish it."""
        source = code(path)
        starts = [int(m.group(1))
                  for m in re.finditer(r"frame: frame - (\d+)", source)]
        last = max(starts) if starts else 0
        pinned_at = int(re.search(r"ENTRANCE_PINNED_AT = (\d+)",
                                  code(SETTLE)).group(1))
        assert pinned_at > last + 12, (
            f"{path.name}: the pin at frame {pinned_at} lands "
            f"{pinned_at - last} frames after its last phase begins at "
            f"{last}, which is not long enough to be an ending rather than "
            f"an interruption")

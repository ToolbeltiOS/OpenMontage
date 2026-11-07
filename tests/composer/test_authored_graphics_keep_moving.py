"""A card that stops moving when its springs settle is a frozen frame.

WHY THIS TEST EXISTS
--------------------
king-tut, 2026-11-07. The delivery gates reported one freeze — three
identical frames at 473.53s — and that was the visible tip of this:

    plate.mp4, 473.0s to 475.0s   mean frame difference 0.00004 (59/59 pairs
                                  identical: the picture is dead still)
    look.mp4,  same two seconds   mean frame difference 0.0896
    final.mp4, same two seconds   mean frame difference 0.0882

The picture under c066 — a `stat_card` — was byte-identical for 149
consecutive frames, five seconds of a 7.7-second cut. The frame-motion gate
reads the DELIVERED file, and the look pass's grain lifts the difference
above its 0.02 floor almost everywhere, so it saw three frames out of 149.

Surveyed across the whole film, in the plate, the longest run of identical
frames per cut split the film in two with nothing in between:

    text_card    (7 cuts)   26 to 195 frames    0.9s to 6.5s
    stat_card    (7 cuts)   49 to 259 frames    1.6s to 8.6s
    act_title_card (4 cuts) 159 to 191 frames   5.3s to 6.4s
    everything else (86)    0 to 2 frames       under 0.07s

The 86 are the documentary scenes, and they are alive because `SceneShell`
gives every one of them a sustaining move — `sustain` defaults to true, and
its own comment says why: "a flat-background scene has no plate to drift, so
it takes the light sweep on its own: without it the frame would be motionless
the moment its reveals finished, which is the defect the sustaining move
exists to prevent."

The three card types never went through `SceneShell`. `TextCard` and
`StatCard` are stock components with a flat `backgroundColor` and two springs
that settle inside a second. `ActTitleCard` calls `<Plate />` and leaves the
sweep off, and `Plate`'s own docstring already records that its drift alone
measures "about a hundredth of a grey level, under the floor the freeze check
uses" — which is why the sweep was written in the first place.

This is a source test for the same reason `test_authored_camera_is_rendered`
is: the render is hours and the defect is one unpassed prop.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "remotion-composer" / "src"

#: Full-frame authored graphics the documentary composition renders, which do
#: not go through `SceneShell` and so have to carry the sustaining move
#: themselves. Each is a cut type a king-tut cut used.
CARDS = {
    "TextCard.tsx": SRC / "components" / "TextCard.tsx",
    "StatCard.tsx": SRC / "components" / "StatCard.tsx",
    "ActTitleCard.tsx": SRC / "scenes" / "ActTitleCard.tsx",
}

#: What counts as carrying it: the light sweep, by either route.
SWEEP = re.compile(r"<PlateSweep\b|<Plate\s[^>]*\bsweep\b|SceneShell")


@pytest.mark.parametrize("name", sorted(CARDS), ids=sorted(CARDS))
def test_the_card_carries_a_sustaining_move(name):
    source = CARDS[name].read_text()
    assert SWEEP.search(source), (
        f"{name} paints a full frame and nothing in it moves once its "
        f"entrance finishes. In the plate that is a run of byte-identical "
        f"frames seconds long; in the delivered file the look pass's grain "
        f"hides it from the frame-motion gate until it happens not to.")


@pytest.mark.parametrize("name", ["TextCard.tsx", "StatCard.tsx"],
                         ids=["TextCard", "StatCard"])
def test_the_sustaining_move_is_on_unless_a_caller_turns_it_off(name):
    """Default on, as `SceneShell` has it.

    A `sustain` that defaults to false is a prop nobody passes, and the
    component is exactly as frozen as it was with the film none the wiser.
    """
    source = CARDS[name].read_text()
    assert re.search(r"sustain\s*=\s*true", source), (
        f"{name} takes a sustaining move but defaults it off")
    assert "sustain?: boolean" in source


def test_the_shell_every_other_scene_uses_still_defaults_it_on():
    """The reference the cards are being held to.

    If `SceneShell` ever defaults `sustain` off, the 86 cuts measured above
    freeze too and these three tests would be guarding the wrong three files.
    """
    shell = (SRC / "design" / "Scene.tsx").read_text()
    assert re.search(r"sustain\s*=\s*true", shell)


def test_the_flat_background_branch_is_what_the_cards_are_copying():
    """`SceneShell`'s own answer for a scene with no plate to drift."""
    shell = (SRC / "design" / "Scene.tsx").read_text()
    assert re.search(r"background\s*\n?\s*\?\s*\(sustain\s*\?\s*<PlateSweep\s*/>", shell), (
        "SceneShell no longer answers a flat background with the light "
        "sweep, so the cards are copying something that is gone")

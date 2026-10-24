"""The camera the edit stage authored is the camera that renders.

WHY THIS TEST EXISTS
--------------------
The first full render of the Easter Island film delivered 49 sourced stills
— 29% of the cuts, 20% of its running time — with a camera nobody asked for.
The edit stage writes the move twice over, as `camera.move` and as
`parallaxFrom`/`parallaxTo`/`driftFrom`/`driftTo`, and `AnnotatedStill` reads
the numbers. A bare sourced still does not go through `AnnotatedStill`; it
goes through `ImageScene`, which read neither, and fell through to its own
default of `"zoom-in"`.

So every one of those stills got the same 18% push in: sixteen cuts authored
`lock` drifted, and ten authored `pull` ran backwards. Nothing caught it. The
CAMERA INTENT gate passed, because it reads the props — and the props were
right. It was the renderer that never read them.

Measured on the delivered file, c085 — authored `lock`, `parallax: false` —
moved the engraved title of a map 14.1px in one second. After the fix it
moves 0.005px.

This is a source test rather than a render test because the render is two and
a half hours and the defect is one unread prop.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "remotion-composer" / "src"

#: The authored camera, as the edit stage writes it onto a cut.
CAMERA_PROPS = ("parallax", "parallaxFrom", "parallaxTo", "driftFrom", "driftTo")


def explainer() -> str:
    return (SRC / "Explainer.tsx").read_text()


class TestEverySourcedStillGetsTheAuthoredCamera:
    def test_image_scene_accepts_the_authored_camera(self):
        """ImageScene takes the same props AnnotatedStill already reads."""
        body = explainer()
        signature = body[body.index("const ImageScene"):]
        signature = signature[: signature.index("=> {")]
        missing = [p for p in CAMERA_PROPS if p not in signature]
        assert not missing, (
            f"ImageScene does not accept {missing}. A sourced still that "
            f"cannot be told the authored camera will invent one.")

    def test_every_call_site_passes_it(self):
        """Accepting the props is no use if the dispatch drops them."""
        body = explainer()
        calls = re.findall(r"<ImageScene\b.*?/>", body, re.S)
        assert calls, "no ImageScene call sites found — has the dispatch moved?"
        for n, call in enumerate(calls):
            missing = [p for p in CAMERA_PROPS if f"{p}={{cut.{p}}}" not in call]
            assert not missing, (
                f"ImageScene call site {n} does not pass {missing}. This is "
                f"exactly how 49 cuts lost their camera.")

    def test_an_authored_cut_never_falls_through_to_a_preset(self):
        """The `animation` presets must not apply to an authored cut.

        `"zoom-in"` is a reasonable default for a caller that says nothing.
        It is not a reasonable default for a cut that said `lock`.
        """
        body = explainer()
        scene = body[body.index("const ImageScene"):]
        scene = scene[: scene.index("const VideoScene")]
        assert "const authored = parallax !== undefined" in scene, (
            "ImageScene does not distinguish a cut that carries an authored "
            "camera from one that does not.")
        assert re.search(r"authored\s*\n?\s*\?", scene), (
            "ImageScene computes an authored transform but never chooses it "
            "over the preset.")

    def test_the_drift_cover_matches_annotated_still(self):
        """A drift at scale 1 slides the picture's edge into frame.

        Both still paths have to guard it the same way or the same cut is
        framed differently depending on whether it carries annotations.
        """
        cover = "1 + 2 * Math.max(Math.abs(driftFrom), Math.abs(driftTo))"
        assert cover in explainer(), "ImageScene lost the drift cover guard"
        assert cover in (SRC / "components" / "AnnotatedStill.tsx").read_text()


class TestTypeDoesNotRideThePlate:
    """A document's push moves the paper, not the words on it.

    `DocumentReveal` applied `scale(1.0 -> 1.045)` — "a slow push so the plate
    is never a dead hold" — to a single wrapper holding the paper AND the
    type. So the type scaled with it: measured 0.76px to 3.85px of travel a
    second across nine cuts, which is the exact thing `verify_type_lock.py`
    fails a film for. The push is still there; the type now sits outside it.
    """

    def test_the_scaled_layer_closes_before_the_type(self):
        body = (SRC / "components" / "DocumentReveal.tsx").read_text()
        scaled = body.index("transform: `scale(${scale})`")
        type_block = body.index("{headline ?")
        closed = body.index("</AbsoluteFill>", scaled)
        assert closed < type_block, (
            "DocumentReveal still renders its type inside the scaled plate — "
            "the words will ride the push and fail type lock.")

    def test_the_push_itself_survives(self):
        """Locking the type must not flatten the plate into a dead hold."""
        body = (SRC / "components" / "DocumentReveal.tsx").read_text()
        assert "[1.0, 1.045]" in body, (
            "the plate's slow push is gone — that was not the defect")

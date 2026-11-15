"""Where the film look's grain gets its field.

postprocessing's `<Noise>` is `rand(uv * (1.0 + time))`, and `time` is the
EffectMaterial's accumulated delta — advanced by `composer.render(delta)` out
of r3f's `useFrame`, which is WALL-CLOCK. The grain was therefore a function
of how long this machine took to draw the previous frame.

Run #6 shipped two three-frame freezes, at 1071.13s and 1077.10s inside c141,
where the plate holds still and the type holds still and the grain was the
only thing left moving — and on those frames it moved by 0.0008 of a grey
level, under the frame-motion gate's 0.02 threshold. That render carried 74
duplicate pairs film-wide. The run before it passed the identical material
because its frames took a little longer to draw.

Nothing about that is visible in the component's intent, so these assertions
read the mechanism instead.
"""
from __future__ import annotations

import re
from pathlib import Path

COMPOSER = Path(__file__).resolve().parents[2] / "remotion-composer" / "src"


def code(path: Path) -> str:
    """The source with its comments removed.

    Each fix here explains itself in a comment that names the thing it
    replaced. A scan that reads the comments finds `<Noise>` in the paragraph
    saying why `<Noise>` is gone, and passes or fails for the wrong reason.
    """
    source = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
    return re.sub(r"^\s*//.*$", "", source, flags=re.M)
FILM_LOOK = COMPOSER / "FilmLook.tsx"

#: The length of the longest film shipped, in frames.
FILM_FRAMES = 36864


class TestTheGrainIsSeededFromTheFilmAndNotTheClock:
    """`<Noise>`'s field is `rand(uv * (1.0 + time))`.

    `time` is advanced by `composer.render(delta)` out of r3f's `useFrame`,
    which is wall-clock. Two frames drawn in quick succession share a field,
    and where the plate is holding still the picture stops: run #6 shipped
    three-frame freezes at 1071.13s and 1077.10s and 74 duplicate pairs
    film-wide, and the run before it passed the same material only because
    its frames took longer to draw.
    """

    def test_the_wall_clock_noise_effect_is_not_in_the_look_pass(self):
        source = code(FILM_LOOK)
        assert "<Noise" not in source, (
            "the look pass is back on postprocessing's NoiseEffect, whose "
            "grain field is a function of how long the machine took to draw "
            "the previous frame rather than of the frame number")
        imports = re.search(r"import \{([^}]*)\} from \"@react-three/postprocessing\"",
                            source)
        assert imports, "the look pass no longer imports from the composer"
        assert "Noise" not in [n.strip() for n in imports.group(1).split(",")], (
            "NoiseEffect is imported again")

    def test_the_grain_field_is_a_function_of_the_frame_number(self):
        source = code(FILM_LOOK)
        assert "grainJitter" in source and "seedFrom" in source
        # the uniform the shader samples must be fed from the frame, in the
        # component body, not from a clock or a random source
        body = source[source.index("const FrameSeededGrain"):]
        assert "useCurrentFrame()" in body
        assert "effect.seedFrom(frame)" in body
        assert "Math.random" not in source, "a random seed is not reproducible"

    def test_no_two_frames_of_a_film_share_a_grain_field(self):
        """The two constants, read out of the source and run forward.

        A Weyl sequence — the fractional parts of n times an irrational — is
        equidistributed and never repeats, but only if the constants really
        are irrational and are applied in doubles. These are the numbers the
        shipped shader uses, so this is the sequence the film gets.
        """
        source = code(FILM_LOOK)
        a = float(re.search(r"JITTER_A = ([0-9.]+)", source).group(1))
        b = float(re.search(r"JITTER_B = ([0-9.]+)", source).group(1))
        seen, collisions, closest = {}, [], 1.0
        prev = None
        for n in range(FILM_FRAMES):
            j = ((n * a) % 1, (n * b) % 1)
            if j in seen:
                collisions.append((seen[j], n))
            seen[j] = n
            if prev is not None:
                closest = min(closest, max(abs(j[0] - prev[0]), abs(j[1] - prev[1])))
            prev = j
        assert not collisions, f"two frames share a grain field: {collisions[:3]}"
        # consecutive frames must not merely differ, they must differ enough
        # that the field is decorrelated rather than nudged
        assert closest > 0.2, (
            f"the closest consecutive pair of fields is {closest:.4f} apart in "
            "uv; a field that barely moves is a field that barely changes")

"""A layer a sample short must not take the mix down with it.

WHAT HAPPENED
-------------
The sound-design layer is rendered from its own spec against the film's
duration; `n` comes from the voice. After resampling the two can disagree
by a sample — measured on noah at 56,873,599 against 56,873,600.

The code was

    design_ducked = design[:n, None] * duck

and A SLICE CANNOT LENGTHEN AN ARRAY. When the design is the shorter of the
two the slice does nothing, numpy is asked to broadcast 56,873,599 against
56,873,600, and refuses: ValueError with the mix 95% built, at the end of a
stage that has already paid for everything above it.

Every test here is paired with the OLD expression on the same input, so
what is being asserted is the difference between them and not merely that
the new code runs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from mix_audio import fit_to_length  # noqa: E402

#: The real numbers, at the real scale, from noah's mix.
VOICE = 56_873_600
DESIGN_SHORT = 56_873_599


def old_way(design: np.ndarray, duck: np.ndarray) -> np.ndarray:
    """What it did before: a slice, and a broadcast that assumes the slice
    worked."""
    return design[:len(duck), None] * duck


class TestTheLayerThatIsOneSampleShort:
    def test_the_old_expression_raises_on_it(self):
        """The control. Without this, the fix has no defect behind it."""
        design = np.ones(DESIGN_SHORT, dtype=np.float32)
        duck = np.ones((VOICE, 1), dtype=np.float32)
        with pytest.raises(ValueError):
            old_way(design, duck)

    def test_the_fix_returns_exactly_the_voice_length(self):
        design = np.ones(DESIGN_SHORT, dtype=np.float32)
        assert fit_to_length(design, VOICE).shape == (VOICE,)

    def test_what_is_added_is_silence_and_only_at_the_end(self):
        design = np.full(DESIGN_SHORT, 0.5, dtype=np.float32)
        fitted = fit_to_length(design, VOICE)
        assert fitted[-1] == 0.0
        assert np.array_equal(fitted[:DESIGN_SHORT], design), (
            "padding must not disturb a single sample of the real layer")

    def test_it_broadcasts_against_the_duck_afterwards(self):
        """The thing the caller actually does next."""
        design = np.ones(DESIGN_SHORT, dtype=np.float32)
        duck = np.ones((VOICE, 1), dtype=np.float32)
        assert (fit_to_length(design, VOICE)[:, None] * duck).shape == (VOICE, 1)


class TestTheOtherTwoCases:
    def test_a_longer_layer_is_trimmed_as_before(self):
        design = np.arange(VOICE + 5, dtype=np.float32)
        fitted = fit_to_length(design, VOICE)
        assert fitted.shape == (VOICE,)
        assert np.array_equal(fitted, design[:VOICE])

    def test_a_longer_layer_was_never_the_broken_case(self):
        """The old expression handled this one, which is why it survived
        three films."""
        design = np.ones(VOICE + 5, dtype=np.float32)
        duck = np.ones((VOICE, 1), dtype=np.float32)
        assert old_way(design, duck).shape == (VOICE, 1)

    def test_an_exact_match_is_untouched(self):
        design = np.linspace(0, 1, VOICE, dtype=np.float32)
        fitted = fit_to_length(design, VOICE)
        assert fitted is design or np.array_equal(fitted, design)


class TestTheCallerUsesIt:
    def test_the_mix_no_longer_slices_the_design_layer_raw(self):
        # The ASSIGNMENT, not the string: `fit_to_length`'s own docstring
        # quotes the old expression to record what it replaced, and a test
        # that greps for the text alone fails on the explanation.
        source = (ROOT / "lib" / "mix_audio.py").read_text()
        assert "design_ducked = (design[:n, None] * duck)" not in source, (
            "the unguarded slice is back at the call site")
        assert "design_ducked = (fit_to_length(design, n)" in source

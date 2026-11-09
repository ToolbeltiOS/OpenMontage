"""A gate measured against a missing reference must never print PASS.

WHAT HAPPENED
-------------
The loudness check compares the delivered film against the figure the mixer
recorded in `mix_report.json`. When that file was absent the expectation was
None, the comparison was silently skipped, and the gate returned no
problems — so the delivery table printed

    | delivery audio | -16.8 dBFS mean, -14.06 LUFS against the mix's None
    (None dB) | PASS |

for a check that never ran. "Against the mix's None ... PASS" reads as
checked-and-fine and means not-checked, which is the one thing a gate table
must not do.

Now there are three outcomes, not two:

  * a REAL FILM with no mix report      -> FAIL
  * a SLICE, which has none by design   -> SKIPPED, with the reason
  * a film compared and in tolerance    -> PASS
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from verify_delivery_audio import check  # noqa: E402


@pytest.fixture(scope="module")
def delivered() -> str:
    """A file shaped like a delivery: picture and a real audio stream."""
    tmp = tempfile.mkdtemp()
    out = Path(tmp) / "delivered.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "color=c=black:s=320x180:d=3:r=30",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3:sample_rate=48000",
         "-filter:a", "volume=0.25",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(out)], check=True)
    return str(out)


class TestTheControlYouAskedFor:
    """A delivery with the mix report removed must fail delivery audio."""

    def test_a_real_film_with_no_mix_report_fails(self, delivered):
        problems, measured = check(delivered, None, reference_required=True)
        assert problems, "a delivery compared with nothing was allowed to pass"
        assert any("no mix report" in p for p in problems), problems
        assert measured["skipped"] is False

    def test_the_failure_says_what_is_missing_and_why_it_matters(self, delivered):
        problems, _ = check(delivered, None, reference_required=True)
        joined = " ".join(problems)
        assert "mix_report.json" in joined
        assert "compared with nothing" in joined

    def test_the_audio_itself_is_still_measured(self, delivered):
        """The failure is the missing comparison, not a refusal to look."""
        _, measured = check(delivered, None, reference_required=True)
        assert measured["has_audio"] is True
        assert isinstance(measured["integrated_lufs"], float)


class TestASliceSkipsRatherThanPasses:
    def test_it_is_not_a_pass(self, delivered):
        problems, measured = check(delivered, None, reference_required=False)
        assert problems == []
        assert measured["skipped"] is True

    def test_it_says_why(self, delivered):
        _, measured = check(delivered, None, reference_required=False)
        assert "no mix report" in measured["skipped_reason"]

    def test_a_slice_with_a_reference_is_still_compared(self, delivered):
        """Not required is not the same as not done."""
        _, measured = check(delivered, -14.0, reference_required=False)
        assert measured["skipped"] is False
        assert measured["loudness_delta_db"] is not None


class TestTheComparisonItselfStillWorks:
    def test_a_matching_mix_passes(self, delivered):
        _, measured = check(delivered, None, reference_required=False)
        problems, _ = check(delivered, measured["integrated_lufs"])
        assert problems == []

    def test_a_mix_it_does_not_carry_fails(self, delivered):
        _, measured = check(delivered, None, reference_required=False)
        problems, _ = check(delivered, measured["integrated_lufs"] - 6.0)
        assert any("not the mix it claims to carry" in p for p in problems)


class TestTheTableCannotCallASkipAPass:
    """Wiring, read off the source: the behaviour above is only useful if
    the report distinguishes the third state."""

    SOURCE = (ROOT / "lib" / "film_render.py").read_text()
    RENDER = (ROOT / "scripts" / "render_film.py").read_text()

    def test_the_verdict_has_three_outcomes(self):
        assert 'return "SKIPPED"' in self.SOURCE
        assert '.get("skipped")' in self.SOURCE

    def test_the_row_says_it_was_compared_with_nothing(self):
        assert "compared " in self.SOURCE and "with NOTHING" in self.SOURCE

    def test_a_real_film_requires_the_reference(self):
        assert "loudness_reference_required=real_film" in self.RENDER
        assert ('real_film = (project / "artifacts" / "render_props.json")'
                ".exists()" in self.RENDER)

    def test_the_gate_defaults_to_requiring_it(self):
        """A caller that says nothing must get the strict behaviour."""
        assert "reference_required: bool = True" in (
            ROOT / "lib" / "verify_delivery_audio.py").read_text()
        assert "loudness_reference_required: bool = True" in self.SOURCE

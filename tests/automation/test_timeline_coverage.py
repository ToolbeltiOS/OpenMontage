"""Every frame of the film belongs to exactly one cut.

WHAT HAPPENED
-------------
`Explainer` laid every cut out as

    from     = Math.round(cut.in_seconds * fps)
    duration = Math.round((cut.out_seconds - cut.in_seconds) * fps)

which rounds two different quantities independently. When they disagree the
cut ends one frame before the next begins and NOTHING covers that frame, so
the composition paints its bare background there — no scene, no chrome —
while the type pass goes on laying captions over it. On a dark shot it reads
as a white flash.

Counted from the props of the four films made so far:

    they-said-it-couldnt-be-built   27 uncovered frames
    king-tut                        13
    easter-island                    0
    noah                             0

COUNTED THE WAY THE COMPOSITION COUNTS. The first pass at this test used
Python's `round`, which rounds a half to EVEN where JavaScript rounds it UP,
and reported 21 instead of 27 — it disagreed with the composition about six
cut boundaries that land exactly on a half frame. `buildability.js_round` is
the composition's rounding; nothing here may use the builtin.

they-said-it is published (CDpzQKwTBsI) and a scan of its delivered file
found eight single-frame flashes — luma 32 against neighbours at 15 — five
of which are in one of those gaps. The two films with no gaps have no
flashes. Nothing in the delivery gates can see this: the frame is present so
frame count passes, one frame is not a freeze so frame motion passes, and
frame order compares the delivered film against the PLATE, where the gap
also is.

The fix is to round BOTH EDGES from the timeline and take the duration as
their difference, so `to` of one cut is `from` of the next by construction.
This test holds the two arithmetics side by side against the real props,
because a fix with no failing measurement behind it is a guess.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from buildability import check_timeline_coverage, frame_span, js_round  # noqa: E402

FPS = 30

#: The props each film was actually rendered from. `edit_decisions.json`
#: cannot answer this for three of the four — its `in_seconds` is relative
#: to the source clip, and only king-tut carries `timeline_start_seconds` —
#: so the authoritative timeline is the props the composition is handed.
FILMS = {
    "they-said-it-couldnt-be-built": 27,
    "easter-island": 0,
    "noah": 0,
    "king-tut": 13,
}


def props_for(film: str):
    for root in ("OpenMontage", "runner", "fix-render-finalise", "asset-library"):
        path = (ROOT.parent / root / "projects" / film / "artifacts"
                / "render_props.json")
        if path.exists():
            return json.loads(path.read_text())["cuts"]
    return None


def legacy_span(cut, fps=FPS):
    """The arithmetic as it shipped: start from the timeline, duration from
    the difference. `js_round` because the shipped arithmetic was
    JavaScript's."""
    first = js_round(float(cut["in_seconds"]) * fps)
    last = first + js_round((float(cut["out_seconds"])
                             - float(cut["in_seconds"])) * fps) - 1
    return first, max(first, last)


class TestTheCheckRoundsTheWayTheCompositionRounds:
    """A half frame is where the two languages part company, and a half
    frame is exactly what a cut boundary lands on when a duration ends in
    .05 of a second. Measured on the real props: Python's rounding finds 21
    of they-said-it's 27 holes."""

    @pytest.mark.parametrize("value,expected", [
        (24220.5, 24221), (0.5, 1), (1.5, 2), (2.5, 3), (-0.5, 0),
        (24220.4, 24220), (24220.6, 24221),
    ])
    def test_a_half_rounds_up_like_math_round(self, value, expected):
        assert js_round(value) == expected

    def test_the_builtin_would_have_disagreed(self):
        """The control: if these ever agree, this test is measuring nothing."""
        assert round(24220.5) == 24220 and js_round(24220.5) == 24221

    def test_the_builtin_undercounts_the_published_film(self):
        cuts = props_for("they-said-it-couldnt-be-built")
        if cuts is None:
            pytest.skip("they-said-it has no render_props.json in any worktree")

        def python_span(cut, fps=FPS):
            first = round(float(cut["in_seconds"]) * fps)
            last = first + round((float(cut["out_seconds"])
                                  - float(cut["in_seconds"])) * fps) - 1
            return first, max(first, last)

        assert uncovered(cuts, python_span) == 21
        assert uncovered(cuts, legacy_span) == 27

    def test_no_source_file_turns_seconds_into_frames_with_the_builtin(self):
        """A SECONDS-TO-FRAMES conversion anywhere in lib/ is this bug again.

        Narrowly: `round(<seconds> * fps)` with no second argument. A
        `round(frames / fps, 2)` is a number for a human to read and is not
        this; it is the conversions the composition also makes that have to
        agree with it frame for frame.
        """
        import re
        pattern = re.compile(r"(?<![\w.])round\s*\([^,()]*\*\s*(?:fps|FPS|30)\s*\)")
        offenders = []
        for path in sorted((ROOT / "lib").glob("*.py")):
            for n, line in enumerate(path.read_text().splitlines(), 1):
                if pattern.search(line):
                    offenders.append(f"{path.name}:{n}: {line.strip()}")
        assert offenders == [], (
            "use buildability.js_round for anything the composition also "
            "rounds:\n" + "\n".join(offenders))


def uncovered(cuts, span) -> int:
    spans = sorted(span(c) for c in cuts)
    holes = 0
    for (a1, b1), (a2, b2) in zip(spans, spans[1:]):
        if a2 > b1 + 1:
            holes += a2 - b1 - 1
    return holes


@pytest.mark.parametrize("film,expected", sorted(FILMS.items()))
def test_the_old_arithmetic_leaves_the_measured_holes(film, expected):
    """The control. Without this the fix is a change with no defect behind it."""
    cuts = props_for(film)
    if cuts is None:
        pytest.skip(f"{film} has no render_props.json in any worktree")
    assert uncovered(cuts, legacy_span) == expected, (
        f"{film} was measured at {expected} uncovered frames under the "
        f"arithmetic that shipped")


@pytest.mark.parametrize("film", sorted(FILMS))
def test_rounding_both_edges_covers_every_frame(film):
    cuts = props_for(film)
    if cuts is None:
        pytest.skip(f"{film} has no render_props.json in any worktree")
    assert uncovered(cuts, frame_span) == 0


@pytest.mark.parametrize("film", sorted(FILMS))
def test_the_check_passes_every_film_under_the_new_arithmetic(film):
    cuts = props_for(film)
    if cuts is None:
        pytest.skip(f"{film} has no render_props.json in any worktree")
    problems, measured = check_timeline_coverage(cuts, FPS)
    assert problems == [], problems[:5]
    assert measured["gap_frames"] == 0 and measured["overlap_frames"] == 0


class TestTheCheckNamesWhatItFound:
    BASE = [{"id": "c001", "in_seconds": 0.0, "out_seconds": 1.0},
            {"id": "c002", "in_seconds": 1.0, "out_seconds": 2.0}]

    def test_a_contiguous_timeline_passes(self):
        problems, measured = check_timeline_coverage(self.BASE, FPS)
        assert problems == []
        assert measured["frames"] == 60

    def test_a_gap_fails_and_names_the_frame_and_both_cuts(self):
        cuts = [dict(self.BASE[0]), dict(self.BASE[1])]
        cuts[1]["in_seconds"] = 1.0334          # one frame later
        problems, measured = check_timeline_coverage(cuts, FPS)
        assert problems and "frame 30" in problems[0]
        assert "c001" in problems[0] and "c002" in problems[0]
        assert measured["gap_frames"] == 1

    def test_an_overlap_fails_too(self):
        cuts = [dict(self.BASE[0]), dict(self.BASE[1])]
        cuts[1]["in_seconds"] = 0.9             # a frame early
        problems, measured = check_timeline_coverage(cuts, FPS)
        assert problems and "at once" in problems[0]
        assert measured["overlap_frames"] >= 1

    def test_a_film_that_does_not_start_at_zero_fails(self):
        cuts = [dict(c) for c in self.BASE]
        cuts[0]["in_seconds"] = 0.2
        problems, _ = check_timeline_coverage(cuts, FPS)
        assert any("not 0" in p for p in problems)

    def test_no_cuts_at_all_is_a_problem_not_a_pass(self):
        problems, _ = check_timeline_coverage([], FPS)
        assert problems

    def test_the_span_matches_the_compositions_own_helper(self):
        """If `frameSpan` in Explainer.tsx stops agreeing with this, the
        check is reading a timeline the renderer will not lay out."""
        source = (ROOT / "remotion-composer" / "src" / "Explainer.tsx").read_text()
        assert "const to = Math.round(element.out_seconds * fps);" in source
        assert "duration: Math.max(1, to - from)" in source
        assert "Math.round((cut.out_seconds - cut.in_seconds) * fps)" not in source


class TestTheRenderRefusesAnUncoveredTimeline:
    """Blocking, and blocking BEFORE the first pass.

    Checking this at delivery would mean finding it after the plate, the
    frames, the look pass and the type pass — about four hours on this film
    — and the delivery gates cannot see it anyway.
    """

    def source(self) -> str:
        return (ROOT / "scripts" / "render_film.py").read_text()

    def test_the_check_runs_in_render_film(self):
        assert "check_timeline_coverage" in self.source()

    def test_it_runs_before_any_pass(self):
        body = self.source()
        checked = body.index("check_timeline_coverage(cuts")
        for marker in ('print("1. plate")', 'render_plate(', 'render_look(',
                       'render_type(', 'extract_frames('):
            assert checked < body.index(marker), (
                f"the timeline is checked after {marker}, which is hours too "
                f"late and several passes too expensive")

    def test_it_raises_rather_than_warning(self):
        body = self.source()
        after = body[body.index("check_timeline_coverage(cuts"):]
        assert "raise SystemExit" in after[:900], (
            "a timeline check that prints and carries on is not a gate")

    def test_the_message_counts_both_kinds(self):
        body = self.source()
        after = body[body.index("check_timeline_coverage(cuts"):][:900]
        assert "gap_frames" in after and "overlap_frames" in after

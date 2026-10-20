"""Camera intent and J/L cuts: the two things run #1 did the same way 182 times.

Every still got the same push, and every boundary cut picture and sound at the
same instant. These pin the rules that replace both, and in particular the two
that are easy to get wrong: a lead must not change the film's length, and a
landing's boundary must not move at all.
"""
from __future__ import annotations

import pytest

from lib import camera_intent, edit_leads


def cut(i, length=6.0, **kw):
    return {"id": f"c{i:03d}", "in_seconds": 0.0, "out_seconds": length, **kw}


def laid_out(cuts):
    """Back-to-back absolute positions, the way build_render_props lays them."""
    t = 0.0
    for c in cuts:
        length = c["out_seconds"] - c["in_seconds"]
        c["in_seconds"] = round(t, 3)
        c["out_seconds"] = round(t + length, 3)
        t += length
    return cuts


class TestCameraIntent:
    def test_the_move_comes_from_the_beat(self):
        cuts = camera_intent.assign([
            cut(0, beat="reveal"), cut(1, beat="exposition"),
            cut(2, beat="landing"), cut(3, beat="transition")])
        assert [c["camera"]["move"] for c in cuts] == ["push", "pull", "lock", "drift"]
        assert all(c["camera"]["reason"] for c in cuts)

    def test_a_run_of_drifts_keeps_one_direction(self):
        cuts = camera_intent.assign([cut(i, beat="transition") for i in range(4)])
        dirs = {c["camera"]["direction"] for c in cuts}
        assert len(dirs) == 1, f"the eye is thrown back: {dirs}"
        assert camera_intent.check(cuts) == []

    def test_opposite_drifts_in_a_run_are_rejected(self):
        cuts = [cut(0, beat="transition"), cut(1, beat="transition")]
        cuts[0]["camera"] = {"move": "drift", "direction": "left", "reason": "x",
                             "speed_pct_per_second": 1.2}
        cuts[1]["camera"] = {"move": "drift", "direction": "right", "reason": "x",
                             "speed_pct_per_second": 1.2}
        assert any("thrown back" in p for p in camera_intent.check(cuts))

    def test_one_ramp_per_act(self):
        cuts = camera_intent.assign(
            [cut(i, beat="reveal", act=1) for i in range(3)])
        assert sum(1 for c in cuts if c["camera"].get("ramp")) == 1
        assert camera_intent.check(cuts) == []

    def test_two_ramps_in_one_act_are_rejected(self):
        cuts = [cut(i, beat="reveal", act=2) for i in range(2)]
        for c in cuts:
            c["camera"] = {"move": "push", "reason": "x", "ramp": True,
                           "speed_pct_per_second": 2.4, "direction": "none"}
        assert any("one per act" in p for p in camera_intent.check(cuts))

    def test_a_cut_with_no_camera_is_rejected(self):
        assert any("no camera intent" in p for p in camera_intent.check([cut(0)]))

    def test_a_speed_over_the_playbook_ceiling_is_rejected(self):
        c = cut(0, beat="reveal")
        c["camera"] = {"move": "push", "reason": "x", "direction": "none",
                       "speed_pct_per_second": 9.0}
        assert any("ceiling" in p for p in camera_intent.check([c]))

    def test_props_push_and_pull_are_the_same_travel_reversed(self):
        push = camera_intent.to_props(
            {"in_seconds": 0, "out_seconds": 10,
             "camera": {"move": "push", "speed_pct_per_second": 2.0}})
        pull = camera_intent.to_props(
            {"in_seconds": 0, "out_seconds": 10,
             "camera": {"move": "pull", "speed_pct_per_second": 2.0}})
        assert push["parallaxFrom"] == pytest.approx(pull["parallaxTo"])
        assert push["parallaxTo"] == pytest.approx(pull["parallaxFrom"])
        assert push["parallaxTo"] == pytest.approx(1.2, abs=1e-6)

    def test_a_lock_renders_no_parallax_at_all(self):
        props = camera_intent.to_props(
            {"in_seconds": 0, "out_seconds": 6,
             "camera": {"move": "lock", "speed_pct_per_second": 0}})
        assert props == {"parallax": False}

    def test_drift_travels_both_ways_from_centre(self):
        props = camera_intent.to_props(
            {"in_seconds": 0, "out_seconds": 10,
             "camera": {"move": "drift", "speed_pct_per_second": 1.2,
                        "direction": "right"}})
        assert props["driftFrom"] == pytest.approx(-props["driftTo"])
        assert props["driftTo"] > 0


class TestLeads:
    def test_act_boundaries_and_reveals_get_a_j_cut(self):
        cuts = edit_leads.assign([
            cut(0, beat="exposition", act=1),
            cut(1, beat="exposition", act=2),      # act boundary
            cut(2, beat="reveal", act=2),
        ])
        assert cuts[1]["audio_lead_frames"] == 18
        assert cuts[2]["audio_lead_frames"] == 15
        assert all(c.get("lead_reason") for c in cuts[1:])

    def test_a_landing_boundary_never_moves(self):
        cuts = edit_leads.assign([cut(0, beat="reveal", act=1),
                                  cut(1, beat="landing", act=1)])
        assert cuts[1]["audio_lead_frames"] == 0
        assert edit_leads.check(cuts) == []

    def test_a_lead_on_a_landing_is_rejected(self):
        c = cut(1, beat="landing", audio_lead_frames=14, lead_reason="x")
        assert any("holds through its air" in p for p in edit_leads.check([cut(0), c]))

    def test_applying_leads_does_not_change_the_films_length(self):
        cuts = laid_out([cut(i, 6.0, beat="exposition", act=1 + i // 4)
                         for i in range(12)])
        edit_leads.assign(cuts)
        before = cuts[-1]["out_seconds"]
        report = edit_leads.apply_leads(cuts, fps=30)
        assert cuts[-1]["out_seconds"] == pytest.approx(before)
        assert report["applied"] > 0
        # and the timeline stays contiguous
        for a, b in zip(cuts, cuts[1:]):
            assert a["out_seconds"] == pytest.approx(b["in_seconds"])

    def test_a_lead_never_eats_a_shot(self):
        cuts = laid_out([cut(0, 1.2), cut(1, 1.2)])
        cuts[1]["audio_lead_frames"] = 18
        cuts[1]["lead_reason"] = "x"
        report = edit_leads.apply_leads(cuts, fps=30)
        assert report["skipped"] == 1
        assert "under 1s" in cuts[1]["lead_skipped"]

    def test_leads_outside_the_budget_are_rejected(self):
        over = cut(1, audio_lead_frames=24, lead_reason="x")
        under = cut(2, audio_lead_frames=-20, lead_reason="x")
        problems = edit_leads.check([cut(0), over, under])
        assert any("outside the 12-18 budget" in p for p in problems)
        assert any("over the 10-frame ceiling" in p for p in problems)

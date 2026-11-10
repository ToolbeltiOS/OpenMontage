"""How many one-shots, and where each one belongs.

WHY THESE CAPS EXIST NOW AND NOT BEFORE
---------------------------------------
Three events that cannot be heard cost nothing. Until 2026-11-09 the
one-shots sat under the continuous floor — ambience at -10 against a riser at
-14 — so the table was a budget for something inaudible and a cap on it would
have been ceremony. With the floor at -18 and the events up at the ceiling the
owner's rule allows, they are audible, and how many there are is a decision.

EACH CAP IS COUNTED ON THE FIELD THE SPEC ALREADY USES to say where the event
belongs: a riser's `act`, a sting's `boundary`, an impact's `act` and `cut`.
No times, no tolerance, no act-span derivation. That is deliberate — an
earlier attempt derived boundary TIMES from the ambience spans and got the
last one wrong by ten seconds, because the outro carries no ambience of its
own and merged into act 4. See TestTheOutroIsABoundary below, which is the
invariant that mistake asked for.

THE RISER IS NOT A BOUNDARY ELEMENT. It ends ON the first word of the landing
line, and a landing line is mid-act; the playbook has said so from the start.
An act has one landing to lead into, so the cap is one per act rather than one
per boundary.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import sound_design as SD        # noqa: E402

KING_TUT = Path("/Users/mac/Developer/wak3up-docs/runner/projects/king-tut")


def playbook() -> dict:
    with open(ROOT / "styles" / "wak3up-documentary.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def prov(**extra) -> dict:
    """The provenance every entry needs, so a cap test fails on the cap."""
    return {"path": "x.mp3", "provider": "p", "url": "u", "licence": "l",
            "title": "t", "attribution": "a", "why": "w", **extra}


def spec(**groups) -> dict:
    base = {
        "version": "1.0",
        "room_tone": prov(),
        "ambience": [
            prov(act="act1", palette="stone", start_seconds=0.0,
                 end_seconds=10.0),
            prov(act="act2", palette="stone", start_seconds=10.0,
                 end_seconds=20.0),
        ],
        "risers": [], "impacts": [], "stings": [],
    }
    base.update(groups)
    return base


def problems(**groups) -> list[str]:
    return SD.check_spec(spec(**groups), playbook())


class TestOneRiserPerAct:
    def test_one_is_fine(self):
        found = problems(risers=[prov(at_seconds=5.0, seconds=2.0, act="act1",
                                      into="c001")])
        assert not [p for p in found if "riser" in p], found

    def test_two_in_one_act_is_refused(self):
        found = problems(risers=[
            prov(at_seconds=5.0, seconds=2.0, act="act1", into="c001"),
            prov(at_seconds=8.0, seconds=2.0, act="act1", into="c002")])
        assert any("2 risers" in p for p in found), found

    def test_one_in_each_of_two_acts_is_fine(self):
        found = problems(risers=[
            prov(at_seconds=5.0, seconds=2.0, act="act1", into="c001"),
            prov(at_seconds=15.0, seconds=2.0, act="act2", into="c002")])
        assert not [p for p in found if "riser" in p], found

    def test_a_riser_must_name_its_landing(self):
        """`into` is how the spec says WHICH line it ends on."""
        found = problems(risers=[prov(at_seconds=5.0, seconds=2.0,
                                      act="act1")])
        assert any("names no landing" in p for p in found), found


class TestOneStingPerBoundary:
    def test_one_per_boundary_is_fine(self):
        found = problems(stings=[
            prov(at_seconds=10.0, boundary="act1->act2"),
            prov(at_seconds=20.0, boundary="act2->act3")])
        assert not [p for p in found if "sting" in p], found

    def test_two_on_one_boundary_is_refused(self):
        found = problems(stings=[
            prov(at_seconds=10.0, boundary="act1->act2"),
            prov(at_seconds=10.5, boundary="act1->act2")])
        assert any("2 stings" in p for p in found), found

    def test_a_sting_must_name_its_boundary(self):
        found = problems(stings=[prov(at_seconds=10.0)])
        assert any("names no boundary" in p for p in found), found


class TestImpactsAtRevealBeats:
    def test_two_per_act_is_fine(self):
        found = problems(impacts=[
            prov(at_seconds=3.0, act="act1", cut="c010"),
            prov(at_seconds=6.0, act="act1", cut="c020")])
        assert not [p for p in found if "impact" in p], found

    def test_three_in_one_act_is_a_trailer(self):
        found = problems(impacts=[
            prov(at_seconds=3.0, act="act1", cut="c010"),
            prov(at_seconds=6.0, act="act1", cut="c020"),
            prov(at_seconds=9.0, act="act1", cut="c030")])
        assert any("3 impacts" in p for p in found), found

    def test_an_impact_must_name_its_reveal_cut(self):
        found = problems(impacts=[prov(at_seconds=3.0, act="act1")])
        assert any("names no cut" in p for p in found), found


class TestTheCapsAreDeclaredInOnePlace:
    """Read from the playbook, not written twice.

    The repo's own rule: `slot_required` is driven by the contract "so the
    rule is declared in one place rather than hard-coded here and documented
    there". These caps follow it, and a number changed in the playbook has to
    change the behaviour.
    """

    def test_the_playbook_carries_all_three(self):
        sd = playbook()["audio"]["sound_design"]
        assert sd["riser"]["max_per_act"] == 1
        assert sd["impact"]["max_per_act"] == 2
        assert sd["sting"]["max_per_boundary"] == 1

    def test_raising_the_riser_cap_in_the_playbook_allows_two(self):
        book = copy.deepcopy(playbook())
        book["audio"]["sound_design"]["riser"]["max_per_act"] = 2
        found = SD.check_spec(spec(risers=[
            prov(at_seconds=5.0, seconds=2.0, act="act1", into="c001"),
            prov(at_seconds=8.0, seconds=2.0, act="act1", into="c002")]), book)
        assert not [p for p in found if "risers" in p], found

    def test_lowering_the_sting_cap_refuses_what_passed(self):
        book = copy.deepcopy(playbook())
        book["audio"]["sound_design"]["sting"]["max_per_boundary"] = 0
        found = SD.check_spec(spec(stings=[
            prov(at_seconds=10.0, boundary="act1->act2")]), book)
        assert any("stings" in p for p in found), found


class TestThePlaybookHasNoBooleanKeys:
    """`on:` in YAML 1.1 is the boolean True, not the string "on".

    `impact` and `sting` both had `on: hard_cut_at_reveal` and
    `on: act_boundary`, so both arrived in Python under the key `True` and
    could not be read by the name written in the file. Nothing read them,
    which is the only reason it never broke — a declared field nobody can
    address is the same defect as one nobody consumes.

    The whole sound-design block is checked, not just those two, because the
    trap catches `on`, `off`, `yes`, `no`, `y`, `n`, `true` and `false`
    equally and the next one will be written by someone who does not know
    that.
    """

    def test_every_key_in_the_sound_design_block_is_a_string(self):
        def walk(node, where="audio.sound_design"):
            bad = []
            if isinstance(node, dict):
                for key, value in node.items():
                    if not isinstance(key, str):
                        bad.append(f"{where}: key {key!r} is "
                                   f"{type(key).__name__}, not a string")
                    bad += walk(value, f"{where}.{key}")
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    bad += walk(value, f"{where}[{i}]")
            return bad

        found = walk(playbook()["audio"]["sound_design"])
        assert not found, "\n".join(found)

    def test_the_two_that_were_wrong_read_by_name(self):
        sd = playbook()["audio"]["sound_design"]
        assert sd["impact"]["on"] == "hard_cut_at_reveal"
        assert sd["sting"]["on"] == "act_boundary"


class TestTheOutroIsABoundary:
    """A film's last boundary is the outro START, not its final frame.

    This is the invariant the mistake asked for. Deriving boundary times from
    the ambience spans put king-tut's last edge at 1226.26s — the end of the
    film — because the outro carries no ambience of its own and merged into
    act 4. The act4->outro sting at 1215.52s then looked like it was 10.7s
    adrift of a boundary when it is 1.2s before one.

    The act spans come from the EDL, where the outro is a section like any
    other.
    """

    @pytest.fixture(scope="class")
    def spans(self):
        props = KING_TUT / "artifacts" / "render_props.json"
        if not props.exists():
            pytest.skip("king-tut's render props are not on this machine")
        from film_render import act_spans
        return act_spans(json.loads(props.read_text())["cuts"])

    def test_the_outro_is_its_own_span(self, spans):
        assert spans[-1]["act"] == "outro", [s["act"] for s in spans]

    def test_the_last_boundary_is_the_outro_start_not_the_final_frame(self, spans):
        outro = spans[-1]
        last_boundary = outro["from_seconds"]
        final_frame = outro["to_seconds"]
        assert last_boundary < final_frame, (outro,)
        assert final_frame - last_boundary > 1.0, (
            "the outro is under a second long, so it is not a section and "
            "this invariant is measuring nothing")

    def test_the_act4_to_outro_sting_sits_on_that_boundary(self, spans):
        """The sting that looked adrift, measured against the right edge."""
        sd_path = KING_TUT / "artifacts" / "sound_design.json"
        if not sd_path.exists():
            pytest.skip("king-tut's sound design is not on this machine")
        stings = json.loads(sd_path.read_text())["stings"]
        last = [s for s in stings if s.get("boundary") == "act4->outro"]
        assert len(last) == 1, stings
        boundary = spans[-1]["from_seconds"]
        off_by = abs(float(last[0]["at_seconds"]) - boundary)
        assert off_by < 2.5, (
            f"the act4->outro sting is {off_by:.2f}s from the outro start at "
            f"{boundary:.2f}s")


class TestTheRealSpecPasses:
    def test_king_tut_satisfies_every_cap(self):
        """Nothing is grandfathered, because nothing needed to be."""
        sd_path = KING_TUT / "artifacts" / "sound_design.json"
        if not sd_path.exists():
            pytest.skip("king-tut's sound design is not on this machine")
        found = SD.check_spec(json.loads(sd_path.read_text()), playbook())
        assert not found, found


class TestARiserIsNotTheSilenceAfterIt:
    """Every riser in every film was silent, and nothing could see it.

    `build` keeps "the top of the riser, not its start" by taking the last
    `max_seconds` of the asset. That is right for a file ending on its peak
    and wrong for one that does not. king-tut's riser.mp3 is 10.03s with its
    swell in the first five — loudest sample at 3.98s — and silence to the
    end, so the slice took 8.0-10.0s at -105 dBFS. `_to_level` then hit its
    own `cur < -110` guard and returned the array UNSCALED, so the level
    table never applied to a riser at all.

    IT HID FOR FOUR FILMS because nothing could see it. The SFX gate measured
    the summed design layer, where the ambience the riser was buried under
    answered for it; no gate asks whether a placed element can be heard; and
    the one number that would have shown it — the riser's own level — read
    the ambience instead. It surfaced only when the gate was changed to
    measure each event's own stem and both tables of an A/B came back at
    -70.0 LUFS, the gate's floor.
    """

    @staticmethod
    def riser_shaped_like_the_real_one(seconds=10.0, swell_until=5.0):
        """A swell in the first half, silence to the end. The real shape."""
        import numpy as np
        sr = SD.SR
        n, upto = int(seconds * sr), int(swell_until * sr)
        a = np.zeros(n, dtype=np.float32)
        body = np.linspace(0.0, 1.0, upto, dtype=np.float32)
        rng = np.random.default_rng(3)
        a[:upto] = body * rng.standard_normal(upto).astype(np.float32) * 0.5
        return a

    def test_the_trim_finds_where_the_sound_stops(self):
        a = self.riser_shaped_like_the_real_one()
        trimmed = SD._trim_trailing_silence(a)
        assert 4.5 * SD.SR < len(trimmed) < 5.5 * SD.SR, len(trimmed) / SD.SR
        assert len(trimmed) < len(a)

    def test_the_last_two_seconds_are_audible_after_trimming(self):
        import numpy as np
        a = self.riser_shaped_like_the_real_one()
        cap = int(2.0 * SD.SR)
        before = a[-cap:]
        after = SD._trim_trailing_silence(a)[-cap:]
        assert SD._loudness(before, True) < -100, (
            "this fixture no longer reproduces the fault: the untrimmed tail "
            "is audible, so there is nothing for the trim to fix")
        assert SD._loudness(after, True) > SD._loudness(before, True) + 60

    def test_a_file_that_ends_on_its_peak_is_untouched(self):
        """The control. Trimming must not shorten a well-formed riser."""
        import numpy as np
        sr = SD.SR
        a = (np.linspace(0.0, 1.0, int(2.0 * sr), dtype=np.float32)
             * np.random.default_rng(4).standard_normal(int(2.0 * sr)
                                                        ).astype(np.float32))
        assert len(SD._trim_trailing_silence(a)) == len(a)

    def test_a_decaying_tail_is_kept(self):
        """A reverb tail is the sound, not silence.

        The threshold is 60 dB under the element's own peak for this reason:
        the job is finding where a file STOPS, not gating a level.
        """
        import numpy as np
        sr = SD.SR
        decay = np.concatenate([
            np.ones(int(0.2 * sr), dtype=np.float32),
            np.geomspace(1.0, 10 ** (-40 / 20), int(1.8 * sr)).astype(np.float32),
        ]) * np.random.default_rng(5).standard_normal(int(2.0 * sr)
                                                      ).astype(np.float32)
        kept = SD._trim_trailing_silence(decay)
        assert len(kept) > 0.9 * len(decay), len(kept) / len(decay)

    def test_the_real_asset_now_carries_sound(self):
        asset = (KING_TUT / "assets" / "audio" / "sound_design" / "riser.mp3")
        if not asset.exists():
            pytest.skip("king-tut's riser asset is not on this machine")
        a = SD._read(str(asset))
        cap = int(2.0 * SD.SR)
        assert SD._loudness(a[-cap:], True) < -100, (
            "riser.mp3 no longer ends in silence, so this regression test is "
            "measuring nothing — check whether the asset was replaced")
        taken = SD._trim_trailing_silence(a)[-cap:]
        assert SD._loudness(taken, True) > -30, SD._loudness(taken, True)

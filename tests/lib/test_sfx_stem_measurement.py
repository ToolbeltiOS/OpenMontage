"""The SFX gate has to measure the event, not the room it plays in.

WHY THIS EXISTS
---------------
`verify_sfx_level.check` took the loudest 400 ms of the SUMMED design layer
inside an event's window and reported it as the event's level. The layer is a
sum of the event and whatever continuous floor runs under it, and the floor
used to be louder: ambience at -10 against a riser at -14.

Measured 2026-11-09 on two full mixes of king-tut differing ONLY in
`riser_peak`, -12 against -14 — every riser row came back

    design_lufs -45.2, excess_db -6.6

identical to the decimal in both, while `sound_design`'s own placement report
showed the riser moving -52.0 -> -54.0 dB. `argmax` was finding the ambience.

THE CONTROL IS THE POINT: a 2 dB change to a one-shot must move the reading
for that one-shot by at least 1.5 dB. A gate whose number does not move when
the thing it names moves is the same defect as a gate with no consumer, and
harder to see, because it prints a plausible figure.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import sound_design as SD        # noqa: E402
import verify_sfx_level as V     # noqa: E402

SR = 48000
TOTAL = 20.0
AT = 10.0                        # where the riser lands


def playbook(riser: int = -6, ambience: int = -18) -> dict:
    """THE REAL PLAYBOOK with the levels overridden, not a hand-built one.

    `build` reads more of this file than the levels — the riser's ceiling,
    the ambience palettes, the impact cap — and a stub that happens to carry
    the keys today drifts from the file that matters. One load, two numbers
    changed.
    """
    import copy

    import yaml
    book = copy.deepcopy(_REAL_PLAYBOOK)
    off = book["audio"]["sound_design"]["levels_relative_to_music_bed_db"]
    off["riser_peak"] = riser
    off["ambience"] = ambience
    return book


def _load_real_playbook() -> dict:
    import yaml
    with open(ROOT / "styles" / "wak3up-documentary.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


_REAL_PLAYBOOK = _load_real_playbook()


@pytest.fixture
def world(tmp_path):
    """A riser over a loud continuous ambience, which is the trap.

    The ambience is deliberately louder than the riser in the old table, so a
    gate that measures the summed layer reports the ambience and a gate that
    measures the stem reports the riser.
    """
    import soundfile as sf

    assets = tmp_path / "sd"
    assets.mkdir()
    rng = np.random.default_rng(7)

    riser = rng.standard_normal(int(2.0 * SR)).astype(np.float32) * 0.2
    sf.write(assets / "riser.wav", riser, SR)
    amb = rng.standard_normal(int(TOTAL * SR)).astype(np.float32) * 0.2
    sf.write(assets / "amb.wav", amb, SR)

    spec = {
        "version": "1.0",
        "ambience": [{"path": "amb.wav", "act": "act1", "palette": "stone",
                      "start_seconds": 0.0, "end_seconds": TOTAL,
                      "provider": "t", "url": "u", "licence": "l",
                      "title": "t", "attribution": "a", "why": "w"}],
        "risers": [{"path": "riser.wav", "at_seconds": AT, "seconds": 2.0,
                    "act": "act1", "into": "c001", "provider": "t", "url": "u",
                    "licence": "l", "title": "t", "attribution": "a",
                    "why": "w"}],
    }
    bed = (rng.standard_normal((int(TOTAL * SR), 1)).astype(np.float32) * 0.1)
    times, st = V.short_term(bed, SR)
    live = st[st > -70.0]
    bed_db = float(np.median(live))
    return spec, str(assets), bed, (times, st), bed_db


def measure(spec, assets, bed, curve, bed_db, riser_db, use_stems=True):
    stems: list = []
    design, _ = SD.build(spec, TOTAL, bed_db, playbook(riser_db), assets,
                         bed_curve=curve, stems_out=stems)
    n = min(len(design), len(bed))
    d = design[:n]
    if d.ndim == 1:
        d = d[:, None]
    problems, report = V.check(d, bed[:n], SR, spec,
                               stems=stems if use_stems else None)
    rows = [r for r in report["events"] if r["kind"] == "riser"]
    assert len(rows) == 1, rows
    return problems, rows[0]


class TestTheControl:
    def test_a_2db_riser_change_moves_the_reading(self, world):
        """The requirement, as stated: at least 1.5 dB of the 2."""
        _, loud = measure(*world, riser_db=-6)
        _, quiet = measure(*world, riser_db=-8)
        moved = loud["design_lufs"] - quiet["design_lufs"]
        assert moved >= 1.5, (
            f"a 2 dB riser change moved the reading {moved:.2f} dB — the gate "
            f"is not measuring the riser (loud {loud}, quiet {quiet})")

    def test_the_reading_comes_from_the_stem(self, world):
        _, row = measure(*world, riser_db=-6)
        assert row["measured_from"] == "stem"

    def test_the_excess_equals_the_playbook_offset(self, world):
        """Placement and the gate now read the same reference.

        An event placed at `bed_reference + off` must measure `off`. That is
        the whole point of (c): before it, placement used the bed's quietest
        window and the gate its loudest, so an offset was not a statement
        about anything.
        """
        for asked in (-6, -8, -10):
            _, row = measure(*world, riser_db=asked)
            assert abs(row["excess_db"] - asked) <= 0.6, (
                f"asked for {asked} dB under the bed, measured "
                f"{row['excess_db']}")

    def test_without_stems_it_says_the_number_is_not_the_event(self, world):
        """The fallback must not pass itself off as a measurement.

        This is the OLD behaviour, kept as a fallback and labelled. The
        ambience here is louder than the riser, so the summed reading is the
        ambience — and the row has to say so rather than print a figure of
        unstated provenance.
        """
        _, row = measure(*world, riser_db=-30, use_stems=False)
        assert row["measured_from"].startswith("summed design layer")
        _, stemmed = measure(*world, riser_db=-30, use_stems=True)
        assert row["design_lufs"] > stemmed["design_lufs"] + 3.0, (
            "the summed layer did not read louder than the stem, so this "
            "fixture no longer reproduces the fault it was built for")


class TestTheRuleStillBlocks:
    def test_an_event_over_the_bed_is_refused(self, world):
        """The owner's rule, unchanged: nothing above the bed at that instant.

        Measured through the stem now, which makes it enforceable rather than
        approximately true.
        """
        problems, row = measure(*world, riser_db=+2)
        assert row["excess_db"] > 0
        assert problems and "over it" in problems[0]

    def test_an_event_under_the_bed_passes(self, world):
        problems, row = measure(*world, riser_db=-6)
        assert row["excess_db"] < 0
        assert not [p for p in problems if "riser" in p]


class TestThePlacementCheck:
    """A level that was applied and did not arrive.

    This is the gate that would have caught four films of silent risers. The
    riser was named in the spec, priced by the playbook, placed by
    sound_design, levelled by the table and printed in the report — and
    delivered at -120 LUFS against a -54 target, because its asset ended in
    eight seconds of silence and the slice that keeps "the top of the riser"
    took the end of the file. Nothing compared what was asked for with what
    arrived.
    """

    def test_a_well_placed_event_passes(self, world):
        problems, row = measure(*world, riser_db=-6)
        assert row["target_db"] is not None
        assert abs(row["placement_error_db"]) <= V.PLACEMENT_TOLERANCE_DB
        assert not [p for p in problems if "placed at" in p or "SILENT" in p]

    def test_a_silent_riser_asset_fails_and_names_it(self, world, tmp_path):
        """THE CONTROL. A riser whose audio is silence must be refused.

        Built the way the real one broke: a file whose sound is at the start
        and whose END — which is what the riser slice takes — is silence. The
        trim in `sound_design` defeats that now, so this goes further and
        makes the whole asset silent, which is the same thing from the gate's
        point of view: an element placed at a target and delivering nothing.
        """
        import soundfile as sf

        spec, assets, bed, curve, bed_db = world
        quiet = tmp_path / "sd_silent"
        quiet.mkdir()
        # the ambience stays audible; only the riser is silence
        amb, sr = sf.read(Path(assets) / "amb.wav", dtype="float32")
        sf.write(quiet / "amb.wav", amb, sr)
        sf.write(quiet / "riser.wav",
                 np.zeros(int(2.0 * SR), dtype=np.float32), SR)

        problems, row = measure(spec, str(quiet), bed, curve, bed_db,
                                riser_db=-6)
        assert row["design_lufs"] <= V.FLOOR_LUFS, row
        silent = [p for p in problems if "SILENT" in p]
        assert silent, problems
        assert "riser" in silent[0]
        assert "riser.wav" in silent[0], silent[0]
        assert "-6" in silent[0] or "placed at" in silent[0], silent[0]

    def test_the_report_counts_it(self, world, tmp_path):
        import soundfile as sf

        spec, assets, bed, curve, bed_db = world
        quiet = tmp_path / "sd_silent2"
        quiet.mkdir()
        amb, sr = sf.read(Path(assets) / "amb.wav", dtype="float32")
        sf.write(quiet / "amb.wav", amb, sr)
        sf.write(quiet / "riser.wav",
                 np.zeros(int(2.0 * SR), dtype=np.float32), SR)

        stems: list = []
        design, _ = SD.build(spec, TOTAL, bed_db, playbook(-6), str(quiet),
                             bed_curve=curve, stems_out=stems)
        n = min(len(design), len(bed))
        d = design[:n]
        if d.ndim == 1:
            d = d[:, None]
        _, report = V.check(d, bed[:n], SR, spec, stems=stems)
        assert report["placement_checked"] is True
        assert report["events_silent"] == 1, report["events"]

    def test_without_stems_the_report_says_it_was_not_checked(self, world):
        """Three-state, so a skipped blocking check cannot look like a pass."""
        spec, assets, bed, curve, bed_db = world
        stems: list = []
        design, _ = SD.build(spec, TOTAL, bed_db, playbook(-6), assets,
                             bed_curve=curve, stems_out=stems)
        n = min(len(design), len(bed))
        d = design[:n]
        if d.ndim == 1:
            d = d[:, None]
        _, report = V.check(d, bed[:n], SR, spec, stems=None)
        assert report["placement_checked"] is False
        assert report["events_off_their_target"] == 0

    def test_an_event_the_build_never_placed_is_refused(self, world):
        """Stems handed over, but one event missing from them.

        A spec that names an event the build did not place is the same class
        of fault as one placed inaudibly, and it must not pass just because
        there is nothing to measure.
        """
        spec, assets, bed, curve, bed_db = world
        stems: list = []
        design, _ = SD.build(spec, TOTAL, bed_db, playbook(-6), assets,
                             bed_curve=curve, stems_out=stems)
        n = min(len(design), len(bed))
        d = design[:n]
        if d.ndim == 1:
            d = d[:, None]
        problems, _ = V.check(d, bed[:n], SR, spec, stems=[])
        assert any("never placed" in p for p in problems), problems

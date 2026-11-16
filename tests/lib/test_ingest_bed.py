"""The trim that turns a candidate into a bed, as a rule rather than a hand.

For five films the step between the audition and the mixer was done by hand
and recorded nowhere. Measuring the two against each other on 2026-11-15
showed what it was worth, on one candidate:

    candidates/bed_cinematic_quiet.mp3          168.1s   file hole 46.59 dB
      through the real gate, 622.82s span                      28.25 dB  REFUSED
    the hand trim, trimmed/bed_cinematic_quiet.wav 117.6s        4.92 dB  passes
    what this rule recovers at a 7 dB ceiling    160.5s          7.29 dB  passes

So the hand trim was the measurement that fixed the rule — and the rule
beats it, keeping 43 more seconds of music at the same hole.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import ingest_bed as ib  # noqa: E402
from lib import mix_audio as mx  # noqa: E402


def noise(path: Path, seconds: float, seed: int = 3) -> Path:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"anoisesrc=d={seconds}:c=pink:r=48000:seed={seed}",
         "-af", "lowpass=f=900", "-ar", "48000", "-ac", "2", str(path)],
        check=True)
    return path


def with_silence(path: Path, seconds: float, hole_at: float,
                 hole_len: float = 2.0) -> Path:
    """Steady material with a silent stretch dropped into it."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"anoisesrc=d={seconds}:c=pink:r=48000:seed=5",
         "-af", f"lowpass=f=900,volume=enable='between(t,{hole_at},"
                f"{hole_at + hole_len})':volume=0",
         "-ar", "48000", "-ac", "2", str(path)], check=True)
    return path


class TestTheMeasureIsTheMixersOwn:
    def test_the_hole_is_median_minus_minimum(self):
        levels = np.array([-20.0, -21.0, -22.0, -30.0])
        assert ib.hole_of(levels) == pytest.approx(
            float(np.median(levels) - levels.min()))

    def test_frames_below_the_floor_are_dropped_as_the_mixer_drops_them(self):
        """`internal_dynamics` discards anything under -70 before measuring.
        The first version of this file omitted the filter and read 60.57 dB
        on a file the mixer's own measure puts at 46.59."""
        import inspect
        assert "live = st[st > -70.0]" in inspect.getsource(
            mx.internal_dynamics)
        quiet = np.array([-20.0, -21.0, -22.0, -120.0])
        assert ib.hole_of(quiet) == pytest.approx(ib.hole_of(quiet[:3]))

    def test_it_is_not_max_minus_min(self):
        """A different and stricter number that the 10 dB ceiling was never
        calibrated against."""
        levels = np.array([-10.0, -20.0, -21.0, -22.0])
        assert ib.hole_of(levels) != pytest.approx(
            float(levels.max() - levels.min()))


class TestItFindsTheLongestSteadyWindow:
    def test_steady_material_is_kept_whole(self, tmp_path):
        src = noise(tmp_path / "steady.wav", 20.0)
        row = ib.ingest(str(src), tmp_path / "lib", min_seconds=5.0,
                        dry_run=True)
        assert "refused" not in row, row
        assert row["seconds"] > 18.0, row

    def test_a_hole_in_the_middle_splits_it(self, tmp_path):
        """The window has to be CONTIGUOUS, so a dip at the midpoint leaves
        half the file, not the file minus two seconds."""
        src = with_silence(tmp_path / "split.wav", 20.0, hole_at=10.0)
        row = ib.ingest(str(src), tmp_path / "lib", min_seconds=5.0,
                        dry_run=True)
        assert "refused" not in row, row
        assert 7.0 < row["seconds"] < 13.0, row

    def test_a_hole_at_the_edge_is_trimmed_off(self, tmp_path):
        """What the real candidates have: near-silence where they fade in."""
        src = with_silence(tmp_path / "edge.wav", 20.0, hole_at=0.5)
        row = ib.ingest(str(src), tmp_path / "lib", min_seconds=5.0,
                        dry_run=True)
        assert "refused" not in row, row
        assert row["window_start_s"] > 0.5, row
        assert row["seconds"] > 14.0, row

    def test_the_window_is_quieter_than_the_file(self, tmp_path):
        src = with_silence(tmp_path / "x.wav", 20.0, hole_at=0.5)
        row = ib.ingest(str(src), tmp_path / "lib", min_seconds=5.0,
                        dry_run=True)
        assert row["window_hole_db"] < row["source_hole_db"], row


class TestWhatItRefuses:
    def test_a_window_under_the_minimum_is_refused(self, tmp_path):
        src = noise(tmp_path / "short.wav", 20.0)
        row = ib.ingest(str(src), tmp_path / "lib", min_seconds=90.0,
                        dry_run=True)
        assert "refused" in row
        assert "under the 90s a bed needs" in row["refused"]

    def test_the_minimum_is_ninety_seconds(self):
        """A bed shorter than this turns over so often the loop becomes the
        rhythm."""
        assert ib.MIN_BED_SECONDS == 90.0

    def test_nothing_is_written_when_it_refuses(self, tmp_path):
        out = tmp_path / "lib"
        src = noise(tmp_path / "short.wav", 20.0)
        ib.ingest(str(src), out, min_seconds=90.0, dry_run=False)
        assert not out.exists() or not list(out.glob("*.wav"))

    def test_a_dry_run_writes_nothing(self, tmp_path):
        out = tmp_path / "lib"
        src = noise(tmp_path / "ok.wav", 20.0)
        row = ib.ingest(str(src), out, min_seconds=5.0, dry_run=True)
        assert row["written"] is False
        assert not out.exists() or not list(out.glob("*.wav"))


class TestWhatItRecords:
    def test_the_bed_carries_its_provenance(self, tmp_path):
        out = tmp_path / "lib"
        src = noise(tmp_path / "bed.wav", 20.0)
        row = ib.ingest(str(src), out, min_seconds=5.0, dry_run=False)
        for key in ("source", "source_sha256", "sha256", "window_start_s",
                    "window_end_s", "seconds", "hole_db", "ingested"):
            assert key in row, key
        assert row["source_sha256"] == ib.sha256(src)
        assert row["sha256"] == ib.sha256(out / row["track"])

    def test_the_written_file_is_measured_not_the_search(self, tmp_path):
        """The authority is the file that was written."""
        out = tmp_path / "lib"
        src = noise(tmp_path / "bed.wav", 20.0)
        row = ib.ingest(str(src), out, min_seconds=5.0, dry_run=False)
        assert row["hole_db"] == mx.internal_dynamics(
            str(out / row["track"]))["hole_db"]

    def test_the_manifest_describes_the_library_not_its_history(self, tmp_path):
        """A hand-written manifest left three raw mp3s listed after ingest
        had replaced them with two wavs — five beds over a library of two."""
        out = tmp_path / "lib"
        out.mkdir()
        (out / ib.MANIFEST).write_text(json.dumps(
            {"beds": [{"track": "gone.wav", "seconds": 1.0}]}))
        src = noise(tmp_path / "real.wav", 20.0)
        row = ib.ingest(str(src), out, min_seconds=5.0, dry_run=False)
        ib.record(out, [row])
        book = json.loads((out / ib.MANIFEST).read_text())
        assert [b["track"] for b in book["beds"]] == [row["track"]]

    def test_the_manifest_names_both_ceilings(self, tmp_path):
        out = tmp_path / "lib"
        src = noise(tmp_path / "bed.wav", 20.0)
        row = ib.ingest(str(src), out, min_seconds=5.0, dry_run=False)
        book = json.loads(ib.record(out, [row]).read_text())
        assert book["mixer_hole_ceiling_db"] == mx.BED_HOLE_MAX_DB
        assert book["ingest_hole_ceiling_db"] == ib.INGEST_HOLE_CEILING_DB


class TestTheCeilingIsItsOwnDecision:
    def test_ingest_is_stricter_than_the_mixer(self):
        """Measured on bed_cinematic_quiet over film #5's own 622.82s span:
        ingesting at 10.0 leaves 0.71 dB of headroom and at 7.0 leaves 2.71,
        for 1.2 seconds of length. The gate it has to clear fails a whole
        film."""
        assert ib.INGEST_HOLE_CEILING_DB <= mx.BED_HOLE_MAX_DB

    def test_a_tighter_ceiling_takes_a_shorter_window(self, tmp_path):
        src = with_silence(tmp_path / "x.wav", 20.0, hole_at=0.5)
        loose = ib.ingest(str(src), tmp_path / "a", 5.0, True, ceiling=12.0)
        tight = ib.ingest(str(src), tmp_path / "b", 5.0, True, ceiling=3.0)
        assert tight["seconds"] <= loose["seconds"]
        assert tight["window_hole_db"] <= loose["window_hole_db"]

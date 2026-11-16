"""The audition asks the question the mixer will ask.

`scripts/measure_music.py` ranks candidate beds before anybody listens, on
three properties OF THE FILE: melodic movement, build, rhythmic periodicity.
The mixer gates on a property of the BED — `hole_db` against
BED_HOLE_MAX_DB, measured after the span has been built and conditioned. A
bed shorter than its span is looped, and looping is where holes come from,
so a file could be flawless on all three and still be refused after it had
won the audition, been EQ'd, levelled and laid under the whole narration.

And it screened one track twice: `bed_ambient_pad` and `bed_sustained_tone`
are the same file, at every stage, in both projects.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import mix_audio as mx  # noqa: E402
from lib.shared_state import MUSIC_DIR_ENV, music_dir, state_dir  # noqa: E402

import measure_music as mm  # noqa: E402


def tone(path: Path, seconds: float, seed: int = 1) -> Path:
    """A short band-limited noise bed, like the real ones after EQ."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"anoisesrc=d={seconds}:c=pink:r=48000:seed={seed}",
         "-af", "lowpass=f=900", "-ar", "48000", "-ac", "2", str(path)],
        check=True)
    return path


class TestOneTrackIsScreenedOnce:
    def test_two_names_for_one_file_are_folded(self, tmp_path):
        """bed_ambient_pad and bed_sustained_tone, which really are one
        file — screened twice, scored twice, offered twice in a shortlist
        of six."""
        a = tone(tmp_path / "bed_ambient_pad.wav", 2.0)
        b = tmp_path / "bed_sustained_tone.wav"
        b.write_bytes(a.read_bytes())
        kept, folded = mm.unique([str(a), str(b)])
        assert len(kept) == 1
        assert len(folded) == 1
        assert folded[0]["same_file_as"] == "bed_ambient_pad.wav"
        assert folded[0]["track"] == "bed_sustained_tone.wav"

    def test_the_kept_name_does_not_depend_on_directory_order(self, tmp_path):
        a = tone(tmp_path / "aaa.wav", 2.0)
        b = tmp_path / "zzz.wav"
        b.write_bytes(a.read_bytes())
        for order in ([str(a), str(b)], [str(b), str(a)]):
            kept, _ = mm.unique(order)
            assert [Path(k).name for k in kept] == ["aaa.wav"]

    def test_two_different_files_are_both_kept(self, tmp_path):
        a = tone(tmp_path / "one.wav", 2.0, seed=1)
        b = tone(tmp_path / "two.wav", 2.0, seed=77)
        kept, folded = mm.unique([str(a), str(b)])
        assert len(kept) == 2 and folded == []

    def test_the_digest_is_of_the_bytes(self, tmp_path):
        a = tone(tmp_path / "x.wav", 1.0)
        assert mm.digest(str(a)) == hashlib.sha256(a.read_bytes()).hexdigest()


class TestTheSpanIsBuiltTheWayTheMixerBuildsIt:
    def test_a_track_longer_than_its_span_takes_a_window(self, tmp_path):
        src = tone(tmp_path / "long.wav", 12.0)
        info = mx.fill_span(str(src), 6.0, str(tmp_path / "span.wav"))
        assert info["looped"] is False
        assert info["reps"] == 1
        assert info["window"] is not None

    def test_a_track_shorter_than_its_span_is_looped(self, tmp_path):
        """Where holes come from, and what the raw file cannot show."""
        src = tone(tmp_path / "short.wav", 10.0)
        info = mx.fill_span(str(src), 30.0, str(tmp_path / "span.wav"))
        assert info["looped"] is True
        assert info["reps"] > 1
        assert info["window"] is None

    def test_the_span_is_the_length_that_was_asked_for(self, tmp_path):
        src = tone(tmp_path / "s.wav", 10.0)
        dest = tmp_path / "span.wav"
        mx.fill_span(str(src), 25.0, str(dest))
        got = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(dest)]).strip())
        assert abs(got - 25.0) < 0.2, got

    def test_the_mixer_itself_uses_this_function(self):
        """Not a second copy of the looping rule — the point of extracting
        it was that the audition and the mixer cannot disagree."""
        import inspect
        assert "fill_span(" in inspect.getsource(mx.build_bed)


class TestABedTheMixerWouldRefuseCannotWin:
    def test_the_hole_is_measured_on_the_conditioned_span(self):
        """The compressor LOWERS ITS THRESHOLD to close a hole, so a hole
        measured before conditioning is not the number the mixer gates on
        and would refuse beds the mixer can rescue."""
        import inspect
        src = inspect.getsource(mx.span_hole_db)
        assert "fill_span(" in src
        assert "condition_bed(" in src

    def test_it_reports_against_the_mixers_own_ceiling(self, tmp_path):
        src = tone(tmp_path / "bed.wav", 8.0)
        out = mx.span_hole_db(str(src), 20.0)
        assert out["hole_ceiling_db"] == mx.BED_HOLE_MAX_DB
        assert out["looped"] is True
        assert out["would_be_refused"] == (
            out["hole_db"] is not None
            and out["hole_db"] > mx.BED_HOLE_MAX_DB)

    def test_the_hole_gates_an_ingested_library_and_reports_elsewhere(self):
        """The distinction the whole item turns on.

        Looping a RAW candidate measures its silence, not its music.
        Measured 2026-11-15: `candidates/bed_cinematic_quiet.mp3` has
        near-silence at its edges — median -22.81 LUFS against a minimum of
        -69.40, a 46.59 dB hole in the FILE — and over film #5's own
        622.82s span it conditions out at 28.25 dB, refused. The 117.6s core
        a hand trim found reads 4.92 dB over the same span, and that is the
        bed the film actually used. A refusal read off a raw file would
        reject every bed whose source fades in, which on that library is all
        of them.

        `scripts/ingest_bed.py` is that trim as a rule, and a library it has
        written carries a MANIFEST. There every bed is loopable already and
        a hole over the ceiling is a real refusal; elsewhere it is a
        candidate nobody has ingested yet.
        """
        source = (ROOT / "scripts" / "measure_music.py").read_text()
        assert "needs_ingest" in source
        assert 'MANIFEST.json' in source, (
            "the refusal must key on the library having been ingested")
        # the refusal exists, and it is inside the `ingested` branch
        refuse = source.index('r["meets_all"] = False')
        guard = source.index("if ingested:")
        assert guard < refuse, (
            "a hole over the ceiling must only be a miss on an ingested "
            "library, or the false refusal is back")

    def test_an_un_ingested_library_is_named_as_such(self):
        source = (ROOT / "scripts" / "measure_music.py").read_text()
        assert "not ingested" in source

    def test_the_candidate_that_proved_it_still_reads_over_the_ceiling(self):
        """The arithmetic is not in doubt — only what it means. Pinned so a
        change to the ceiling or the conditioning shows up here."""
        assert mx.BED_HOLE_MAX_DB == 10.0

    def test_the_hole_is_measured_after_the_cheap_criteria(self):
        """It builds and conditions a real span per candidate. Measuring it
        first would spend that on tracks the three criteria reject."""
        source = (ROOT / "scripts" / "measure_music.py").read_text()
        assert source.index("rows.sort(") < source.index("span_hole_db")

    def test_it_can_be_skipped(self):
        source = (ROOT / "scripts" / "measure_music.py").read_text()
        assert "--no-hole" in source


class TestOneSharedLibrary:
    def test_it_sits_beside_the_ledger(self):
        assert music_dir() == state_dir() / "music"

    def test_the_environment_overrides_it(self, tmp_path, monkeypatch):
        monkeypatch.setenv(MUSIC_DIR_ENV, str(tmp_path))
        assert music_dir() == tmp_path

    def test_the_env_name_is_the_one_already_in_use(self):
        """`build_render_props` read MUSIC_LIBRARY_DIR from the environment
        before anything defined it."""
        assert MUSIC_DIR_ENV == "MUSIC_LIBRARY_DIR"
        props = (ROOT / "lib" / "build_render_props.py").read_text()
        assert MUSIC_DIR_ENV in props

    def test_the_screening_defaults_to_it(self):
        source = (ROOT / "scripts" / "measure_music.py").read_text()
        assert "music_dir()" in source

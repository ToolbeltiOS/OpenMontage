"""Review excerpts: the head of the film and each act boundary.

An audio change is judged by ear on the passages where it matters. The two
that matter after a mix change are the head — where a bed's character is most
exposed, because there is least narration over it — and an act boundary, where
the bed crossfades, the envelope lifts to its loudest level and the sting
lands, all within five seconds of each other and nowhere else.

The boundaries come from the mix report, not from the script's section
durations, because the mix report is written from the timeline the mixer
actually built. Two sources for one set of positions is how the picture and
the sound came out of step once already.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("scripts").resolve()))
import export_excerpts as ex  # noqa: E402


class TestWhereTheWindowsComeFrom:
    def test_the_boundaries_are_read_from_the_mix_report(self, tmp_path, monkeypatch):
        renders = tmp_path / "projects" / "p" / "renders"
        renders.mkdir(parents=True)
        (renders / "mix_report.json").write_text(json.dumps(
            {"air": {"act_boundaries": [45.0, 317.45, 628.61]}}))
        monkeypatch.setattr(ex, "ROOT", tmp_path)
        assert ex.act_boundaries("p") == [
            ("boundary-1", 45.0), ("boundary-2", 317.45),
            ("boundary-3", 628.61)]

    def test_a_project_with_no_mix_report_has_no_boundaries(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ex, "ROOT", tmp_path)
        assert ex.act_boundaries("p") == []

    def test_the_pad_and_the_head_are_the_owners_numbers(self):
        assert ex.BOUNDARY_PAD == 30.0
        assert ex.HEAD_SECONDS == 180.0


class TestTheCut:
    @pytest.fixture
    def film(self, tmp_path):
        path = tmp_path / "film.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y",
             "-f", "lavfi", "-i", "testsrc=size=128x72:rate=24:duration=12",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
             "-c:v", "libx264", "-crf", "24", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-shortest", str(path)], check=True)
        return path

    def test_the_window_is_the_window_that_was_asked_for(self, film, tmp_path):
        """`-c:v copy` could only start on a keyframe, which is why the
        picture is re-encoded: an excerpt asked for at 598.6s would otherwise
        silently begin somewhere else."""
        dest = tmp_path / "cut.mp4"
        ex.cut(film, 5.0, 3.0, dest)
        assert ex.seconds(dest) == pytest.approx(3.0, abs=0.3)

    def test_the_audio_is_copied_not_re_encoded(self, film, tmp_path):
        """What the owner hears has to be the delivered mix, not a second
        generation of it."""
        dest = tmp_path / "cut.mp4"
        ex.cut(film, 2.0, 3.0, dest)
        codec = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0",
             str(dest)], capture_output=True, text=True, check=True).stdout
        assert codec.strip() == "aac"
        src = Path("scripts/export_excerpts.py").read_text()
        assert '"-c:a", "copy"' in src

    def test_it_makes_the_output_directory(self, film, tmp_path):
        dest = tmp_path / "nested" / "dir" / "cut.mp4"
        ex.cut(film, 1.0, 2.0, dest)
        assert dest.exists()

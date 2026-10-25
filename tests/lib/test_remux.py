"""A new mix onto a delivered film, without a second generation of picture.

An audio change is the one kind of change that can be delivered by remuxing,
and a twenty-minute ProRes-to-h264 pass is the one kind of cost worth avoiding
to do it. `-c:v copy` is what makes it safe: the video stream in the output is
the same bytes as the input, so the graded, composited, encoded picture is not
re-encoded and cannot drift.

THE THING THIS MUST NOT BECOME is the defect the whole music-authority rule
exists for: a mix adjusted by hand and muxed onto a finished render, which the
props builder never learns about, so the next full re-render puts the rejected
audio back. The mix a remux carries has to be one `lib/mix_audio.py` built from
the EDL, and the hash beside `mix_final.wav` is what says so.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from lib import film_render as fr


def streams(path: Path) -> list[dict]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_name,codec_type,width,height,sample_rate",
         "-of", "json", str(path)], capture_output=True, text=True,
        check=True).stdout
    return json.loads(out)["streams"]


def video_md5(path: Path) -> str:
    """Hash of the DECODED video, which is what "not re-encoded" means."""
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0",
         "-f", "md5", "-"], capture_output=True, text=True,
        check=True).stdout.strip()


@pytest.fixture
def film(tmp_path):
    """A tiny delivered film: picture plus a tone."""
    path = tmp_path / "film.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=size=128x72:rate=24:duration=3",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-shortest", str(path)], check=True)
    return path


@pytest.fixture
def new_mix(tmp_path):
    path = tmp_path / "mix.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=110:duration=3", "-ar", "48000", "-ac", "2",
         str(path)], check=True)
    return path


class TestTheRemux:
    def test_the_picture_is_the_same_bytes_afterwards(self, film, new_mix):
        before = video_md5(film)
        fr.remux(film, new_mix)
        assert video_md5(film) == before, (
            "the video was re-encoded; -c:v copy is the whole point")

    def test_the_audio_is_the_new_mix(self, film, new_mix):
        """A 440 Hz film becomes a 110 Hz one."""
        def peak_hz(path):
            import numpy as np

            raw = subprocess.run(
                ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
                 "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "1",
                 "-ar", "48000", "-"], capture_output=True, check=True).stdout
            y = np.frombuffer(raw, dtype="float32")[:48000 * 2]
            spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
            return float(np.fft.rfftfreq(len(y), 1 / 48000)[int(spec.argmax())])

        assert peak_hz(film) == pytest.approx(440, abs=20)
        fr.remux(film, new_mix)
        assert peak_hz(film) == pytest.approx(110, abs=20)

    def test_it_stays_one_video_and_one_audio_stream(self, film, new_mix):
        fr.remux(film, new_mix)
        st = streams(film)
        assert [s["codec_type"] for s in st] == ["video", "audio"]
        assert st[1]["codec_name"] == "aac"

    def test_the_picture_size_is_untouched(self, film, new_mix):
        before = [(s.get("width"), s.get("height")) for s in streams(film)
                  if s["codec_type"] == "video"]
        fr.remux(film, new_mix)
        after = [(s.get("width"), s.get("height")) for s in streams(film)
                 if s["codec_type"] == "video"]
        assert before == after

    def test_a_failed_remux_leaves_the_delivered_film_alone(self, film, tmp_path):
        """It writes beside the film and replaces it only on success."""
        before = film.read_bytes()
        with pytest.raises(subprocess.CalledProcessError):
            fr.remux(film, tmp_path / "not-a-file.wav")
        assert film.read_bytes() == before


class TestItIsWiredIntoTheOnlyRenderPath:
    def test_render_film_offers_remux(self):
        src = Path("scripts/render_film.py").read_text()
        assert '"--remux"' in src
        assert "remux(dest, mix)" in src

    def test_remux_refuses_without_a_delivered_film(self):
        src = Path("scripts/render_film.py").read_text()
        assert "--remux needs a delivered film" in src

    def test_the_gates_still_run_after_it(self):
        """A remux that skipped the gates would be the old defect exactly."""
        src = Path("scripts/render_film.py").read_text()
        remux_at = src.index("remux(dest, mix)")
        gates_at = src.index("problems, results = gates(")
        assert gates_at > remux_at

    def test_copying_the_video_is_stated_in_the_source(self):
        src = Path("lib/film_render.py").read_text()
        i = src.index("def remux(")
        body = src[i:i + 2000]
        assert '"-c:v", "copy"' in body
        assert "libx264" not in body


class TestEveryFrameTheEditAsksForIsInTheFile:
    """`-shortest` took the end off the film, and the report printed the
    number the edit asked for beside a file that did not have it.

    The cut durations and the narration timeline do not come to the same
    length — 169 cuts each rounded to a frame leaves them 0.486s apart on
    easter-island — and with the audio the shorter of the two, `-shortest`
    truncated the PICTURE: 36,302 frames delivered against 36,317 asked,
    half a second of the outro under the closing title card.

    Two things were wrong and both are fixed: the audio is padded to the
    picture rather than the picture truncated to the audio, and `gates`
    compares the delivered count against the asked-for one. The frame-motion
    gate already decoded the film and counted; nothing compared the numbers.
    """

    @pytest.fixture
    def short_mix(self, tmp_path):
        """A mix half a second shorter than the picture, as the real one is."""
        path = tmp_path / "short.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", "sine=frequency=110:duration=2.5", "-ar", "48000",
             "-ac", "2", str(path)], check=True)
        return path

    def _frames(self, path: Path) -> int:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-count_frames", "-show_entries", "stream=nb_read_frames",
             "-of", "csv=p=0", str(path)], capture_output=True, text=True,
            check=True).stdout
        return int(out.strip().rstrip(","))

    def test_a_short_mix_no_longer_truncates_the_picture(self, film, short_mix):
        before = self._frames(film)
        assert before == 72, before          # 3s at 24fps
        fr.remux(film, short_mix)
        assert self._frames(film) == before, (
            "the picture was truncated to the audio; apad is missing")

    def test_the_padding_is_silence_and_not_a_repeat(self, film, short_mix):
        import numpy as np

        fr.remux(film, short_mix)
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", "2.7", "-i", str(film),
             "-map", "0:a:0", "-f", "f32le", "-acodec", "pcm_f32le",
             "-ac", "1", "-ar", "48000", "-"],
            capture_output=True, check=True).stdout
        tail = np.frombuffer(raw, dtype="float32")
        assert tail.size and float(np.abs(tail).max()) < 0.02, (
            f"the tail peaks at {float(np.abs(tail).max()):.3f}; apad should "
            f"write silence, not loop the mix")

    def test_the_gate_catches_a_short_file(self):
        """INJECTED: cuts asking for more frames than the file holds."""
        import lib.film_render as m

        cuts = [{"out_seconds": 3.5}]        # 105 frames at 30fps
        asked = m.frame_count(cuts, 30)
        got = 90
        assert asked == 105
        assert asked != got
        src = Path("lib/film_render.py").read_text()
        assert "has had the end taken off it" in src
        assert '"frame count"' in src

    def test_the_report_prints_what_was_delivered_not_what_was_asked(self):
        src = Path("lib/film_render.py").read_text()
        assert "delivered of {count} asked" in src
        assert "| frame count |" in src

"""A pass that wrote its file is finished, and a finished pass is not re-rendered.

WHAT HAPPENED
-------------
2026-11-07, the king-tut plate. The log, in order:

    Rendered 36803/36803                        line 36,840
    Encoded 2/36803 … Encoded 36803/36803       lines 36,841–40,833
    +   …/out/king-tut/plate.mp4 1.3 GB         line 40,834
    plate FAILED: no progress for 600s          line 40,835

and in the middle of it, at line 37,768:

    WATCHDOG: no progress for 628s at frame 36803/36803 — killing plate

`ffprobe -count_frames` on that file afterwards: 36,803 frames of 36,803,
the last second decodes, 1,226.77s against a 1,226.26s mix. The picture was
finished. The run was not.

Three separate defects produced that, and each one has a control here:

  1. THE ENCODE HAD NO HEARTBEAT. `_PROGRESS` matches `Rendered|Encoded`,
     but the reader only reset the stall clock on `Rendered`, and an h264
     render prints no `Rendered` line after the last frame. The 50-minute
     encode-and-mux therefore ran with the clock frozen — the watchdog armed
     while `Encoded` climbed three lines a second in front of it.
  2. THE OUTPUT LINE MEANT NOTHING. Remotion names the file it wrote before
     it tears the browser tree down, and teardown is where a render throws
     (`Page.bringToFront: Target closed`, line 24 of this same log) or hangs.
     Nothing read that line, so a finished pass could still be failed.
  3. THE KILL DID NOT REACH THE RENDERER. The watchdog killed at line
     37,768 and Remotion wrote 3,000 more lines and finished the file —
     because `proc.kill()` killed `npm exec`, a shell wrapper, while node
     and the compositor were grandchildren in the same process group. The
     log proves it: a watchdog whose kill works cannot see output after it.

And one consequence, which is what actually cost the day: there was no way
to resume. `--skip-picture` skips the plate AND the frames AND the type pass,
so the only route past a finished plate was to render it again.

Every test below drives the real `run_watched` with a real subprocess. The
clocks are shortened; nothing else is faked. The fakes that "hang" hang for
25 seconds rather than forever, because a regression that makes this file
block the suite teaches nobody anything — each one has to FAIL.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import film_render  # noqa: E402


#: The real line, copied from projects/king-tut/render.log line 40,834.
REAL_OUTPUT_LINE = (
    "+                    /Users/mac/Developer/wak3up-docs/runner/"
    "remotion-composer/out/king-tut/plate.mp4 1.3 GB")


@pytest.fixture
def quick(monkeypatch):
    """The same watchdog, on a clock a test can wait out.

    WATCH_FINALISE is patched too, since the asset-library merge: a pass
    that has printed its last frame is given that limit rather than
    WATCH_STALL, so a case here whose script reaches `Rendered n/n` waits
    out the finalise clock and not the stall clock. Left unpatched it is
    1,800 seconds and every such case passes by never being judged.
    """
    monkeypatch.setattr(film_render, "WATCH_INTERVAL", 0.2)
    monkeypatch.setattr(film_render, "WATCH_STALL", 1.0)
    monkeypatch.setattr(film_render, "WATCH_FINALISE", 1.0)
    monkeypatch.setattr(film_render, "FINISH_GRACE", 1.0)


def fake_pass(tmp_path: Path, body: str, name: str = "pass.sh") -> list[str]:
    script = tmp_path / name
    script.write_text("#!/bin/bash\nset -u\n" + textwrap.dedent(body))
    script.chmod(0o755)
    return ["/bin/bash", str(script)]


# ── 1. the control pair the owner asked for ──────────────────────────────

class TestTheOutputLineEndsThePass:
    """A pass that printed its output line and then hung must PASS.
    A pass that hung without printing one must still FAIL.
    """

    def test_wrote_its_file_then_hung_forever(self, tmp_path, quick, capsys):
        out = tmp_path / "plate.mp4"
        out.write_bytes(b"not really an mp4, but it is on disk")
        cmd = fake_pass(tmp_path, f"""
            echo "Rendered 10/10"
            echo "+                    {out} 1.3 GB"
            for i in $(seq 1 250); do sleep 0.1; done
        """)
        # No exception: this is the whole point.
        film_render.run_watched(cmd, tmp_path, "plate", 10, output=out)
        said = capsys.readouterr().out
        assert "reaping the render tree" in said, said

    def test_hung_without_ever_naming_an_output(self, tmp_path, quick):
        cmd = fake_pass(tmp_path, """
            echo "Rendered 5/10"
            for i in $(seq 1 250); do sleep 0.1; done
        """)
        with pytest.raises(SystemExit) as caught:
            film_render.run_watched(cmd, tmp_path, "plate", 10,
                                    output=tmp_path / "plate.mp4")
        said = str(caught.value)
        assert "plate FAILED" in said
        assert "reached frame 5 of 10" in said
        assert "never named an output file" in said

    def test_a_pass_that_names_someone_elses_file_is_not_finished(
            self, tmp_path, quick):
        """Remotion prints a `+` line per artifact. The pass ends on OURS.

        Without this, the first `+` line of a multi-artifact render would end
        the pass early and the next pass would read a file nobody wrote.
        """
        other = tmp_path / "something_else.mp4"
        other.write_bytes(b"x")
        cmd = fake_pass(tmp_path, f"""
            echo "Rendered 5/10"
            echo "+                    {other} 2.0 MB"
            for i in $(seq 1 250); do sleep 0.1; done
        """)
        with pytest.raises(SystemExit) as caught:
            film_render.run_watched(cmd, tmp_path, "plate", 10,
                                    output=tmp_path / "plate.mp4")
        assert "never named an output file" in str(caught.value)

    def test_the_line_has_to_be_true_as_well_as_printed(self, tmp_path, quick):
        """The `+` line is a claim; `stat` is the fact."""
        out = tmp_path / "plate.mp4"  # deliberately never created
        cmd = fake_pass(tmp_path, f"""
            echo "Rendered 10/10"
            echo "+                    {out} 1.3 GB"
            for i in $(seq 1 250); do sleep 0.1; done
        """)
        with pytest.raises(SystemExit):
            film_render.run_watched(cmd, tmp_path, "plate", 10, output=out)

    def test_the_real_king_tut_line_parses(self, tmp_path):
        got = film_render._WROTE.match(REAL_OUTPUT_LINE)
        assert got, REAL_OUTPUT_LINE
        assert got.group(1).endswith("/out/king-tut/plate.mp4")


# ── 2. the encode is a heartbeat ─────────────────────────────────────────

class TestTheEncodeCounts:
    """`Encoded` keeps the clock alive; it does not move the frame reached."""

    def test_a_long_encode_with_no_rendered_line_is_not_a_stall(
            self, tmp_path, quick):
        """This is defect 1, reproduced at 1/600th scale.

        Twelve `Encoded` lines a quarter-second apart is three seconds of
        silence on the `Rendered` counter, against a 1-second stall ceiling.
        Before the fix this raised; the real one raised after 628s.
        """
        out = tmp_path / "plate.mp4"
        out.write_bytes(b"x")
        cmd = fake_pass(tmp_path, f"""
            echo "Rendered 10/10"
            for i in $(seq 1 12); do echo "Encoded $i/10"; sleep 0.25; done
            echo "+                    {out} 1.3 GB"
        """)
        film_render.run_watched(cmd, tmp_path, "plate", 10, output=out)

    def test_the_frame_reached_is_the_rendered_counter_not_the_encoder(
            self, tmp_path, quick):
        """`Encoded` trailed `Rendered` by 32,000 once.

        A failure that names the encoder's number sends whoever reads it to
        the wrong cut, so the two counters stay in their own jobs: both are a
        heartbeat, only one is a position.
        """
        cmd = fake_pass(tmp_path, """
            echo "Rendered 9000/10000"
            echo "Encoded 12/10000"
            for i in $(seq 1 250); do sleep 0.1; done
        """)
        with pytest.raises(SystemExit) as caught:
            film_render.run_watched(cmd, tmp_path, "plate", 10000,
                                    output=tmp_path / "nope.mp4")
        assert "reached frame 9000 of 10000" in str(caught.value)


# ── 3. the kill reaches the renderer ─────────────────────────────────────

class TestTheReapReachesTheWholeTree:

    def test_the_child_leads_its_own_process_group(self, tmp_path, quick):
        """Without this, killing the group would kill the run."""
        out = tmp_path / "plate.mp4"
        out.write_bytes(b"x")
        pgid_file = tmp_path / "pgid"
        cmd = fake_pass(tmp_path, f"""
            ps -o pgid= -p $$ | tr -d ' ' > {pgid_file}
            echo "Rendered 10/10"
            echo "+                    {out} 1.3 GB"
            for i in $(seq 1 250); do sleep 0.1; done
        """)
        film_render.run_watched(cmd, tmp_path, "plate", 10, output=out)
        child_pgid = int(pgid_file.read_text().strip())
        assert child_pgid != os.getpgid(0), (
            "the render shares our process group, so a group kill would take "
            "the run with it — and a kill that is not a group kill does not "
            "reach node or the compositor.")

    def test_a_grandchild_does_not_survive_the_reap(self, tmp_path, quick):
        """The 3,000 log lines after the kill, as a test.

        `npm exec` is a shell wrapper; the renderer is its grandchild. The
        grandchild here is a `sleep` whose pid is written out before the pass
        hangs, and after the reap it must be gone.
        """
        out = tmp_path / "plate.mp4"
        out.write_bytes(b"x")
        pidfile = tmp_path / "grandchild"
        cmd = fake_pass(tmp_path, f"""
            sleep 25 &
            echo $! > {pidfile}
            echo "Rendered 10/10"
            echo "+                    {out} 1.3 GB"
            for i in $(seq 1 250); do sleep 0.1; done
        """)
        film_render.run_watched(cmd, tmp_path, "plate", 10, output=out)
        pid = int(pidfile.read_text().strip())
        for _ in range(50):
            if subprocess.run(["kill", "-0", str(pid)],
                              capture_output=True).returncode != 0:
                break
            time.sleep(0.1)
        else:
            subprocess.run(["kill", "-9", str(pid)], capture_output=True)
            pytest.fail(f"grandchild {pid} outlived the reap")


# ── 4. a pass whose output verifies is skipped ────────────────────────────

def make_video(path: Path, frames: int, fps: int = 30) -> Path:
    """A real file, because the thing under test is ffprobe's answer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         f"testsrc=size=64x64:rate={fps}", "-frames:v", str(frames),
         "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


class TestAFinishedPassIsNotRenderedAgain:

    def test_the_right_frame_count_verifies(self, tmp_path):
        ok, why = film_render.verified_video(make_video(tmp_path / "a.mp4", 10), 10)
        assert ok, why
        assert "10 frames" in why and "tail decodes" in why

    def test_the_wrong_frame_count_does_not(self, tmp_path):
        ok, why = film_render.verified_video(make_video(tmp_path / "a.mp4", 10), 11)
        assert not ok
        assert "10 frames" in why and "asks for 11" in why

    def test_a_missing_file_says_missing_and_nothing_else(self, tmp_path):
        ok, why = film_render.verified_video(tmp_path / "nope.mp4", 10)
        assert (ok, why) == (False, "missing")

    def test_an_empty_file_is_missing_not_broken(self, tmp_path):
        (tmp_path / "e.mp4").write_bytes(b"")
        assert film_render.verified_video(tmp_path / "e.mp4", 10) == (False, "missing")

    def test_a_truncated_render_is_never_reused(self, tmp_path):
        """What a killed render actually leaves behind."""
        path = make_video(tmp_path / "a.mp4", 120)
        whole = path.read_bytes()
        path.write_bytes(whole[: int(len(whole) * 0.55)])
        ok, _ = film_render.verified_video(path, 120)
        assert not ok

    def test_the_stills_are_counted_by_the_name_the_extractor_writes(self, tmp_path):
        frames = tmp_path / "frames_x"
        frames.mkdir()
        for i in range(1, 6):
            (frames / f"f_{i:05d}.jpg").write_bytes(b"x")
        assert film_render.verified_stills(frames, 5)[0]
        assert not film_render.verified_stills(frames, 6)[0]
        assert film_render.verified_stills(tmp_path / "gone", 5) == (False, "missing")

    def test_a_stray_jpeg_does_not_make_a_short_extraction_pass(self, tmp_path):
        frames = tmp_path / "frames_x"
        frames.mkdir()
        (frames / "f_00001.jpg").write_bytes(b"x")
        (frames / "thumbnail.jpg").write_bytes(b"x")
        assert not film_render.verified_stills(frames, 2)[0]


class TestEveryPassAsksBeforeItRenders:
    """Read as a tree, not as text: the guard has to be on each pass.

    A test that grepped for the word `reuse` would pass on a file where three
    of four passes render unconditionally.
    """

    @staticmethod
    def _tree():
        import ast
        return ast.parse((ROOT / "scripts" / "render_film.py").read_text())

    def test_each_render_call_sits_under_a_reuse_check(self):
        import ast

        tree = self._tree()
        guarded: dict[str, str] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            if not (isinstance(test, ast.UnaryOp)
                    and isinstance(test.op, ast.Not)
                    and isinstance(test.operand, ast.Call)
                    and getattr(test.operand.func, "id", None) == "reuse"):
                continue
            which = test.operand.args[0]
            name = which.value if isinstance(which, ast.Constant) else "?"
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    called = getattr(inner.func, "id", None)
                    if called in {"render_plate", "render_look", "render_type",
                                  "extract_frames"}:
                        guarded[called] = name

        assert guarded == {"render_plate": "plate",
                           "extract_frames": "frames",
                           "render_look": "look",
                           "render_type": "type"}, guarded

    def test_no_pass_is_also_called_outside_its_guard(self):
        """The `elif not args.gates_only` branch renders each pass ONCE."""
        import ast

        tree = self._tree()
        inside = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.If) and isinstance(node.test, ast.UnaryOp)
                    and isinstance(node.test.operand, ast.Call)
                    and getattr(node.test.operand.func, "id", None) == "reuse"):
                inside.update(id(n) for n in ast.walk(node)
                              if isinstance(n, ast.Call))
        loose = [getattr(n.func, "id", None) for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and id(n) not in inside
                 and getattr(n.func, "id", None) in {
                     "render_plate", "render_look", "render_type",
                     "extract_frames"}]
        assert loose == [], f"rendered without asking first: {loose}"

    def test_redo_refuses_a_pass_name_it_does_not_have(self, tmp_path):
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "render_film.py"),
             "--project", "king-tut", "--redo", "plate,platte"],
            capture_output=True, text=True, cwd=ROOT)
        said = done.stdout + done.stderr
        assert done.returncode != 0
        assert "--redo names no such pass: platte" in said, said
        # ...and it says so before it reads anything, so a typo costs nothing.
        assert "render_props.json" not in said, said

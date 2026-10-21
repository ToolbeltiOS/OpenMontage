"""The asset's one opinion, and the join that gives it to a cut.

The mood table picks a move from the beat and the register, and the asset is
allowed exactly one veto: a push into a dense frame becomes a lock. That veto
was a rule about a field nobody filled in until this existed.

The CLIP calls are stubbed. What is tested here is the shape of the question —
three contests, not one choice among six — the measured half of it, and the
join, which is where a real cut meets a real classification and the names have
to agree.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from lib import asset_classifier as ac
from lib import camera_intent


def grey(path, level, size=(80, 45)):
    from PIL import Image

    Image.new("L", size, level).convert("RGB").save(path)
    return str(path)


class TestTheQuestionsAsked:
    def test_the_vocabulary_is_asked_as_pairs_not_as_six_way_choice(self):
        """A frame can be dark AND vast; those are not alternatives."""
        assert set(ac.CONTESTS) == {"scale", "occupancy"}
        for pair in ac.CONTESTS.values():
            assert len(pair) == 2
        names = {side[0] for pair in ac.CONTESTS.values() for side in pair}
        assert names == {"vast", "intimate", "dense", "empty"}

    def test_brightness_is_measured_and_not_asked(self):
        """CLIP is worse at this than a mean is, so it is not consulted."""
        prompts = [side[1] for pair in ac.CONTESTS.values() for side in pair]
        assert not any("bright" in p or "dark" in p for p in prompts)

    def test_every_playbook_class_can_be_produced(self):
        import yaml

        playbook = yaml.safe_load(
            (ac.ROOT / "styles" / "wak3up-documentary.yaml").read_text())
        declared = set(playbook["motion"]["mood"]["asset_classes"])
        produced = {side[0] for pair in ac.CONTESTS.values() for side in pair}
        produced |= {"bright", "dark"}
        assert produced == declared


class TestLuminance:
    def test_a_bright_frame_is_bright(self, tmp_path):
        assert ac.mean_luma(grey(tmp_path / "b.png", 220)) > ac.BRIGHT_LUMA

    def test_a_dark_frame_is_dark(self, tmp_path):
        assert ac.mean_luma(grey(tmp_path / "d.png", 20)) < ac.BRIGHT_LUMA


class TestClassify:
    @staticmethod
    def _stub(monkeypatch, scale_pref, occupancy_pref):
        """Make CLIP prefer a chosen side of each contest by a wide margin."""
        text = np.eye(4, dtype="float32")

        def embed_texts(prompts):
            return text

        def embed_images(paths):
            vec = np.zeros((len(paths), 4), dtype="float32")
            vec[:, 0 if scale_pref == "vast" else 1] = 1.0
            vec[:, 2 if occupancy_pref == "dense" else 3] = 1.0
            return vec

        import sys
        module = type(sys)("clip_embedder")
        module.embed_texts = embed_texts
        module.embed_images = embed_images
        monkeypatch.setitem(sys.modules, "clip_embedder", module)

    def test_the_winner_of_each_contest_is_recorded(self, monkeypatch, tmp_path):
        self._stub(monkeypatch, "vast", "empty")
        row = ac.classify_images([grey(tmp_path / "x.png", 200)])[0]
        assert set(row["classes"]) == {"vast", "empty", "bright"}

    def test_a_tie_is_recorded_rather_than_called(self, monkeypatch, tmp_path):
        import sys

        module = type(sys)("clip_embedder")
        module.embed_texts = lambda p: np.eye(4, dtype="float32")
        module.embed_images = lambda p: np.full((len(p), 4), 0.5, dtype="float32")
        monkeypatch.setitem(sys.modules, "clip_embedder", module)
        row = ac.classify_images([grey(tmp_path / "y.png", 20)])[0]
        assert row["margins"]["scale_tie"] is True
        assert row["classes"] == ["dark"], row["classes"]

    def test_a_video_is_sampled_from_its_middle(self, tmp_path, monkeypatch):
        """A clip that opens on a fade would otherwise classify as the fade."""
        import subprocess

        from PIL import Image

        frames = tmp_path / "raw"
        frames.mkdir()
        for i in range(30):
            Image.new("RGB", (160, 90), (250, 250, 250) if i >= 10 else (0, 0, 0)).save(
                frames / f"f_{i:03d}.png")
        clip = tmp_path / "clip.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "30",
                        "-i", str(frames / "f_%03d.png"), "-pix_fmt", "yuv420p",
                        str(clip)], check=True)
        still = ac.still_of(clip, tmp_path)
        assert still != clip and still.exists()
        assert ac.mean_luma(still) > 200, "the fade-in was sampled, not the shot"


class TestTheJoin:
    def test_a_cut_takes_the_class_of_its_asset(self, tmp_path, monkeypatch):
        project = tmp_path / "projects" / "p" / "artifacts"
        project.mkdir(parents=True)
        (project / "asset_classes_film.json").write_text(json.dumps({"assets": [
            {"path": "assets/images/wall.jpg", "classes": ["dense", "dark"]},
            {"path": "assets/images/plain.jpg", "classes": ["vast", "empty", "bright"]},
        ]}))
        monkeypatch.setattr(ac, "ROOT", tmp_path)
        cuts = [{"id": "c1", "source": "/somewhere/else/wall.jpg"},
                {"id": "c2", "source": "assets/images/plain.jpg"},
                {"id": "c3", "source": "Ledger c06"}]
        assert ac.annotate_cuts(cuts, "p") == 2
        assert cuts[0]["asset_class"] == "dense"
        assert cuts[1]["asset_class"] == "empty"
        assert "asset_class" not in cuts[2]

    def test_a_staged_copy_is_the_same_picture(self, tmp_path, monkeypatch):
        """The demo copies shots to `<cut id>__<name>` so Chrome can load them."""
        project = tmp_path / "projects" / "p" / "artifacts"
        project.mkdir(parents=True)
        (project / "asset_classes_film.json").write_text(json.dumps({"assets": [
            {"path": "assets/images/wall.jpg", "classes": ["dense"]}]}))
        monkeypatch.setattr(ac, "ROOT", tmp_path)
        cuts = [{"id": "c1", "source": "demo/c049__wall.jpg"}]
        assert ac.annotate_cuts(cuts, "p") == 1
        assert cuts[0]["asset_class"] == "dense"

    def test_the_veto_fires_once_a_cut_is_classified(self, tmp_path, monkeypatch):
        """The whole point: an unclassified cut cannot be vetoed."""
        project = tmp_path / "projects" / "p" / "artifacts"
        project.mkdir(parents=True)
        (project / "asset_classes_film.json").write_text(json.dumps({"assets": [
            {"path": "a/wall.jpg", "classes": ["dense"]}]}))
        monkeypatch.setattr(ac, "ROOT", tmp_path)

        before = [{"id": "c1", "source": "a/wall.jpg", "beat": "reveal",
                   "register": "awe", "in_seconds": 0, "out_seconds": 14}]
        camera_intent.assign([dict(before[0])])
        unclassified = camera_intent.assign([dict(before[0])])[0]
        assert unclassified["camera"]["move"] == "push"

        ac.annotate_cuts(before, "p")
        classified = camera_intent.assign(before)[0]
        assert classified["camera"]["move"] == "lock"
        assert "zoom" in classified["camera"]["reason"]

"""A post that asks a question must wait for its answer.

THE INCIDENT
------------
On 2026-11-22 two music-bed previews were posted to Telegram so the owner
could choose between them by ear. They went out through `telegram._upload`
— the private multipart helper — because there was no public `send_audio`
and no reason to think one was needed.

Nothing was listening. `_upload` posts and returns. The owner replied
"Drone" at 19:35:26 and "drone" again at 19:36:15, and BOTH answers sat
unread in the update queue, because the only thing that consumes replies is
`await_reply`, and nothing had called it. The second reply is the tell: a
person answering twice is a person watching an answer go nowhere.

It was survivable only by luck. `TELEGRAM_DOCS_BOT_TOKEN` is set, so the
Shorts cron — which polls the same API every five minutes and CONFIRMS
every update it reads — did not consume the reply first. On a shared bot
the answer would have been gone, and indistinguishable from silence.

THE RULE
--------
A question goes through the gate pair: `drain()` before the post so a stale
reply cannot be misread as this answer, `await_reply()` after it so the
answer is actually collected. `ask_with_file` is that pair in one call.
Notifications may still be sent best-effort; questions may not.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

import telegram                                          # noqa: E402


def repo_python() -> list[Path]:
    """Every tracked .py file, so an untracked scratch file cannot fail the suite."""
    listed = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    return [ROOT / line for line in listed.stdout.split() if line]


def production_python() -> list[Path]:
    skip = ("tests/", "lib/telegram.py")
    out = []
    for path in repo_python():
        rel = path.relative_to(ROOT).as_posix()
        if any(rel.startswith(s) or rel == s for s in skip):
            continue
        out.append(path)
    return out


class TestNobodyPostsAQuestionOutsideTheGate:

    def test_no_module_calls_the_private_uploader(self):
        offenders = []
        for path in production_python():
            src = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"telegram\._upload\s*\(", src):
                offenders.append(path.relative_to(ROOT).as_posix())
            imported = re.search(r"from telegram import ([^\n]+)", src)
            if imported and "_upload" in imported.group(1):
                offenders.append(path.relative_to(ROOT).as_posix())
        assert offenders == [], (
            "these call telegram's private uploader directly, which posts "
            "without draining or waiting: " + ", ".join(offenders)
            + " — use send_audio/send_photo/send_document for a "
              "notification, or ask_with_file for a question")

    def test_there_is_a_public_way_to_post_audio(self):
        # Otherwise the rule above forbids the only route there is, which
        # is how the private helper got called in the first place.
        assert callable(telegram.send_audio)

    def test_every_await_reply_caller_drains_first(self):
        offenders = []
        for path in production_python():
            src = path.read_text(encoding="utf-8", errors="replace")
            if not re.search(r"telegram\.await_reply\s*\(", src):
                continue
            if not re.search(r"telegram\.drain\s*\(", src):
                offenders.append(path.relative_to(ROOT).as_posix())
        assert offenders == [], (
            "these wait for a reply without draining first, so a reply to "
            "an earlier question can be read as this answer: "
            + ", ".join(offenders))


class TestTheGatePair:

    def test_it_drains_before_it_posts(self):
        src = (ROOT / "lib" / "telegram.py").read_text(encoding="utf-8")
        body = src[src.index("def ask_with_file("):]
        body = body[:body.index("\ndef ", 1)]
        assert body.index("drain()") < body.index("_upload("), (
            "drain() must run before the post, or a reply that arrived "
            "while the file was uploading is discarded")

    def test_it_waits_for_the_answer(self, monkeypatch, tmp_path):
        posted, waited = {}, {}
        monkeypatch.setattr(telegram, "drain", lambda: 77)
        monkeypatch.setattr(telegram, "_upload",
                            lambda m, f, p, c: posted.update(method=m, caption=c))

        def fake_wait(offset, hours):
            waited.update(offset=offset, hours=hours)
            return ("notes", "drone")

        monkeypatch.setattr(telegram, "await_reply", fake_wait)

        clip = tmp_path / "bed.mp3"
        clip.write_bytes(b"\x00")
        verdict, text = telegram.ask_with_file(clip, "drone or lake?", hours=2)

        assert (verdict, text) == ("notes", "drone")
        assert posted["method"] == "sendAudio"
        assert waited["offset"] == 77, (
            "it must wait from the offset drain returned, not from zero")

    def test_a_notification_still_does_not_wait(self, monkeypatch, tmp_path):
        # send_audio is best effort by design — only questions block.
        monkeypatch.setattr(telegram, "_upload", lambda m, f, p, c: {"ok": True})
        monkeypatch.setattr(telegram, "await_reply",
                            lambda *a, **k: pytest.fail("send_audio must not wait"))
        clip = tmp_path / "bed.mp3"
        clip.write_bytes(b"\x00")
        assert telegram.send_audio(clip, "fyi") == {"ok": True}

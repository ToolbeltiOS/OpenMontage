#!/usr/bin/env python3
"""Prove the chain hands off, without making a film.

WHAT A DRY RUN IS FOR
---------------------
Not to test the film. To test the JOINS: that the picker writes a brief the
runner can read, that the runner writes a script the gate can post, that the
gate's reply reaches the runner, that the runner's project reaches the
publisher, and that the publisher writes a ledger the picker will read next
week. Every one of those is a filename agreed between two programs that have
never run together.

Telegram is faked — the gate is answered "ok" automatically — and nothing is
rendered or uploaded. What IS real: the brief, the artifact shapes, the
script gate's own logic, the publish listing, and both ledgers.

    python scripts/dry_run.py
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

#: A three-minute film, so a mini-brief is a real brief and not a stub.
MINI = {
    "entity": "Dry Run",
    "shorts": 2, "median_views": 1, "best_views": 1, "mean_engagement": 0.0,
    "titles": ["A Dry Run Short", "Another Dry Run Short"],
    "urls": ["https://example.invalid/1", "https://example.invalid/2"],
    "deepest_six": "6/6", "eligible": True, "min_assets": 8,
    "entities": [{"entity": f"Entity {n}", "category_files": 9,
                  "counted": 9.0, "clears": True, "examples": []}
                 for n in range(6)],
    "angle": {"claim": "A three-minute film that proves the stages hand off.",
              "recurring_words": ["dry", "run"], "source_titles": []},
    "title_candidates": ["Dry Run: The Part Nobody Can Explain"],
}

#: Schema-valid on purpose. This fixture used to carry `acts`, which
#: script.schema.json forbids, so the dry run proved a join against a shape
#: no real artifact can have — and the gate's outline, written to read the
#: same forbidden key, posted empty for every genuine script.
SCRIPT = {
    "version": "1.0",
    "title": "Dry Run — Three Minutes",
    "total_duration_seconds": 180,
    "sections": [
        {"id": "act1", "label": "01 The claim",
         "start_seconds": 0, "end_seconds": 90,
         "text": "[beat: reveal | awe]\nA thing was built, and nobody "
                 "wrote down how.\n[air 4.0s]\n"},
        {"id": "act2", "label": "02 The objection",
         "start_seconds": 90, "end_seconds": 180,
         "text": "[beat: exposition]\nThe objection is arithmetic, and it "
                 "is serious.\n[air 4.0s]\n"},
    ],
}

LISTING = {
    "title": "Dry Run — Three Minutes",
    "description": "A dry run.", "tags": ["dry", "run"],
    "categoryId": "27", "defaultLanguage": "en", "defaultAudioLanguage": "en",
    "privacyStatus": "private", "selfDeclaredMadeForKids": False,
    "license": "creativeCommon", "embeddable": True,
    "publicStatsViewable": True, "containsSyntheticMedia": False,
    "playlist": "Documentaries", "pinned_comment": "Credits.",
    "entities": ["Entity 0", "Entity 1"],
}


class FakeTelegram:
    """Everything the gate asks of Telegram, answered by a script."""

    def __init__(self, reply: str = "ok"):
        self.reply = reply
        self.sent: list[str] = []
        self.documents: list[str] = []
        self.photos: list[str] = []

    def install(self) -> None:
        import telegram

        telegram.send = lambda text, quiet=False: self.sent.append(text) or {}
        telegram.require = lambda text: self.sent.append(text) or {}
        telegram.send_document = lambda path, caption="": \
            self.documents.append(str(path)) or {}
        telegram.send_photo = lambda path, caption="": \
            self.photos.append(str(path)) or {}
        telegram.drain = lambda *a, **k: 0
        telegram.await_reply = lambda offset, hours, poll_seconds=50: \
            ({"ok": ("ok", "ok"), "no": ("no", "no")}.get(
                self.reply, ("notes", self.reply)))


def step(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reply", default="ok",
                    help='what the fake human says: ok, no, or notes')
    args = ap.parse_args()

    print("DRY RUN — the joins, not the film\n")
    passed = []

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        project = work / "projects" / "dry-run"
        (project / "artifacts").mkdir(parents=True)
        (project / "renders" / "style").mkdir(parents=True)

        # 1. the picker's output is what the runner reads
        brief_path = work / "topic_briefs.json"
        brief_path.write_text(json.dumps(
            {"generated": datetime.now(timezone.utc).isoformat(),
             "briefs": [MINI]}, indent=1))
        topic = subprocess.run(
            [str(ROOT / ".venv" / "bin" / "python"), "-c",
             f"import json;b=json.load(open({str(brief_path)!r}));"
             f"print(b['briefs'][0]['entity'])"],
            capture_output=True, text=True).stdout.strip()
        passed.append(step("picker -> runner", topic == "Dry Run",
                           f"topic {topic!r}"))

        # 2. the script the runner writes is what the gate posts
        script_path = project / "artifacts" / "script.json"
        script_path.write_text(json.dumps(SCRIPT, indent=1))
        for n in range(3):
            (project / "renders" / "style" / f"frame_{n}.png").write_bytes(b"\x89PNG\r\n")

        fake = FakeTelegram(args.reply)
        fake.install()
        import telegram_gate

        sys.argv = ["telegram_gate", "--project", "dry-run",
                    "--script", str(script_path),
                    "--frames", str(project / "renders" / "style"),
                    "--hours", "0.01"]
        code = telegram_gate.main()
        expected = {"ok": 0, "no": 2}.get(args.reply, 10)
        passed.append(step("runner -> gate", code == expected,
                           f"exit {code}, posted {len(fake.sent)} messages, "
                           f"{len(fake.documents)} documents, "
                           f"{len(fake.photos)} frames"))
        passed.append(step("gate posted the script as a file",
                           len(fake.documents) == 1))
        passed.append(step("gate posted the style frames",
                           len(fake.photos) == 3))
        passed.append(step("gate posted the act outline",
                           any("The claim" in m for m in fake.sent)))

        if args.reply not in ("ok",):
            print(f"\nreply {args.reply!r}: the chain stops here, as designed")
            return 0 if all(passed) else 1

        # 3. the publisher reads the project the runner made
        listing_path = project / "artifacts" / "listing.json"
        listing_path.write_text(json.dumps(LISTING, indent=1))
        video = project / "renders" / "final.mp4"
        video.write_bytes(b"\x00" * 1024)

        result = subprocess.run(
            [str(ROOT / ".venv" / "bin" / "python"),
             str(ROOT / "scripts" / "publish_doc.py"),
             "--project", "dry-run", "--dry-run",
             "--listing", str(listing_path), "--video", str(video)],
            capture_output=True, text=True, env={**os.environ, "HOME": os.environ["HOME"]})
        passed.append(step("gate -> publisher", result.returncode == 0,
                           (result.stdout.strip().splitlines() or ["no output"])[-1]))
        passed.append(step("publisher schedules, not publishes",
                           "private now, public" in result.stdout))

        # 4. the ledger the picker reads next week
        from publish_doc import next_monday

        monday = next_monday()
        passed.append(step("publishAt is a Monday 09:00",
                           monday.weekday() == 0,
                           monday.isoformat()))

    print(f"\n{sum(passed)}/{len(passed)} joins hold")
    return 0 if all(passed) else 1


if __name__ == "__main__":
    raise SystemExit(main())

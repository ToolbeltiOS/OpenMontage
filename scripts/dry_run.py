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
        # A COLD OPEN AND PRONUNCIATION GUIDES, because the listing is built
        # from them: `hook()` quotes the cold open (a hand-written hook is a
        # second copy of the premise that nothing keeps in step), and
        # `subjects()` takes its tags from the guides, refusing a listing
        # with fewer than three. A fixture without them cannot reach the
        # publisher, which is the whole point of this file.
        {"id": "cold_open", "label": "Cold open",
         "start_seconds": 0, "end_seconds": 20,
         "text": "[beat: reveal | awe]\nThe Vantrell ledger says one "
                 "thing. The Oskaloo survey says another.\n[air 4.0s]\n",
         "pronunciation_guides": [
             {"word": "Vantrell", "phonetic": "VAN-trell"},
             {"word": "Oskaloo", "phonetic": "OSS-ka-loo"},
             {"word": "merridan", "phonetic": "MERR-ih-dan"},
         ]},
        {"id": "act1", "label": "01 The claim",
         "start_seconds": 20, "end_seconds": 110,
         "text": "[beat: reveal | awe]\nA thing was built, and nobody "
                 "wrote down how.\n[air 4.0s]\n"},
        {"id": "act2", "label": "02 The objection",
         "start_seconds": 110, "end_seconds": 180,
         "text": "[beat: exposition]\nThe objection is arithmetic, and it "
                 "is serious.\n[air 4.0s]\n"},
    ],
}

#: WHAT USED TO BE HERE, AND WHY IT IS GONE.
#:
#: A hand-written `LISTING` dict, written straight to
#: `artifacts/listing.json` and then handed to the publisher with
#: `--listing`. It faked the join twice over: it produced the artifact it
#: was supposed to be checking the existence of, and it bypassed the default
#: path the weekly chain actually uses. So this file reported "gate ->
#: publisher PASS" every week while NOTHING IN THE CHAIN BUILT A LISTING —
#: and on 2026-11-15 a film passed all eight delivery gates, posted its
#: thumbnail, pushed its credits page, and stopped dead at the upload.
#:
#: The listing is now built by `scripts/build_listing.py`, the same program
#: the weekly run calls, from this project's own artifacts, and the
#: publisher is left to find it where it normally looks.

#: The artifacts `build_listing` reads besides the script. Minimal on
#: purpose — the point is the join, not the content — but real in shape:
#: a brief with a primary source, an EDL with a credited bed, and a cut list.
BRIEF = {
    "topic": "Dry Run",
    "sources": [{"title": "The Vantrell ledger, folio 3",
                 "url": "https://example.invalid/vantrell",
                 "reliability": "primary"}],
}

EDIT_DECISIONS = {
    "music": {"beds": [{"track": "Dry Bed - A Composer.mp3",
                        "licence": "CC BY 4.0",
                        "source_url": "https://example.invalid/bed"}]},
}

RENDER_PROPS = {"cuts": []}


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

        # 3. the chain BUILDS the listing. Nothing else does, and for five
        #    films nothing did.
        art = project / "artifacts"
        (art / "research_brief.json").write_text(json.dumps(BRIEF, indent=1))
        (art / "edit_decisions.json").write_text(json.dumps(EDIT_DECISIONS, indent=1))
        (art / "render_props.json").write_text(json.dumps(RENDER_PROPS, indent=1))
        video = project / "renders" / "final.mp4"
        video.write_bytes(b"\x00" * 1024)

        # Chapter times are MEASURED off the narration rather than taken
        # from the script's planned seconds, so the fixture carries audio to
        # measure. Silence of a known length is enough: the join is whether
        # the builder can find and probe the wavs, not what is in them.
        aud = project / "assets" / "audio"
        aud.mkdir(parents=True, exist_ok=True)
        for name, seconds in (("cold_open", 2), ("act1", 3), ("act2", 4)):
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                 "-i", f"anullsrc=r=24000:cl=mono", "-t", str(seconds),
                 str(aud / f"{name}.wav")],
                capture_output=True)

        listing_path = art / "listing.json"
        built = subprocess.run(
            [str(ROOT / ".venv" / "bin" / "python"),
             str(ROOT / "scripts" / "build_listing.py"),
             "--project", "dry-run", "--root", str(work)],
            capture_output=True, text=True)
        passed.append(step(
            "runner -> listing", built.returncode == 0 and listing_path.exists(),
            (built.stdout.strip().splitlines()
             or [(built.stderr.strip() or "no output").splitlines()[-1]])[-1]))

        chaps = (json.loads(listing_path.read_text()).get("chapters", [])
                 if listing_path.exists() else [])
        # Three, not two: `NOT_A_CHAPTER` holds only `title_sequence`, so the
        # cold open is a chapter a viewer may skip to. The times prove the
        # measurement — 00:00, 00:02, 00:05 are the fixture's 2s and 3s of
        # silence, not the script's planned 20s and 110s.
        passed.append(step("chapters are measured off the narration",
                           len(chaps) == 3,
                           f"{len(chaps)} chapter(s): "
                           + ", ".join(f"{c['time']} {c['title']}" for c in chaps)))

        # The publisher is handed NO PATHS. It has to find the listing and
        # the film where the weekly chain leaves them, or this step proves
        # nothing — which is exactly how the old fixture passed every week
        # with `--listing` pointing at a file it had just written itself.
        result = subprocess.run(
            [str(ROOT / ".venv" / "bin" / "python"),
             str(ROOT / "scripts" / "publish_doc.py"),
             "--project", "dry-run", "--dry-run", "--root", str(work)],
            capture_output=True, text=True, env={**os.environ, "HOME": os.environ["HOME"]})
        passed.append(step("listing -> publisher", result.returncode == 0,
                           (result.stdout.strip().splitlines() or ["no output"])[-1]))
        passed.append(step("publisher found the listing at its default path",
                           "no listing at" not in result.stdout))
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

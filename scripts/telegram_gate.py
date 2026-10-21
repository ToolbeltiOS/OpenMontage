#!/usr/bin/env python3
"""The one place a human is in the loop: the script gate.

WHY THE SCRIPT AND NOTHING ELSE
-------------------------------
Everything downstream of the script is mechanical and gated by a measurement
— the rhythm, the leads, the frame order, the type lock, the mix. The script
is the only artifact where being wrong is invisible to every gate in the
repository and obvious to a viewer. So it is the only thing that waits for a
person.

WHAT IT POSTS
-------------
The title, the act outline, the full script as a .txt, and the hero style
frames. Four things, because a reply of "ok" has to be an informed one: the
outline says what the film argues, the script says how, and the frames say
what it will look like.

THE REPLY
---------
    ok              continue
    no              abort
    anything else   notes. They are applied to the script, and the gate
                    posts ONCE more. A second round of notes aborts, because
                    a conversation at two in the morning is a conversation
                    the person did not agree to have.
    silence         ABORT, never continue. A film that publishes because
                    nobody said no is what this exists to prevent.

    python scripts/telegram_gate.py --project <id> --script <path> --hours 12
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import telegram  # noqa: E402

#: How many style frames go with the script. Eight is what the playbook calls
#: a hero set and what fits on a phone screen as a strip.
HERO_FRAMES = 8


def outline_of(script: dict) -> list[str]:
    """The act outline, from the script artifact."""
    lines = []
    for act in (script.get("acts") or []):
        title = act.get("title") or act.get("name") or f"Act {act.get('number', '?')}"
        beats = act.get("beats") or act.get("sections") or []
        lines.append(f"<b>{act.get('number', '')} {title}</b>")
        for beat in beats[:6]:
            text = (beat if isinstance(beat, str)
                    else beat.get("summary") or beat.get("title") or "")
            if text:
                lines.append(f"  · {text[:110]}")
    return lines


def post(project: str, script_path: Path, frames: list[Path],
         title: str, outline: list[str], attempt: int = 1) -> None:
    header = (f"<b>{title}</b>\n"
              f"<i>{project}</i> — script gate"
              + (" (revised)" if attempt > 1 else "") + "\n\n"
              + "\n".join(outline[:40]))
    telegram.require(header)
    telegram.send_document(script_path, caption="the full script")
    for frame in frames[:HERO_FRAMES]:
        telegram.send_photo(frame)
    telegram.require(
        "Reply <b>ok</b> to continue, <b>no</b> to abort, or send notes.\n"
        "Notes are applied and reposted once. Silence aborts.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--script", required=True, help="the script artifact JSON")
    ap.add_argument("--script-text", default=None,
                    help="the .txt that is attached; defaults beside --script")
    ap.add_argument("--frames", default=None,
                    help="directory of hero style frames")
    ap.add_argument("--hours", type=float, default=12.0)
    ap.add_argument("--notes-out", default=None,
                    help="where to write notes if the reply is notes")
    ap.add_argument("--attempt", type=int, default=1)
    args = ap.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        # The real failure this guards: the script stage exited 0 and wrote
        # nothing. Without it the gate dies on a traceback at two in the
        # morning and the Telegram message says "unexpected exit 1".
        message = (f"no script at {script_path} — the script stage produced "
                   f"nothing to approve")
        print(message, file=sys.stderr)
        telegram.send(f"<b>Script gate cannot run</b>\n{message}")
        return 5
    script = json.loads(script_path.read_text())
    title = script.get("title") or args.project
    outline = outline_of(script)

    text_path = (Path(args.script_text) if args.script_text
                 else script_path.with_suffix(".txt"))
    if not text_path.exists():
        # the attachment is the point; build it from the artifact
        body = []
        for act in (script.get("acts") or []):
            body.append(f"\n\n=== {act.get('number','')} "
                        f"{act.get('title') or ''} ===\n")
            for beat in (act.get("beats") or act.get("sections") or []):
                body.append(beat if isinstance(beat, str)
                            else (beat.get("narration") or beat.get("text") or ""))
        text_path.write_text("\n".join(filter(None, body)) or
                             json.dumps(script, indent=1))

    frames = []
    if args.frames:
        frames = sorted(Path(args.frames).glob("*.png")) + \
                 sorted(Path(args.frames).glob("*.jpg"))

    offset = telegram.drain()
    post(args.project, text_path, frames, title, outline, args.attempt)

    verdict, text = telegram.await_reply(offset, args.hours)
    print(f"gate: {verdict}")

    if verdict == "ok":
        telegram.send("Approved. Rendering.")
        return 0
    if verdict == "no":
        telegram.send("Aborted, as asked.")
        return 2
    if verdict == "timeout":
        telegram.send(
            f"No reply in {args.hours:g}h — aborting. Silence is not approval.")
        return 3

    notes_path = Path(args.notes_out) if args.notes_out else \
        script_path.with_name("script_notes.txt")
    notes_path.write_text(text + "\n")
    print(f"notes -> {notes_path}")
    if args.attempt > 1:
        telegram.send("Second round of notes — aborting. Let us do this awake.")
        return 4
    telegram.send("Notes received. Applying them and reposting once.")
    return 10                               # the runner applies and re-posts


if __name__ == "__main__":
    raise SystemExit(main())
